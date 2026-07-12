from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .forms import (
    AvatarChoiceForm,
    AvatarUploadForm,
    DishCategoryForm,
    DishForm,
    FamilyForm,
    FamilyJoinForm,
    MAIN_DISH_SECTIONS,
    RegisterForm,
    UserProfileForm,
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
from .utils import (
    date_shortcuts,
    create_family_notifications,
    create_family_history,
    daily_meal_change_summary,
    daily_meal_sections,
    get_current_family,
    get_or_create_daily_plans,
    get_user_profile,
    meal_plan_change_summary,
    set_current_family,
)


CATEGORY_RETURN_OPTIONS = {
    "dish_list": ("meals:dish_list", "返回菜品库"),
    "dish_create": ("meals:dish_create", "返回新增菜品"),
}

MEAL_SECTION_META = {
    MealPlan.BREAKFAST: {
        "plan_title": "早餐",
        "dish_title": "早餐",
        "select_title": "添加到早餐",
        "action": "加入早餐",
    },
    MealPlan.LUNCH: {
        "plan_title": "午餐",
        "dish_title": "午餐",
        "select_title": "添加到午餐",
        "action": "加入午餐",
    },
    MealPlan.DINNER: {
        "plan_title": "晚餐",
        "dish_title": "晚餐",
        "select_title": "添加到晚餐",
        "action": "加入晚餐",
    },
}

DISH_LIBRARY_SECTION_META = {
    Dish.DISCARDED: {
        "plan_title": "废弃",
        "dish_title": "废弃",
        "select_title": "废弃",
        "action": "",
    },
}

ACTIVE_DISH_SECTIONS = MAIN_DISH_SECTIONS

SPICE_ICON_PATHS = {
    MealPlanItem.SPICE_NONE: "images/meal-customization/spice-none.svg",
    MealPlanItem.SPICE_MILD: "images/meal-customization/spice-mild.svg",
    MealPlanItem.SPICE_MEDIUM: "images/meal-customization/spice-medium.svg",
    MealPlanItem.SPICE_HOT: "images/meal-customization/spice-hot.svg",
}
ICE_ICON_PATHS = {
    MealPlanItem.ICE_NONE: "images/meal-customization/ice-none.svg",
    MealPlanItem.ICE_LESS: "images/meal-customization/ice-less.svg",
    MealPlanItem.ICE_MEDIUM: "images/meal-customization/ice-medium.svg",
    MealPlanItem.ICE_MORE: "images/meal-customization/ice-more.svg",
}
QUANTITY_OPTIONS = range(1, 7)


def is_family_owner(user, family):
    return family and family.owner_id == user.id


def delete_dish_image_file(image_name):
    if not image_name:
        return
    if Dish.objects.filter(image=image_name).exists():
        return
    if default_storage.exists(image_name):
        default_storage.delete(image_name)


def delete_avatar_image_file(image_name):
    if not image_name:
        return
    if UserAvatar.objects.filter(image=image_name).exists():
        return
    if default_storage.exists(image_name):
        default_storage.delete(image_name)


def get_category_options_by_section(family):
    options = {"library": []}
    categories = (
        DishCategory.objects.filter(
            family=family,
            meal_section__in=ACTIVE_DISH_SECTIONS,
        )
        .order_by("name")
    )
    for category in categories:
        options["library"].append(
            {
                "id": str(category.id),
                "name": category.name,
            }
        )
    return options


def get_category_picker_sections(family):
    categories_by_section = get_category_options_by_section(family)
    return categories_by_section["library"]


def dish_queryset_for_family(family):
    return (
        Dish.objects.filter(family=family)
        .select_related("category", "created_by")
        .prefetch_related("categories", "meal_section_links")
    )


def filter_dishes_by_section(dishes, section):
    return dishes.filter(
        Q(meal_section_links__meal_section=section)
        | Q(meal_section=section, meal_section_links__isnull=True)
    ).distinct()


def filter_active_library_dishes(dishes):
    return dishes.filter(
        Q(meal_section_links__meal_section__in=ACTIVE_DISH_SECTIONS)
        | Q(meal_section__in=ACTIVE_DISH_SECTIONS, meal_section_links__isnull=True)
    ).distinct()


def filter_dishes_by_category(dishes, category):
    return dishes.filter(
        Q(categories=category)
        | Q(category=category, categories__isnull=True)
    ).distinct()


def filter_dishes_by_category_name(dishes, category):
    category_sections = (
        [DishCategory.DISCARDED]
        if category.meal_section == DishCategory.DISCARDED
        else ACTIVE_DISH_SECTIONS
    )
    matching_categories = DishCategory.objects.filter(
        family=category.family,
        meal_section__in=category_sections,
        name=category.name,
    )
    return dishes.filter(
        Q(categories__in=matching_categories)
        | Q(category__in=matching_categories, categories__isnull=True)
    ).distinct()


def group_categories_for_library(categories):
    seen_names = set()
    unique_categories = []
    for category in categories:
        if category.name in seen_names:
            continue
        seen_names.add(category.name)
        unique_categories.append(category)
    return unique_categories


def sync_dish_classification_after_category_change(
    dish,
    *,
    removed_sections=None,
    fallback_to_discarded=False,
):
    removed_sections = set(removed_sections or [])
    existing_sections = set(
        dish.meal_section_links.values_list("meal_section", flat=True)
    )
    if not existing_sections and dish.meal_section:
        existing_sections = {dish.meal_section}

    remaining_categories = list(
        dish.categories.exclude(meal_section=DishCategory.DISCARDED).order_by(
            "meal_section",
            "name",
        )
    )
    if (
        dish.category_id
        and dish.category
        and dish.category.meal_section != DishCategory.DISCARDED
        and dish.category not in remaining_categories
    ):
        remaining_categories.insert(0, dish.category)

    category_sections = {
        category.meal_section
        for category in remaining_categories
    }
    desired_sections = (existing_sections - removed_sections) | category_sections

    if not desired_sections and fallback_to_discarded:
        MealPlanItem.objects.filter(
            dish=dish,
            meal_plan__meal_type__in=ACTIVE_DISH_SECTIONS,
        ).delete()
        dish.meal_section_links.all().delete()
        DishMealSection.objects.create(
            dish=dish,
            meal_section=Dish.DISCARDED,
        )
        dish.meal_section = Dish.DISCARDED
        dish.category = None
        dish.save(update_fields=["meal_section", "category", "updated_at"])
        return

    if not desired_sections:
        return

    primary_category = (
        dish.category
        if dish.category in remaining_categories
        else remaining_categories[0] if remaining_categories else None
    )
    dish.category = primary_category
    dish.meal_section = (
        primary_category.meal_section
        if primary_category
        else sorted(desired_sections)[0]
    )
    dish.save(update_fields=["meal_section", "category", "updated_at"])

    DishMealSection.objects.filter(dish=dish).exclude(
        meal_section__in=desired_sections
    ).delete()
    DishMealSection.objects.bulk_create(
        [
            DishMealSection(dish=dish, meal_section=meal_section)
            for meal_section in desired_sections
        ],
        ignore_conflicts=True,
    )

    removed_active_sections = (
        existing_sections - desired_sections
    ) & set(ACTIVE_DISH_SECTIONS)
    if removed_active_sections:
        MealPlanItem.objects.filter(
            dish=dish,
            meal_plan__meal_type__in=removed_active_sections,
        ).delete()


def sync_legacy_dish_fields_from_form(dish, form):
    dish.meal_section = form.primary_meal_section()
    dish.category = form.primary_category()


def level_options(choices, icon_paths):
    return [
        {"value": value, "label": label, "icon_path": icon_paths[value]}
        for value, label in choices
    ]


def clean_choice(value, choices, fallback):
    allowed_values = {choice_value for choice_value, _label in choices}
    if value in allowed_values:
        return value
    return fallback


def save_meal_item_for_request(
    *,
    meal_plan,
    dish,
    user,
    values,
    duplicate_when_noted,
):
    note = values["note"]
    quantity = values["quantity"]
    spice_level = values["spice_level"]
    ice_level = values["ice_level"]

    item = None
    if note and not duplicate_when_noted:
        item = MealPlanItem.objects.filter(meal_plan=meal_plan, dish=dish).first()
    elif not note:
        item = MealPlanItem.objects.filter(
            meal_plan=meal_plan,
            dish=dish,
            note="",
        ).first()

    if item:
        item.note = note
        item.quantity = quantity
        item.spice_level = spice_level
        item.ice_level = ice_level
        item.save(update_fields=["note", "quantity", "spice_level", "ice_level"])
        return item, False

    return (
        MealPlanItem.objects.create(
            meal_plan=meal_plan,
            dish=dish,
            created_by=user,
            note=note,
            quantity=quantity,
            spice_level=spice_level,
            ice_level=ice_level,
        ),
        True,
    )


def get_category_return_target(request):
    next_name = request.POST.get("next") or request.GET.get("next") or "dish_list"
    if next_name not in CATEGORY_RETURN_OPTIONS:
        next_name = "dish_list"
    url_name, label = CATEGORY_RETURN_OPTIONS[next_name]
    return_url = reverse(url_name)
    return next_name, return_url, label, ""


def parse_positive_quantity(value):
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        return 1
    return max(quantity, 1)


def redirect_to_next(request, fallback_url_name="meals:meal_plan"):
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(fallback_url_name)


def meal_item_defaults_from_request(request, dish, meal_type):
    note_value = request.POST.get(f"note_{dish.id}")
    if note_value is None:
        note_value = request.POST.get("note", "")
    note = note_value.strip()
    quantity = parse_positive_quantity(
        request.POST.get(f"quantity_{dish.id}") or request.POST.get("quantity")
    )
    spice_level = ""
    ice_level = ""
    if dish.supports_spice:
        spice_level = clean_choice(
            request.POST.get(f"spice_level_{dish.id}")
            or request.POST.get("spice_level"),
            MealPlanItem.SPICE_LEVEL_CHOICES,
            MealPlanItem.SPICE_NONE,
        )
    if dish.supports_ice:
        ice_level = clean_choice(
            request.POST.get(f"ice_level_{dish.id}") or request.POST.get("ice_level"),
            MealPlanItem.ICE_LEVEL_CHOICES,
            MealPlanItem.ICE_NONE,
        )
    return {
        "note": note,
        "quantity": quantity,
        "spice_level": spice_level,
        "ice_level": ice_level,
    }


def register_view(request):
    if request.user.is_authenticated:
        return redirect("meals:meal_plan")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "注册成功，先创建或加入一个家庭吧。")
            return redirect("meals:family_create")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def family_create_view(request):
    if request.method == "POST":
        form = FamilyForm(request.POST)
        if form.is_valid():
            family = form.save(commit=False)
            family.owner = request.user
            family.save()
            FamilyMember.objects.get_or_create(
                family=family,
                user=request.user,
                defaults={"role": "owner"},
            )
            set_current_family(request, family)
            messages.success(request, f"已创建家庭：{family.name}")
            return redirect("meals:meal_plan")
    else:
        form = FamilyForm()

    return render(request, "meals/family_create.html", {"form": form})


@login_required
def family_join_view(request):
    if request.method == "POST":
        form = FamilyJoinForm(request.POST)
        if form.is_valid():
            invite_code = form.cleaned_data["invite_code"].strip()
            family = Family.objects.filter(invite_code=invite_code).first()
            if family is None:
                form.add_error("invite_code", "没有找到对应家庭，请检查邀请码。")
                return render(request, "meals/family_join.html", {"form": form})
            FamilyMember.objects.get_or_create(family=family, user=request.user)
            set_current_family(request, family)
            messages.success(request, f"已加入家庭：{family.name}")
            return redirect("meals:meal_plan")
    else:
        form = FamilyJoinForm()

    return render(request, "meals/family_join.html", {"form": form})


@login_required
def profile_view(request):
    family = get_current_family(request)
    profile = get_user_profile(request.user)
    memberships = request.user.family_memberships.select_related("family").order_by(
        "joined_at"
    )
    family_members = []
    can_manage_family = False
    if family:
        family_members = (
            FamilyMember.objects.filter(family=family)
            .select_related("user")
            .order_by("joined_at")
        )
        can_manage_family = is_family_owner(request.user, family)
    return render(
        request,
        "meals/profile.html",
        {
            "family": family,
            "memberships": memberships,
            "family_members": family_members,
            "can_manage_family": can_manage_family,
            "profile_form": UserProfileForm(instance=request.user),
            "avatar_upload_form": AvatarUploadForm(user=request.user),
            "profile": profile,
            "default_avatars": UserProfile.DEFAULT_AVATARS,
            "custom_avatars": request.user.custom_avatars.all(),
            "family_form": FamilyForm(instance=family) if family else None,
        },
    )


@login_required
@require_POST
def profile_update_view(request):
    form = UserProfileForm(request.POST, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "个人信息已更新。")
    else:
        error = " ".join(
            error
            for errors in form.errors.values()
            for error in errors
        )
        messages.error(request, error or "用户名更新失败，请检查后再试。")
    return redirect("meals:profile")


@login_required
@require_POST
def avatar_update_view(request):
    profile = get_user_profile(request.user)
    form = AvatarChoiceForm(request.POST, user=request.user)
    if form.is_valid():
        form.save(profile)
        messages.success(request, "头像已更新。")
    else:
        error = " ".join(
            error
            for errors in form.errors.values()
            for error in errors
        )
        messages.error(request, error or "头像更新失败，请重新选择。")
    return redirect("meals:profile")


@login_required
@require_POST
def avatar_upload_view(request):
    form = AvatarUploadForm(request.POST, request.FILES, user=request.user)
    if form.is_valid():
        avatar = form.save(commit=False)
        avatar.user = request.user
        avatar.save()
        profile = get_user_profile(request.user)
        profile.custom_avatar = avatar
        profile.save(update_fields=["custom_avatar", "updated_at"])
        messages.success(request, "头像已上传并设为当前头像。")
    else:
        error = " ".join(
            error
            for errors in form.errors.values()
            for error in errors
        )
        messages.error(request, error or "头像上传失败，请检查图片。")
    return redirect("meals:profile")


@login_required
@require_POST
def avatar_delete_view(request, avatar_id):
    avatar = get_object_or_404(UserAvatar, id=avatar_id, user=request.user)
    image_name = avatar.image.name if avatar.image else ""
    UserProfile.objects.filter(
        user=request.user,
        custom_avatar=avatar,
    ).update(custom_avatar=None)
    avatar.delete()
    delete_avatar_image_file(image_name)
    messages.success(request, "已删除自定义头像。")
    return redirect("meals:profile")


@login_required
@require_POST
def family_switch_view(request):
    family_id = request.POST.get("family_id")
    membership = (
        request.user.family_memberships.select_related("family")
        .filter(family_id=family_id)
        .first()
    )
    if not membership:
        messages.error(request, "没有找到这个家庭，无法切换。")
        return redirect_to_next(request)

    set_current_family(request, membership.family)
    messages.success(request, f"已切换到 {membership.family.name}。")
    return redirect_to_next(request)


@login_required
@require_POST
def family_update_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")
    if not is_family_owner(request.user, family):
        return HttpResponseForbidden("只有家庭 owner 可以编辑家庭信息。")

    form = FamilyForm(request.POST, instance=family)
    if form.is_valid():
        form.save()
        messages.success(request, "家庭信息已更新。")
    else:
        error = " ".join(
            error
            for errors in form.errors.values()
            for error in errors
        )
        messages.error(request, error or "家庭信息更新失败，请检查后再试。")
    return redirect_to_next(request, "meals:family_manage")


@login_required
def family_manage_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")
    if not is_family_owner(request.user, family):
        return HttpResponseForbidden("只有家庭 owner 可以管理家庭信息。")

    family_members = (
        FamilyMember.objects.filter(family=family)
        .select_related("user")
        .order_by("joined_at")
    )
    return render(
        request,
        "meals/family_manage.html",
        {
            "family": family,
            "family_form": FamilyForm(instance=family),
            "family_members": family_members,
        },
    )


@login_required
@require_POST
def family_leave_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    membership = get_object_or_404(
        FamilyMember,
        family=family,
        user=request.user,
    )
    other_members = FamilyMember.objects.filter(family=family).exclude(
        user=request.user
    )
    if family.owner_id == request.user.id and other_members.exists():
        messages.error(request, "请先把 owner 权限转让给其他成员，再退出家庭。")
        return redirect("meals:profile")

    family_name = family.name
    if family.owner_id == request.user.id:
        family.delete()
    else:
        membership.delete()

    next_membership = (
        request.user.family_memberships.select_related("family")
        .order_by("joined_at")
        .first()
    )
    if next_membership:
        set_current_family(request, next_membership.family)
        messages.success(request, f"已退出 {family_name}。")
        return redirect("meals:profile")

    request.session.pop("current_family_id", None)
    messages.success(request, f"已退出 {family_name}。")
    return redirect("meals:family_create")


@login_required
@require_POST
def family_transfer_owner_view(request, member_id):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")
    if not is_family_owner(request.user, family):
        return HttpResponseForbidden("只有家庭 owner 可以转让 owner 权限。")

    target_membership = get_object_or_404(
        FamilyMember.objects.select_related("user"),
        id=member_id,
        family=family,
    )
    if target_membership.user_id == request.user.id:
        messages.info(request, "你已经是这个家庭的 owner。")
        return redirect("meals:profile")

    with transaction.atomic():
        locked_family = Family.objects.select_for_update().get(id=family.id)
        if locked_family.owner_id != request.user.id:
            return HttpResponseForbidden("只有当前 owner 可以转让 owner 权限。")
        locked_family.owner = target_membership.user
        locked_family.save(update_fields=["owner", "updated_at"])
        FamilyMember.objects.filter(family=locked_family).update(role="member")
        FamilyMember.objects.filter(
            family=locked_family,
            user=target_membership.user,
        ).update(role="owner")

    messages.success(request, f"已把 owner 权限转让给 {target_membership.user.username}。")
    return redirect_to_next(request, "meals:profile")


@login_required
@require_POST
def family_remove_member_view(request, member_id):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")
    if not is_family_owner(request.user, family):
        return HttpResponseForbidden("只有家庭 owner 可以管理家庭成员。")

    membership = get_object_or_404(
        FamilyMember.objects.select_related("user"),
        id=member_id,
        family=family,
    )
    if membership.user_id == family.owner_id:
        messages.error(request, "不能移除当前 owner，请先把 owner 权限转让给其他成员。")
        return redirect("meals:profile")

    username = membership.user.username
    membership.delete()
    messages.success(request, f"已将 {username} 移出家庭。")
    return redirect_to_next(request, "meals:profile")


@login_required
def shopping_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")
    return render(request, "meals/shopping.html", {"family": family})


@login_required
def family_notifications_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    notifications = (
        FamilyNotification.objects.filter(family=family)
        .select_related("actor", "recipient", "family")
        .order_by("-created_at", "-id")
    )
    paginator = Paginator(notifications, 10)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    context = {
        "family": family,
        "page_obj": page_obj,
        "notifications": page_obj.object_list,
    }
    if request.GET.get("partial") == "1":
        return render(request, "meals/partials/notification_page.html", context)
    return render(request, "meals/notifications.html", context)


@login_required
@require_POST
def family_notifications_clear_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    deleted_count, _details = FamilyNotification.objects.filter(family=family).delete()
    if deleted_count:
        messages.success(request, "已清空家庭消息。")
    else:
        messages.info(request, "当前还没有家庭消息。")
    return redirect("meals:notifications")


@login_required
@require_POST
def family_notification_delete_view(request, notification_id):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    notification = get_object_or_404(
        FamilyNotification,
        id=notification_id,
        family=family,
    )
    notification.delete()
    messages.success(request, "已删除这条消息。")
    return redirect("meals:notifications")


@login_required
def dish_list_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    category_id = request.GET.get("category")
    section = request.GET.get("section")
    dishes = dish_queryset_for_family(family)
    selected_category = None
    selected_category_name = ""
    is_discarded_view = section == Dish.DISCARDED
    if is_discarded_view:
        dishes = filter_dishes_by_section(dishes, Dish.DISCARDED)
    else:
        dishes = filter_active_library_dishes(dishes)
    if category_id:
        selected_category = get_object_or_404(
            DishCategory,
            id=category_id,
            family=family,
        )
        selected_category_name = selected_category.name
        if not is_discarded_view and selected_category.meal_section == Dish.DISCARDED:
            return redirect(
                f"{reverse('meals:dish_list')}?section={Dish.DISCARDED}&category={selected_category.id}"
            )
        if is_discarded_view and selected_category.meal_section != Dish.DISCARDED:
            return redirect(f"{reverse('meals:dish_list')}?section={Dish.DISCARDED}")
        if not is_discarded_view and selected_category.meal_section not in ACTIVE_DISH_SECTIONS:
            return redirect("meals:dish_list")
        dishes = filter_dishes_by_category_name(dishes, selected_category)

    categories = DishCategory.objects.filter(family=family)
    if is_discarded_view:
        categories = categories.filter(meal_section=DishCategory.DISCARDED).order_by("name")
    else:
        categories = categories.filter(meal_section__in=ACTIVE_DISH_SECTIONS).order_by("name")
    categories = group_categories_for_library(categories)
    return render(
        request,
        "meals/dish_list.html",
        {
            "family": family,
            "dishes": dishes,
            "categories": categories,
            "selected_category": selected_category,
            "selected_category_name": selected_category_name,
            "is_discarded_view": is_discarded_view,
            "can_manage_categories": is_family_owner(request.user, family),
            "can_create_library_content": not is_discarded_view,
        },
    )


@login_required
def dish_create_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    if request.method == "POST":
        form = DishForm(request.POST, request.FILES, family=family)
        if form.is_valid():
            dish = form.save(commit=False)
            dish.family = family
            dish.created_by = request.user
            sync_legacy_dish_fields_from_form(dish, form)
            dish.save()
            form.save_m2m()
            form.save_meal_sections(dish)
            messages.success(request, f"已添加菜品：{dish.name}")
            return redirect("meals:dish_list")
    else:
        form = DishForm(family=family)

    return render(
        request,
        "meals/dish_form.html",
        {
            "form": form,
            "family": family,
            "page_title": "新增菜品",
            "submit_label": "保存菜品",
            "is_edit": False,
            "category_picker_categories": get_category_picker_sections(family),
        },
    )


@login_required
def dish_edit_view(request, dish_id):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    dish = get_object_or_404(Dish, id=dish_id, family=family)

    if request.method == "POST":
        old_image_name = dish.image.name if dish.image else ""
        old_meal_sections = set(
            dish.meal_section_links.values_list("meal_section", flat=True)
        )
        if not old_meal_sections and dish.meal_section:
            old_meal_sections = {dish.meal_section}
        form = DishForm(request.POST, request.FILES, family=family, instance=dish)
        if form.is_valid():
            updated_dish = form.save(commit=False)
            sync_legacy_dish_fields_from_form(updated_dish, form)
            clear_image = request.POST.get("clear_image") == "1"
            has_new_image = bool(request.FILES.get("image"))
            if clear_image:
                updated_dish.image = None
            updated_dish.save()
            form.save_m2m()
            form.save_meal_sections(updated_dish)

            new_meal_sections = set(ACTIVE_DISH_SECTIONS)
            removed_meal_sections = old_meal_sections - new_meal_sections
            if removed_meal_sections:
                MealPlanItem.objects.filter(
                    dish=updated_dish,
                    meal_plan__family=family,
                    meal_plan__meal_type__in=removed_meal_sections,
                ).delete()
            if old_image_name and (
                clear_image
                or (has_new_image and old_image_name != updated_dish.image.name)
            ):
                delete_dish_image_file(old_image_name)

            messages.success(request, f"已更新菜品：{dish.name}")
            return redirect("meals:dish_list")
    else:
        form = DishForm(family=family, instance=dish)

    return render(
        request,
        "meals/dish_form.html",
        {
            "form": form,
            "family": family,
            "dish": dish,
            "page_title": "编辑菜品",
            "submit_label": "保存修改",
            "is_edit": True,
            "category_picker_categories": get_category_picker_sections(family),
        },
    )


@login_required
@require_POST
def dish_delete_view(request, dish_id):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    dish = get_object_or_404(Dish, id=dish_id, family=family)
    dish_name = dish.name
    image_name = dish.image.name if dish.image else ""
    dish.delete()
    delete_dish_image_file(image_name)
    messages.success(request, f"已删除菜品：{dish_name}")
    return redirect("meals:dish_list")


@login_required
def category_create_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    next_name, return_url, return_label, section = get_category_return_target(request)

    if request.method == "POST":
        form = DishCategoryForm(request.POST, family=family)
        if form.is_valid():
            category = form.save(commit=False)
            category.family = family
            category.meal_section = DishCategory.LUNCH
            category.save()
            messages.success(request, f"已添加分类：{category.name}")
            return redirect(return_url)
    else:
        form = DishCategoryForm(family=family)

    return render(
        request,
        "meals/category_form.html",
        {
            "form": form,
            "family": family,
            "next_name": next_name,
            "return_url": return_url,
            "return_label": return_label,
            "section": section,
            "page_title": "新增分类",
            "submit_label": "保存分类",
            "is_edit": False,
        },
    )


@login_required
def category_edit_view(request, category_id):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")
    if not is_family_owner(request.user, family):
        return HttpResponseForbidden("只有家庭创建者可以编辑分类。")

    category = get_object_or_404(DishCategory, id=category_id, family=family)
    old_meal_section = category.meal_section
    return_url = reverse("meals:dish_list")

    if request.method == "POST":
        form = DishCategoryForm(request.POST, family=family, instance=category)
        if form.is_valid():
            with transaction.atomic():
                affected_ids = list(
                    Dish.objects.filter(
                        Q(categories=category) | Q(category=category),
                        family=family,
                    )
                    .distinct()
                    .values_list("id", flat=True)
                )
                category = form.save(commit=False)
                category.meal_section = DishCategory.LUNCH
                category.save()
                if old_meal_section != category.meal_section:
                    affected_dishes = (
                        Dish.objects.filter(id__in=affected_ids)
                        .select_related("category")
                        .prefetch_related("categories", "meal_section_links")
                    )
                    for dish in affected_dishes:
                        sync_dish_classification_after_category_change(
                            dish,
                            removed_sections=[old_meal_section],
                        )
            messages.success(request, f"已更新分类：{category.name}")
            return redirect("meals:dish_list")
    else:
        form = DishCategoryForm(family=family, instance=category)

    return render(
        request,
        "meals/category_form.html",
        {
            "form": form,
            "family": family,
            "category": category,
            "next_name": "dish_list",
            "return_url": return_url,
            "return_label": "返回菜品库",
            "section": "",
            "page_title": "编辑分类",
            "submit_label": "保存分类",
            "is_edit": True,
        },
    )


@login_required
@require_POST
def category_delete_view(request, category_id):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")
    if not is_family_owner(request.user, family):
        return HttpResponseForbidden("只有家庭创建者可以删除分类。")

    category = get_object_or_404(DishCategory, id=category_id, family=family)
    category_name = category.name
    with transaction.atomic():
        affected_dishes = list(
            Dish.objects.filter(
                Q(categories=category) | Q(category=category),
                family=family,
            )
            .prefetch_related("categories", "meal_section_links")
            .distinct()
        )
        for dish in affected_dishes:
            dish.categories.remove(category)
            if dish.category_id == category.id:
                dish.category = None
                dish.save(update_fields=["category", "updated_at"])
            sync_dish_classification_after_category_change(
                dish,
                removed_sections=[category.meal_section],
                fallback_to_discarded=True,
            )
        category.delete()
    messages.success(
        request,
        f"已删除分类：{category_name}，没有其他归属的菜品已移入废弃。",
    )
    return redirect("meals:dish_list")


@login_required
def meal_plan_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    selected_date = parse_date(request.GET.get("date") or "")
    if selected_date is None:
        selected_date = timezone.localdate()

    plans = get_or_create_daily_plans(family, selected_date)

    return render(
        request,
        "meals/meal_plan.html",
        {
            "family": family,
            "selected_date": selected_date,
            "date_shortcuts": date_shortcuts(selected_date),
            "breakfast_plan": plans[MealPlan.BREAKFAST],
            "lunch_plan": plans[MealPlan.LUNCH],
            "dinner_plan": plans[MealPlan.DINNER],
            "quantity_options": QUANTITY_OPTIONS,
            "spice_level_options": level_options(
                MealPlanItem.SPICE_LEVEL_CHOICES,
                SPICE_ICON_PATHS,
            ),
            "ice_level_options": level_options(
                MealPlanItem.ICE_LEVEL_CHOICES,
                ICE_ICON_PATHS,
            ),
        },
    )


def record_meal_plan_history(*, family, actor, meal_plan):
    meal_plan = (
        MealPlan.objects.prefetch_related("items__dish")
        .select_related("family")
        .get(pk=meal_plan.pk)
    )
    return create_family_history(
        family=family,
        actor=actor,
        meal_plan_date=meal_plan.date,
        meal_type=meal_plan.meal_type,
        change_summary=meal_plan_change_summary(meal_plan),
    )


@login_required
def meal_plan_share_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    selected_date = parse_date(
        request.POST.get("date") or request.GET.get("date") or ""
    )
    if selected_date is None:
        selected_date = timezone.localdate()

    meal_sections = daily_meal_sections(family, selected_date)
    recipients = (
        FamilyMember.objects.filter(family=family)
        .exclude(user=request.user)
        .select_related("user", "user__meal_profile")
        .order_by("joined_at")
    )

    if request.method == "POST":
        notify_user_ids = request.POST.getlist("notify_user_ids")
        if not notify_user_ids:
            messages.error(request, "请先选择至少一位家庭成员。")
        else:
            notification_count = create_family_notifications(
                family=family,
                actor=request.user,
                recipient_ids=notify_user_ids,
                meal_plan_date=selected_date,
                change_summary=daily_meal_change_summary(family, selected_date),
                request=request,
                meal_sections=meal_sections,
            )
            if notification_count:
                messages.success(
                    request,
                    f"已把 {selected_date.isoformat()} 的排餐提醒发送给 {notification_count} 位家人。",
                )
                return redirect(
                    f"{reverse('meals:meal_plan')}?date={selected_date.isoformat()}"
                )
            messages.error(request, "没有找到可提醒的家庭成员。")

    return render(
        request,
        "meals/meal_plan_share.html",
        {
            "family": family,
            "selected_date": selected_date,
            "meal_sections": meal_sections,
            "recipients": recipients,
        },
    )


@login_required
def meal_plan_select_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    meal_type = request.POST.get("meal_type") or request.GET.get("meal_type")
    selected_date = parse_date(
        request.POST.get("date") or request.GET.get("date") or ""
    )

    if meal_type not in MEAL_SECTION_META:
        return HttpResponseBadRequest("Invalid meal type")
    if selected_date is None:
        selected_date = timezone.localdate()

    meal_plan, _created = MealPlan.objects.get_or_create(
        family=family,
        date=selected_date,
        meal_type=meal_type,
    )

    category_id = request.POST.get("category") or request.GET.get("category")
    selected_category = None
    selected_category_name = ""
    dishes = filter_active_library_dishes(dish_queryset_for_family(family))
    if category_id:
        selected_category = get_object_or_404(
            DishCategory,
            id=category_id,
            family=family,
        )
        selected_category_name = selected_category.name
        if selected_category.meal_section not in ACTIVE_DISH_SECTIONS:
            return redirect(
                f"{reverse('meals:meal_plan_select')}?date={selected_date.isoformat()}&meal_type={meal_type}"
            )
        dishes = filter_dishes_by_category_name(dishes, selected_category)

    categories = (
        DishCategory.objects.filter(
            family=family,
            meal_section__in=ACTIVE_DISH_SECTIONS,
        )
        .order_by("name")
    )
    categories = group_categories_for_library(categories)
    existing_items = (
        meal_plan.items.filter(dish__family=family)
        .select_related("dish")
        .order_by("created_at")
    )
    items_by_dish = {}
    for item in existing_items:
        items_by_dish.setdefault(item.dish_id, item)
    selected_ids = set(items_by_dish)
    dish_rows = []
    for dish in dishes:
        item = items_by_dish.get(dish.id)
        dish_rows.append(
            {
                "dish": dish,
                "item": item,
                "is_selected": dish.id in selected_ids,
                "quantity": item.quantity if item else 1,
                "spice_level": item.spice_level
                if item and item.spice_level
                else MealPlanItem.SPICE_NONE,
                "ice_level": item.ice_level
                if item and item.ice_level
                else MealPlanItem.ICE_NONE,
            }
        )

    if request.method == "POST":
        checked_ids = request.POST.getlist("dish_ids")
        notify_user_ids = request.POST.getlist("notify_user_ids")
        selected_dishes = dishes.filter(id__in=checked_ids)
        MealPlanItem.objects.filter(
            meal_plan=meal_plan,
            dish__in=dishes,
        ).exclude(dish_id__in=checked_ids).delete()

        for dish in selected_dishes:
            values = meal_item_defaults_from_request(request, dish, meal_type)
            save_meal_item_for_request(
                meal_plan=meal_plan,
                dish=dish,
                user=request.user,
                values=values,
                duplicate_when_noted=False,
            )
        record_meal_plan_history(
            family=family,
            actor=request.user,
            meal_plan=meal_plan,
        )
        if notify_user_ids:
            meal_plan = (
                MealPlan.objects.prefetch_related("items__dish")
                .select_related("family")
                .get(pk=meal_plan.pk)
            )
            notification_count = create_family_notifications(
                family=family,
                actor=request.user,
                recipient_ids=notify_user_ids,
                meal_plan_date=selected_date,
                meal_type=meal_type,
                change_summary=meal_plan_change_summary(meal_plan),
                request=request,
            )
            if notification_count:
                messages.success(request, f"已保存选择，并提醒 {notification_count} 位家人。")
            else:
                messages.info(request, "已保存选择，但没有找到可提醒的家庭成员。")
        return redirect(f"{reverse('meals:meal_plan')}?date={selected_date.isoformat()}")

    notification_recipients = (
        FamilyMember.objects.filter(family=family)
        .exclude(user=request.user)
        .select_related("user", "user__meal_profile")
        .order_by("joined_at")
    )
    return render(
        request,
        "meals/meal_plan_select.html",
        {
            "family": family,
            "selected_date": selected_date,
            "meal_type": meal_type,
            "meal_meta": MEAL_SECTION_META[meal_type],
            "meal_plan": meal_plan,
            "dishes": dishes,
            "dish_rows": dish_rows,
            "categories": categories,
            "selected_category": selected_category,
            "selected_category_name": selected_category_name,
            "selected_ids": selected_ids,
            "notification_recipients": notification_recipients,
            "quantity_options": QUANTITY_OPTIONS,
            "spice_level_options": level_options(
                MealPlanItem.SPICE_LEVEL_CHOICES,
                SPICE_ICON_PATHS,
            ),
            "ice_level_options": level_options(
                MealPlanItem.ICE_LEVEL_CHOICES,
                ICE_ICON_PATHS,
            ),
        },
    )


@login_required
@require_POST
def meal_plan_toggle_view(request):
    family = get_current_family(request)
    if not family:
        return HttpResponseBadRequest("Missing family")

    dish_id = request.POST.get("dish_id")
    meal_type = request.POST.get("meal_type")
    selected_date = parse_date(request.POST.get("date") or "")
    should_select = request.POST.get("selected") == "1"

    if meal_type not in MEAL_SECTION_META:
        return HttpResponseBadRequest("Invalid meal type")
    if selected_date is None:
        return HttpResponseBadRequest("Invalid date")

    dish = get_object_or_404(
        filter_active_library_dishes(dish_queryset_for_family(family)),
        id=dish_id,
    )
    meal_plan, _created = MealPlan.objects.get_or_create(
        family=family,
        date=selected_date,
        meal_type=meal_type,
    )

    if should_select:
        values = meal_item_defaults_from_request(request, dish, meal_type)
        save_meal_item_for_request(
            meal_plan=meal_plan,
            dish=dish,
            user=request.user,
            values=values,
            duplicate_when_noted=False,
        )
    else:
        MealPlanItem.objects.filter(meal_plan=meal_plan, dish=dish).delete()

    record_meal_plan_history(
        family=family,
        actor=request.user,
        meal_plan=meal_plan,
    )
    return HttpResponse(status=204)


@login_required
@require_POST
def meal_plan_add_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    dish_id = request.POST.get("dish_id")
    meal_type = request.POST.get("meal_type")
    selected_date = parse_date(request.POST.get("date") or "")

    if meal_type not in MEAL_SECTION_META:
        return HttpResponseBadRequest("Invalid meal type")
    if selected_date is None:
        return HttpResponseBadRequest("Invalid date")

    dish = get_object_or_404(
        filter_active_library_dishes(dish_queryset_for_family(family)),
        id=dish_id,
    )
    meal_plan, _created = MealPlan.objects.get_or_create(
        family=family,
        date=selected_date,
        meal_type=meal_type,
    )
    values = meal_item_defaults_from_request(request, dish, meal_type)
    save_meal_item_for_request(
        meal_plan=meal_plan,
        dish=dish,
        user=request.user,
        values=values,
        duplicate_when_noted=True,
    )
    record_meal_plan_history(
        family=family,
        actor=request.user,
        meal_plan=meal_plan,
    )
    return redirect(f"{reverse('meals:meal_plan')}?date={selected_date.isoformat()}")


@login_required
@require_POST
def meal_plan_clear_day_view(request):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    selected_date = parse_date(request.POST.get("date") or "")
    if selected_date is None:
        return HttpResponseBadRequest("Invalid date")

    deleted_count, _details = MealPlanItem.objects.filter(
        meal_plan__family=family,
        meal_plan__date=selected_date,
        meal_plan__meal_type__in=[
            MealPlan.BREAKFAST,
            MealPlan.LUNCH,
            MealPlan.DINNER,
        ],
    ).delete()
    if deleted_count:
        create_family_history(
            family=family,
            actor=request.user,
            meal_plan_date=selected_date,
            change_summary=f"{selected_date.isoformat()} 三餐已清空。",
        )
        messages.success(request, f"已清空 {selected_date.isoformat()} 的三餐排餐。")
    else:
        messages.info(request, f"{selected_date.isoformat()} 还没有排过三餐。")
    return redirect(f"{reverse('meals:meal_plan')}?date={selected_date.isoformat()}")


@login_required
@require_POST
def meal_plan_update_item_view(request, item_id):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    item = get_object_or_404(
        MealPlanItem.objects.select_related("meal_plan", "dish"),
        id=item_id,
        meal_plan__family=family,
    )
    selected_date = item.meal_plan.date
    item.note = request.POST.get("note", "").strip()
    item.quantity = parse_positive_quantity(request.POST.get("quantity"))
    item.spice_level = ""
    item.ice_level = ""
    if item.dish.supports_spice:
        item.spice_level = clean_choice(
            request.POST.get("spice_level"),
            MealPlanItem.SPICE_LEVEL_CHOICES,
            MealPlanItem.SPICE_NONE,
        )
    if item.dish.supports_ice:
        item.ice_level = clean_choice(
            request.POST.get("ice_level"),
            MealPlanItem.ICE_LEVEL_CHOICES,
            MealPlanItem.ICE_NONE,
        )
    item.save(update_fields=["note", "quantity", "spice_level", "ice_level"])
    record_meal_plan_history(
        family=family,
        actor=request.user,
        meal_plan=item.meal_plan,
    )
    return redirect(f"{reverse('meals:meal_plan')}?date={selected_date.isoformat()}")


@login_required
@require_POST
def meal_plan_remove_view(request, item_id):
    family = get_current_family(request)
    if not family:
        return redirect("meals:family_create")

    selected_date = parse_date(request.POST.get("date") or "")
    item = (
        MealPlanItem.objects.filter(id=item_id, meal_plan__family=family)
        .select_related("meal_plan")
        .first()
    )
    if item:
        selected_date = item.meal_plan.date
        meal_plan = item.meal_plan
        item.delete()
        record_meal_plan_history(
            family=family,
            actor=request.user,
            meal_plan=meal_plan,
        )
    if selected_date is None:
        selected_date = timezone.localdate()

    return redirect(f"{reverse('meals:meal_plan')}?date={selected_date.isoformat()}")
