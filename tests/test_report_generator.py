from calculation_engine import FeeSettings, calculate_daily_decisions, default_rates
from report_generator import attach_recommendations, generate_recommendation


def test_negative_conversion_uses_benefit_language():
    df = attach_recommendations(calculate_daily_decisions(default_rates(), FeeSettings(), 1_000_000))
    row = df.loc[df["Origin Currency Code"] == "USD_Istanbul"].iloc[0]
    assert "سر می‌گیرد" in row["Recommendation Text"]


def test_inactive_routes_are_not_listed_in_narrative():
    df = attach_recommendations(calculate_daily_decisions(default_rates(), FeeSettings(), 1_000_000))
    row = df.loc[df["Origin Currency Code"] == "USD_Tehran"].iloc[0]
    assert "اظهارنامه با ارز مستقیم استانبول" not in row["Recommendation Text"]


def test_single_route_available_message():
    df = attach_recommendations(
        calculate_daily_decisions(
            default_rates(),
            FeeSettings(),
            1_000_000,
            active_route_overrides={"DUBAI_FX_DECLARATION": False, "ISTANBUL_DIRECT": False},
        )
    )
    row = df.loc[df["Origin Currency Code"] == "USD_Tehran"].iloc[0]
    text = generate_recommendation(row)
    assert "گزینه دوم قابل مقایسه‌ای" in text
