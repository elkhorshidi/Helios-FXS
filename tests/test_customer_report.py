from calculation_engine import FeeSettings, calculate_daily_decisions, default_rates
from customer_report import (
    FONT_BOLD,
    FONT_MEDIUM,
    FONT_REGULAR,
    FONT_SEMIBOLD,
    NO_DATA_MESSAGE,
    build_customer_report_data,
    generate_customer_report_pdf,
    generate_customer_report_png,
    render_customer_report_card,
)
from report_generator import attach_recommendations


def test_customer_report_builds_for_every_origin_and_exports():
    decisions = attach_recommendations(calculate_daily_decisions(default_rates(), FeeSettings(), 1_000_000))

    for _, row in decisions.iterrows():
        report = build_customer_report_data(row, "1405/04/17", 1_000_000)
        html = render_customer_report_card(report)
        assert report.origin_label
        assert report.has_enough_data is True
        assert html.startswith('<div class="customer-wrap">')
        assert "\n    <div" not in html
        assert "customer-metrics" in html
        assert "customer-secondary" in html
        assert "customer-ltr" in html
        assert "جمع‌بندی کوتاه" in html
        assert "یادداشت تغییرپذیری ریت‌ها" in html
        assert "Route ID" not in html
        assert generate_customer_report_png(report).startswith(b"\x89PNG")
        assert generate_customer_report_pdf(report).startswith(b"%PDF")


def test_bundled_vazirmatn_fonts_are_available():
    for font_path in [FONT_REGULAR, FONT_MEDIUM, FONT_SEMIBOLD, FONT_BOLD]:
        assert font_path.exists()
        assert font_path.stat().st_size > 100_000


def test_customer_report_missing_data_is_client_facing():
    rates = default_rates()
    rates["Buy"] = None
    decisions = attach_recommendations(
        calculate_daily_decisions(
            rates,
            FeeSettings(),
            1_000_000,
            active_route_overrides={"ISTANBUL_DIRECT": False},
        )
    )

    row = decisions.loc[decisions["Origin Currency Code"] == "USD_Tehran"].iloc[0]
    report = build_customer_report_data(row, "1405/04/17", 1_000_000)
    html = render_customer_report_card(report)

    assert report.has_enough_data is False
    assert NO_DATA_MESSAGE in html
    assert "Origin Currency Code" not in html
    assert "Best Route ID" not in html
