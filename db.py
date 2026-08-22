#!/usr/bin/env python3
"""SQLite store for one gold-price snapshot per Malaysia calendar day."""

from __future__ import annotations

import json
import sqlite3
import threading
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "gold_prices.db"
API_URL = "https://api.hargaemas.my/prices"
MYT = ZoneInfo("Asia/Kuala_Lumpur")
KARATS = (999, 916, 835, 750, 585, 375)

_lock = threading.Lock()


def gram_prices(spot_sell_per_kg: float) -> dict[int, float]:
    spot = float(spot_sell_per_kg) / 1000.0
    return {code: spot if code == 999 else spot * (code / 1000.0) for code in KARATS}


def malaysia_date(iso_stamp: str | None = None) -> str:
    if iso_stamp:
        try:
            parsed = datetime.fromisoformat(iso_stamp.replace("Z", "+00:00"))
            return parsed.astimezone(MYT).date().isoformat()
        except ValueError:
            pass
    return datetime.now(MYT).date().isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock, connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_prices (
              price_date TEXT PRIMARY KEY,
              spot_sell_rm_per_kg REAL NOT NULL,
              spot_buy_rm_per_kg REAL,
              tael_sell_rm REAL,
              tael_buy_rm REAL,
              usd_myr_sell REAL,
              usd_myr_buy REAL,
              gram_999 REAL NOT NULL,
              gram_916 REAL NOT NULL,
              gram_835 REAL NOT NULL,
              gram_750 REAL NOT NULL,
              gram_585 REAL NOT NULL,
              gram_375 REAL NOT NULL,
              source_updated_at TEXT,
              recorded_at TEXT NOT NULL
            )
            """
        )


def save_snapshot(payload: dict) -> dict:
    prices = payload.get("prices") or {}
    spot_sell = prices.get("spotSellRmPerKg")
    if spot_sell is None:
        raise ValueError("payload tiada spotSellRmPerKg")

    grams = gram_prices(spot_sell)
    source_updated = payload.get("lastUpdate")
    row = {
        "price_date": malaysia_date(source_updated),
        "spot_sell_rm_per_kg": float(spot_sell),
        "spot_buy_rm_per_kg": prices.get("spotBuyRmPerKg"),
        "tael_sell_rm": prices.get("taelSellRm"),
        "tael_buy_rm": prices.get("taelBuyRm"),
        "usd_myr_sell": prices.get("usdMyrSell"),
        "usd_myr_buy": prices.get("usdMyrBuy"),
        "gram_999": grams[999],
        "gram_916": grams[916],
        "gram_835": grams[835],
        "gram_750": grams[750],
        "gram_585": grams[585],
        "gram_375": grams[375],
        "source_updated_at": source_updated,
        "recorded_at": datetime.now(MYT).isoformat(timespec="seconds"),
    }

    with _lock, connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_prices (
              price_date, spot_sell_rm_per_kg, spot_buy_rm_per_kg,
              tael_sell_rm, tael_buy_rm, usd_myr_sell, usd_myr_buy,
              gram_999, gram_916, gram_835, gram_750, gram_585, gram_375,
              source_updated_at, recorded_at
            ) VALUES (
              :price_date, :spot_sell_rm_per_kg, :spot_buy_rm_per_kg,
              :tael_sell_rm, :tael_buy_rm, :usd_myr_sell, :usd_myr_buy,
              :gram_999, :gram_916, :gram_835, :gram_750, :gram_585, :gram_375,
              :source_updated_at, :recorded_at
            )
            ON CONFLICT(price_date) DO UPDATE SET
              spot_sell_rm_per_kg = excluded.spot_sell_rm_per_kg,
              spot_buy_rm_per_kg = excluded.spot_buy_rm_per_kg,
              tael_sell_rm = excluded.tael_sell_rm,
              tael_buy_rm = excluded.tael_buy_rm,
              usd_myr_sell = excluded.usd_myr_sell,
              usd_myr_buy = excluded.usd_myr_buy,
              gram_999 = excluded.gram_999,
              gram_916 = excluded.gram_916,
              gram_835 = excluded.gram_835,
              gram_750 = excluded.gram_750,
              gram_585 = excluded.gram_585,
              gram_375 = excluded.gram_375,
              source_updated_at = excluded.source_updated_at,
              recorded_at = excluded.recorded_at
            """,
            row,
        )
    return row


def row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def latest_row() -> dict | None:
    with _lock, connect() as conn:
        found = conn.execute(
            "SELECT * FROM daily_prices ORDER BY price_date DESC LIMIT 1"
        ).fetchone()
    return row_to_dict(found) if found else None


def as_api_payload(row: dict, stale: bool = False) -> dict:
    return {
        "prices": {
            "spotSellRmPerKg": row["spot_sell_rm_per_kg"],
            "spotBuyRmPerKg": row.get("spot_buy_rm_per_kg"),
            "taelSellRm": row.get("tael_sell_rm"),
            "taelBuyRm": row.get("tael_buy_rm"),
            "usdMyrSell": row.get("usd_myr_sell"),
            "usdMyrBuy": row.get("usd_myr_buy"),
        },
        "lastUpdate": row.get("source_updated_at") or row.get("recorded_at"),
        "isStale": stale,
        "fromDatabase": True,
        "priceDate": row.get("price_date"),
    }


def get_history(days: int = 14) -> list[dict]:
    limit = max(1, min(int(days), 365))
    with _lock, connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM daily_prices
            ORDER BY price_date DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    items = [row_to_dict(row) for row in rows]
    chronological = list(reversed(items))
    previous_999 = None
    for item in chronological:
        current = item["gram_999"]
        item["change_999"] = None if previous_999 is None else current - previous_999
        previous_999 = current
    chronological.reverse()
    return chronological


def fetch_live() -> dict:
    request = urllib.request.Request(
        API_URL,
        headers={"User-Agent": "hargaemas-landing/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    import sys

    init_db()
    command = sys.argv[1] if len(sys.argv) > 1 else "show"
    if command == "fetch":
        payload = fetch_live()
        saved = save_snapshot(payload)
        print(json.dumps(saved, indent=2))
    elif command == "show":
        print(json.dumps({"latest": latest_row(), "history": get_history(14)}, indent=2))
    else:
        raise SystemExit("Guna: python3 db.py fetch|show")
