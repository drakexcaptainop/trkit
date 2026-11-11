"""Local SQLite record of every forecast served, so it can be scored later."""

from __future__ import annotations

import sqlite3
from dataclasses import astuple, dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class LedgerRow:
    ticker: str
    as_of: str
    horizon: int
    model: str
    last_close: float
    annualized_vol: float
    horizon_sigma: float
    band_low: float
    band_high: float
    baseline_vol: float
    baseline_sigma: float
    baseline_band_low: float
    baseline_band_high: float
    created_at: str


_COLUMNS = [f.name for f in fields(LedgerRow)]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS forecasts (
    ticker TEXT NOT NULL,
    as_of TEXT NOT NULL,
    horizon INTEGER NOT NULL,
    model TEXT NOT NULL,
    last_close REAL NOT NULL,
    annualized_vol REAL NOT NULL,
    horizon_sigma REAL NOT NULL,
    band_low REAL NOT NULL,
    band_high REAL NOT NULL,
    baseline_vol REAL NOT NULL,
    baseline_sigma REAL NOT NULL,
    baseline_band_low REAL NOT NULL,
    baseline_band_high REAL NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (ticker, as_of, horizon, model)
)
"""


class Ledger:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def record(self, rows: list[LedgerRow]) -> None:
        """Insert rows; a forecast already recorded for the same key is left as it was."""
        placeholders = ",".join("?" for _ in _COLUMNS)
        with self._connect() as db:
            db.executemany(
                f"INSERT OR IGNORE INTO forecasts ({','.join(_COLUMNS)}) VALUES ({placeholders})",
                [astuple(r) for r in rows],
            )

    def rows(self, ticker: str | None = None) -> list[LedgerRow]:
        query = f"SELECT {','.join(_COLUMNS)} FROM forecasts"
        args: tuple = ()
        if ticker:
            query += " WHERE ticker = ?"
            args = (ticker.upper(),)
        query += " ORDER BY as_of, model, horizon"
        with self._connect() as db:
            return [LedgerRow(*r) for r in db.execute(query, args).fetchall()]
