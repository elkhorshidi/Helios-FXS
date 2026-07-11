import inspect

import pandas as pd
import pytest

from app import (
    BUILD_MARKER,
    GLOBAL_CSS,
    best_cost_chart_data,
    daily_input_page,
    latest_history_versions,
    render_decision_table_html,
    render_html_table,
    route_cost_chart_data,
    technical_notes_table,
)


def test_build_marker_for_table_fix():
    assert BUILD_MARKER == "Build: History-Charts-v17"


def test_render_html_table_escapes_values_and_uses_direction_classes():
    df = pd.DataFrame({"فارسی": ["<b>دلار تهران</b>"], "Code": ["USD_Tehran"]})
    html = render_html_table(df, rtl_columns=["فارسی"], ltr_columns=["Code"])

    assert "&lt;b&gt;دلار تهران&lt;/b&gt;" in html
    assert 'class="fa-cell"' in html
    assert 'class="ltr-cell"' in html
    assert "<th>0</th>" not in html
    assert "USD_Tehran" in html


def test_material_symbols_are_excluded_from_vazirmatn_override():
    assert '[data-testid="stExpander"] span[data-testid="stIconMaterial"]' in GLOBAL_CSS
    assert 'font-family: "Material Symbols Rounded", "Material Icons" !important' in GLOBAL_CSS
    assert ':not(.material-symbols-rounded)' in GLOBAL_CSS


def test_origin_table_css_uses_static_html_table_rules():
    assert ".html-table-wrap" in GLOBAL_CSS
    assert ".html-table .ltr-cell" in GLOBAL_CSS
    assert "unicode-bidi: isolate" in GLOBAL_CSS
    assert ".stDataFrame, [data-testid=\"stDataFrame\"]" not in GLOBAL_CSS


def test_decision_table_html_uses_rtl_and_numeric_alignment():
    df = pd.DataFrame(
        [
            {
                "منشأ ارز": "دلار تهران",
                "بهترین مسیر": "اظهارنامه بدون ارز",
                "هزینه نهایی": "0.70%",
                "هزینه دلاری": "$7,000",
                "گزینه دوم": "اظهارنامه با ارز از مسیر دوبی",
                "هزینه گزینه دوم": "1.20%",
                "اختلاف با گزینه بعدی": "0.50%",
                "صرفه‌جویی دلاری": "$5,000",
            }
        ]
    )
    html = render_decision_table_html(df)

    assert 'class="html-table-wrap"' in html
    assert 'class="fa-cell"' in html
    assert 'class="ltr-cell"' in html
    assert html.index("منشأ ارز") < html.index("بهترین مسیر") < html.index("هزینه نهایی")
    assert ".html-table .ltr-cell" in GLOBAL_CSS


def test_editable_rates_editor_is_scoped_and_ordered_for_rtl():
    source = inspect.getsource(daily_input_page)

    assert 'st.container(key="rates_editor_rtl")' in source
    order_literal = 'column_order=["Notes", "Sell", "Buy", "Market", "Date"]'
    assert order_literal in source
    assert ".st-key-rates_editor_rtl [data-testid=\"stDataEditor\"]" in GLOBAL_CSS


def test_history_chart_data_uses_latest_version_and_separate_origins():
    history = pd.DataFrame(
        [
            {
                "report_date": "1405/04/17",
                "version": 1,
                "Origin Currency Persian": "دلار تهران",
                "Best Cost %": 0.01,
                "Best Route": "قدیمی",
            },
            {
                "report_date": "1405/04/17",
                "version": 2,
                "Origin Currency Persian": "دلار تهران",
                "Best Cost %": 0.007,
                "Best Route": "اظهارنامه بدون ارز",
            },
            {
                "report_date": "1405/04/17",
                "version": 1,
                "Origin Currency Persian": "دلار تتر",
                "Best Cost %": 0.009,
                "Best Route": "اظهارنامه بدون ارز",
            },
        ]
    )

    latest = latest_history_versions(history)
    chart = best_cost_chart_data(history)

    assert len(latest) == 2
    assert set(chart["منشأ ارز"]) == {"دلار تهران", "دلار تتر"}
    assert chart.loc[chart["منشأ ارز"] == "دلار تهران", "هزینه نهایی"].iloc[0] == pytest.approx(0.7)
    assert chart.loc[chart["منشأ ارز"] == "دلار تهران", "بهترین مسیر"].iloc[0] == "اظهارنامه بدون ارز"


def test_route_chart_data_hides_inactive_routes_and_formats_percentages():
    history = pd.DataFrame(
        [
            {
                "report_date": "1405/04/17",
                "version": 1,
                "Origin Currency Persian": "دلار تهران",
                "No-FX Cost %": 0.007,
                "Dubai Route Cost %": 0.012,
                "Istanbul Direct Cost %": None,
            }
        ]
    )

    chart = route_cost_chart_data(history, "دلار تهران")

    assert set(chart["مسیر"]) == {"اظهارنامه بدون ارز", "مسیر دوبی"}
    assert "مسیر مستقیم استانبول" not in set(chart["مسیر"])
    assert set(chart["هزینه متنی"]) == {"0.70%", "1.20%"}
    assert chart["هزینه"].tolist() == pytest.approx([0.7, 1.2])


def test_technical_notes_table_keeps_full_market_names():
    rates = pd.DataFrame(
        [
            {"Market": "Tether", "Notes": "Paste/overwrite this block daily"},
            {"Market": "Dubai", "Notes": "AED origin; USD Dubai conversion uses Dubai spread"},
        ]
    )
    notes = technical_notes_table(rates)
    html = render_html_table(notes, ltr_columns=["بازار"], note_columns=["توضیحات"])

    assert "Tether" in html
    assert "Dubai" in html
    assert "Sulaymaniyah" in html
    assert "Paste/overwrite this block daily" in html
    assert "AED origin; USD Dubai conversion uses Dubai spread" in html
    assert "USD_Tehran" not in html
