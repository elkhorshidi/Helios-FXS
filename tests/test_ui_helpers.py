import inspect

import pandas as pd

from app import BUILD_MARKER, GLOBAL_CSS, daily_input_page, render_decision_table_html, styled_table


def test_build_marker_for_table_fix():
    assert BUILD_MARKER == "Build: Editable-Rates-RTL-v12"


def test_styled_table_uses_vazirmatn_and_alignment():
    df = pd.DataFrame({"منشأ ارز": ["دلار تهران"], "هزینه نهایی": ["0.70%"]})
    html = styled_table(df, right_columns=["منشأ ارز"], center_columns=["هزینه نهایی"]).to_html()

    assert "Vazirmatn" in html
    assert "text-align: right" in html
    assert "text-align: center" in html


def test_material_symbols_are_excluded_from_vazirmatn_override():
    assert '[data-testid="stExpander"] span[data-testid="stIconMaterial"]' in GLOBAL_CSS
    assert 'font-family: "Material Symbols Rounded", "Material Icons" !important' in GLOBAL_CSS
    assert ':not(.material-symbols-rounded)' in GLOBAL_CSS


def test_origin_table_css_uses_static_html_table_rules():
    assert ".origin-table-wrap" in GLOBAL_CSS
    assert ".origin-table .ltr-cell" in GLOBAL_CSS
    assert "unicode-bidi: isolate" in GLOBAL_CSS


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

    assert 'class="decision-table-wrap"' in html
    assert 'class="fa-cell"' in html
    assert 'class="num-cell"' in html
    assert html.index("منشأ ارز") < html.index("بهترین مسیر") < html.index("هزینه نهایی")
    assert ".decision-table .num-cell" in GLOBAL_CSS


def test_editable_rates_editor_is_scoped_and_ordered_for_rtl():
    source = inspect.getsource(daily_input_page)

    assert 'st.container(key="rates_editor_rtl")' in source
    assert 'column_order=("Sell", "Buy", "Market", "Date", "Notes")' in source
    assert ".st-key-rates_editor_rtl [data-testid=\"stDataEditor\"]" in GLOBAL_CSS
