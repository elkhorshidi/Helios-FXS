from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from calculation_engine import FeeSettings, decision_table_for_display


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "history.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS report_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            version INTEGER NOT NULL,
            saved_at TEXT NOT NULL,
            sample_amount_usd REAL NOT NULL,
            fees_json TEXT NOT NULL,
            rates_json TEXT NOT NULL,
            UNIQUE(report_date, version)
        );

        CREATE TABLE IF NOT EXISTS decision_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            origin_code TEXT NOT NULL,
            origin_label TEXT NOT NULL,
            best_route TEXT,
            best_route_id TEXT,
            best_cost_pct REAL,
            best_cost_usd REAL,
            second_best_route TEXT,
            second_best_route_id TEXT,
            second_best_cost_pct REAL,
            saving_vs_next_pct REAL,
            saving_vs_next_usd REAL,
            no_fx_cost_pct REAL,
            dubai_route_cost_pct REAL,
            istanbul_direct_cost_pct REAL,
            recommendation_text TEXT,
            route_costs_json TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES report_runs(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()


def existing_versions(report_date: str, conn: Optional[sqlite3.Connection] = None) -> list[int]:
    close = conn is None
    conn = conn or get_connection()
    rows = conn.execute("SELECT version FROM report_runs WHERE report_date = ? ORDER BY version", (report_date,)).fetchall()
    if close:
        conn.close()
    return [int(row["version"]) for row in rows]


def save_daily_report(
    report_date: str,
    rates: pd.DataFrame,
    fees: FeeSettings,
    sample_amount_usd: float,
    decisions: pd.DataFrame,
    overwrite: bool = False,
    db_path: Path = DB_PATH,
) -> int:
    conn = get_connection(db_path)
    versions = existing_versions(report_date, conn)
    if versions and not overwrite:
        conn.close()
        raise ValueError("duplicate_date")

    version = max(versions, default=0) + 1
    if overwrite and versions:
        version = max(versions)
        run = conn.execute("SELECT id FROM report_runs WHERE report_date = ? AND version = ?", (report_date, version)).fetchone()
        if run:
            conn.execute("DELETE FROM report_runs WHERE id = ?", (run["id"],))

    cursor = conn.execute(
        """
        INSERT INTO report_runs (report_date, version, saved_at, sample_amount_usd, fees_json, rates_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            report_date,
            version,
            datetime.utcnow().isoformat(timespec="seconds"),
            sample_amount_usd,
            json.dumps(fees.__dict__, ensure_ascii=False),
            rates.to_json(orient="records", force_ascii=False),
        ),
    )
    run_id = int(cursor.lastrowid)

    for _, row in decisions.iterrows():
        route_costs = {
            route.route_id: {
                "active": route.active,
                "conversion_cost": route.conversion_cost,
                "fee": route.fee,
                "total_cost": route.total_cost,
                "cost_usd": route.cost_usd,
                "inactive_reason": route.inactive_reason,
            }
            for route in row["Routes"]
        }
        conn.execute(
            """
            INSERT INTO decision_rows (
                run_id, origin_code, origin_label, best_route, best_route_id, best_cost_pct, best_cost_usd,
                second_best_route, second_best_route_id, second_best_cost_pct, saving_vs_next_pct,
                saving_vs_next_usd, no_fx_cost_pct, dubai_route_cost_pct, istanbul_direct_cost_pct,
                recommendation_text, route_costs_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                row["Origin Currency Code"],
                row["Origin Currency Persian"],
                row["Best Route"],
                row["Best Route ID"],
                row["Best Cost %"],
                row["Best Cost USD"],
                row["Second Best Route"],
                row["Second Best Route ID"],
                row["Second Best Cost %"],
                row["Saving vs Next %"],
                row["Saving vs Next USD"],
                row["No-FX Cost %"],
                row["Dubai Route Cost %"],
                row["Istanbul Direct Cost %"],
                row["Recommendation Text"],
                json.dumps(route_costs, ensure_ascii=False),
            ),
        )

    conn.commit()
    conn.close()
    return version


def load_history(db_path: Path = DB_PATH) -> pd.DataFrame:
    conn = get_connection(db_path)
    query = """
        SELECT
            r.report_date,
            r.version,
            r.saved_at,
            r.sample_amount_usd,
            d.origin_code AS "Origin Currency Code",
            d.origin_label AS "Origin Currency Persian",
            d.best_route AS "Best Route",
            d.best_route_id AS "Best Route ID",
            d.best_cost_pct AS "Best Cost %",
            d.best_cost_usd AS "Best Cost USD",
            d.second_best_route AS "Second Best Route",
            d.second_best_cost_pct AS "Second Best Cost %",
            d.saving_vs_next_pct AS "Saving vs Next %",
            d.saving_vs_next_usd AS "Saving vs Next USD",
            d.no_fx_cost_pct AS "No-FX Cost %",
            d.dubai_route_cost_pct AS "Dubai Route Cost %",
            d.istanbul_direct_cost_pct AS "Istanbul Direct Cost %",
            d.recommendation_text AS "Recommendation Text"
        FROM decision_rows d
        JOIN report_runs r ON r.id = d.run_id
        ORDER BY r.report_date, r.version, d.origin_code
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def export_decisions(decisions: pd.DataFrame) -> pd.DataFrame:
    return decision_table_for_display(decisions)
