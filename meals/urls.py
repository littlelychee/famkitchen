from django.urls import path

from . import views

app_name = "meals"

urlpatterns = [
    path("", views.meal_plan_view, name="home"),
    path("family/create/", views.family_create_view, name="family_create"),
    path("family/join/", views.family_join_view, name="family_join"),
    path("family/switch/", views.family_switch_view, name="family_switch"),
    path("family/manage/", views.family_manage_view, name="family_manage"),
    path("family/update/", views.family_update_view, name="family_update"),
    path("family/leave/", views.family_leave_view, name="family_leave"),
    path(
        "family/members/<int:member_id>/transfer-owner/",
        views.family_transfer_owner_view,
        name="family_transfer_owner",
    ),
    path(
        "family/members/<int:member_id>/remove/",
        views.family_remove_member_view,
        name="family_remove_member",
    ),
    path("me/", views.profile_view, name="profile"),
    path("me/update/", views.profile_update_view, name="profile_update"),
    path("me/avatar/update/", views.avatar_update_view, name="avatar_update"),
    path("me/avatar/upload/", views.avatar_upload_view, name="avatar_upload"),
    path(
        "me/avatar/<int:avatar_id>/delete/",
        views.avatar_delete_view,
        name="avatar_delete",
    ),
    path("notifications/", views.family_notifications_view, name="notifications"),
    path(
        "notifications/new/",
        views.family_message_create_view,
        name="notification_create",
    ),
    path(
        "notifications/thread/<uuid:thread_id>/",
        views.family_message_thread_view,
        name="notification_thread",
    ),
    path(
        "notifications/clear/",
        views.family_notifications_clear_view,
        name="notifications_clear",
    ),
    path(
        "notifications/<int:notification_id>/delete/",
        views.family_notification_delete_view,
        name="notification_delete",
    ),
    path("shopping/", views.shopping_view, name="shopping"),
    path("dishes/", views.dish_list_view, name="dish_list"),
    path("dishes/create/", views.dish_create_view, name="dish_create"),
    path("dishes/<int:dish_id>/edit/", views.dish_edit_view, name="dish_edit"),
    path("dishes/<int:dish_id>/delete/", views.dish_delete_view, name="dish_delete"),
    path("categories/create/", views.category_create_view, name="category_create"),
    path(
        "categories/sort-mode/",
        views.category_sort_mode_view,
        name="category_sort_mode",
    ),
    path(
        "categories/reorder/",
        views.category_reorder_view,
        name="category_reorder",
    ),
    path(
        "categories/<int:category_id>/edit/",
        views.category_edit_view,
        name="category_edit",
    ),
    path(
        "categories/<int:category_id>/delete/",
        views.category_delete_view,
        name="category_delete",
    ),
    path("meal-plan/", views.meal_plan_view, name="meal_plan"),
    path("meal-plan/share/", views.meal_plan_share_view, name="meal_plan_share"),
    path("meal-plan/select/", views.meal_plan_select_view, name="meal_plan_select"),
    path("meal-plan/toggle/", views.meal_plan_toggle_view, name="meal_plan_toggle"),
    path("meal-plan/add/", views.meal_plan_add_view, name="meal_plan_add"),
    path("meal-plan/clear-day/", views.meal_plan_clear_day_view, name="meal_plan_clear_day"),
    path(
        "meal-plan/items/<int:item_id>/update/",
        views.meal_plan_update_item_view,
        name="meal_plan_update_item",
    ),
    path(
        "meal-plan/remove/<int:item_id>/",
        views.meal_plan_remove_view,
        name="meal_plan_remove",
    ),
]
