from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import textwrap
from typing import Optional

import arabic_reshaper
from bidi.algorithm import get_display
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "assets" / "fonts"
FONT_REGULAR = FONT_DIR / "Vazirmatn-Regular.ttf"
FONT_BOLD = FONT_DIR / "Vazirmatn-Bold.ttf"
LOGO_PATH = BASE_DIR / "assets" / "logo.png"

REPORT_TITLE = "گزارش روزانه بهترین مسیر رفع تعهد ارزی"
NO_DATA_MESSAGE = "به دلیل کامل نبودن ریت‌های موردنیاز، در حال حاضر امکان ارائه پیشنهاد نهایی برای این منشأ ارز وجود ندارد."
DISCLAIMER = "این گزارش بر اساس ریت‌ها و هزینه‌های ثبت‌شده در تاریخ فوق تهیه شده و ممکن است با تغییر شرایط بازار به‌روزرسانی شود."


@dataclass(frozen=True)
class CustomerReportData:
    report_date: str
    origin_label: str
    base_amount_usd: float
    best_route: str
    best_cost_percent: Optional[float]
    best_cost_usd: Optional[float]
    second_route: str
    second_cost_percent: Optional[float]
    saving_percent: Optional[float]
    saving_usd: Optional[float]
    has_enough_data: bool
    conclusion: str


def format_percent(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value * 100:.2f}%"


def format_usd(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"${value:,.0f}"


def build_customer_report_data(row: pd.Series | dict, report_date: str, base_amount_usd: float) -> CustomerReportData:
    origin_label = row["Origin Currency Persian"]
    best_cost = row["Best Cost %"]
    has_enough_data = best_cost is not None and not pd.isna(best_cost)

    best_route = row["Best Route"] if has_enough_data else "داده کافی نیست"
    conclusion = (
        f"با توجه به ریت‌های امروز و هزینه‌های اجرایی هر مسیر، «{best_route}» "
        f"کم‌هزینه‌ترین گزینه برای رفع تعهد با منشأ {origin_label} است."
        if has_enough_data
        else NO_DATA_MESSAGE
    )

    return CustomerReportData(
        report_date=report_date,
        origin_label=origin_label,
        base_amount_usd=base_amount_usd,
        best_route=best_route,
        best_cost_percent=best_cost if has_enough_data else None,
        best_cost_usd=row["Best Cost USD"] if has_enough_data else None,
        second_route=row["Second Best Route"] or "—",
        second_cost_percent=row["Second Best Cost %"],
        saving_percent=row["Saving vs Next %"],
        saving_usd=row["Saving vs Next USD"],
        has_enough_data=has_enough_data,
        conclusion=conclusion,
    )


def render_customer_report_card(data: CustomerReportData) -> str:
    if not data.has_enough_data:
        body = f"<div class='customer-empty'>{NO_DATA_MESSAGE}</div>"
        actions = ""
    else:
        body = f"""
        <div class="customer-highlight">
            <div class="customer-label">بهترین مسیر پیشنهادی</div>
            <div class="customer-route">{data.best_route}</div>
        </div>
        <div class="customer-grid">
            <div><span>هزینه نهایی مسیر منتخب</span><strong>{format_percent(data.best_cost_percent)}</strong></div>
            <div><span>هزینه دلاری بر اساس مبلغ مبنا</span><strong>{format_usd(data.best_cost_usd)}</strong></div>
            <div><span>گزینه دوم</span><strong>{data.second_route}</strong></div>
            <div><span>هزینه گزینه دوم</span><strong>{format_percent(data.second_cost_percent)}</strong></div>
        </div>
        <div class="customer-saving">
            <span>صرفه‌جویی مسیر پیشنهادی نسبت به گزینه دوم</span>
            <strong>{format_percent(data.saving_percent)} معادل {format_usd(data.saving_usd)}</strong>
        </div>
        <p class="customer-conclusion">{data.conclusion}</p>
        """
        actions = ""

    return f"""
    <div class="customer-card">
        <div class="customer-topline">
            <div>
                <h2>{REPORT_TITLE}</h2>
                <p>تاریخ گزارش: <strong>{data.report_date}</strong></p>
            </div>
        </div>
        <div class="customer-meta">
            <div><span>منشأ ارز</span><strong>{data.origin_label}</strong></div>
            <div><span>مبلغ مبنا</span><strong>{format_usd(data.base_amount_usd)}</strong></div>
        </div>
        {body}
        {actions}
        <div class="customer-footer">{DISCLAIMER}</div>
    </div>
    """


def generate_customer_report_png(data: CustomerReportData) -> bytes:
    image = Image.new("RGB", (1080, 1350), "#f8fafc")
    draw = ImageDraw.Draw(image)
    regular = _font(FONT_REGULAR, 34)
    regular_small = _font(FONT_REGULAR, 28)
    small = _font(FONT_REGULAR, 24)
    bold = _font(FONT_BOLD, 44)
    bold_big = _font(FONT_BOLD, 58)
    bold_mid = _font(FONT_BOLD, 36)

    card = (70, 70, 1010, 1280)
    draw.rounded_rectangle(card, radius=28, fill="#ffffff", outline="#dbe3ef", width=2)

    y = 125
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo.thumbnail((120, 80))
        image.paste(logo, (120, y - 8), logo)

    _draw_rtl(draw, REPORT_TITLE, 940, y, bold, "#0f172a")
    y += 70
    _draw_rtl(draw, f"تاریخ گزارش: {data.report_date}", 940, y, regular_small, "#475569")
    y += 78

    _draw_pair(draw, "منشأ ارز", data.origin_label, 940, y, regular_small, bold_mid)
    _draw_pair(draw, "مبلغ مبنا", format_usd(data.base_amount_usd), 520, y, regular_small, bold_mid)
    y += 115

    if not data.has_enough_data:
        draw.rounded_rectangle((120, y, 940, y + 220), radius=20, fill="#fff7ed", outline="#fed7aa")
        _draw_multiline_rtl(draw, NO_DATA_MESSAGE, 900, y + 55, regular, "#9a3412", width=34, line_gap=14)
    else:
        draw.rounded_rectangle((120, y, 940, y + 185), radius=24, fill="#ecfdf5", outline="#a7f3d0")
        _draw_rtl(draw, "بهترین مسیر پیشنهادی", 900, y + 34, regular_small, "#047857")
        _draw_rtl(draw, data.best_route, 900, y + 88, bold_big, "#064e3b")
        y += 225

        _draw_metric_box(draw, "هزینه نهایی مسیر منتخب", format_percent(data.best_cost_percent), 550, y, 390, 145, bold_mid)
        _draw_metric_box(draw, "هزینه دلاری بر اساس مبلغ مبنا", format_usd(data.best_cost_usd), 120, y, 390, 145, bold_mid)
        y += 185
        _draw_metric_box(draw, "گزینه دوم", data.second_route, 550, y, 390, 145, bold_mid)
        _draw_metric_box(draw, "هزینه گزینه دوم", format_percent(data.second_cost_percent), 120, y, 390, 145, bold_mid)
        y += 185

        draw.rounded_rectangle((120, y, 940, y + 150), radius=22, fill="#eff6ff", outline="#bfdbfe")
        _draw_rtl(draw, "صرفه‌جویی مسیر پیشنهادی نسبت به گزینه دوم", 900, y + 28, regular_small, "#1d4ed8")
        _draw_rtl(draw, f"{format_percent(data.saving_percent)} معادل {format_usd(data.saving_usd)}", 900, y + 82, bold_mid, "#1e3a8a")
        y += 195

        _draw_multiline_rtl(draw, data.conclusion, 900, y, regular, "#334155", width=42, line_gap=12)

    _draw_multiline_rtl(draw, DISCLAIMER, 900, 1175, small, "#64748b", width=50, line_gap=8)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def generate_customer_report_pdf(data: CustomerReportData) -> bytes:
    width, height = portrait((1080, 1350))
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    pdfmetrics.registerFont(TTFont("Vazirmatn", str(FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("Vazirmatn-Bold", str(FONT_BOLD)))

    pdf.setFillColor(colors.HexColor("#f8fafc"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.roundRect(70, 70, 940, 1210, 28, fill=1, stroke=1)

    y = height - 125
    _pdf_rtl(pdf, REPORT_TITLE, 940, y, "Vazirmatn-Bold", 44, "#0f172a")
    y -= 58
    _pdf_rtl(pdf, f"تاریخ گزارش: {data.report_date}", 940, y, "Vazirmatn", 28, "#475569")
    y -= 80
    _pdf_rtl(pdf, f"منشأ ارز: {data.origin_label}", 940, y, "Vazirmatn-Bold", 34, "#0f172a")
    _pdf_rtl(pdf, f"مبلغ مبنا: {format_usd(data.base_amount_usd)}", 520, y, "Vazirmatn-Bold", 34, "#0f172a")
    y -= 105

    if not data.has_enough_data:
        pdf.setFillColor(colors.HexColor("#fff7ed"))
        pdf.roundRect(120, y - 150, 820, 190, 20, fill=1, stroke=0)
        _pdf_multiline(pdf, NO_DATA_MESSAGE, 900, y - 35, "Vazirmatn", 31, "#9a3412", width=36)
    else:
        pdf.setFillColor(colors.HexColor("#ecfdf5"))
        pdf.roundRect(120, y - 130, 820, 170, 24, fill=1, stroke=0)
        _pdf_rtl(pdf, "بهترین مسیر پیشنهادی", 900, y - 20, "Vazirmatn", 27, "#047857")
        _pdf_rtl(pdf, data.best_route, 900, y - 82, "Vazirmatn-Bold", 48, "#064e3b")
        y -= 215
        _pdf_metric(pdf, "هزینه نهایی مسیر منتخب", format_percent(data.best_cost_percent), 550, y, 390, 135)
        _pdf_metric(pdf, "هزینه دلاری بر اساس مبلغ مبنا", format_usd(data.best_cost_usd), 120, y, 390, 135)
        y -= 175
        _pdf_metric(pdf, "گزینه دوم", data.second_route, 550, y, 390, 135)
        _pdf_metric(pdf, "هزینه گزینه دوم", format_percent(data.second_cost_percent), 120, y, 390, 135)
        y -= 175
        pdf.setFillColor(colors.HexColor("#eff6ff"))
        pdf.roundRect(120, y - 105, 820, 140, 20, fill=1, stroke=0)
        _pdf_rtl(pdf, "صرفه‌جویی مسیر پیشنهادی نسبت به گزینه دوم", 900, y - 10, "Vazirmatn", 27, "#1d4ed8")
        _pdf_rtl(pdf, f"{format_percent(data.saving_percent)} معادل {format_usd(data.saving_usd)}", 900, y - 65, "Vazirmatn-Bold", 34, "#1e3a8a")
        y -= 170
        _pdf_multiline(pdf, data.conclusion, 900, y, "Vazirmatn", 30, "#334155", width=44)

    _pdf_multiline(pdf, DISCLAIMER, 900, 165, "Vazirmatn", 22, "#64748b", width=52)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _shape(text: object) -> str:
    return get_display(arabic_reshaper.reshape(str(text)))


def _draw_rtl(draw: ImageDraw.ImageDraw, text: object, right: int, y: int, font: ImageFont.FreeTypeFont, fill: str) -> None:
    shaped = _shape(text)
    bbox = draw.textbbox((0, 0), shaped, font=font)
    draw.text((right - (bbox[2] - bbox[0]), y), shaped, font=font, fill=fill)


def _draw_pair(draw: ImageDraw.ImageDraw, label: str, value: str, right: int, y: int, label_font, value_font) -> None:
    _draw_rtl(draw, label, right, y, label_font, "#64748b")
    _draw_rtl(draw, value, right, y + 42, value_font, "#0f172a")


def _draw_metric_box(draw: ImageDraw.ImageDraw, label: str, value: str, x: int, y: int, w: int, h: int, value_font) -> None:
    draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill="#f8fafc", outline="#e2e8f0")
    _draw_rtl(draw, label, x + w - 28, y + 26, _font(FONT_REGULAR, 25), "#64748b")
    _draw_rtl(draw, value, x + w - 28, y + 76, value_font, "#0f172a")


def _draw_multiline_rtl(draw: ImageDraw.ImageDraw, text: str, right: int, y: int, font, fill: str, width: int, line_gap: int) -> None:
    for line in textwrap.wrap(text, width=width):
        _draw_rtl(draw, line, right, y, font, fill)
        y += font.size + line_gap


def _pdf_rtl(pdf: canvas.Canvas, text: object, right: float, y: float, font_name: str, size: int, fill: str) -> None:
    pdf.setFont(font_name, size)
    pdf.setFillColor(colors.HexColor(fill))
    pdf.drawRightString(right, y, _shape(text))


def _pdf_multiline(pdf: canvas.Canvas, text: str, right: float, y: float, font_name: str, size: int, fill: str, width: int) -> None:
    for line in textwrap.wrap(text, width=width):
        _pdf_rtl(pdf, line, right, y, font_name, size, fill)
        y -= size + 10


def _pdf_metric(pdf: canvas.Canvas, label: str, value: str, x: float, y: float, w: float, h: float) -> None:
    pdf.setFillColor(colors.HexColor("#f8fafc"))
    pdf.roundRect(x, y - h, w, h, 18, fill=1, stroke=0)
    _pdf_rtl(pdf, label, x + w - 26, y - 42, "Vazirmatn", 23, "#64748b")
    _pdf_rtl(pdf, value, x + w - 26, y - 92, "Vazirmatn-Bold", 31, "#0f172a")
