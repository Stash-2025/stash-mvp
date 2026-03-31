"""
Stash – Datenbankmodul
SQLite-Speicher für analysierte Belege und Rechnungen unter ~/.stash/belege.db
"""

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".stash" / "belege.db"


def _get_conn() -> sqlite3.Connection:
    """Öffnet DB-Verbindung und initialisiert Schema falls nötig."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS belege (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            quelle          TEXT    NOT NULL,          -- 'foto' | 'email' | 'pdf'
            quelle_id       TEXT    UNIQUE,            -- Datei-Pfad oder E-Mail Message-ID
            haendler        TEXT,
            datum           TEXT,                      -- YYYY-MM-DD
            gesamtbetrag    REAL,
            waehrung        TEXT    DEFAULT 'EUR',
            kategorie       TEXT,
            mwst            REAL,
            zahlungsart     TEXT,
            artikel         TEXT,                      -- JSON-Array
            beleg_typ       TEXT,
            notizen         TEXT,
            roh_daten       TEXT,                      -- Vollständige JSON-Antwort von Claude
            erstellt_am     TEXT    NOT NULL
        )
    """)
    conn.commit()


# ─── Schreiben ─────────────────────────────────────────────────────────────────

def beleg_exists(quelle_id: str) -> bool:
    """Gibt True zurück wenn ein Beleg mit dieser quelle_id bereits existiert."""
    if not quelle_id:
        return False
    conn = _get_conn()
    try:
        return conn.execute(
            "SELECT 1 FROM belege WHERE quelle_id = ?", (quelle_id,)
        ).fetchone() is not None
    finally:
        conn.close()


def save_beleg(quelle: str, quelle_id: Optional[str], data: dict) -> Optional[int]:
    """
    Speichert einen analysierten Beleg.
    Gibt die neue ID zurück, oder None wenn der Beleg bereits existiert.
    """
    conn = _get_conn()
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO belege
                (quelle, quelle_id, haendler, datum, gesamtbetrag, waehrung,
                 kategorie, mwst, zahlungsart, artikel, beleg_typ, notizen,
                 roh_daten, erstellt_am)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quelle,
                quelle_id,
                data.get("haendler"),
                data.get("datum"),
                data.get("gesamtbetrag"),
                data.get("waehrung", "EUR"),
                data.get("kategorie"),
                data.get("mwst"),
                data.get("zahlungsart"),
                json.dumps(data.get("artikel") or [], ensure_ascii=False),
                data.get("beleg_typ"),
                data.get("notizen"),
                json.dumps(data, ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return cursor.lastrowid if cursor.rowcount > 0 else None
    finally:
        conn.close()


# ─── Lesen ─────────────────────────────────────────────────────────────────────

def get_belege(
    limit: int = 50,
    kategorie: Optional[str] = None,
    monat: Optional[str] = None,
) -> list[dict]:
    """Gibt Belege zurück, optional nach Monat (YYYY-MM) oder Kategorie gefiltert."""
    conn = _get_conn()
    try:
        query = "SELECT * FROM belege WHERE 1=1"
        params: list = []
        if kategorie:
            query += " AND kategorie = ?"
            params.append(kategorie)
        if monat:
            query += " AND datum LIKE ?"
            params.append(f"{monat}%")
        query += " ORDER BY COALESCE(datum, erstellt_am) DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def get_zusammenfassung(monat: Optional[str] = None) -> dict:
    """Ausgaben-Zusammenfassung nach Kategorien."""
    conn = _get_conn()
    try:
        params: list = []
        date_filter = ""
        if monat:
            date_filter = "AND datum LIKE ?"
            params.append(f"{monat}%")

        kategorien = conn.execute(
            f"""
            SELECT  kategorie,
                    ROUND(SUM(gesamtbetrag), 2) AS gesamt,
                    COUNT(*) AS anzahl
            FROM    belege
            WHERE   gesamtbetrag IS NOT NULL {date_filter}
            GROUP   BY kategorie
            ORDER   BY gesamt DESC
            """,
            params,
        ).fetchall()

        total = conn.execute(
            f"""
            SELECT  ROUND(SUM(gesamtbetrag), 2) AS gesamt,
                    COUNT(*) AS anzahl
            FROM    belege
            WHERE   gesamtbetrag IS NOT NULL {date_filter}
            """,
            params,
        ).fetchone()

        return {
            "gesamt": total["gesamt"] or 0.0,
            "anzahl": total["anzahl"] or 0,
            "nach_kategorie": [dict(k) for k in kategorien],
        }
    finally:
        conn.close()


# ─── Export ────────────────────────────────────────────────────────────────────

EXPORT_FELDER = [
    "id", "quelle", "haendler", "datum", "gesamtbetrag", "waehrung",
    "kategorie", "mwst", "zahlungsart", "beleg_typ", "notizen", "erstellt_am",
]


def export_csv(output_path: str, monat: Optional[str] = None) -> int:
    """Exportiert Belege als CSV. Gibt Anzahl exportierter Zeilen zurück."""
    belege = get_belege(limit=100_000, monat=monat)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FELDER, extrasaction="ignore")
        writer.writeheader()
        for b in belege:
            writer.writerow({k: b.get(k) for k in EXPORT_FELDER})
    return len(belege)
