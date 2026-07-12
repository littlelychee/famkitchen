from datetime import timedelta
import logging
from uuid import uuid4

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils.html import escape
from django.utils import timezone

from .models import FamilyMember, FamilyNotification, MealPlan, UserProfile


MAIN_MEAL_TYPES = (MealPlan.BREAKFAST, MealPlan.LUNCH, MealPlan.DINNER)
logger = logging.getLogger(__name__)


def get_user_profile(user):
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return profile


def get_current_family(request_or_user):
    request = None
    user = request_or_user
    if hasattr(request_or_user, "user") and hasattr(request_or_user, "session"):
        request = request_or_user
        user = request_or_user.user

    if not user.is_authenticated:
        return None

    memberships = user.family_memberships.select_related("family").order_by(
        "joined_at"
    )
    if request is not None:
        family_id = request.session.get("current_family_id")
        if family_id:
            membership = memberships.filter(family_id=family_id).first()
            if membership:
                return membership.family
            request.session.pop("current_family_id", None)

    membership = (
        memberships.first()
    )
    if membership:
        if request is not None:
            request.session["current_family_id"] = membership.family_id
        return membership.family
    return None


def set_current_family(request, family):
    request.session["current_family_id"] = family.id


def date_shortcuts(selected_date):
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    return {
        "today": today,
        "tomorrow": tomorrow,
        "previous_week": selected_date - timedelta(days=7),
        "previous_day": selected_date - timedelta(days=1),
        "next_day": selected_date + timedelta(days=1),
        "next_week": selected_date + timedelta(days=7),
        "is_today": selected_date == today,
        "is_tomorrow": selected_date == tomorrow,
    }


def get_or_create_daily_plans(family, selected_date):
    plans = {}
    for meal_type in MAIN_MEAL_TYPES:
        plan, _created = MealPlan.objects.prefetch_related(
            "items__dish__category",
            "items__dish__categories",
            "items__dish__meal_section_links",
            "items__dish__created_by",
        ).get_or_create(
            family=family,
            date=selected_date,
            meal_type=meal_type,
        )
        plans[meal_type] = plan
    return plans


def meal_item_display(item):
    label = item.dish.name
    if item.quantity > 1:
        label = f"{label} x{item.quantity}"
    details = []
    if item.spice_level_label:
        details.append(item.spice_level_label)
    if item.warm_label:
        details.append(item.warm_label)
    if item.ice_level_label:
        details.append(item.ice_level_label)
    if item.note:
        details.append(item.note)
    if details:
        label = f"{label}（{' / '.join(details)}）"
    return label


def meal_plan_items_summary(meal_plan):
    items = (
        meal_plan.items.select_related("dish")
        .order_by("created_at", "id")
    )
    parts = [meal_item_display(item) for item in items]
    return "、".join(parts) if parts else "已清空"


def meal_plan_change_summary(meal_plan):
    meal_type_label = meal_plan.get_meal_type_display()
    items_summary = meal_plan_items_summary(meal_plan)
    return f"{meal_plan.date.isoformat()} {meal_type_label}：{items_summary}"


def daily_meal_sections(family, selected_date):
    plans = get_or_create_daily_plans(family, selected_date)
    sections = []
    for meal_type in MAIN_MEAL_TYPES:
        plan = plans[meal_type]
        items = []
        for item in plan.items.select_related("dish").order_by("created_at", "id"):
            items.append(
                {
                    "name": item.dish.name,
                    "quantity": item.quantity,
                    "note": item.note,
                    "spice_level_label": item.spice_level_label,
                    "warm_label": item.warm_label,
                    "ice_level_label": item.ice_level_label,
                    "display": meal_item_display(item),
                }
            )
        sections.append(
            {
                "meal_type": meal_type,
                "label": plan.get_meal_type_display(),
                "items": items,
                "summary": "、".join(item["display"] for item in items) if items else "未安排",
            }
        )
    return sections


def daily_meal_change_summary(family, selected_date):
    parts = [
        f"{section['label']}：{section['summary']}"
        for section in daily_meal_sections(family, selected_date)
    ]
    return f"{selected_date.isoformat()} 排餐：{'；'.join(parts)}"


def prune_family_notifications(family):
    stale_ids = list(
        FamilyNotification.objects.filter(family=family)
        .order_by("-created_at", "-id")
        .values_list("id", flat=True)[FamilyNotification.MAX_PER_FAMILY:]
    )
    if stale_ids:
        FamilyNotification.objects.filter(id__in=stale_ids).delete()


def build_absolute_site_url(path, request=None):
    if settings.PUBLIC_SITE_URL:
        return f"{settings.PUBLIC_SITE_URL}{path}"
    if request:
        return request.build_absolute_uri(path)
    return path


def meal_sections_text(meal_sections):
    lines = []
    for section in meal_sections or []:
        lines.append(f"{section['label']}：")
        if section["items"]:
            for item in section["items"]:
                lines.append(f"- {item['display']}")
        else:
            lines.append("- 未安排")
    return "\n".join(lines)


def meal_sections_html(meal_sections):
    blocks = []
    palette = [
        ("#fff8e7", "#f2d89c", "#7b510f"),
        ("#f4fbef", "#cfe7bd", "#486c32"),
        ("#fff2f4", "#f4c7cf", "#8c3f4c"),
    ]
    for section in meal_sections or []:
        if section["items"]:
            items_html = "".join(
                "<tr>"
                "<td style='padding:9px 16px;border-top:1px solid rgba(220,215,206,0.72);'>"
                f"<span style='display:inline-block;width:8px;height:8px;border-radius:999px;background:{palette[index % len(palette)][2]};margin-right:8px;vertical-align:middle;'></span>"
                f"<span style='font-size:15px;line-height:1.55;color:#211d19;vertical-align:middle;'>{escape(item['display'])}</span>"
                "</td>"
                "</tr>"
                for index, item in enumerate(section["items"])
            )
        else:
            items_html = (
                "<tr><td style='padding:9px 16px;border-top:1px solid rgba(220,215,206,0.72);"
                "font-size:15px;line-height:1.55;color:#8b8176;'>今天这里还空着，可以继续补一道家常菜。</td></tr>"
            )
        bg, border, ink = palette[len(blocks) % len(palette)]
        blocks.append(
            f"<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='margin:14px 0;border:1px solid {border};border-radius:14px;background:{bg};overflow:hidden;'>"
            "<tr>"
            "<td style='padding:14px 16px 6px;'>"
            f"<span style='display:inline-block;padding:5px 10px;border-radius:999px;background:#fffefa;border:1px solid {border};color:{ink};font-size:15px;font-weight:800;'>{escape(section['label'])}</span>"
            f"<span style='display:inline-block;margin-left:8px;color:#8b8176;font-size:12px;'>{len(section['items'])} 道</span>"
            "</td>"
            "</tr>"
            f"{items_html}"
            "</table>"
        )
    return "".join(blocks)


def send_notification_email(notification, detail_url="", meal_sections=None):
    recipient = notification.recipient
    if not recipient or not recipient.email:
        return False

    actor_name = notification.actor.username if notification.actor else "一位家人"
    meal_label = notification.meal_type_label
    target_date = notification.meal_plan_date.isoformat()
    target = f"{target_date} {meal_label}".strip()
    detail_line = f"\n查看详情：{detail_url}" if detail_url else ""
    meal_detail = (
        f"\n\n本次排餐详情：\n{meal_sections_text(meal_sections)}"
        if meal_sections
        else ""
    )
    sent_at = timezone.localtime(notification.created_at).strftime("%Y-%m-%d %H:%M")
    html_detail_link = (
        "<table role='presentation' cellspacing='0' cellpadding='0' style='margin:22px 0 0;'>"
        "<tr><td style='border-radius:12px;background:#ffd166;box-shadow:0 8px 18px rgba(122,83,20,0.18);'>"
        f"<a href='{escape(detail_url)}' style='display:inline-block;padding:13px 18px;border-radius:12px;color:#4a3100;text-decoration:none;font-size:16px;font-weight:800;'>查看这天排餐</a>"
        "</td></tr></table>"
        if detail_url
        else ""
    )
    html_message = (
        "<div style='margin:0;padding:0;background:#f7f5f1;'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f7f5f1;padding:18px 10px;'>"
        "<tr><td align='center'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='max-width:640px;border:1px solid #dcd7ce;border-radius:18px;background:#fffefa;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;color:#211d19;'>"
        "<tr><td style='padding:22px 22px 18px;background:#fff7dc;border-bottom:1px solid #ecd8a9;'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0'><tr>"
        "<td style='vertical-align:top;'>"
        "<div style='display:inline-block;padding:5px 10px;border-radius:999px;background:#fffefa;border:1px solid #ecd8a9;color:#6f5121;font-size:13px;font-weight:800;'>法米狗私厨给的通知</div>"
        f"<div style='margin-top:14px;font-size:28px;line-height:1.18;font-weight:900;color:#211d19;letter-spacing:0;'>{escape(actor_name)} 提醒你</div>"
        f"<div style='margin-top:8px;font-size:18px;line-height:1.35;font-weight:800;color:#7b510f;'>关注 {escape(target_date)} 的排餐</div>"
        "</td>"
        "<td width='76' align='right' style='vertical-align:top;'>"
        "<div style='width:58px;height:58px;border-radius:18px;background:#fffefa;border:1px solid #ecd8a9;text-align:center;line-height:58px;font-size:26px;font-weight:900;color:#d49a21;'>饭</div>"
        "</td>"
        "</tr></table>"
        "</td></tr>"
        "<tr><td style='padding:18px 22px 8px;'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='border:1px solid #e8dcc4;border-radius:14px;background:#fffdf7;'>"
        "<tr>"
        f"<td style='padding:12px 14px;font-size:14px;line-height:1.7;color:#4b443d;'><strong>家庭</strong><br>{escape(notification.family.name)}</td>"
        f"<td style='padding:12px 14px;font-size:14px;line-height:1.7;color:#4b443d;'><strong>发送人</strong><br>{escape(actor_name)}</td>"
        "</tr><tr>"
        f"<td style='padding:12px 14px;border-top:1px solid #eee4d2;font-size:14px;line-height:1.7;color:#4b443d;'><strong>被提醒人</strong><br>{escape(recipient.username)}</td>"
        f"<td style='padding:12px 14px;border-top:1px solid #eee4d2;font-size:14px;line-height:1.7;color:#4b443d;'><strong>发送时间</strong><br>{escape(sent_at)}</td>"
        "</tr>"
        "</table>"
        f"{meal_sections_html(meal_sections)}"
        f"{html_detail_link}"
        "</td></tr>"
        "<tr><td style='padding:0 22px 22px;color:#8b8176;font-size:12px;line-height:1.6;'>"
        "如果按钮打不开，可以复制这封邮件中的链接到浏览器访问。"
        "</td></tr>"
        "</table>"
        "</td></tr></table>"
        "</div>"
    )
    try:
        sent_count = send_mail(
            subject=f"法米狗私厨给的通知：{actor_name} 提醒你关注 {target} 的排餐",
            message=(
                f"{recipient.username}，\n\n"
                f"{actor_name} 在 {sent_at} "
                f"更改了 {notification.family.name} 的 {target} 排餐需求。\n\n"
                f"{notification.change_summary}"
                f"{meal_detail}"
                f"{detail_line}\n"
            ),
            from_email=None,
            recipient_list=[recipient.email],
            fail_silently=settings.EMAIL_FAIL_SILENTLY,
            html_message=html_message,
        )
    except Exception:
        logger.exception(
            "Failed to send meal notification email to user_id=%s notification_id=%s",
            recipient.id,
            notification.id,
        )
        return False

    if not sent_count:
        logger.warning(
            "Meal notification email was not sent to user_id=%s notification_id=%s",
            recipient.id,
            notification.id,
        )
        return False
    return True


def send_family_message_email(notification, detail_url=""):
    recipient = notification.recipient
    if not recipient or not recipient.email:
        return False

    actor_name = notification.actor.username if notification.actor else "一位家人"
    sent_at = timezone.localtime(notification.created_at).strftime("%Y-%m-%d %H:%M")
    detail_line = f"\n查看留言：{detail_url}" if detail_url else ""
    html_detail_link = (
        "<table role='presentation' cellspacing='0' cellpadding='0' style='margin:22px 0 0;'>"
        "<tr><td style='border-radius:12px;background:#ffd166;box-shadow:0 8px 18px rgba(122,83,20,0.18);'>"
        f"<a href='{escape(detail_url)}' style='display:inline-block;padding:13px 18px;border-radius:12px;color:#4a3100;text-decoration:none;font-size:16px;font-weight:800;'>查看并回复留言</a>"
        "</td></tr></table>"
        if detail_url
        else ""
    )
    html_message = (
        "<div style='margin:0;padding:0;background:#f7f5f1;'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='background:#f7f5f1;padding:18px 10px;'>"
        "<tr><td align='center'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='max-width:640px;border:1px solid #dcd7ce;border-radius:18px;background:#fffefa;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;color:#211d19;'>"
        "<tr><td style='padding:22px;background:#fff7dc;border-bottom:1px solid #ecd8a9;'>"
        "<div style='display:inline-block;padding:5px 10px;border-radius:999px;background:#fffefa;border:1px solid #ecd8a9;color:#6f5121;font-size:13px;font-weight:800;'>法米狗私厨给的通知</div>"
        f"<div style='margin-top:14px;font-size:28px;line-height:1.18;font-weight:900;color:#211d19;'>{escape(actor_name)} 给你留言</div>"
        f"<div style='margin-top:8px;font-size:14px;color:#8b8176;'>发送时间：{escape(sent_at)}</div>"
        "</td></tr>"
        "<tr><td style='padding:18px 22px 8px;'>"
        f"<div style='padding:14px 16px;border:1px solid #e8dcc4;border-radius:14px;background:#fffdf7;color:#4b443d;font-size:16px;line-height:1.7;'>{escape(notification.message_body)}</div>"
        f"{html_detail_link}"
        "</td></tr>"
        "<tr><td style='padding:0 22px 22px;color:#8b8176;font-size:12px;line-height:1.6;'>"
        "如果按钮打不开，可以复制这封邮件中的链接到浏览器访问。"
        "</td></tr>"
        "</table>"
        "</td></tr></table>"
        "</div>"
    )
    try:
        sent_count = send_mail(
            subject=f"法米狗私厨给的通知：{actor_name} 给你留了一条家庭消息",
            message=(
                f"{recipient.username}，\n\n"
                f"{actor_name} 在 {sent_at} 给你留了一条消息：\n\n"
                f"{notification.message_body}"
                f"{detail_line}\n"
            ),
            from_email=None,
            recipient_list=[recipient.email],
            fail_silently=settings.EMAIL_FAIL_SILENTLY,
            html_message=html_message,
        )
    except Exception:
        logger.exception(
            "Failed to send family message email to user_id=%s notification_id=%s",
            recipient.id,
            notification.id,
        )
        return False

    if not sent_count:
        logger.warning(
            "Family message email was not sent to user_id=%s notification_id=%s",
            recipient.id,
            notification.id,
        )
        return False
    return True


def create_family_history(
    *,
    family,
    actor,
    meal_plan_date,
    meal_type="",
    change_summary="",
):
    notification = FamilyNotification.objects.create(
        family=family,
        actor=actor,
        recipient=None,
        meal_plan_date=meal_plan_date,
        meal_type=meal_type,
        change_summary=change_summary[:255],
    )
    prune_family_notifications(family)
    return notification


def create_family_notifications(
    *,
    family,
    actor,
    recipient_ids,
    meal_plan_date,
    meal_type="",
    change_summary="",
    request=None,
    meal_sections=None,
):
    normalized_ids = []
    for recipient_id in recipient_ids:
        try:
            normalized_ids.append(int(recipient_id))
        except (TypeError, ValueError):
            continue
    normalized_ids = sorted(set(normalized_ids))
    if not normalized_ids:
        return 0

    memberships = (
        FamilyMember.objects.filter(family=family, user_id__in=normalized_ids)
        .exclude(user=actor)
        .select_related("user")
        .order_by("joined_at")
    )
    recipients = [membership.user for membership in memberships]
    if not recipients:
        return 0

    detail_path = f"{reverse('meals:meal_plan')}?date={meal_plan_date.isoformat()}"
    detail_url = build_absolute_site_url(detail_path, request)
    notifications = []
    with transaction.atomic():
        for recipient in recipients:
            notifications.append(
                FamilyNotification.objects.create(
                    family=family,
                    actor=actor,
                    recipient=recipient,
                    meal_plan_date=meal_plan_date,
                    meal_type=meal_type,
                    change_summary=change_summary[:255],
                )
            )
        prune_family_notifications(family)

    transaction.on_commit(
        lambda: [
            send_notification_email(notification, detail_url, meal_sections)
            for notification in notifications
        ]
    )
    return len(notifications)


def create_family_message_notifications(
    *,
    family,
    actor,
    recipient_ids,
    message_body,
    request=None,
    thread_id=None,
):
    normalized_ids = []
    for recipient_id in recipient_ids:
        try:
            normalized_ids.append(int(recipient_id))
        except (TypeError, ValueError):
            continue
    normalized_ids = sorted(set(normalized_ids))
    if not normalized_ids:
        return 0, thread_id

    memberships = (
        FamilyMember.objects.filter(family=family, user_id__in=normalized_ids)
        .exclude(user=actor)
        .select_related("user")
        .order_by("joined_at")
    )
    recipients = [membership.user for membership in memberships]
    if not recipients:
        return 0, thread_id

    thread_id = thread_id or uuid4()
    message_body = message_body.strip()
    summary = message_body[:255]
    notifications = []
    with transaction.atomic():
        for recipient in recipients:
            notifications.append(
                FamilyNotification.objects.create(
                    family=family,
                    actor=actor,
                    recipient=recipient,
                    meal_plan_date=timezone.localdate(),
                    change_summary=summary,
                    kind=FamilyNotification.KIND_MESSAGE,
                    message_body=message_body,
                    message_thread_id=thread_id,
                )
            )
        prune_family_notifications(family)

    detail_path = reverse("meals:notification_thread", args=[thread_id])
    detail_url = build_absolute_site_url(detail_path, request)
    transaction.on_commit(
        lambda: [
            send_family_message_email(notification, detail_url)
            for notification in notifications
        ]
    )
    return len(notifications), thread_id
