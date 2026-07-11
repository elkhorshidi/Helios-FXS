import inspect

import pandas as pd

from app import (
    BUILD_MARKER,
    GLOBAL_CSS,
    daily_input_page,
    render_decision_table_html,
    render_html_table,
    technical_notes_table,
)


def test_build_marker_for_table_fix():
    assert BUILD_MARKER == "Build: Tables-Audit-v15"


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
    order_literal = 'column_order=["Notes", "Date", "Market", "Buy", "Sell"]'
    assert order_literal in source
    assert ".st-key-rates_editor_rtl [data-testid=\"stDataEditor\"]" in GLOBAL_CSS


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
