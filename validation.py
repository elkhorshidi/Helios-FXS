from __future__ import annotations

from typing import List

import pandas as pd

from calculation_engine import MARKET_TO_ORIGIN


REQUIRED_MARKETS = set(MARKET_TO_ORIGIN)


def validate_rates(rates: pd.DataFrame) -> List[str]:
    errors: List[str] = []
    required_columns = {"Date", "Market", "Buy", "Sell", "Notes"}
    missing_columns = required_columns - set(rates.columns)
    if missing_columns:
        return [f"ستون‌های ضروری وجود ندارند: {', '.join(sorted(missing_columns))}"]

    clean = rates.copy()
    clean["Market"] = clean["Market"].astype(str).str.strip()
    clean = clean[clean["Market"].ne("") & clean["Market"].str.lower().ne("nan")]

    duplicates = clean["Market"][clean["Market"].duplicated()].unique().tolist()
    if duplicates:
        errors.append(f"بازارهای تکراری: {', '.join(duplicates)}")

    markets = set(clean["Market"])
    missing_markets = REQUIRED_MARKETS - markets
    if missing_markets:
        errors.append(f"بازارهای ضروری وارد نشده‌اند: {', '.join(sorted(missing_markets))}")

    unknown_markets = markets - REQUIRED_MARKETS
    if unknown_markets:
        errors.append(f"بازارهای ناشناخته: {', '.join(sorted(unknown_markets))}")

    for column in ["Buy", "Sell"]:
        numeric = pd.to_numeric(clean[column], errors="coerce")
        bad = clean.loc[numeric.isna(), "Market"].tolist()
        if bad:
            errors.append(f"مقادیر غیرعددی در ستون {column}: {', '.join(bad)}")
        clean[column] = numeric

    zero_buy = clean.loc[clean["Buy"] <= 0, "Market"].tolist()
    if zero_buy:
        errors.append(f"نرخ خرید باید بزرگ‌تر از صفر باشد: {', '.join(zero_buy)}")

    negative_sell = clean.loc[clean["Sell"] < 0, "Market"].tolist()
    if negative_sell:
        errors.append(f"نرخ فروش نباید منفی باشد: {', '.join(negative_sell)}")

    return errors


def coerce_rates(rates: pd.DataFrame) -> pd.DataFrame:
    clean = rates.reindex(columns=["Date", "Market", "Buy", "Sell", "Notes"]).copy()
    clean["Market"] = clean["Market"].astype(str).str.strip()
    clean["Buy"] = pd.to_numeric(clean["Buy"], errors="coerce")
    clean["Sell"] = pd.to_numeric(clean["Sell"], errors="coerce")
    clean["Notes"] = clean["Notes"].fillna("").astype(str)
    return clean


def parse_pasted_rates(text: str) -> pd.DataFrame:
    rows = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.replace("\t", " ").split()
        if parts[0].lower() == "date":
            continue
        if len(parts) < 4:
            continue
        date, market, buy, sell = parts[:4]
        notes = " ".join(parts[4:])
        rows.append({"Date": date, "Market": market, "Buy": buy, "Sell": sell, "Notes": notes})
    return pd.DataFrame(rows, columns=["Date", "Market", "Buy", "Sell", "Notes"])
