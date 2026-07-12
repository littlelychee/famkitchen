from datetime import date, timedelta
from io import BytesIO
import tempfile

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .forms import (
    AvatarUploadForm,
    DishForm,
    FamilyForm,
    RegisterForm,
    UserProfileForm,
    looks_like_heif,
)
from .models import (
    Dish,
    DishCategory,
    DishMealSection,
    Family,
    FamilyMember,
    FamilyNotification,
    MealPlan,
    MealPlanItem,
    UserAvatar,
    UserProfile,
)
from .utils import create_family_notifications


def uploaded_test_image(name="test.png", image_format="PNG"):
    buffer = BytesIO()
    Image.new("RGBA", (4, 4), (211, 77, 55, 180)).save(buffer, format=image_format)
    return SimpleUploadedFile(
        name,
        buffer.getvalue(),
        content_type=f"image/{image_format.lower()}",
    )


class LoginFeedbackTests(TestCase):
    def test_invalid_credentials_use_toast_without_inline_error_box(self):
        User.objects.create_user(username="owner", password="correct-password")

        response = self.client.post(
            reverse("login"),
            {"username": "owner", "password": "wrong-password"},
        )

        self.assertContains(response, "登录失败，用户名或密码不正确，请再试一次。")
        self.assertContains(response, "message-toast-error")
        self.assertNotContains(response, "alert alert-error")

    def test_user_can_login_with_registered_email(self):
        user = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="correct-password",
        )

        response = self.client.post(
            reverse("login"),
            {"username": "owner@example.com", "password": "correct-password"},
        )

        self.assertRedirects(response, "/meal-plan/", fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)


class DisplayWidthValidationTests(TestCase):
    def test_register_form_limits_username_to_eight_han_characters(self):
        form = RegisterForm(
            data={
                "username": "一二三四五六七八九",
                "email": "new@example.com",
                "password1": "strong-password-123",
                "password2": "strong-password-123",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("用户名不能超过 8 个汉字长度", str(form.errors))

    def test_register_form_rejects_duplicate_email(self):
        User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="password",
        )

        form = RegisterForm(
            data={
                "username": "newowner",
                "email": "OWNER@example.com",
                "password1": "strong-password-123",
                "password2": "strong-password-123",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("这个邮箱已经被注册", str(form.errors))

    def test_profile_form_rejects_too_long_username(self):
        user = User.objects.create_user(username="owner", password="password")
        form = UserProfileForm(
            data={
                "username": "一二三四五六七八九",
                "email": "owner@example.com",
                "phone_number": "",
            },
            instance=user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("用户名不能超过 8 个汉字长度", str(form.errors))

    def test_family_form_limits_name_to_seven_han_characters(self):
        form = FamilyForm(data={"name": "一二三四五六七八"})

        self.assertFalse(form.is_valid())
        self.assertIn("家庭名称不能超过 7 个汉字长度", str(form.errors))

    def test_dish_form_limits_name_to_eight_han_characters(self):
        user = User.objects.create_user(username="owner", password="password")
        family = Family.objects.create(name="测试家", owner=user)
        form = DishForm(
            data={"name": "一二三四五六七八九"},
            files={},
            family=family,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("菜品名称不能超过 8 个汉字长度", str(form.errors))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AutoConvertingImageUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.family = Family.objects.create(name="测试家庭", owner=self.user)
        FamilyMember.objects.create(
            family=self.family,
            user=self.user,
            role="owner",
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["current_family_id"] = self.family.id
        session.save()

    def test_dish_form_converts_supported_image_to_jpeg(self):
        form = DishForm(
            data={"name": "小红书菜品"},
            files={"image": uploaded_test_image("xiaohongshu.png")},
            family=self.family,
        )

        self.assertTrue(form.is_valid(), form.errors)
        image = form.cleaned_data["image"]
        image.seek(0)
        converted_image = Image.open(BytesIO(image.read()))

        self.assertEqual(image.name, "xiaohongshu.jpg")
        self.assertEqual(image.content_type, "image/jpeg")
        self.assertTrue(image.was_auto_converted)
        self.assertEqual(converted_image.format, "JPEG")

    def test_dish_form_rejects_file_that_is_not_an_image(self):
        upload = SimpleUploadedFile(
            "not-image.jpg",
            b"this is not an image",
            content_type="image/jpeg",
        )

        form = DishForm(
            data={"name": "问题菜品"},
            files={"image": upload},
            family=self.family,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("不是可识别的图片", str(form.errors))

    def test_invalid_dish_image_is_reported_in_toast(self):
        upload = SimpleUploadedFile(
            "not-image.jpg",
            b"this is not an image",
            content_type="image/jpeg",
        )

        response = self.client.post(
            reverse("meals:dish_create"),
            {"name": "问题菜品", "image": upload},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "message-toast-error")
        self.assertContains(response, "菜品图片：这个文件不是可识别的图片")
        self.assertNotContains(response, "alert alert-error")
        self.assertNotContains(response, "请上传一张有效的图片")

    def test_heif_brand_is_detected_before_pillow_can_identify_it(self):
        raw_data = b"\x00\x00\x00\x18ftypheif\x00\x00\x00\x00"

        self.assertTrue(looks_like_heif(raw_data))


class DishListDiscardedVisibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.family = Family.objects.create(name="测试家庭", owner=self.user)
        FamilyMember.objects.create(
            family=self.family,
            user=self.user,
            role="owner",
        )
        self.client.force_login(self.user)

        self.breakfast_category = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.BREAKFAST,
            name="早餐小类",
        )
        self.discarded_category = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.DISCARDED,
            name="废弃小类",
        )
        Dish.objects.create(
            family=self.family,
            category=self.breakfast_category,
            meal_section=Dish.BREAKFAST,
            name="正常早餐",
        )
        Dish.objects.create(
            family=self.family,
            category=self.discarded_category,
            meal_section=Dish.DISCARDED,
            name="坏掉剩菜",
        )

    def test_all_section_hides_discarded_dishes_and_categories(self):
        response = self.client.get(reverse("meals:dish_list"))

        self.assertContains(response, "正常早餐")
        self.assertContains(response, "早餐小类")
        self.assertNotContains(response, "坏掉剩菜")
        self.assertNotContains(response, "废弃小类")

    def test_discarded_section_shows_discarded_dishes_and_categories(self):
        response = self.client.get(
            reverse("meals:dish_list"),
            {"section": Dish.DISCARDED},
        )

        self.assertContains(response, "坏掉剩菜")
        self.assertContains(response, "废弃小类")
        self.assertNotContains(response, "正常早餐")

    def test_discarded_category_without_section_redirects_to_discarded_section(self):
        response = self.client.get(
            reverse("meals:dish_list"),
            {"category": self.discarded_category.id},
        )

        self.assertRedirects(
            response,
            f"{reverse('meals:dish_list')}?section={Dish.DISCARDED}&category={self.discarded_category.id}",
        )


class CategoryAndDishOrderingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.family = Family.objects.create(name="测试家庭", owner=self.user)
        FamilyMember.objects.create(
            family=self.family,
            user=self.user,
            role="owner",
        )
        self.member = User.objects.create_user(
            username="library_member",
            password="password",
        )
        FamilyMember.objects.create(
            family=self.family,
            user=self.member,
            role="member",
        )
        self.client.force_login(self.user)

        self.category_b = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.LUNCH,
            name="B类",
            sort_order=10,
        )
        self.category_a = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.LUNCH,
            name="A类",
            sort_order=20,
        )
        self.b_dish = Dish.objects.create(
            family=self.family,
            category=self.category_b,
            meal_section=Dish.LUNCH,
            name="B菜",
        )
        self.a_dish = Dish.objects.create(
            family=self.family,
            category=self.category_a,
            meal_section=Dish.LUNCH,
            name="A菜",
        )
        self.b_dish.categories.add(self.category_b)
        self.a_dish.categories.add(self.category_a)
        DishMealSection.objects.create(dish=self.b_dish, meal_section=Dish.LUNCH)
        DishMealSection.objects.create(dish=self.a_dish, meal_section=Dish.LUNCH)

    def test_default_library_orders_categories_and_all_dishes_by_name(self):
        response = self.client.get(reverse("meals:dish_list"))

        self.assertEqual(
            [category.name for category in response.context["categories"]],
            ["A类", "B类"],
        )
        self.assertEqual(
            [dish.name for dish in response.context["dishes"]],
            ["A菜", "B菜"],
        )

    def test_sort_mode_cycles_to_descending_and_updates_meal_select(self):
        response = self.client.post(
            reverse("meals:category_sort_mode"),
            {"next": reverse("meals:dish_list")},
        )

        self.assertRedirects(response, reverse("meals:dish_list"))
        self.family.refresh_from_db()
        self.assertEqual(self.family.category_sort_mode, Family.CATEGORY_SORT_NAME_DESC)

        response = self.client.get(
            reverse("meals:meal_plan_select"),
            {"meal_type": MealPlan.LUNCH, "date": "2026-07-11"},
        )
        self.assertEqual(
            [category.name for category in response.context["categories"]],
            ["B类", "A类"],
        )
        self.assertEqual(
            [row["dish"].name for row in response.context["dish_rows"]],
            ["B菜", "A菜"],
        )

    def test_custom_reorder_saves_category_order(self):
        self.family.category_sort_mode = Family.CATEGORY_SORT_CUSTOM
        self.family.save(update_fields=["category_sort_mode"])

        response = self.client.post(
            reverse("meals:category_reorder"),
            {"category_ids": [str(self.category_a.id), str(self.category_b.id)]},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.category_a.refresh_from_db()
        self.category_b.refresh_from_db()
        self.assertLess(self.category_a.sort_order, self.category_b.sort_order)

        response = self.client.get(reverse("meals:dish_list"))
        self.assertEqual(
            [category.name for category in response.context["categories"]],
            ["A类", "B类"],
        )

    def test_regular_family_member_can_manage_category_order(self):
        self.client.force_login(self.member)
        self.family.category_sort_mode = Family.CATEGORY_SORT_CUSTOM
        self.family.save(update_fields=["category_sort_mode"])

        response = self.client.get(reverse("meals:dish_list"))
        self.assertContains(response, "category-edit-pill")

        response = self.client.post(
            reverse("meals:category_reorder"),
            {"category_ids": [str(self.category_a.id), str(self.category_b.id)]},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.category_a.refresh_from_db()
        self.category_b.refresh_from_db()
        self.assertLess(self.category_a.sort_order, self.category_b.sort_order)


class FamilyMemberManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            password="password",
            email="owner@example.com",
        )
        self.member = User.objects.create_user(username="member", password="password")
        self.other_member = User.objects.create_user(
            username="other_member",
            password="password",
        )
        self.family = Family.objects.create(name="测试家庭", owner=self.owner)
        self.owner_membership = FamilyMember.objects.create(
            family=self.family,
            user=self.owner,
            role="owner",
        )
        self.member_membership = FamilyMember.objects.create(
            family=self.family,
            user=self.member,
            role="member",
        )
        self.other_membership = FamilyMember.objects.create(
            family=self.family,
            user=self.other_member,
            role="member",
        )

    def test_profile_keeps_member_management_out_of_regular_member_view(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("meals:profile"))

        self.assertContains(response, "member")
        self.assertContains(response, "我的家庭")
        self.assertContains(response, "当前家庭成员")
        self.assertContains(response, "other_member")
        self.assertNotContains(response, "转让家主")
        self.assertNotContains(response, "移除")

    def test_owner_manage_page_shows_family_members(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("meals:family_manage"))

        self.assertContains(response, "owner")
        self.assertContains(response, "member")
        self.assertContains(response, "other_member")
        self.assertContains(response, "转让家主")
        self.assertContains(response, "移除")

    def test_owner_can_transfer_ownership_to_family_member(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "meals:family_transfer_owner",
                args=[self.member_membership.id],
            )
        )

        self.assertRedirects(response, reverse("meals:profile"))
        self.family.refresh_from_db()
        self.owner_membership.refresh_from_db()
        self.member_membership.refresh_from_db()
        self.assertEqual(self.family.owner, self.member)
        self.assertEqual(self.owner_membership.role, "member")
        self.assertEqual(self.member_membership.role, "owner")

    def test_regular_member_cannot_transfer_ownership(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse(
                "meals:family_transfer_owner",
                args=[self.other_membership.id],
            )
        )

        self.assertEqual(response.status_code, 403)
        self.family.refresh_from_db()
        self.assertEqual(self.family.owner, self.owner)

    def test_owner_can_remove_regular_member(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "meals:family_remove_member",
                args=[self.member_membership.id],
            )
        )

        self.assertRedirects(response, reverse("meals:profile"))
        self.assertFalse(
            FamilyMember.objects.filter(id=self.member_membership.id).exists()
        )

    def test_owner_cannot_remove_current_owner(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "meals:family_remove_member",
                args=[self.owner_membership.id],
            )
        )

        self.assertRedirects(response, reverse("meals:profile"))
        self.assertTrue(
            FamilyMember.objects.filter(id=self.owner_membership.id).exists()
        )


class FamilySwitchingAndProfileUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.first_family = Family.objects.create(name="第一个家", owner=self.user)
        self.second_family = Family.objects.create(name="第二个家", owner=self.user)
        FamilyMember.objects.create(
            family=self.first_family,
            user=self.user,
            role="owner",
        )
        FamilyMember.objects.create(
            family=self.second_family,
            user=self.user,
            role="owner",
        )
        self.client.force_login(self.user)

    def test_switch_family_changes_current_family_in_session(self):
        response = self.client.post(
            reverse("meals:family_switch"),
            {
                "family_id": self.second_family.id,
                "next": reverse("meals:profile"),
            },
        )

        self.assertRedirects(response, reverse("meals:profile"))
        self.assertEqual(
            self.client.session["current_family_id"],
            self.second_family.id,
        )
        response = self.client.get(reverse("meals:profile"))
        self.assertContains(response, "第二个家")

    def test_profile_update_changes_username(self):
        response = self.client.post(
            reverse("meals:profile_update"),
            {"username": "new_owner"},
        )

        self.assertRedirects(response, reverse("meals:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "new_owner")

    def test_owner_can_update_current_family_name(self):
        session = self.client.session
        session["current_family_id"] = self.second_family.id
        session.save()

        response = self.client.post(
            reverse("meals:family_update"),
            {"name": "新的家名"},
        )

        self.assertRedirects(response, reverse("meals:family_manage"))
        self.second_family.refresh_from_db()
        self.assertEqual(self.second_family.name, "新的家名")

    def test_top_header_shows_v14_version_and_rotating_logo(self):
        response = self.client.get(reverse("meals:meal_plan"))

        self.assertContains(response, "当前版本：v1.4")
        self.assertContains(response, "images/logo-candidates/v14-02.svg")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AvatarUploadFormTests(TestCase):
    def test_upload_form_rejects_more_than_ten_custom_avatars(self):
        user = User.objects.create_user(username="owner", password="password")
        for index in range(UserAvatar.MAX_CUSTOM_AVATARS):
            UserAvatar.objects.create(
                user=user,
                image=f"avatars/user_1/avatar-{index}.png",
            )
        image = SimpleUploadedFile(
            "avatar.gif",
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        form = AvatarUploadForm(files={"image": image}, user=user)

        self.assertFalse(form.is_valid())
        self.assertIn("达到最大 10 张头像的上限了", str(form.errors))

    def test_avatar_upload_json_does_not_apply_avatar_before_save(self):
        user = User.objects.create_user(username="owner", password="password")
        UserProfile.objects.create(user=user)
        self.client.force_login(user)
        image = SimpleUploadedFile(
            "avatar.gif",
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("meals:avatar_upload"),
            {"image": image},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(UserAvatar.objects.filter(user=user).count(), 1)
        user.meal_profile.refresh_from_db()
        self.assertIsNone(user.meal_profile.custom_avatar)


class MultiSectionDishTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.family = Family.objects.create(name="测试家庭", owner=self.user)
        FamilyMember.objects.create(family=self.family, user=self.user, role="owner")
        self.client.force_login(self.user)

        self.lunch_category = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.LUNCH,
            name="午餐主食",
        )
        self.dinner_category = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.DINNER,
            name="晚餐主食",
        )
        self.rice = Dish.objects.create(
            family=self.family,
            category=self.lunch_category,
            meal_section=Dish.LUNCH,
            name="大米饭",
        )
        self.rice.categories.add(self.lunch_category, self.dinner_category)
        DishMealSection.objects.create(dish=self.rice, meal_section=Dish.LUNCH)
        DishMealSection.objects.create(dish=self.rice, meal_section=Dish.DINNER)

    def test_dish_can_show_in_multiple_sections(self):
        lunch_response = self.client.get(
            reverse("meals:dish_list"),
            {"section": Dish.LUNCH},
        )
        dinner_response = self.client.get(
            reverse("meals:dish_list"),
            {"section": Dish.DINNER},
        )

        self.assertContains(lunch_response, "大米饭")
        self.assertContains(dinner_response, "大米饭")


class CategorySectionSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.family = Family.objects.create(name="测试家庭", owner=self.user)
        FamilyMember.objects.create(family=self.family, user=self.user, role="owner")
        self.member = User.objects.create_user(
            username="category_member",
            password="password",
        )
        FamilyMember.objects.create(family=self.family, user=self.member, role="member")
        self.client.force_login(self.user)

        self.lunch_category = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.LUNCH,
            name="午餐主食",
        )
        self.dinner_category = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.DINNER,
            name="晚餐主食",
        )
        self.rice = Dish.objects.create(
            family=self.family,
            category=self.lunch_category,
            meal_section=Dish.LUNCH,
            name="大米饭",
        )
        self.rice.categories.add(self.lunch_category, self.dinner_category)
        DishMealSection.objects.create(dish=self.rice, meal_section=Dish.LUNCH)
        DishMealSection.objects.create(dish=self.rice, meal_section=Dish.DINNER)

    def meal_sections_for_rice(self):
        return set(
            self.rice.meal_section_links.values_list("meal_section", flat=True)
        )

    def test_editing_category_renames_without_section_redirect(self):
        response = self.client.post(
            reverse("meals:category_edit", args=[self.lunch_category.id]),
            {
                "name": "日常主食",
            },
        )

        self.assertRedirects(
            response,
            reverse("meals:dish_list"),
        )
        self.lunch_category.refresh_from_db()
        self.assertEqual(self.lunch_category.name, "日常主食")

    def test_regular_family_member_can_edit_category(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("meals:category_edit", args=[self.lunch_category.id]),
            {
                "name": "成员主食",
            },
        )

        self.assertRedirects(response, reverse("meals:dish_list"))
        self.lunch_category.refresh_from_db()
        self.assertEqual(self.lunch_category.name, "成员主食")

    def test_deleting_category_removes_only_that_section_link(self):
        response = self.client.post(
            reverse("meals:category_delete", args=[self.lunch_category.id])
        )

        self.assertRedirects(
            response,
            reverse("meals:dish_list"),
        )
        self.rice.refresh_from_db()
        self.assertEqual(self.meal_sections_for_rice(), {Dish.DINNER})
        self.assertEqual(list(self.rice.categories.all()), [self.dinner_category])

    def test_regular_family_member_can_delete_category(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("meals:category_delete", args=[self.dinner_category.id])
        )

        self.assertRedirects(response, reverse("meals:dish_list"))
        self.rice.refresh_from_db()
        self.assertEqual(self.meal_sections_for_rice(), {Dish.LUNCH})
        self.assertEqual(list(self.rice.categories.all()), [self.lunch_category])

    def test_deleting_last_category_moves_dish_to_discarded(self):
        noodle_category = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.LUNCH,
            name="面食",
        )
        noodle = Dish.objects.create(
            family=self.family,
            category=noodle_category,
            meal_section=Dish.LUNCH,
            name="汤面",
        )
        noodle.categories.add(noodle_category)
        DishMealSection.objects.create(dish=noodle, meal_section=Dish.LUNCH)
        meal_plan = MealPlan.objects.create(
            family=self.family,
            date=date(2026, 7, 11),
            meal_type=MealPlan.LUNCH,
        )
        MealPlanItem.objects.create(meal_plan=meal_plan, dish=noodle)

        self.client.post(reverse("meals:category_delete", args=[noodle_category.id]))

        noodle.refresh_from_db()
        self.assertEqual(noodle.meal_section, Dish.DISCARDED)
        self.assertEqual(
            set(noodle.meal_section_links.values_list("meal_section", flat=True)),
            {Dish.DISCARDED},
        )
        self.assertIsNone(noodle.category)
        self.assertFalse(MealPlanItem.objects.filter(dish=noodle).exists())


class DishDefaultImageTests(TestCase):
    def test_default_image_path_matches_primary_meal_section(self):
        dish = Dish(meal_section=Dish.BREAKFAST, name="粥")

        self.assertEqual(
            dish.default_image_path,
            "images/default-dishes/breakfast.svg",
        )

    def test_default_image_path_falls_back_to_lunch(self):
        dish = Dish(meal_section=Dish.DISCARDED, name="旧菜")

        self.assertEqual(
            dish.default_image_path,
            "images/default-dishes/lunch.svg",
        )


class MealPlanRepeatItemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.family = Family.objects.create(name="测试家庭", owner=self.user)
        FamilyMember.objects.create(family=self.family, user=self.user, role="owner")
        self.client.force_login(self.user)

        self.category = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.LUNCH,
            name="主食",
        )
        self.water = Dish.objects.create(
            family=self.family,
            category=self.category,
            meal_section=Dish.LUNCH,
            name="米饭",
        )
        self.water.categories.add(self.category)
        DishMealSection.objects.create(dish=self.water, meal_section=Dish.LUNCH)

    def test_noted_item_does_not_get_overwritten_by_plain_item(self):
        url = reverse("meals:meal_plan_add")
        payload = {
            "dish_id": self.water.id,
            "date": "2026-07-11",
            "meal_type": MealPlan.LUNCH,
            "quantity": "2",
            "note": "加葱",
        }
        self.client.post(url, payload)
        payload["quantity"] = "1"
        payload["note"] = ""
        self.client.post(url, payload)

        items = MealPlanItem.objects.filter(dish=self.water).order_by("created_at")
        self.assertEqual(items.count(), 2)
        self.assertEqual(items[0].note, "加葱")
        self.assertEqual(items[0].quantity, 2)
        self.assertEqual(items[1].note, "")
        self.assertEqual(items[1].quantity, 1)

    def test_meal_item_saves_quantity_spice_and_ice(self):
        self.water.supports_spice = True
        self.water.supports_ice = True
        self.water.save(update_fields=["supports_spice", "supports_ice"])

        response = self.client.post(
            reverse("meals:meal_plan_toggle"),
            {
                "dish_id": self.water.id,
                "date": "2026-07-11",
                "meal_type": MealPlan.LUNCH,
                "selected": "1",
                f"quantity_{self.water.id}": "3",
                f"spice_level_{self.water.id}": MealPlanItem.SPICE_MEDIUM,
                f"ice_level_{self.water.id}": MealPlanItem.ICE_MORE,
            },
        )

        self.assertEqual(response.status_code, 204)
        item = MealPlanItem.objects.get(dish=self.water)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.spice_level, MealPlanItem.SPICE_MEDIUM)
        self.assertEqual(item.ice_level, MealPlanItem.ICE_MORE)

    def test_warm_selection_clears_ice_level(self):
        self.water.supports_ice = True
        self.water.supports_warm = True
        self.water.save(update_fields=["supports_ice", "supports_warm"])

        response = self.client.post(
            reverse("meals:meal_plan_toggle"),
            {
                "dish_id": self.water.id,
                "date": "2026-07-11",
                "meal_type": MealPlan.LUNCH,
                "selected": "1",
                f"serve_warm_{self.water.id}": "1",
                f"ice_level_{self.water.id}": MealPlanItem.ICE_MORE,
            },
        )

        self.assertEqual(response.status_code, 204)
        item = MealPlanItem.objects.get(dish=self.water)
        self.assertTrue(item.serve_warm)
        self.assertEqual(item.ice_level, "")
        self.assertEqual(item.ice_level_label, "")
        self.assertEqual(item.warm_label, "温热")


class GlobalMealPlanSelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.family = Family.objects.create(name="测试家庭", owner=self.user)
        FamilyMember.objects.create(family=self.family, user=self.user, role="owner")
        self.client.force_login(self.user)

        self.category = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.LUNCH,
            name="主食",
        )
        self.bun = Dish.objects.create(
            family=self.family,
            category=self.category,
            meal_section=Dish.LUNCH,
            name="包子",
        )
        self.bun.categories.add(self.category)
        DishMealSection.objects.create(dish=self.bun, meal_section=Dish.LUNCH)
        self.snack = Dish.objects.create(
            family=self.family,
            meal_section=Dish.SNACK,
            name="小零嘴",
        )

    def test_breakfast_select_uses_global_active_library(self):
        response = self.client.get(
            reverse("meals:meal_plan_select"),
            {
                "meal_type": MealPlan.BREAKFAST,
                "date": "2026-07-11",
            },
        )

        self.assertContains(response, "包子")
        self.assertNotContains(response, "小零嘴")


class MobileMealPlanSelectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.family = Family.objects.create(name="测试家庭", owner=self.user)
        FamilyMember.objects.create(family=self.family, user=self.user, role="owner")
        self.client.force_login(self.user)

        self.category = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.LUNCH,
            name="主食",
        )
        self.water = Dish.objects.create(
            family=self.family,
            category=self.category,
            meal_section=Dish.LUNCH,
            name="米饭",
        )
        self.water.categories.add(self.category)
        DishMealSection.objects.create(dish=self.water, meal_section=Dish.LUNCH)
        self.meal_plan = MealPlan.objects.create(
            family=self.family,
            date=date(2026, 7, 11),
            meal_type=MealPlan.LUNCH,
        )

    def test_toggle_unselect_deletes_noted_item(self):
        MealPlanItem.objects.create(
            meal_plan=self.meal_plan,
            dish=self.water,
            created_by=self.user,
            note="冰镇",
            quantity=2,
        )

        response = self.client.post(
            reverse("meals:meal_plan_toggle"),
            {
                "dish_id": self.water.id,
                "meal_type": MealPlan.LUNCH,
                "date": "2026-07-11",
                "selected": "0",
            },
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(MealPlanItem.objects.filter(dish=self.water).exists())

    def test_full_save_deletes_unchecked_existing_item(self):
        MealPlanItem.objects.create(
            meal_plan=self.meal_plan,
            dish=self.water,
            created_by=self.user,
            note="冰镇",
            quantity=2,
        )

        response = self.client.post(
            reverse("meals:meal_plan_select"),
            {
                "meal_type": MealPlan.LUNCH,
                "date": "2026-07-11",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('meals:meal_plan')}?date=2026-07-11",
        )
        self.assertFalse(MealPlanItem.objects.filter(dish=self.water).exists())


class MealPlanClearDayTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="password")
        self.family = Family.objects.create(name="测试家庭", owner=self.user)
        FamilyMember.objects.create(family=self.family, user=self.user, role="owner")
        self.client.force_login(self.user)

        self.breakfast_dish = Dish.objects.create(
            family=self.family,
            meal_section=Dish.BREAKFAST,
            name="早餐",
        )
        self.lunch_dish = Dish.objects.create(
            family=self.family,
            meal_section=Dish.LUNCH,
            name="午餐",
        )
        self.dinner_dish = Dish.objects.create(
            family=self.family,
            meal_section=Dish.DINNER,
            name="晚餐",
        )
        self.snack_dish = Dish.objects.create(
            family=self.family,
            meal_section=Dish.SNACK,
            name="零嘴",
        )
        self.other_day_dish = Dish.objects.create(
            family=self.family,
            meal_section=Dish.BREAKFAST,
            name="明天早餐",
        )

    def create_item(self, selected_date, meal_type, dish):
        meal_plan = MealPlan.objects.create(
            family=self.family,
            date=selected_date,
            meal_type=meal_type,
        )
        return MealPlanItem.objects.create(
            meal_plan=meal_plan,
            dish=dish,
            created_by=self.user,
        )

    def test_clear_day_removes_current_date_main_meals_only(self):
        selected_date = date(2026, 7, 11)
        self.create_item(selected_date, MealPlan.BREAKFAST, self.breakfast_dish)
        self.create_item(selected_date, MealPlan.LUNCH, self.lunch_dish)
        self.create_item(selected_date, MealPlan.DINNER, self.dinner_dish)
        snack_item = self.create_item(selected_date, MealPlan.SNACK, self.snack_dish)
        other_day_item = self.create_item(
            date(2026, 7, 12),
            MealPlan.BREAKFAST,
            self.other_day_dish,
        )

        response = self.client.post(
            reverse("meals:meal_plan_clear_day"),
            {"date": selected_date.isoformat()},
        )

        self.assertRedirects(
            response,
            f"{reverse('meals:meal_plan')}?date={selected_date.isoformat()}",
        )
        remaining_items = set(MealPlanItem.objects.values_list("id", flat=True))
        self.assertEqual(remaining_items, {snack_item.id, other_day_item.id})


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class FamilyNotificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            password="password",
            email="owner@example.com",
        )
        self.member = User.objects.create_user(
            username="member",
            password="password",
            email="member@example.com",
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            password="password",
            email="outsider@example.com",
        )
        self.family = Family.objects.create(name="测试家庭", owner=self.owner)
        FamilyMember.objects.create(
            family=self.family,
            user=self.owner,
            role="owner",
        )
        FamilyMember.objects.create(family=self.family, user=self.member)
        self.category = DishCategory.objects.create(
            family=self.family,
            meal_section=DishCategory.LUNCH,
            name="主食",
        )
        self.rice = Dish.objects.create(
            family=self.family,
            category=self.category,
            meal_section=Dish.LUNCH,
            name="米饭",
        )
        self.rice.categories.add(self.category)
        DishMealSection.objects.create(dish=self.rice, meal_section=Dish.LUNCH)
        self.client.force_login(self.owner)

    def test_meal_plan_selection_can_create_notification_and_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("meals:meal_plan_select"),
                {
                    "meal_type": MealPlan.LUNCH,
                    "date": "2026-07-11",
                    "dish_ids": [str(self.rice.id)],
                    f"quantity_{self.rice.id}": "2",
                    "notify_user_ids": [str(self.member.id)],
                },
            )

        self.assertRedirects(
            response,
            f"{reverse('meals:meal_plan')}?date=2026-07-11",
        )
        self.assertEqual(FamilyNotification.objects.count(), 2)
        history = FamilyNotification.objects.get(recipient__isnull=True)
        reminder = FamilyNotification.objects.get(recipient=self.member)
        self.assertEqual(history.family, self.family)
        self.assertEqual(history.actor, self.owner)
        self.assertEqual(history.meal_plan_date, date(2026, 7, 11))
        self.assertEqual(history.meal_type, MealPlan.LUNCH)
        self.assertIn("米饭 x2", history.change_summary)
        self.assertEqual(reminder.family, self.family)
        self.assertEqual(reminder.actor, self.owner)
        self.assertEqual(reminder.meal_plan_date, date(2026, 7, 11))
        self.assertEqual(reminder.meal_type, MealPlan.LUNCH)
        self.assertIn("米饭 x2", reminder.change_summary)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("法米狗私厨给的通知", mail.outbox[0].subject)
        self.assertIn("owner", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["member@example.com"])
        self.assertIn("发送人", mail.outbox[0].alternatives[0][0])
        self.assertIn("owner 提醒你", mail.outbox[0].alternatives[0][0])
        self.assertIn("关注 2026-07-11 的排餐", mail.outbox[0].alternatives[0][0])
        self.assertNotIn("小餐桌便签", mail.outbox[0].alternatives[0][0])
        self.assertIn("米饭 x2", mail.outbox[0].body)

    def test_meal_plan_selection_page_shows_family_reminder_choices(self):
        response = self.client.get(
            reverse("meals:meal_plan_select"),
            {
                "meal_type": MealPlan.LUNCH,
                "date": "2026-07-11",
            },
        )

        self.assertContains(response, "提醒家人")
        self.assertContains(response, "member")
        self.assertContains(response, "邮箱通知")

    def test_notification_recipient_must_belong_to_same_family(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("meals:meal_plan_select"),
                {
                    "meal_type": MealPlan.LUNCH,
                    "date": "2026-07-11",
                    "dish_ids": [str(self.rice.id)],
                    "notify_user_ids": [str(self.outsider.id)],
                },
            )

        self.assertRedirects(
            response,
            f"{reverse('meals:meal_plan')}?date=2026-07-11",
        )
        history = FamilyNotification.objects.get()
        self.assertIsNone(history.recipient)
        self.assertEqual(len(mail.outbox), 0)

    def test_meal_plan_save_without_recipient_still_creates_family_history(self):
        response = self.client.post(
            reverse("meals:meal_plan_select"),
            {
                "meal_type": MealPlan.LUNCH,
                "date": "2026-07-11",
                "dish_ids": [str(self.rice.id)],
                f"quantity_{self.rice.id}": "3",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('meals:meal_plan')}?date=2026-07-11",
        )
        notification = FamilyNotification.objects.get()
        self.assertIsNone(notification.recipient)
        self.assertEqual(notification.actor, self.owner)
        self.assertEqual(notification.meal_plan_date, date(2026, 7, 11))
        self.assertIn("米饭 x3", notification.change_summary)

    def test_meal_plan_page_links_to_share_member_picker(self):
        response = self.client.get(
            reverse("meals:meal_plan"),
            {"date": "2026-07-11"},
        )

        self.assertContains(response, "分享")
        self.assertContains(
            response,
            f"{reverse('meals:meal_plan_share')}?date=2026-07-11",
        )

    def test_share_page_sends_detailed_email_to_selected_member(self):
        meal_plan = MealPlan.objects.create(
            family=self.family,
            date=date(2026, 7, 11),
            meal_type=MealPlan.LUNCH,
        )
        MealPlanItem.objects.create(
            meal_plan=meal_plan,
            dish=self.rice,
            created_by=self.owner,
            note="少盐",
            quantity=2,
        )

        get_response = self.client.get(
            reverse("meals:meal_plan_share"),
            {"date": "2026-07-11"},
        )
        self.assertContains(get_response, "发送给谁")
        self.assertContains(get_response, "member@example.com")
        self.assertContains(get_response, "米饭")
        self.assertContains(get_response, "少盐")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("meals:meal_plan_share"),
                {
                    "date": "2026-07-11",
                    "notify_user_ids": [str(self.member.id)],
                },
            )

        self.assertRedirects(
            response,
            f"{reverse('meals:meal_plan')}?date=2026-07-11",
        )
        notification = FamilyNotification.objects.get(recipient=self.member)
        self.assertEqual(notification.meal_plan_date, date(2026, 7, 11))
        self.assertIn("午餐", notification.change_summary)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("被提醒人", mail.outbox[0].alternatives[0][0])
        self.assertIn("米饭 x2", mail.outbox[0].body)

    @override_settings(PUBLIC_SITE_URL="https://example.pythonanywhere.com")
    def test_email_detail_link_can_use_public_site_url(self):
        with self.captureOnCommitCallbacks(execute=True):
            create_family_notifications(
                family=self.family,
                actor=self.owner,
                recipient_ids=[self.member.id],
                meal_plan_date=date(2026, 7, 11),
                meal_type=MealPlan.LUNCH,
                change_summary="2026-07-11 午餐：米饭",
            )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "https://example.pythonanywhere.com/meal-plan/?date=2026-07-11",
            mail.outbox[0].body,
        )

    def test_notifications_keep_latest_fifty_per_family(self):
        for offset in range(55):
            create_family_notifications(
                family=self.family,
                actor=self.owner,
                recipient_ids=[self.member.id],
                meal_plan_date=date(2026, 7, 1) + timedelta(days=offset),
                meal_type=MealPlan.LUNCH,
                change_summary=f"第 {offset} 条",
            )

        notifications = FamilyNotification.objects.filter(family=self.family)
        self.assertEqual(notifications.count(), 50)
        self.assertFalse(
            notifications.filter(
                change_summary__in=[f"第 {offset} 条" for offset in range(5)]
            ).exists()
        )
        self.assertTrue(notifications.filter(change_summary="第 54 条").exists())

    def test_notifications_page_marks_current_recipient(self):
        FamilyNotification.objects.create(
            family=self.family,
            actor=self.owner,
            recipient=self.member,
            meal_plan_date=date(2026, 7, 11),
            meal_type=MealPlan.LUNCH,
            change_summary="2026-07-11 午餐：米饭",
        )
        self.client.force_login(self.member)

        response = self.client.get(reverse("meals:notifications"))

        self.assertContains(response, "提醒你")
        self.assertContains(response, "owner")
        self.assertContains(response, "2026-07-11")
        self.assertContains(response, f"{reverse('meals:meal_plan')}?date=2026-07-11")

    def test_family_message_create_sends_email_and_opens_thread(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("meals:notification_create"),
                {
                    "notify_user_ids": [str(self.member.id)],
                    "message_body": "今晚米饭多煮一点。",
                },
            )

        notification = FamilyNotification.objects.get(
            kind=FamilyNotification.KIND_MESSAGE,
            recipient=self.member,
        )
        self.assertRedirects(
            response,
            reverse("meals:notification_thread", args=[notification.message_thread_id]),
        )
        self.assertEqual(notification.actor, self.owner)
        self.assertEqual(notification.message_body, "今晚米饭多煮一点。")
        self.assertIn("今晚米饭多煮一点", notification.change_summary)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("法米狗私厨给的通知", mail.outbox[0].subject)
        self.assertIn("给你留了一条家庭消息", mail.outbox[0].subject)
        self.assertIn("今晚米饭多煮一点", mail.outbox[0].body)

        response = self.client.get(reverse("meals:notifications"))
        self.assertContains(response, "留言")
        self.assertContains(
            response,
            reverse("meals:notification_thread", args=[notification.message_thread_id]),
        )

    def test_family_message_thread_can_add_reply(self):
        initial = FamilyNotification.objects.create(
            family=self.family,
            actor=self.owner,
            recipient=self.member,
            meal_plan_date=date(2026, 7, 11),
            kind=FamilyNotification.KIND_MESSAGE,
            message_body="记得买鸡蛋。",
            change_summary="记得买鸡蛋。",
            message_thread_id="11111111-1111-1111-1111-111111111111",
        )
        self.client.force_login(self.member)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("meals:notification_thread", args=[initial.message_thread_id]),
                {
                    "notify_user_ids": [str(self.owner.id)],
                    "message_body": "收到，我下班买。",
                },
            )

        self.assertRedirects(
            response,
            reverse("meals:notification_thread", args=[initial.message_thread_id]),
        )
        reply = FamilyNotification.objects.get(message_body="收到，我下班买。")
        self.assertEqual(reply.actor, self.member)
        self.assertEqual(reply.recipient, self.owner)
        self.assertEqual(str(reply.message_thread_id), str(initial.message_thread_id))
        self.assertEqual(len(mail.outbox), 1)

    def test_family_member_can_delete_and_clear_notifications(self):
        first = FamilyNotification.objects.create(
            family=self.family,
            actor=self.owner,
            recipient=self.member,
            meal_plan_date=date(2026, 7, 11),
            meal_type=MealPlan.LUNCH,
            change_summary="第一条",
        )
        FamilyNotification.objects.create(
            family=self.family,
            actor=self.member,
            recipient=self.owner,
            meal_plan_date=date(2026, 7, 12),
            meal_type=MealPlan.DINNER,
            change_summary="第二条",
        )
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("meals:notification_delete", args=[first.id])
        )
        self.assertRedirects(response, reverse("meals:notifications"))
        self.assertFalse(FamilyNotification.objects.filter(id=first.id).exists())
        self.assertEqual(FamilyNotification.objects.count(), 1)

        response = self.client.post(reverse("meals:notifications_clear"))

        self.assertRedirects(response, reverse("meals:notifications"))
        self.assertFalse(FamilyNotification.objects.exists())
