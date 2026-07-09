from __future__ import annotations

from io import BytesIO
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
from report_generator import attach_recommendations, daily_report_text, format_percent, format_usd
from storage import existing_versions, load_history, save_daily_report
from validation import coerce_rates, parse_pasted_rates, validate_rates


st.set_page_config(page_title="داشبورد تصمیم رفع تعهد ارزی", page_icon="FX", layout="wide")

st.markdown(
    """
    <style>
    html, body, [class*="css"], .stApp {direction: rtl; text-align: right;}
    .block-container {padding-top: 1.5rem; max-width: 1220px;}
    [data-testid="stSidebar"] {direction: rtl; text-align: right;}
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 0.85rem 0.95rem;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    [data-testid="stMetricLabel"] {font-size: 0.82rem; color: #475569;}
    [data-testid="stMetricValue"] {font-size: 1.25rem; color: #0f172a;}
    .stButton > button, .stDownloadButton > button {border-radius: 8px;}
    .stDataFrame, .stDataEditor {direction: rtl;}
    textarea {direction: ltr; text-align: left;}
    .rtl-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 0.9rem 1rem;
        background: #ffffff;
        margin-bottom: 0.75rem;
    }
    .rtl-card-title {font-weight: 700; color: #0f172a; margin-bottom: 0.45rem;}
    .rtl-muted {color: #64748b; font-size: 0.9rem;}
    .rtl-narrative {
        direction: rtl;
        text-align: right;
        line-height: 2;
        white-space: pre-wrap;
    }
    code, pre {direction: ltr; text-align: left;}
    </style>
    """,
    unsafe_allow_html=True,
)


DATE_PATTERN = re.compile(r"^\d{4}/\d{2}/\d{2}$")

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


def format_usd_display(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"${format_usd(float(value))}"


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
        st.dataframe(notes, width="stretch", hide_index=True)

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
    st.dataframe(user_decision_table(decisions), width="stretch", hide_index=True)

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
        st.dataframe(reference, width="stretch", hide_index=True)


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
    st.dataframe(user_history_table(filtered), width="stretch", hide_index=True)
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
            st.dataframe(freq, hide_index=True)
        with summary_cols[1]:
            st.write("میانگین Best Cost % بر اساس منشأ ارز")
            avg = filtered.groupby("Origin Currency Persian", as_index=False)["Best Cost %"].mean()
            avg = avg.rename(columns={"Origin Currency Persian": "منشأ ارز", "Best Cost %": "میانگین هزینه"})
            avg["میانگین هزینه"] = avg["میانگین هزینه"].map(format_percent_display)
            st.dataframe(avg, hide_index=True)


def settings_page() -> None:
    st.title("راهنما و فرمول‌ها")

    with st.expander("۱. نقش فایل Excel", expanded=True):
        st.markdown(
            """
            فایل Excel نمونه تأییدشده منطق کسب‌وکار و معیار اعتبارسنجی نسخه اول است. اپلیکیشن در زمان اجرا به Excel وابسته نیست و فرمول‌های تاییدشده مستقیم در Python پیاده‌سازی شده‌اند.
            """
        )

    with st.expander("۲. تعریف منشأ ارزها"):
        origins = pd.DataFrame(
            [
                {"کد داخلی": "USD_Tehran", "عنوان فارسی": "دلار تهران", "بازار": "Tehran"},
                {"کد داخلی": "USD_Istanbul", "عنوان فارسی": "دلار استانبول", "بازار": "Istanbul"},
                {"کد داخلی": "USD_Sulaymaniyah", "عنوان فارسی": "دلار سلیمانیه", "بازار": "Sulaymaniyah"},
                {"کد داخلی": "USD_Tether", "عنوان فارسی": "دلار تتر", "بازار": "Tether"},
                {"کد داخلی": "AED_Dubai", "عنوان فارسی": "درهم دوبی", "بازار": "Dubai"},
            ]
        )
        st.dataframe(origins, width="stretch", hide_index=True)

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
page = st.sidebar.radio("ناوبری", ["ورود روزانه", "گزارش تصمیم روزانه", "تاریخچه گزارش‌ها", "راهنما و فرمول‌ها"])

if page == "ورود روزانه":
    daily_input_page()
elif page == "گزارش تصمیم روزانه":
    decision_report_page()
elif page == "تاریخچه گزارش‌ها":
    history_page()
else:
    settings_page()
