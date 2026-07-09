from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd

from calculation_engine import RouteResult


def format_percent(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{value * 100:.2f}%"


def format_usd(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{value:,.0f}"


def conversion_phrase(route: RouteResult, origin_label: str) -> str:
    if route.route_id == "ISTANBUL_DIRECT":
        return "این مسیر شامل تبدیل ارز و هزینه انتقال با کارمزد ثابت تأمین‌کننده است."

    destination = "دلار تهران" if route.route_id == "NO_FX_DECLARATION" else "دلار دوبی"
    conversion = route.conversion_cost or 0.0
    abs_pct = format_percent(abs(conversion))

    if conversion > 0:
        return f"{abs_pct} بابت تبدیل {origin_label} به {destination} هزینه می‌دهد"
    if conversion < 0:
        return f"{abs_pct} بابت تبدیل {origin_label} به {destination} سر می‌گیرد"
    return f"{format_percent(0)} بابت تبدیل {origin_label} به {destination} هزینه می‌دهد"


def fee_phrase(route: RouteResult) -> str:
    if route.route_id == "NO_FX_DECLARATION":
        return f"{format_percent(route.fee)} هزینه کارمزد اظهارنامه بدون ارز پرداخت می‌کند"
    if route.route_id == "DUBAI_FX_DECLARATION":
        return f"{format_percent(route.fee)} هزینه انتقال / ورود ارز از مسیر دوبی پرداخت می‌کند"
    return f"{format_percent(route.fee)} کارمزد ثابت تأمین‌کننده پرداخت می‌کند"


def selected_route_breakdown(route: RouteResult, origin_label: str) -> str:
    if route.route_id == "ISTANBUL_DIRECT":
        return f"مشتری {fee_phrase(route)}؛ بنابراین هزینه نهایی {format_percent(route.total_cost)} می‌شود."

    return (
        f"مشتری {fee_phrase(route)} و {conversion_phrase(route, origin_label)}؛ "
        f"بنابراین هزینه نهایی {format_percent(route.total_cost)} می‌شود."
    )


def next_option_line(route: RouteResult, origin_label: str) -> str:
    details = conversion_phrase(route, origin_label)
    if route.route_id != "ISTANBUL_DIRECT":
        details = f"شامل {details} و {fee_phrase(route)}."
    return (
        f"- {route.route_label}: هزینه تمام‌شده {format_percent(route.total_cost)} "
        f"معادل حدود {format_usd(route.cost_usd)} دلار. {details}"
    )


def generate_recommendation(row: pd.Series | dict) -> str:
    origin_label = row["Origin Currency Persian"]
    ranked: Iterable[RouteResult] = row["Ranked Routes"]
    ranked = list(ranked)

    if not ranked:
        return (
            f"برای منشأ ارز {origin_label} داده کافی برای محاسبه مسیر وجود ندارد.\n\n"
            "ریت‌های موردنیاز بازارها کامل یا معتبر نیستند؛ بنابراین مسیرهای متاثر به عنوان «ریت موجود نیست» "
            "از رتبه‌بندی امروز کنار گذاشته شده‌اند."
        )

    best = ranked[0]
    next_routes = ranked[1:]

    parts = [
        f"بهترین مسیر امروز برای رفع تعهد با منشأ ارز {origin_label}، «{best.route_label}» است.",
        "",
        f"هزینه تمام‌شده این مسیر {format_percent(best.total_cost)} معادل حدود {format_usd(best.cost_usd)} دلار است.",
        "",
        "جزئیات مسیر پیشنهادی:",
        selected_route_breakdown(best, origin_label),
    ]

    if next_routes:
        parts.extend(["", "گزینه‌های بعدی به ترتیب هزینه:"])
        parts.extend(next_option_line(route, origin_label) for route in next_routes)
        second = next_routes[0]
        saving_pct = (second.total_cost or 0) - (best.total_cost or 0)
        saving_usd = (second.cost_usd or 0) - (best.cost_usd or 0)
        parts.extend(
            [
                "",
                f"اختلاف بهترین مسیر با نزدیک‌ترین گزینه بعدی {format_percent(saving_pct)} "
                f"معادل حدود {format_usd(saving_usd)} دلار است.",
            ]
        )
    else:
        parts.extend(["", "در حال حاضر گزینه دوم قابل مقایسه‌ای برای این منشأ ارز وجود ندارد."])

    return "\n".join(parts)


def attach_recommendations(decisions: pd.DataFrame) -> pd.DataFrame:
    enriched = decisions.copy()
    enriched["Recommendation Text"] = enriched.apply(generate_recommendation, axis=1)
    return enriched


def daily_report_text(decisions: pd.DataFrame) -> str:
    return "\n\n--------------------\n\n".join(decisions["Recommendation Text"].tolist())
