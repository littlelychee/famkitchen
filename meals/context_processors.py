from .utils import get_current_family, get_user_profile


def is_mobile_browser(request):
    user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
    mobile_markers = [
        "iphone",
        "ipod",
        "android mobile",
        "windows phone",
        "blackberry",
        "iemobile",
        "opera mini",
        "mobile",
    ]
    return any(marker in user_agent for marker in mobile_markers)


def current_family(request):
    context = {"is_mobile_device": is_mobile_browser(request)}
    if not request.user.is_authenticated:
        context["current_family"] = None
        context["current_family_memberships"] = []
        context["current_user_profile"] = None
        return context
    context["current_family"] = get_current_family(request)
    context["current_family_memberships"] = (
        request.user.family_memberships.select_related("family").order_by("joined_at")
    )
    context["current_user_profile"] = get_user_profile(request.user)
    return context
