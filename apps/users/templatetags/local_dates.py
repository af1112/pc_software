from datetime import date, datetime
from functools import lru_cache

from django import template
from django.template.defaultfilters import date as django_date
from django.utils import timezone
from django.utils.translation import get_language

register = template.Library()

PERSIAN_MONTHS = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]


def _gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666
        + (365 * gy)
        + ((gy2 + 3) // 4)
        - ((gy2 + 99) // 100)
        + ((gy2 + 399) // 400)
        + gd
        + g_d_m[gm - 1]
    )
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)

    return jy, jm, jd


@lru_cache(maxsize=8192)
def _format_jalali_cached(year, month, day, hour, minute, second, has_time, fmt):
    jy, jm, jd = _gregorian_to_jalali(year, month, day)

    replacements = {
        "Y": f"{jy:04d}",
        "y": f"{jy % 100:02d}",
        "m": f"{jm:02d}",
        "n": str(jm),
        "d": f"{jd:02d}",
        "j": str(jd),
        "F": PERSIAN_MONTHS[jm - 1],
        "M": PERSIAN_MONTHS[jm - 1],
    }

    if has_time:
        replacements.update(
            {
                "H": f"{hour:02d}",
                "i": f"{minute:02d}",
                "s": f"{second:02d}",
            }
        )

    out = []
    escape = False
    for ch in fmt:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        out.append(replacements.get(ch, ch))

    return "".join(out)


def _format_jalali(value, fmt):
    if isinstance(value, str):
        raw = value.strip()
        for parser in (datetime.fromisoformat,):
            try:
                value = parser(raw)
                break
            except Exception:
                continue
        if isinstance(value, str):
            for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    value = datetime.strptime(raw, pattern)
                    break
                except Exception:
                    continue

    if isinstance(value, datetime):
        dt = timezone.localtime(value) if timezone.is_aware(value) else value
        d = dt.date()
    elif isinstance(value, date):
        dt = None
        d = value
    else:
        return ""

    hour = dt.hour if dt is not None else 0
    minute = dt.minute if dt is not None else 0
    second = dt.second if dt is not None else 0
    return _format_jalali_cached(d.year, d.month, d.day, hour, minute, second, dt is not None, fmt)


@register.simple_tag(takes_context=True)
def localized_date(context, value, fmt="Y/m/d"):
    if isinstance(value, datetime) and timezone.is_aware(value):
        value = timezone.localtime(value)
    request = context.get("request")
    lang = str(getattr(request, "LANGUAGE_CODE", "") or get_language() or "").lower()
    if lang.startswith("fa"):
        return _format_jalali(value, fmt)
    return django_date(value, fmt)
