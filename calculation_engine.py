from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Iterable, List, Optional

import pandas as pd


ORIGIN_LABELS_FA = {
    "USD_Tehran": "دلار تهران",
    "USD_Istanbul": "دلار استانبول",
    "USD_Sulaymaniyah": "دلار سلیمانیه",
    "USD_Tether": "دلار تتر",
    "AED_Dubai": "درهم دوبی",
}

MARKET_TO_ORIGIN = {
    "Tehran": "USD_Tehran",
    "Istanbul": "USD_Istanbul",
    "Sulaymaniyah": "USD_Sulaymaniyah",
    "Tether": "USD_Tether",
    "Dubai": "AED_Dubai",
}

ORIGIN_TO_MARKET = {value: key for key, value in MARKET_TO_ORIGIN.items()}

ROUTE_LABELS_FA = {
    "NO_FX_DECLARATION": "اظهارنامه بدون ارز",
    "DUBAI_FX_DECLARATION": "اظهارنامه با ارز از مسیر دوبی",
    "ISTANBUL_DIRECT": "اظهارنامه با ارز مستقیم استانبول",
}

ROUTE_COLUMNS = {
    "NO_FX_DECLARATION": "No-FX Cost %",
    "DUBAI_FX_DECLARATION": "Dubai Route Cost %",
    "ISTANBUL_DIRECT": "Istanbul Direct Cost %",
}


@dataclass(frozen=True)
class FeeSettings:
    no_fx_declaration_fee: float = 0.007
    dubai_transfer_fee: float = 0.005
    istanbul_direct_fee: float = 0.015


@dataclass(frozen=True)
class RouteResult:
    route_id: str
    route_label: str
    active: bool
    conversion_cost: Optional[float]
    fee: Optional[float]
    total_cost: Optional[float]
    cost_usd: Optional[float]
    inactive_reason: str = ""


def default_rates(report_date: str = "1405/04/17") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Date": report_date, "Market": "Tether", "Buy": 3.670, "Sell": 3.677, "Notes": "Paste/overwrite this block daily"},
            {"Date": report_date, "Market": "Tehran", "Buy": 3.660, "Sell": 3.670, "Notes": ""},
            {"Date": report_date, "Market": "Istanbul", "Buy": 3.677, "Sell": 3.683, "Notes": ""},
            {"Date": report_date, "Market": "Sulaymaniyah", "Buy": 3.686, "Sell": 3.694, "Notes": ""},
            {"Date": report_date, "Market": "Dubai", "Buy": 3.670, "Sell": 3.688, "Notes": "AED origin; USD Dubai conversion uses Dubai spread"},
        ]
    )


def normalize_rates(rates: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    normalized: Dict[str, Dict[str, float]] = {}
    for _, row in rates.iterrows():
        market = str(row["Market"]).strip()
        if not market or market.lower() == "nan":
            continue
        buy = pd.to_numeric(row["Buy"], errors="coerce")
        sell = pd.to_numeric(row["Sell"], errors="coerce")
        if pd.isna(buy) or pd.isna(sell) or not math.isfinite(float(buy)) or not math.isfinite(float(sell)):
            continue
        if float(buy) <= 0 or float(sell) < 0:
            continue
        normalized[market] = {"Buy": float(buy), "Sell": float(sell)}
    return normalized


def conversion_cost(origin_code: str, destination_market: str, rates: Dict[str, Dict[str, float]]) -> Optional[float]:
    if destination_market not in rates:
        return None

    destination = rates[destination_market]
    if origin_code == "AED_Dubai":
        return (destination["Sell"] - destination["Buy"]) / destination["Buy"]

    origin_market = ORIGIN_TO_MARKET[origin_code]
    if origin_market not in rates:
        return None
    if origin_market == destination_market:
        return 0.0

    origin_buy = rates[origin_market]["Buy"]
    return (destination["Sell"] - origin_buy) / origin_buy


def calculate_routes_for_origin(
    origin_code: str,
    rates: Dict[str, Dict[str, float]],
    fees: FeeSettings,
    sample_amount_usd: float,
    active_route_overrides: Optional[Dict[str, bool]] = None,
) -> List[RouteResult]:
    active_route_overrides = active_route_overrides or {}

    no_fx_conv = conversion_cost(origin_code, "Tehran", rates)
    no_fx_active = active_route_overrides.get("NO_FX_DECLARATION", True) and no_fx_conv is not None
    dubai_conv = conversion_cost(origin_code, "Dubai", rates)
    dubai_active = active_route_overrides.get("DUBAI_FX_DECLARATION", True) and dubai_conv is not None
    istanbul_active = origin_code == "USD_Istanbul" and active_route_overrides.get("ISTANBUL_DIRECT", True)

    route_specs = [
        ("NO_FX_DECLARATION", no_fx_active, no_fx_conv, fees.no_fx_declaration_fee),
        ("DUBAI_FX_DECLARATION", dubai_active, dubai_conv, fees.dubai_transfer_fee),
        ("ISTANBUL_DIRECT", istanbul_active, 0.0 if istanbul_active else None, fees.istanbul_direct_fee if istanbul_active else None),
    ]

    results: List[RouteResult] = []
    for route_id, active, conv, fee in route_specs:
        total = (conv + fee) if active and conv is not None and fee is not None else None
        results.append(
            RouteResult(
                route_id=route_id,
                route_label=ROUTE_LABELS_FA[route_id],
                active=active,
                conversion_cost=conv if active else None,
                fee=fee if active else None,
                total_cost=total,
                cost_usd=sample_amount_usd * total if total is not None else None,
                inactive_reason="" if active else _inactive_reason(route_id, origin_code, conv),
            )
        )
    return results


def _inactive_reason(route_id: str, origin_code: str, conversion: Optional[float]) -> str:
    if route_id == "ISTANBUL_DIRECT" and origin_code != "USD_Istanbul":
        return "غیرفعال"
    if conversion is None:
        return "ریت موجود نیست"
    return "غیرفعال"


def rank_active_routes(routes: Iterable[RouteResult]) -> List[RouteResult]:
    return sorted([route for route in routes if route.active and route.total_cost is not None], key=lambda item: item.total_cost)


def build_decision_row(origin_code: str, routes: List[RouteResult], sample_amount_usd: float) -> dict:
    ranked = rank_active_routes(routes)
    best = ranked[0] if ranked else None
    second = ranked[1] if len(ranked) > 1 else None
    route_by_id = {route.route_id: route for route in routes}

    saving_pct = (second.total_cost - best.total_cost) if best and second else None
    saving_usd = sample_amount_usd * saving_pct if saving_pct is not None else None

    row = {
        "Origin Currency Code": origin_code,
        "Origin Currency Persian": ORIGIN_LABELS_FA[origin_code],
        "Best Route": best.route_label if best else "داده کافی نیست",
        "Best Route ID": best.route_id if best else "",
        "Best Cost %": best.total_cost if best else None,
        "Best Cost USD": best.cost_usd if best else None,
        "Second Best Route": second.route_label if second else "",
        "Second Best Route ID": second.route_id if second else "",
        "Second Best Cost %": second.total_cost if second else None,
        "Saving vs Next %": saving_pct,
        "Saving vs Next USD": saving_usd,
        "No-FX Cost %": _route_total(route_by_id, "NO_FX_DECLARATION"),
        "No-FX Status": _route_status(route_by_id, "NO_FX_DECLARATION"),
        "Dubai Route Cost %": _route_total(route_by_id, "DUBAI_FX_DECLARATION"),
        "Dubai Route Status": _route_status(route_by_id, "DUBAI_FX_DECLARATION"),
        "Istanbul Direct Cost %": _route_total(route_by_id, "ISTANBUL_DIRECT"),
        "Istanbul Direct Status": _route_status(route_by_id, "ISTANBUL_DIRECT"),
        "Routes": routes,
        "Ranked Routes": ranked,
    }
    return row


def _route_total(route_by_id: Dict[str, RouteResult], route_id: str) -> Optional[float]:
    route = route_by_id[route_id]
    return route.total_cost if route.active else None


def _route_status(route_by_id: Dict[str, RouteResult], route_id: str) -> str:
    route = route_by_id[route_id]
    return "فعال" if route.active else route.inactive_reason


def calculate_daily_decisions(
    rates_df: pd.DataFrame,
    fees: FeeSettings,
    sample_amount_usd: float,
    active_route_overrides: Optional[Dict[str, bool]] = None,
) -> pd.DataFrame:
    rates = normalize_rates(rates_df)
    rows = []
    for origin_code in ORIGIN_LABELS_FA:
        routes = calculate_routes_for_origin(origin_code, rates, fees, sample_amount_usd, active_route_overrides)
        rows.append(build_decision_row(origin_code, routes, sample_amount_usd))
    return pd.DataFrame(rows)


def decision_table_for_display(decisions: pd.DataFrame) -> pd.DataFrame:
    return decisions.drop(columns=["Routes", "Ranked Routes"], errors="ignore")


def compare_to_excel_reference(decisions: pd.DataFrame) -> pd.DataFrame:
    expected = {
        "USD_Tehran": {"Best Route": "اظهارنامه بدون ارز", "Best Cost %": 0.007, "Second Best Cost %": 0.012650273224},
        "USD_Istanbul": {"Best Route": "اظهارنامه بدون ارز", "Best Cost %": 0.005096274137, "Second Best Cost %": 0.007991569214},
        "USD_Sulaymaniyah": {"Best Route": "اظهارنامه بدون ارز", "Best Cost %": 0.002659251221, "Second Best Cost %": 0.005542593597},
        "USD_Tether": {"Best Route": "اظهارنامه بدون ارز", "Best Cost %": 0.007, "Second Best Cost %": 0.009904632153},
        "AED_Dubai": {"Best Route": "اظهارنامه بدون ارز", "Best Cost %": 0.009732240437, "Second Best Cost %": 0.009904632153},
    }
    rows = []
    for _, row in decisions.iterrows():
        origin = row["Origin Currency Code"]
        ref = expected[origin]
        rows.append(
            {
                "Origin Currency Code": origin,
                "Python Best Route": row["Best Route"],
                "Excel Best Route": ref["Best Route"],
                "Best Route Match": row["Best Route"] == ref["Best Route"],
                "Python Best Cost %": row["Best Cost %"],
                "Excel Best Cost %": ref["Best Cost %"],
                "Best Cost Delta": _safe_delta(row["Best Cost %"], ref["Best Cost %"]),
                "Python Second Best Cost %": row["Second Best Cost %"],
                "Excel Second Best Cost %": ref["Second Best Cost %"],
                "Second Best Delta": _safe_delta(row["Second Best Cost %"], ref["Second Best Cost %"]),
            }
        )
    return pd.DataFrame(rows)


def _safe_delta(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None or pd.isna(left) or pd.isna(right):
        return None
    return left - right
