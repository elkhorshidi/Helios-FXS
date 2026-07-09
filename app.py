from __future__ import annotations

import base64
from html import escape
from io import BytesIO
from pathlib import Path
import re

import pandas as pd
import streamlit as st

from calculation_engine import (
    FeeSettings,
    compare_to_excel_reference,
    calculate_daily_decisions,
    decision_table_for_display,
    default_rates,
)
from customer_report import (
    build_customer_report_data,
    generate_customer_report_pdf,
    generate_customer_report_png,
    render_customer_report_card,
)
from report_generator import attach_recommendations, daily_report_text, format_percent, format_usd
from storage import existing_versions, load_history, save_daily_report
from validation import coerce_rates, parse_pasted_rates, validate_rates


BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "assets" / "fonts"


def font_face_css() -> str:
    weights = {
        400: "Vazirmatn-Regular.ttf",
        500: "Vazirmatn-Medium.ttf",
        600: "Vazirmatn-SemiBold.ttf",
        700: "Vazirmatn-Bold.ttf",
    }
    declarations = []
    for weight, filename in weights.items():
        font_bytes = (FONT_DIR / filename).read_bytes()
        encoded = base64.b64encode(font_bytes).decode("ascii")
        declarations.append(
            f"""
            @font-face {{
                font-family: 'Vazirmatn';
                src: url(data:font/ttf;base64,{encoded}) format('truetype');
                font-weight: {weight};
                font-style: normal;
                font-display: swap;
            }}
            """
        )
    return "\n".join(declarations)


st.set_page_config(page_title="داشبورد تصمیم رفع تعهد ارزی", page_icon="FX", layout="wide")

GLOBAL_CSS = """
    <style>
    __FONT_FACE_CSS__
    html, body, [class*="css"], .stApp {
        direction: rtl;
        text-align: right;
        font-family: "Vazirmatn", sans-serif !important;
    }
    body,
    p, li, label, input, textarea, select, option,
    h1, h2, h3, h4, h5, h6,
    button:not(.material-symbols-rounded):not(.material-symbols-outlined):not(.material-icons):not([data-testid="stIconMaterial"]),
    [data-testid="stAppViewContainer"],
    [data-testid="stSidebar"],
    [data-testid="stWidgetLabel"],
    [data-testid="stMarkdownContainer"],
    [data-testid="stCaptionContainer"],
    [data-testid="stAlert"],
    [data-testid="stExpander"],
    [data-testid="stMetric"],
    [data-testid="stDataFrame"],
    [data-testid="stDataEditor"],
    [data-testid="stTable"],
    [data-baseweb="select"] {
        font-family: "Vazirmatn", sans-serif !important;
    }
    .block-container {padding-top: 1.5rem; max-width: 1220px;}
    [data-testid="stAppViewContainer"],
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] *:not(.material-symbols-rounded):not(.material-symbols-outlined):not(.material-icons):not([data-testid="stIconMaterial"]),
    button:not(.material-symbols-rounded):not(.material-symbols-outlined):not(.material-icons):not([data-testid="stIconMaterial"]),
    input,
    textarea,
    select,
    option,
    [role="button"],
    [role="listbox"],
    [role="option"],
    [data-baseweb="select"],
    [data-testid="stDownloadButton"] {
        font-family: "Vazirmatn", sans-serif !important;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp p, .stApp li, .stApp label,
    .stApp span:not(.material-symbols-rounded):not(.material-symbols-outlined):not(.material-icons):not([data-testid="stIconMaterial"]),
    .stApp div:not(.material-symbols-rounded):not(.material-symbols-outlined):not(.material-icons):not([data-testid="stIconMaterial"]) {
        text-align: right;
        font-family: "Vazirmatn", sans-serif !important;
    }
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] *:not(.material-symbols-rounded):not(.material-symbols-outlined):not(.material-icons):not([data-testid="stIconMaterial"]) {
        direction: rtl;
        text-align: right;
    }
    [data-testid="stSidebar"] [role="radiogroup"],
    [data-testid="stSidebar"] [role="radiogroup"] label {
        align-items: flex-end;
        justify-content: flex-start;
    }
    [data-testid="stWidgetLabel"],
    [data-testid="stMarkdownContainer"],
    [data-testid="stCaptionContainer"],
    [data-testid="stAlert"],
    [data-testid="stExpander"],
    [data-testid="stExpander"] summary,
    [data-testid="stForm"],
    [data-testid="stRadio"],
    [data-testid="stCheckbox"],
    [data-testid="stMultiSelect"],
    [data-testid="stTextInput"],
    [data-testid="stNumberInput"] {
        direction: rtl;
        text-align: right;
    }
    [data-testid="stAlert"] *:not(.material-symbols-rounded):not(.material-symbols-outlined):not(.material-icons):not([data-testid="stIconMaterial"]),
    [data-testid="stExpander"] *:not(.material-symbols-rounded):not(.material-symbols-outlined):not(.material-icons):not([data-testid="stIconMaterial"]),
    [data-testid="stWidgetLabel"] *:not(.material-symbols-rounded):not(.material-symbols-outlined):not(.material-icons):not([data-testid="stIconMaterial"]) {
        direction: rtl;
        text-align: right;
    }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 0.85rem 0.95rem;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        direction: rtl;
        text-align: right;
    }
    [data-testid="stMetricLabel"] {font-size: 0.82rem; color: #475569;}
    [data-testid="stMetricValue"] {font-size: 1.25rem; color: #0f172a;}
    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"],
    [data-testid="stMetricDelta"] {
        direction: rtl;
        text-align: right;
    }
    .stButton, .stDownloadButton {
        direction: rtl;
        text-align: right;
    }
    .stButton > button, .stDownloadButton > button {
        border-radius: 8px;
        direction: rtl;
        text-align: center;
        justify-content: center;
    }
    input, textarea, [contenteditable="true"] {
        direction: rtl;
        text-align: right;
    }
    textarea {
        direction: ltr;
        text-align: left;
        unicode-bidi: plaintext;
    }
    .stDataFrame, .stDataEditor, [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
        direction: rtl;
        text-align: right;
    }
    [data-testid="stDataFrame"] *,
    [data-testid="stDataEditor"] * {
        font-family: "Vazirmatn", sans-serif !important;
        line-height: 1.6;
    }
    [data-testid="stDataFrame"] [role="columnheader"],
    [data-testid="stDataEditor"] [role="columnheader"] {
        text-align: center !important;
        font-weight: 600 !important;
        color: #0f172a !important;
        white-space: normal !important;
        line-height: 1.6 !important;
    }
    [data-testid="stDataFrame"] [role="gridcell"],
    [data-testid="stDataEditor"] [role="gridcell"] {
        line-height: 1.6 !important;
        min-height: 38px !important;
        white-space: normal !important;
    }
    [data-testid="stVegaLiteChart"],
    [data-testid="stPlotlyChart"],
    [data-testid="stVegaLiteChart"] *,
    [data-testid="stPlotlyChart"] *,
    canvas, svg {
        direction: ltr;
        text-align: left;
    }
    .rtl-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 0.9rem 1rem;
        background: #ffffff;
        margin-bottom: 0.75rem;
        direction: rtl;
        text-align: right;
    }
    .rtl-card-title {font-weight: 700; color: #0f172a; margin-bottom: 0.45rem;}
    .rtl-muted {color: #64748b; font-size: 0.9rem;}
    .rtl-narrative {
        direction: rtl;
        text-align: right;
        line-height: 2;
        white-space: pre-wrap;
    }
    .customer-wrap {
        width: 100%;
        max-width: 760px;
        margin: 0 auto;
        direction: rtl;
        text-align: right;
        font-family: "Vazirmatn", sans-serif !important;
    }
    .customer-card,
    .customer-card * {
        box-sizing: border-box;
        min-width: 0;
        overflow-wrap: anywhere;
        word-break: normal;
        white-space: normal;
        font-family: "Vazirmatn", sans-serif !important;
    }
    .customer-card {
        width: 100%;
        height: auto;
        background: #ffffff;
        border: 1px solid #dbe3ef;
        border-radius: 12px;
        padding: 28px 32px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.07);
        direction: rtl;
        text-align: right;
        color: #0f172a;
    }
    .customer-topline {
        border-bottom: 1px solid #e5e7eb;
        padding-bottom: 16px;
        margin-bottom: 18px;
    }
    .customer-topline h2 {
        margin: 0 0 8px 0;
        font-size: clamp(1.35rem, 2.4vw, 1.75rem);
        line-height: 1.45;
        font-weight: 800;
        color: #0f172a;
    }
    .customer-topline p,
    .customer-footer,
    .customer-label,
    .customer-card-label,
    .customer-saving-label {
        color: #64748b;
        margin: 0;
        font-size: 0.9rem;
        line-height: 1.7;
    }
    .customer-meta,
    .customer-metrics,
    .customer-secondary {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin: 14px 0;
        align-items: stretch;
    }
    .customer-info-card,
    .customer-metric-card {
        height: auto;
        min-height: 96px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 14px 16px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .customer-info-card strong,
    .customer-metric-card strong {
        display: block;
        color: #0f172a;
        font-size: clamp(1.05rem, 2vw, 1.25rem);
        line-height: 1.55;
        font-weight: 800;
        margin-top: 4px;
    }
    .customer-highlight {
        width: 100%;
        height: auto;
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        border-radius: 12px;
        padding: 18px 20px;
        margin: 18px 0 14px;
    }
    .customer-label {
        color: #047857;
        margin-bottom: 8px;
    }
    .customer-route {
        color: #064e3b;
        font-size: clamp(1.45rem, 3vw, 2rem);
        line-height: 1.55;
        font-weight: 900;
    }
    .customer-saving {
        width: 100%;
        height: auto;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 12px;
        padding: 16px 18px;
        margin: 16px 0;
    }
    .customer-saving strong {
        display: block;
        color: #1e3a8a;
        font-size: clamp(1.18rem, 2.5vw, 1.45rem);
        line-height: 1.65;
        font-weight: 900;
        margin-top: 4px;
    }
    .customer-ltr {
        direction: ltr;
        unicode-bidi: isolate;
        display: inline-block;
        text-align: left;
    }
    .customer-conclusion {
        line-height: 1.9;
        color: #334155;
        font-size: 1rem;
        margin: 18px 0 0;
        padding-top: 2px;
    }
    .customer-empty {
        background: #fff7ed;
        border: 1px solid #fed7aa;
        border-radius: 12px;
        padding: 20px;
        color: #9a3412;
        line-height: 1.9;
        margin: 18px 0;
    }
    .customer-footer {
        border-top: 1px solid #e5e7eb;
        padding-top: 14px;
        margin-top: 18px;
        font-size: 0.86rem;
        line-height: 1.85;
    }
    @media (max-width: 760px) {
        .customer-meta,
        .customer-metrics,
        .customer-secondary {
            grid-template-columns: 1fr;
        }
        .customer-card {
            padding: 22px;
        }
    }
    .origin-table-wrap {
        width: 100%;
        direction: rtl;
        overflow-x: visible;
    }
    .decision-table-wrap {
        width: 100%;
        direction: rtl;
        overflow-x: visible;
    }
    .decision-table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        font-family: "Vazirmatn", sans-serif !important;
        color: #0f172a;
        background: #ffffff;
        border: 1px solid #e5e7eb;
        direction: rtl;
    }
    .decision-table th {
        text-align: center;
        font-weight: 600;
        background: #f8fafc;
        color: #0f172a;
        border: 1px solid #e5e7eb;
        padding: 12px 10px;
        line-height: 1.7;
        vertical-align: middle;
        white-space: normal;
    }
    .decision-table td {
        padding: 12px 10px;
        border: 1px solid #e5e7eb;
        vertical-align: middle;
        line-height: 1.7;
        overflow: visible;
        text-overflow: clip;
    }
    .decision-table tbody tr:nth-child(even) {
        background: #f9fafb;
    }
    .decision-table .fa-cell {
        text-align: right;
        direction: rtl;
        white-space: normal;
        overflow-wrap: anywhere;
    }
    .decision-table .num-cell {
        text-align: center;
        direction: ltr;
        unicode-bidi: isolate;
        white-space: normal;
        overflow-wrap: anywhere;
    }
    @media (max-width: 900px) {
        .decision-table {
            table-layout: auto;
        }
        .decision-table th,
        .decision-table td {
            padding: 10px 8px;
            font-size: 0.88rem;
        }
    }
    .origin-table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        font-family: "Vazirmatn", sans-serif !important;
        color: #0f172a;
        background: #ffffff;
        border: 1px solid #e5e7eb;
    }
    .origin-table th {
        text-align: center;
        font-weight: 600;
        background: #f8fafc;
        color: #0f172a;
        border: 1px solid #e5e7eb;
        padding: 12px 16px;
        line-height: 1.7;
        white-space: normal;
    }
    .origin-table td {
        padding: 12px 16px;
        border: 1px solid #e5e7eb;
        vertical-align: middle;
        line-height: 1.7;
        overflow: visible;
        text-overflow: clip;
    }
    .origin-table tbody tr:nth-child(even) {
        background: #f9fafb;
    }
    .origin-table .fa-cell {
        text-align: right;
        direction: rtl;
        white-space: normal;
        overflow-wrap: anywhere;
    }
    .origin-table .ltr-cell {
        text-align: center;
        direction: ltr;
        unicode-bidi: isolate;
        white-space: nowrap;
        overflow-wrap: normal;
    }
    @media (max-width: 640px) {
        .origin-table {
            table-layout: auto;
        }
        .origin-table th,
        .origin-table td {
            padding: 10px 8px;
            font-size: 0.9rem;
        }
    }
    code, pre, .ltr, .ltr * {
        direction: ltr;
        text-align: left;
        unicode-bidi: isolate;
    }
    span.material-symbols-rounded,
    span.material-symbols-outlined,
    span.material-icons,
    span.material-icons-outlined,
    span.material-icons-round,
    span.material-icons-sharp,
    span.material-icons-two-tone,
    [data-testid="stIconMaterial"],
    [data-testid="stExpander"] span[data-testid="stIconMaterial"],
    [data-testid="stExpander"] .material-symbols-rounded,
    [data-testid="stExpander"] .material-symbols-outlined,
    [data-testid="stSelectbox"] .material-symbols-rounded,
    [data-testid="stSelectbox"] .material-symbols-outlined,
    [data-testid="stMultiSelect"] .material-symbols-rounded,
    [data-testid="stMultiSelect"] .material-symbols-outlined,
    [data-testid="stSidebar"] .material-symbols-rounded,
    [data-testid="stSidebar"] .material-symbols-outlined,
    button .material-symbols-rounded,
    button .material-symbols-outlined,
    .material-symbols-rounded,
    .material-symbols-outlined,
    .material-icons,
    .material-icons-outlined,
    .material-icons-round,
    .material-icons-sharp,
    .material-icons-two-tone {
        font-family: "Material Symbols Rounded", "Material Icons" !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 20px !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        display: inline-block !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        direction: ltr !important;
        text-align: center !important;
        -webkit-font-feature-settings: "liga" !important;
        font-feature-settings: "liga" !important;
        -webkit-font-smoothing: antialiased !important;
    }
    </style>
    """

st.markdown(
    GLOBAL_CSS.replace("__FONT_FACE_CSS__", font_face_css()),
    unsafe_allow_html=True,
)


DATE_PATTERN = re.compile(r"^\d{4}/\d{2}/\d{2}$")
BUILD_MARKER = "Build: Decision-Table-RTL-v11"

RATE_COLUMN_LABELS = {
    "Date": "تاریخ",
    "Market": "بازار",
    "Buy": "خرید",
    "Sell": "فروش",
    "Notes": "توضیحات",
}

ORIGIN_MARKET_FA = {
    "USD_Tehran": "Tehran",
    "USD_Istanbul": "Istanbul",
    "USD_Sulaymaniyah": "Sulaymaniyah",
    "USD_Tether": "Tether",
    "AED_Dubai": "Dubai",
}


def init_state() -> None:
    if "rates_df" not in st.session_state:
        st.session_state.rates_df = default_rates()
    if "report_date" not in st.session_state:
        st.session_state.report_date = str(st.session_state.rates_df["Date"].iloc[0])
    if "sample_amount_usd" not in st.session_state:
        st.session_state.sample_amount_usd = 1_000_000.0
    if "fees" not in st.session_state:
        st.session_state.fees = FeeSettings()
    if "pending_rates_df" not in st.session_state:
        st.session_state.pending_rates_df = None
    if "pending_rate_date" not in st.session_state:
        st.session_state.pending_rate_date = None
    if "history_success_message" not in st.session_state:
        st.session_state.history_success_message = ""


def current_decisions() -> tuple[pd.DataFrame, list[str]]:
    rates = coerce_rates(st.session_state.rates_df)
    errors = validate_rates(rates)
    decisions = calculate_daily_decisions(rates, st.session_state.fees, st.session_state.sample_amount_usd)
    decisions = attach_recommendations(decisions)
    return decisions, errors


def format_table(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()
    route_status_map = {
        "No-FX Cost %": "No-FX Status",
        "Dubai Route Cost %": "Dubai Route Status",
        "Istanbul Direct Cost %": "Istanbul Direct Status",
    }
    for column in [c for c in display.columns if c.endswith("%")]:
        if column in route_status_map and route_status_map[column] in display.columns:
            status_column = route_status_map[column]
            display[column] = [
                str(status) if pd.isna(value) else format_percent(value)
                for value, status in zip(display[column], display[status_column])
            ]
        else:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else format_percent(value))
    for column in [c for c in display.columns if c.endswith("USD")]:
        display[column] = display[column].map(lambda value: f"${format_usd(value)}" if pd.notna(value) else "")
    return display


def dash_if_missing(value: object) -> str:
    if value is None or pd.isna(value) or value == "":
        return "—"
    return str(value)


def format_percent_display(value: object, unavailable_label: str = "—") -> str:
    if value is None or pd.isna(value):
        return unavailable_label
    return format_percent(float(value))


def ltr_value(value: object) -> str:
    return f"\u2066{value}\u2069"


def format_usd_display(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    return ltr_value(f"${format_usd(float(value))}")


def user_decision_table(decisions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in decisions.iterrows():
        rows.append(
            {
                "منشأ ارز": row["Origin Currency Persian"],
                "بهترین مسیر": row["Best Route"] if row["Best Route"] else "داده کافی نیست",
                "هزینه نهایی": format_percent_display(row["Best Cost %"]),
                "هزینه دلاری": format_usd_display(row["Best Cost USD"]),
                "گزینه دوم": dash_if_missing(row["Second Best Route"]),
                "هزینه گزینه دوم": format_percent_display(row["Second Best Cost %"]),
                "اختلاف با گزینه بعدی": format_percent_display(row["Saving vs Next %"]),
                "صرفه‌جویی دلاری": format_usd_display(row["Saving vs Next USD"]),
            }
        )
    return pd.DataFrame(rows)


DECISION_TEXT_COLUMNS = ["منشأ ارز", "بهترین مسیر", "گزینه دوم"]
DECISION_NUMERIC_COLUMNS = ["هزینه نهایی", "هزینه دلاری", "هزینه گزینه دوم", "اختلاف با گزینه بعدی", "صرفه‌جویی دلاری"]


def render_decision_table_html(decision_display: pd.DataFrame) -> str:
    headers = "".join(f"<th>{escape(str(column))}</th>" for column in decision_display.columns)
    body_rows = []
    for _, row in decision_display.iterrows():
        cells = []
        for column in decision_display.columns:
            class_name = "fa-cell" if column in DECISION_TEXT_COLUMNS else "num-cell"
            cells.append(f'<td class="{class_name}">{escape(str(row[column]))}</td>')
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<div class="decision-table-wrap">'
        '<table class="decision-table">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        "</div>"
    )


def user_history_table(history: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in history.iterrows():
        rows.append(
            {
                "تاریخ گزارش": row["report_date"],
                "نسخه": row["version"],
                "منشأ ارز": row["Origin Currency Persian"],
                "بهترین مسیر": row["Best Route"],
                "هزینه نهایی": format_percent_display(row["Best Cost %"]),
                "هزینه دلاری": format_usd_display(row["Best Cost USD"]),
                "گزینه دوم": dash_if_missing(row["Second Best Route"]),
                "صرفه‌جویی دلاری": format_usd_display(row["Saving vs Next USD"]),
            }
        )
    return pd.DataFrame(rows)


def route_status(row: pd.Series, route_id: str) -> str:
    route = next((item for item in row["Routes"] if item.route_id == route_id), None)
    if route is None:
        return "—"
    if route.active:
        return format_percent_display(route.total_cost)
    return route.inactive_reason or "غیرفعال"


def detect_single_paste_date(parsed: pd.DataFrame) -> tuple[str | None, str | None]:
    if parsed.empty or "Date" not in parsed:
        return None, "تاریخ در جدول نرخ‌ها پیدا نشد."
    dates = [str(value).strip() for value in parsed["Date"].dropna().tolist() if str(value).strip()]
    unique_dates = sorted(set(dates))
    if not unique_dates:
        return None, "تاریخ در جدول نرخ‌ها پیدا نشد."
    invalid = [date for date in unique_dates if not DATE_PATTERN.match(date)]
    if invalid:
        return None, f"فرمت تاریخ معتبر نیست: {', '.join(invalid)}"
    if len(unique_dates) > 1:
        return None, "تاریخ‌های جدول نرخ‌ها یکسان نیستند. لطفا فقط نرخ‌های یک روز را وارد کنید."
    return unique_dates[0], None


def apply_rates(parsed: pd.DataFrame, rate_date: str) -> None:
    st.session_state.rates_df = parsed
    st.session_state.report_date = rate_date
    st.session_state.pending_rates_df = None
    st.session_state.pending_rate_date = None


def markdown_narrative(text: str, best_route: str, best_cost: object, saving: object) -> str:
    safe = text
    if best_route:
        safe = safe.replace(f"«{best_route}»", f"**«{best_route}»**", 1)
    if best_cost is not None and not pd.isna(best_cost):
        safe = safe.replace(format_percent(best_cost), f"**{format_percent(best_cost)}**", 1)
    if saving is not None and not pd.isna(saving):
        safe = safe.replace(format_percent(saving), f"**{format_percent(saving)}**", 1)
    return safe


def dataframe_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def dataframe_excel_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def styled_table(
    df: pd.DataFrame,
    right_columns: list[str] | None = None,
    center_columns: list[str] | None = None,
):
    right_columns = right_columns or []
    center_columns = center_columns or []
    styles = [
        {
            "selector": "table",
            "props": [
                ("font-family", '"Vazirmatn", sans-serif'),
                ("width", "100%"),
                ("border-collapse", "collapse"),
                ("direction", "rtl"),
            ],
        },
        {
            "selector": "th",
            "props": [
                ("font-family", '"Vazirmatn", sans-serif'),
                ("font-weight", "600"),
                ("text-align", "center"),
                ("vertical-align", "middle"),
                ("background-color", "#f8fafc"),
                ("color", "#0f172a"),
                ("border", "1px solid #e2e8f0"),
                ("padding", "10px 12px"),
                ("line-height", "1.6"),
                ("white-space", "normal"),
            ],
        },
        {
            "selector": "td",
            "props": [
                ("font-family", '"Vazirmatn", sans-serif'),
                ("font-weight", "400"),
                ("vertical-align", "middle"),
                ("border", "1px solid #e2e8f0"),
                ("padding", "10px 12px"),
                ("line-height", "1.6"),
                ("white-space", "normal"),
                ("overflow-wrap", "anywhere"),
            ],
        },
    ]
    styler = df.style.hide(axis="index").set_table_styles(styles)
    if right_columns:
        styler = styler.set_properties(
            subset=right_columns,
            **{"text-align": "right", "direction": "rtl"},
        )
    if center_columns:
        styler = styler.set_properties(
            subset=center_columns,
            **{"text-align": "center", "direction": "ltr"},
        )
    return styler


def daily_input_page() -> None:
    st.title("ورود روزانه")
    st.caption("همه نرخ‌ها بر پایه AED وارد می‌شوند. درصدها در فرم به شکل کاربرپسند نمایش داده می‌شوند.")

    top = st.columns([1, 1, 1, 1])
    with top[0]:
        st.session_state.report_date = st.text_input("تاریخ گزارش", value=st.session_state.report_date)
    with top[1]:
        st.session_state.sample_amount_usd = st.number_input(
            "مبلغ نمونه USD",
            min_value=1.0,
            value=float(st.session_state.sample_amount_usd),
            step=10_000.0,
            format="%.0f",
            help="مبلغ مبنا برای تبدیل درصد هزینه مسیرها به دلار.",
        )
    with top[2]:
        no_fx_pct = st.number_input("کارمزد اظهارنامه بدون ارز (%)", value=st.session_state.fees.no_fx_declaration_fee * 100, step=0.05, format="%.3f")
    with top[3]:
        dubai_pct = st.number_input("کارمزد مسیر دوبی (%)", value=st.session_state.fees.dubai_transfer_fee * 100, step=0.05, format="%.3f")
    istanbul_pct = st.number_input("کارمزد مستقیم استانبول (%)", value=st.session_state.fees.istanbul_direct_fee * 100, step=0.05, format="%.3f")
    st.session_state.fees = FeeSettings(no_fx_pct / 100, dubai_pct / 100, istanbul_pct / 100)

    st.subheader("ورود سریع نرخ‌ها")
    pasted = st.text_area(
        "ورود سریع نرخ‌ها",
        placeholder="Date        Market          Buy     Sell\n1405/04/18  Tether          3.670   3.677",
        height=140,
        label_visibility="collapsed",
    )
    if st.button("اعمال جدول نرخ‌ها", type="primary"):
        parsed = parse_pasted_rates(pasted)
        if parsed.empty:
            st.warning("متنی برای تبدیل به جدول نرخ پیدا نشد.")
        else:
            rate_date, date_error = detect_single_paste_date(parsed)
            if date_error:
                st.error(date_error)
            elif rate_date != st.session_state.report_date:
                st.session_state.pending_rates_df = parsed
                st.session_state.pending_rate_date = rate_date
                st.warning(
                    f"تاریخ جدول نرخ‌ها {rate_date} است اما تاریخ گزارش فعلی {st.session_state.report_date} است. "
                    "برای جلوگیری از ترکیب دو تاریخ، اعمال جدول را تایید کنید."
                )
            else:
                apply_rates(parsed, rate_date)
                st.success(f"۵ بازار با موفقیت ثبت شدند. تاریخ گزارش: {rate_date}")

    if st.session_state.pending_rates_df is not None and st.session_state.pending_rate_date:
        if st.button("تایید تغییر تاریخ و اعمال نرخ‌ها"):
            apply_rates(st.session_state.pending_rates_df, st.session_state.pending_rate_date)
            st.success(f"۵ بازار با موفقیت ثبت شدند. تاریخ گزارش: {st.session_state.report_date}")

    st.subheader("جدول قابل ویرایش نرخ‌ها")
    editable = st.session_state.rates_df.copy()
    editable["Date"] = st.session_state.report_date
    st.session_state.rates_df = st.data_editor(
        editable,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_order=("Date", "Market", "Buy", "Sell"),
        column_config={
            "Date": st.column_config.TextColumn("تاریخ"),
            "Market": st.column_config.TextColumn("بازار", help="نام بازار باید یکی از Tether, Tehran, Istanbul, Sulaymaniyah, Dubai باشد."),
            "Buy": st.column_config.NumberColumn("خرید", min_value=0.0, step=0.001, format="%.3f"),
            "Sell": st.column_config.NumberColumn("فروش", min_value=0.0, step=0.001, format="%.3f"),
            "Notes": st.column_config.TextColumn("توضیحات", help="توضیحات اختیاری؛ در محاسبات استفاده نمی‌شود."),
        },
    )

    with st.expander("یادداشت‌های فنی نرخ‌ها"):
        notes = st.session_state.rates_df[["Market", "Notes"]].copy()
        notes = notes.rename(columns={"Market": "بازار", "Notes": "توضیحات"})
        st.dataframe(
            styled_table(notes, right_columns=["بازار", "توضیحات"]),
            width="stretch",
            hide_index=True,
        )

    errors = validate_rates(coerce_rates(st.session_state.rates_df))
    if errors:
        for error in errors:
            st.error(error)
    else:
        st.success("۵ بازار با موفقیت ثبت شدند.")


def decision_report_page() -> None:
    st.title("گزارش تصمیم روزانه")
    decisions, errors = current_decisions()
    if errors:
        st.warning("برخی نرخ‌ها ناقص یا نامعتبر هستند. مسیرهای متاثر با وضعیت «ریت موجود نیست» از رتبه‌بندی حذف شده‌اند.")
        for error in errors:
            st.write(f"- {error}")

    table = decision_table_for_display(decisions)
    calculable = table.dropna(subset=["Best Cost %"])
    min_best = calculable["Best Cost %"].min() if not calculable.empty else None
    max_best = calculable["Best Cost %"].max() if not calculable.empty else None
    cheapest_origin = calculable.loc[calculable["Best Cost %"].idxmin(), "Origin Currency Persian"] if not calculable.empty else "داده کافی نیست"
    best_routes = calculable["Best Route"] if not calculable.empty else pd.Series(dtype=str)
    route_mode = best_routes.mode().iloc[0] if not best_routes.empty else "داده کافی نیست"
    largest_saving = table["Saving vs Next %"].dropna().max()

    metrics = st.columns(5)
    metrics[0].metric("کمترین هزینه امروز", format_percent_display(min_best))
    metrics[1].metric("بیشترین هزینه مسیر منتخب", format_percent_display(max_best))
    metrics[2].metric("کم‌هزینه‌ترین منشأ ارز", cheapest_origin)
    metrics[3].metric("پرتکرارترین مسیر منتخب", route_mode)
    metrics[4].metric("بیشترین صرفه‌جویی نسبت به گزینه بعدی", format_percent_display(largest_saving))

    st.subheader("جدول تصمیم")
    decision_display = user_decision_table(decisions)
    st.markdown(render_decision_table_html(decision_display), unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.download_button("دانلود جدول CSV", dataframe_csv_bytes(table), "daily_decision_table.csv", "text/csv")
    col2.download_button("دانلود گزارش Excel", dataframe_excel_bytes(table, "Daily Decision"), "daily_decision_report.xlsx")
    col3.download_button("دانلود متن فارسی", daily_report_text(decisions).encode("utf-8-sig"), "persian_daily_report.txt")

    st.subheader("گزارش تفصیلی فارسی")
    for _, row in decisions.iterrows():
        next_route = dash_if_missing(row["Second Best Route"])
        saving = format_percent_display(row["Saving vs Next %"])
        with st.expander(f"{row['Origin Currency Persian']} | {row['Best Route']}", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("بهترین مسیر", row["Best Route"])
            c2.metric("هزینه نهایی", format_percent_display(row["Best Cost %"]))
            c3.metric("گزینه بعدی", next_route)
            c4.metric("صرفه‌جویی", saving)
            narrative = markdown_narrative(
                row["Recommendation Text"],
                row["Best Route"],
                row["Best Cost %"],
                row["Saving vs Next %"],
            )
            st.markdown(narrative.replace("\n", "  \n"))

    with st.expander("اعتبارسنجی با سناریوی نمونه Excel"):
        reference = compare_to_excel_reference(decisions)
        st.dataframe(styled_table(reference, center_columns=reference.columns.tolist()), width="stretch", hide_index=True)


def history_page() -> None:
    st.title("تاریخچه گزارش‌ها")
    decisions, errors = current_decisions()
    duplicate_versions = existing_versions(st.session_state.report_date)
    if st.session_state.history_success_message:
        st.success(st.session_state.history_success_message)
        st.session_state.history_success_message = ""

    calculable_count = int(decisions["Best Cost %"].notna().sum()) if not decisions.empty else 0
    insufficient_count = int(decisions["Best Cost %"].isna().sum()) if not decisions.empty else 0

    c1, c2 = st.columns([1.2, 2.8])
    with c1:
        st.markdown(
            f"""
            <div class="rtl-card">
                <div class="rtl-card-title">پیش‌نمایش ذخیره</div>
                <div>تاریخ گزارش: <strong>{st.session_state.report_date}</strong></div>
                <div>تعداد منشأهای محاسبه‌شده: <strong>{calculable_count}</strong></div>
                <div>تعداد منشأهای فاقد داده کافی: <strong>{insufficient_count}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        overwrite = st.checkbox("در صورت وجود گزارش همین تاریخ، نسخه قبلی جایگزین شود.", value=False, disabled=not duplicate_versions)
        if errors:
            st.warning("گزارش با مسیرهای ناقص قابل ذخیره است؛ مقادیر ناقص خالی یا غیرفعال ذخیره می‌شوند.")
        if st.button("ذخیره گزارش امروز", type="primary", disabled=decisions.empty):
            try:
                version = save_daily_report(
                    st.session_state.report_date,
                    coerce_rates(st.session_state.rates_df),
                    st.session_state.fees,
                    st.session_state.sample_amount_usd,
                    decisions,
                    overwrite=overwrite,
                )
                st.session_state.history_success_message = f"گزارش تاریخ {st.session_state.report_date} با نسخه {version} ذخیره شد."
                st.rerun()
            except ValueError:
                st.warning("برای این تاریخ قبلا گزارش ذخیره شده است. گزینه جایگزینی آخرین نسخه را فعال کنید یا تاریخ جدید وارد کنید.")
    with c2:
        if duplicate_versions:
            st.info(f"نسخه‌های موجود برای این تاریخ: {', '.join(map(str, duplicate_versions))}")

    history = load_history()
    if history.empty:
        st.info("هنوز گزارشی در تاریخچه ذخیره نشده است. پس از ذخیره گزارش امروز، سوابق و نمودارها در این بخش نمایش داده می‌شوند.")
        return

    filters = st.columns(3)
    with filters[0]:
        dates = sorted(history["report_date"].unique())
        selected_dates = st.multiselect("فیلتر تاریخ", dates, default=dates)
    with filters[1]:
        origins = sorted(history["Origin Currency Persian"].unique())
        selected_origins = st.multiselect("فیلتر منشأ ارز", origins, default=origins)
    with filters[2]:
        routes = sorted(history["Best Route"].dropna().unique())
        selected_routes = st.multiselect("فیلتر بهترین مسیر", routes, default=routes)

    filtered = history[
        history["report_date"].isin(selected_dates)
        & history["Origin Currency Persian"].isin(selected_origins)
        & history["Best Route"].isin(selected_routes)
    ].copy()

    st.subheader("جدول سوابق ذخیره‌شده")
    history_display = user_history_table(filtered)
    st.dataframe(
        styled_table(
            history_display,
            right_columns=["منشأ ارز", "بهترین مسیر", "گزینه دوم"],
            center_columns=["تاریخ گزارش", "نسخه", "هزینه نهایی", "هزینه دلاری", "صرفه‌جویی دلاری"],
        ),
        width="stretch",
        hide_index=True,
    )
    st.download_button("دانلود تاریخچه CSV", dataframe_csv_bytes(filtered), "fx_decision_history.csv", "text/csv")

    if not filtered.empty:
        chart_df = filtered.rename(columns={"report_date": "Date"}).set_index("Date")
        st.subheader("روند هزینه نهایی")
        st.line_chart(chart_df, y="Best Cost %", color="#2563eb")
        st.subheader("مقایسه هزینه مسیرها")
        st.line_chart(chart_df[["No-FX Cost %", "Dubai Route Cost %", "Istanbul Direct Cost %"]])

        summary_cols = st.columns(2)
        with summary_cols[0]:
            st.write("تعداد انتخاب هر مسیر به عنوان بهترین گزینه")
            freq = filtered["Best Route"].value_counts().reset_index(name="تعداد").rename(columns={"Best Route": "مسیر"})
            st.dataframe(styled_table(freq, right_columns=["مسیر"], center_columns=["تعداد"]), hide_index=True)
        with summary_cols[1]:
            st.write("میانگین Best Cost % بر اساس منشأ ارز")
            avg = filtered.groupby("Origin Currency Persian", as_index=False)["Best Cost %"].mean()
            avg = avg.rename(columns={"Origin Currency Persian": "منشأ ارز", "Best Cost %": "میانگین هزینه"})
            avg["میانگین هزینه"] = avg["میانگین هزینه"].map(format_percent_display)
            st.dataframe(styled_table(avg, right_columns=["منشأ ارز"], center_columns=["میانگین هزینه"]), hide_index=True)


def customer_report_page() -> None:
    st.title("گزارش مشتری")
    st.caption("یک کارت روزانه و مشتری‌پسند برای ارسال در واتساپ یا خروجی گرفتن به صورت تصویر و PDF.")

    decisions, errors = current_decisions()
    origin_options = decisions["Origin Currency Persian"].tolist()

    controls = st.columns([1, 1, 1])
    with controls[0]:
        selected_origin = st.selectbox("منشأ ارز", origin_options)
    with controls[1]:
        st.session_state.sample_amount_usd = st.number_input(
            "مبلغ مبنا",
            min_value=1.0,
            value=float(st.session_state.sample_amount_usd),
            step=10_000.0,
            format="%.0f",
        )
    with controls[2]:
        st.session_state.report_date = st.text_input("تاریخ گزارش", value=st.session_state.report_date)

    decisions, errors = current_decisions()
    selected_row = decisions.loc[decisions["Origin Currency Persian"] == selected_origin].iloc[0]
    report_data = build_customer_report_data(selected_row, st.session_state.report_date, st.session_state.sample_amount_usd)

    if errors:
        st.warning("برخی ریت‌ها ناقص یا نامعتبر هستند. گزارش مشتری فقط در صورت وجود داده کافی برای منشأ انتخاب‌شده قابل خروجی گرفتن است.")

    report_html = render_customer_report_card(report_data)
    st.markdown(report_html, unsafe_allow_html=True)

    export_cols = st.columns([1, 1, 2])
    png_bytes = generate_customer_report_png(report_data) if report_data.has_enough_data else None
    pdf_bytes = generate_customer_report_pdf(report_data) if report_data.has_enough_data else None
    export_cols[0].download_button(
        "دانلود تصویر گزارش",
        data=png_bytes or b"",
        file_name="customer_fx_report.png",
        mime="image/png",
        disabled=not report_data.has_enough_data,
    )
    export_cols[1].download_button(
        "دانلود PDF گزارش",
        data=pdf_bytes or b"",
        file_name="customer_fx_report.pdf",
        mime="application/pdf",
        disabled=not report_data.has_enough_data,
    )


def settings_page() -> None:
    st.title("راهنما و فرمول‌ها")

    with st.expander("۱. نقش فایل Excel", expanded=True):
        st.markdown(
            """
            فایل Excel نمونه تأییدشده منطق کسب‌وکار و معیار اعتبارسنجی نسخه اول است. اپلیکیشن در زمان اجرا به Excel وابسته نیست و فرمول‌های تاییدشده مستقیم در Python پیاده‌سازی شده‌اند.
            """
        )

    with st.expander("۲. تعریف منشأ ارزها"):
        origin_rows = [
            {"بازار": "Tehran", "عنوان فارسی": "دلار تهران", "کد داخلی": "USD_Tehran"},
            {"بازار": "Istanbul", "عنوان فارسی": "دلار استانبول", "کد داخلی": "USD_Istanbul"},
            {"بازار": "Sulaymaniyah", "عنوان فارسی": "دلار سلیمانیه", "کد داخلی": "USD_Sulaymaniyah"},
            {"بازار": "Tether", "عنوان فارسی": "دلار تتر", "کد داخلی": "USD_Tether"},
            {"بازار": "Dubai", "عنوان فارسی": "درهم دوبی", "کد داخلی": "AED_Dubai"},
        ]
        origin_body = "".join(
            f'<tr><td class="ltr-cell">{row["بازار"]}</td><td class="fa-cell">{row["عنوان فارسی"]}</td><td class="ltr-cell">{row["کد داخلی"]}</td></tr>'
            for row in origin_rows
        )
        origin_table_html = (
            '<div class="origin-table-wrap">'
            '<table class="origin-table">'
            "<thead><tr><th>بازار</th><th>عنوان فارسی</th><th>کد داخلی</th></tr></thead>"
            f"<tbody>{origin_body}</tbody>"
            "</table>"
            "</div>"
        )
        st.markdown(origin_table_html, unsafe_allow_html=True)

    with st.expander("۳. فرمول اظهارنامه بدون ارز"):
        st.markdown("هزینه کل برابر هزینه تبدیل منشأ ارز به دلار تهران به اضافه کارمزد اظهارنامه بدون ارز است.")
        st.code("(Tehran Sell - Origin Buy) / Origin Buy", language="text")
        st.markdown("برای منشأ AED_Dubai، تبدیل به دلار تهران با اسپرد بازار تهران محاسبه می‌شود.")
        st.code("(Tehran Sell - Tehran Buy) / Tehran Buy", language="text")

    with st.expander("۴. فرمول مسیر دوبی"):
        st.markdown("هزینه کل برابر هزینه تبدیل منشأ ارز به دلار دوبی به اضافه کارمزد انتقال / ورود دوبی است.")
        st.code("(Dubai Sell - Origin Buy) / Origin Buy", language="text")
        st.markdown("برای AED_Dubai، هزینه تبدیل صفر نیست و با اسپرد دوبی محاسبه می‌شود.")
        st.code("(Dubai Sell - Dubai Buy) / Dubai Buy", language="text")

    with st.expander("۵. مسیر مستقیم استانبول"):
        st.markdown("این مسیر فقط زمانی فعال است که منشأ ارز USD_Istanbul باشد.")
        st.code("total cost = Istanbul direct supplier fee", language="text")

    with st.expander("۶. مفهوم هزینه منفی و سرگیری"):
        st.markdown("اگر هزینه تبدیل مثبت باشد، مشتری هزینه پرداخت می‌کند. اگر هزینه تبدیل منفی باشد، گزارش فارسی آن را با عبارت «سر می‌گیرد» نمایش می‌دهد.")

    with st.expander("۷. رفتار ریت‌های ناموجود"):
        st.markdown(
            """
            ریت ناموجود یا نامعتبر هیچ‌وقت صفر فرض نمی‌شود. مسیرهای متاثر با وضعیت «ریت موجود نیست» از رتبه‌بندی حذف می‌شوند. اگر برای یک منشأ ارز هیچ مسیر قابل محاسبه‌ای باقی نماند، بهترین مسیر با عنوان «داده کافی نیست» نمایش داده می‌شود.
            """
        )


init_state()
st.sidebar.caption(BUILD_MARKER)
page = st.sidebar.radio("ناوبری", ["ورود روزانه", "گزارش تصمیم روزانه", "گزارش مشتری", "تاریخچه گزارش‌ها", "راهنما و فرمول‌ها"])

if page == "ورود روزانه":
    daily_input_page()
elif page == "گزارش تصمیم روزانه":
    decision_report_page()
elif page == "گزارش مشتری":
    customer_report_page()
elif page == "تاریخچه گزارش‌ها":
    history_page()
else:
    settings_page()
