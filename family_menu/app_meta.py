from django.utils import timezone


APP_VERSION = "v1.6"
APP_STARTED_AT = timezone.now()

ACTIVE_LOGO_CANDIDATES = [
    "images/logo-candidates/v14-02.svg",
    "images/logo-candidates/v14-03.svg",
    "images/logo-candidates/v14-04.svg",
    "images/logo-candidates/v14-06.svg",
    "images/logo-candidates/v14-08.svg",
    "images/logo-candidates/v14-09.svg",
    "images/logo-candidates/v14-10.svg",
]


def current_logo_path(now=None):
    if not ACTIVE_LOGO_CANDIDATES:
        return "images/famigo-candidates/logo-05.svg"
    current = now or timezone.now()
    elapsed_days = max((current - APP_STARTED_AT).days, 0)
    index = (elapsed_days // 7) % len(ACTIVE_LOGO_CANDIDATES)
    return ACTIVE_LOGO_CANDIDATES[index]
