import pandas as pd

from app import BUILD_MARKER, GLOBAL_CSS, styled_table


def test_build_marker_for_table_fix():
    assert BUILD_MARKER == "Build: Icon-Fix-v8"


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
