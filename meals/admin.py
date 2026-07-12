from django.contrib import admin

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


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ("name", "invite_code", "owner", "created_at")
    search_fields = ("name", "invite_code", "owner__username")


@admin.register(FamilyMember)
class FamilyMemberAdmin(admin.ModelAdmin):
    list_display = ("family", "user", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("family__name", "user__username")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number", "default_avatar", "custom_avatar", "updated_at")
    search_fields = ("user__username", "user__email", "phone_number")


@admin.register(UserAvatar)
class UserAvatarAdmin(admin.ModelAdmin):
    list_display = ("user", "image", "created_at")
    search_fields = ("user__username",)


@admin.register(DishCategory)
class DishCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "meal_section", "family", "created_at")
    list_filter = ("meal_section", "family")
    search_fields = ("name", "family__name")


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name", "family", "meal_section", "category", "calories", "created_by", "created_at")
    list_filter = ("family", "meal_section", "category", "categories")
    filter_horizontal = ("categories",)
    search_fields = ("name", "description", "family__name")


@admin.register(DishMealSection)
class DishMealSectionAdmin(admin.ModelAdmin):
    list_display = ("dish", "meal_section")
    list_filter = ("meal_section",)
    search_fields = ("dish__name",)


class MealPlanItemInline(admin.TabularInline):
    model = MealPlanItem
    extra = 0


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ("family", "date", "meal_type", "updated_at")
    list_filter = ("meal_type", "date", "family")
    inlines = [MealPlanItemInline]


@admin.register(MealPlanItem)
class MealPlanItemAdmin(admin.ModelAdmin):
    list_display = ("meal_plan", "dish", "created_by", "created_at")
    search_fields = ("dish__name", "meal_plan__family__name")


@admin.register(FamilyNotification)
class FamilyNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "family",
        "actor",
        "recipient",
        "meal_plan_date",
        "meal_type",
        "created_at",
    )
    list_filter = ("family", "meal_type", "created_at")
    search_fields = (
        "family__name",
        "actor__username",
        "recipient__username",
        "change_summary",
    )
