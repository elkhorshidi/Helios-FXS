from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from calculation_engine import (
    FeeSettings,
    compare_to_excel_reference,
    calculate_daily_decisions,
    decision_table_for_display,
    default_rates,
)
from report_generator import attach_recommendations, daily_report_text, format_percent, format_usd
from storage import existing_versions, load_history, save_daily_report
from validation import coerce_rates, parse_pasted_rates, validate_rates


st.set_page_config(page_title="FX Declaration Decision Dashboard", page_icon="FX", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem;}
    [data-testid="stMetricValue"] {font-size: 1.35rem;}
    .stDataFrame, .stDataEditor {direction: ltr;}
    textarea {direction: ltr;}
    </style>
    """,
    unsafe_allow_html=True,
)


def init_state() -> None:
    if "rates_df" not in st.session_state:
        st.session_state.rates_df = default_rates()
    if "report_date" not in st.session_state:
        st.session_state.report_date = str(st.session_state.rates_df["Date"].iloc[0])
    if "sample_amount_usd" not in st.session_state:
        st.session_state.sample_amount_usd = 1_000_000.0
    if "fees" not in st.session_state:
        st.session_state.fees = FeeSettings()


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


def dataframe_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def dataframe_excel_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def daily_input_page() -> None:
    st.title("ورودی روزانه")
    st.caption("همه نرخ‌ها بر پایه AED وارد می‌شوند. درصدها با مقدار داخلی اعشاری ذخیره می‌شوند، مثلا 0.70% برابر 0.007 است.")

    top = st.columns([1, 1, 1, 1])
    with top[0]:
        st.session_state.report_date = st.text_input("تاریخ گزارش", value=st.session_state.report_date)
    with top[1]:
        st.session_state.sample_amount_usd = st.number_input("مبلغ نمونه USD", min_value=1.0, value=float(st.session_state.sample_amount_usd), step=10_000.0)
    with top[2]:
        no_fx_pct = st.number_input("کارمزد اظهارنامه بدون ارز (%)", value=st.session_state.fees.no_fx_declaration_fee * 100, step=0.05, format="%.3f")
    with top[3]:
        dubai_pct = st.number_input("کارمزد مسیر دوبی (%)", value=st.session_state.fees.dubai_transfer_fee * 100, step=0.05, format="%.3f")
    istanbul_pct = st.number_input("کارمزد مستقیم استانبول (%)", value=st.session_state.fees.istanbul_direct_fee * 100, step=0.05, format="%.3f")
    st.session_state.fees = FeeSettings(no_fx_pct / 100, dubai_pct / 100, istanbul_pct / 100)

    st.subheader("ورود سریع نرخ‌ها")
    pasted = st.text_area(
        "Paste-friendly table",
        placeholder="Date        Market          Buy     Sell\n1405/04/18  Tether          3.670   3.677",
        height=140,
    )
    if st.button("اعمال متن واردشده", type="secondary"):
        parsed = parse_pasted_rates(pasted)
        if parsed.empty:
            st.warning("متنی برای تبدیل به جدول نرخ پیدا نشد.")
        else:
            st.session_state.rates_df = parsed
            st.session_state.report_date = str(parsed["Date"].iloc[0])
            st.success("نرخ‌ها از متن واردشده به جدول منتقل شدند.")

    st.subheader("جدول نرخ قابل ویرایش")
    editable = st.session_state.rates_df.copy()
    editable["Date"] = st.session_state.report_date
    st.session_state.rates_df = st.data_editor(
        editable,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Buy": st.column_config.NumberColumn("Buy", min_value=0.0, step=0.001, format="%.6f"),
            "Sell": st.column_config.NumberColumn("Sell", min_value=0.0, step=0.001, format="%.6f"),
        },
    )

    errors = validate_rates(coerce_rates(st.session_state.rates_df))
    if errors:
        for error in errors:
            st.error(error)
    else:
        st.success("ورودی‌ها معتبر هستند.")


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
    metrics[0].metric("کمترین هزینه امروز", format_percent(min_best))
    metrics[1].metric("بالاترین هزینه مسیر منتخب", format_percent(max_best))
    metrics[2].metric("ارزان‌ترین منشأ ارز", cheapest_origin)
    metrics[3].metric("پرتکرارترین مسیر منتخب", route_mode)
    metrics[4].metric("بزرگ‌ترین صرفه‌جویی", format_percent(largest_saving))

    st.subheader("جدول تصمیم")
    st.dataframe(format_table(table), width="stretch", hide_index=True)

    col1, col2, col3 = st.columns(3)
    col1.download_button("دانلود CSV جدول", dataframe_csv_bytes(table), "daily_decision_table.csv", "text/csv")
    col2.download_button("دانلود Excel گزارش", dataframe_excel_bytes(table, "Daily Decision"), "daily_decision_report.xlsx")
    col3.download_button("دانلود متن فارسی", daily_report_text(decisions).encode("utf-8-sig"), "persian_daily_report.txt")

    st.subheader("روایت فارسی")
    for _, row in decisions.iterrows():
        with st.expander(f"{row['Origin Currency Persian']} - {row['Best Route']}", expanded=False):
            st.markdown(row["Recommendation Text"].replace("\n", "  \n"))

    with st.expander("اعتبارسنجی با سناریوی نمونه Excel"):
        reference = compare_to_excel_reference(decisions)
        st.dataframe(reference, width="stretch", hide_index=True)


def history_page() -> None:
    st.title("History")
    decisions, errors = current_decisions()
    duplicate_versions = existing_versions(st.session_state.report_date)

    c1, c2 = st.columns([1, 3])
    with c1:
        overwrite = st.checkbox("ذخیره به عنوان نسخه جایگزین آخرین گزارش همین تاریخ", value=False, disabled=not duplicate_versions)
        if errors:
            st.warning("گزارش با مسیرهای ناقص قابل ذخیره است؛ مقادیر ناقص خالی یا غیرفعال ذخیره می‌شوند.")
        if st.button("Save Daily Report", type="primary", disabled=decisions.empty):
            try:
                version = save_daily_report(
                    st.session_state.report_date,
                    coerce_rates(st.session_state.rates_df),
                    st.session_state.fees,
                    st.session_state.sample_amount_usd,
                    decisions,
                    overwrite=overwrite,
                )
                st.success(f"گزارش تاریخ {st.session_state.report_date} با نسخه {version} ذخیره شد.")
            except ValueError:
                st.warning("برای این تاریخ قبلا گزارش ذخیره شده است. گزینه جایگزینی آخرین نسخه را فعال کنید یا تاریخ جدید وارد کنید.")
    with c2:
        if duplicate_versions:
            st.info(f"نسخه‌های موجود برای این تاریخ: {', '.join(map(str, duplicate_versions))}")

    history = load_history()
    if history.empty:
        st.info("هنوز گزارشی در تاریخچه ذخیره نشده است.")
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
        selected_routes = st.multiselect("فیلتر مسیر منتخب", routes, default=routes)

    filtered = history[
        history["report_date"].isin(selected_dates)
        & history["Origin Currency Persian"].isin(selected_origins)
        & history["Best Route"].isin(selected_routes)
    ].copy()

    st.dataframe(format_table(filtered), width="stretch", hide_index=True)
    st.download_button("دانلود History CSV", dataframe_csv_bytes(filtered), "fx_decision_history.csv", "text/csv")

    if not filtered.empty:
        chart_df = filtered.rename(columns={"report_date": "Date"}).set_index("Date")
        st.subheader("Best Cost % over time")
        st.line_chart(chart_df, y="Best Cost %", color="#2563eb")
        st.subheader("Route Cost % comparison")
        st.line_chart(chart_df[["No-FX Cost %", "Dubai Route Cost %", "Istanbul Direct Cost %"]])

        summary_cols = st.columns(2)
        with summary_cols[0]:
            st.write("تعداد انتخاب هر مسیر به عنوان بهترین گزینه")
            st.dataframe(filtered["Best Route"].value_counts().reset_index(name="Count").rename(columns={"index": "Best Route"}), hide_index=True)
        with summary_cols[1]:
            st.write("میانگین Best Cost % بر اساس منشأ ارز")
            avg = filtered.groupby("Origin Currency Persian", as_index=False)["Best Cost %"].mean()
            st.dataframe(format_table(avg), hide_index=True)


def settings_page() -> None:
    st.title("Settings / Notes")
    st.markdown(
        """
        **نقش فایل Excel**  
        فایل Excel نمونه تأییدشده منطق کسب‌وکار است و برای بررسی ساختار، فرمول‌ها، خروجی Daily_Report و سناریوی مرجع استفاده شده است. این اپلیکیشن در زمان اجرا به Excel وابسته نیست.

        **منشأ ارزها**  
        USD_Tehran = دلار تهران، USD_Istanbul = دلار استانبول، USD_Sulaymaniyah = دلار سلیمانیه، USD_Tether = دلار تتر، AED_Dubai = درهم دوبی.

        **فرمول اظهارنامه بدون ارز**  
        هزینه کل = هزینه تبدیل منشأ ارز به دلار تهران + کارمزد اظهارنامه بدون ارز. برای منشأهای USD فرمول تبدیل برابر `(Tehran Sell - Origin Buy) / Origin Buy` است. برای AED_Dubai فرمول برابر `(Tehran Sell - Tehran Buy) / Tehran Buy` است.

        **فرمول مسیر دوبی**  
        هزینه کل = هزینه تبدیل منشأ ارز به دلار دوبی + کارمزد انتقال / ورود دوبی. برای AED_Dubai هزینه تبدیل صفر نیست و از اسپرد دوبی یعنی `(Dubai Sell - Dubai Buy) / Dubai Buy` محاسبه می‌شود.

        **فرمول مستقیم استانبول**  
        فقط برای USD_Istanbul فعال است و هزینه کل آن برابر کارمزد مستقیم استانبول است.

        **هزینه یا منفعت تبدیل**  
        اگر هزینه تبدیل مثبت باشد، در گزارش به عنوان هزینه پرداختی مشتری نمایش داده می‌شود. اگر منفی باشد، گزارش فارسی آن را با عبارت «سر می‌گیرد» بیان می‌کند.
        """
    )


init_state()
page = st.sidebar.radio("Navigation", ["Daily Input", "Daily Decision Report", "History", "Settings / Notes"])

if page == "Daily Input":
    daily_input_page()
elif page == "Daily Decision Report":
    decision_report_page()
elif page == "History":
    history_page()
else:
    settings_page()
