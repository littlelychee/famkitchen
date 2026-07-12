from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import AvatarUploadForm
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
)
from .utils import create_family_notifications


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


class FamilyMemberManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="password")
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
        self.assertNotContains(response, "other_member")
        self.assertNotContains(response, "转让 owner")
        self.assertNotContains(response, "移除")

    def test_owner_manage_page_shows_family_members(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("meals:family_manage"))

        self.assertContains(response, "owner")
        self.assertContains(response, "member")
        self.assertContains(response, "other_member")
        self.assertContains(response, "转让 owner")
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


class AvatarUploadFormTests(TestCase):
    def test_upload_form_rejects_more_than_two_custom_avatars(self):
        user = User.objects.create_user(username="owner", password="password")
        UserAvatar.objects.create(user=user, image="avatars/user_1/a.png")
        UserAvatar.objects.create(user=user, image="avatars/user_1/b.png")
        image = SimpleUploadedFile(
            "avatar.gif",
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        form = AvatarUploadForm(files={"image": image}, user=user)

        self.assertFalse(form.is_valid())
        self.assertIn("达到最大两个头像的上限了", str(form.errors))


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
        self.owner = User.objects.create_user(username="owner", password="password")
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
        self.assertIn("owner", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["member@example.com"])
        self.assertIn("发送人", mail.outbox[0].alternatives[0][0])
        self.assertIn("owner 提醒你", mail.outbox[0].alternatives[0][0])
        self.assertIn("关注 2026-07-11 的排餐", mail.outbox[0].alternatives[0][0])
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
