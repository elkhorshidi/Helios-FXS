import math

import pandas as pd

from calculation_engine import (
    FeeSettings,
    calculate_daily_decisions,
    calculate_routes_for_origin,
    default_rates,
    normalize_rates,
)
from report_generator import attach_recommendations


def decisions():
    return attach_recommendations(calculate_daily_decisions(default_rates(), FeeSettings(), 1_000_000))


def row_for(origin_code):
    df = decisions()
    return df.loc[df["Origin Currency Code"] == origin_code].iloc[0]


def assert_close(actual, expected):
    assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)


def test_usd_tehran_matches_excel_reference():
    row = row_for("USD_Tehran")
    assert row["Best Route"] == "اظهارنامه بدون ارز"
    assert_close(row["Best Cost %"], 0.007)
    assert_close(row["Dubai Route Cost %"], 0.012650273224043721)


def test_usd_istanbul_matches_excel_reference_and_direct_active():
    row = row_for("USD_Istanbul")
    assert row["Best Route"] == "اظهارنامه بدون ارز"
    assert_close(row["Best Cost %"], 0.005096274136524309)
    assert_close(row["Dubai Route Cost %"], 0.007991569214033212)
    assert_close(row["Istanbul Direct Cost %"], 0.015)


def test_usd_sulaymaniyah_negative_conversion_benefit():
    row = row_for("USD_Sulaymaniyah")
    assert row["Best Route"] == "اظهارنامه بدون ارز"
    assert_close(row["Best Cost %"], 0.0026592512208355908)
    no_fx = next(route for route in row["Routes"] if route.route_id == "NO_FX_DECLARATION")
    assert no_fx.conversion_cost < 0


def test_usd_tether_matches_excel_reference():
    row = row_for("USD_Tether")
    assert row["Best Route"] == "اظهارنامه بدون ارز"
    assert_close(row["Best Cost %"], 0.007)
    assert_close(row["Dubai Route Cost %"], 0.00990463215258862)


def test_aed_dubai_conversion_to_dubai_is_not_zero():
    row = row_for("AED_Dubai")
    assert row["Best Route"] == "اظهارنامه بدون ارز"
    assert_close(row["Best Cost %"], 0.009732240437158412)
    dubai = next(route for route in row["Routes"] if route.route_id == "DUBAI_FX_DECLARATION")
    assert_close(dubai.conversion_cost, 0.0049046321525886205)


def test_positive_conversion_cost():
    rates = normalize_rates(default_rates())
    routes = calculate_routes_for_origin("USD_Tehran", rates, FeeSettings(), 1_000_000)
    dubai = next(route for route in routes if route.route_id == "DUBAI_FX_DECLARATION")
    assert dubai.conversion_cost > 0


def test_inactive_istanbul_route_for_non_istanbul_origins():
    row = row_for("USD_Tehran")
    assert pd.isna(row["Istanbul Direct Cost %"])
    route = next(route for route in row["Routes"] if route.route_id == "ISTANBUL_DIRECT")
    assert route.active is False


def test_missing_required_rate_marks_affected_routes_inactive():
    rates = default_rates()
    rates = rates[rates["Market"] != "Dubai"]
    df = attach_recommendations(calculate_daily_decisions(rates, FeeSettings(), 1_000_000))

    tehran = df.loc[df["Origin Currency Code"] == "USD_Tehran"].iloc[0]
    assert tehran["Best Route"] == "اظهارنامه بدون ارز"
    assert pd.isna(tehran["Dubai Route Cost %"])
    assert tehran["Dubai Route Status"] == "ریت موجود نیست"

    aed = df.loc[df["Origin Currency Code"] == "AED_Dubai"].iloc[0]
    assert aed["Best Route"] == "اظهارنامه بدون ارز"
    assert pd.isna(aed["Dubai Route Cost %"])
    assert aed["Dubai Route Status"] == "ریت موجود نیست"


def test_invalid_rate_is_not_interpreted_as_zero():
    rates = default_rates()
    rates.loc[rates["Market"] == "Tehran", "Buy"] = 0
    df = attach_recommendations(calculate_daily_decisions(rates, FeeSettings(), 1_000_000))

    row = df.loc[df["Origin Currency Code"] == "USD_Istanbul"].iloc[0]
    assert row["Best Route"] == "اظهارنامه با ارز از مسیر دوبی"
    assert pd.isna(row["No-FX Cost %"])
    assert row["No-FX Status"] == "ریت موجود نیست"


def test_no_calculable_route_sets_insufficient_data():
    rates = default_rates()
    rates["Buy"] = None
    df = attach_recommendations(
        calculate_daily_decisions(
            rates,
            FeeSettings(),
            1_000_000,
            active_route_overrides={"ISTANBUL_DIRECT": False},
        )
    )

    row = df.loc[df["Origin Currency Code"] == "USD_Tehran"].iloc[0]
    assert row["Best Route"] == "داده کافی نیست"
    assert pd.isna(row["Best Cost %"])
    assert "ریت‌های موردنیاز" in row["Recommendation Text"]
