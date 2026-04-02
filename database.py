"""
Stash – Datenbankmodul
SQLite-Speicher für Benutzer, Belege und Rechnungen unter ~/.stash/belege.db
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
    conn.execute("PRAGMA foreign_keys = ON")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    # ── Benutzer-Tabelle ───────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            erstellt_am   TEXT    NOT NULL
        )
    """)

    # ── Belege-Tabelle ─────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS belege (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER REFERENCES users(id),
            quelle        TEXT    NOT NULL,
            quelle_id     TEXT,
            haendler      TEXT,
            datum         TEXT,
            gesamtbetrag  REAL,
            waehrung      TEXT    DEFAULT 'CHF',
            kategorie     TEXT,
            mwst          REAL,
            zahlungsart   TEXT,
            artikel       TEXT,
            beleg_typ     TEXT,
            notizen       TEXT,
            roh_daten     TEXT,
            erstellt_am   TEXT    NOT NULL
        )
    """)

    # ── Migration: user_id hinzufügen falls noch nicht vorhanden ───
    cols = {row[1] for row in conn.execute("PRAGMA table_info(belege)").fetchall()}
    if "user_id" not in cols:
        conn.execute("ALTER TABLE belege ADD COLUMN user_id INTEGER REFERENCES users(id)")

    # ── Unique-Index für (user_id, quelle_id) ─────────────────────
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_belege_quelle_id
        ON belege (quelle_id) WHERE quelle_id IS NOT NULL
    """)

    conn.commit()


# ═══════════════════════════════════════════════════════════════════
# Benutzer-Verwaltung
# ═══════════════════════════════════════════════════════════════════

def user_count() -> int:
    """Anzahl registrierter Benutzer."""
    conn = _get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def create_user(name: str, email: str, password_hash: str) -> dict:
    """
    Erstellt einen neuen Benutzer. Wirft ValueError wenn E-Mail bereits existiert.
    Gibt das neue Benutzer-Dict zurück.
    """
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash, erstellt_am) VALUES (?, ?, ?, ?)",
            (name.strip(), email.strip().lower(), password_hash, datetime.now().isoformat()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)
    except sqlite3.IntegrityError:
        raise ValueError(f"E-Mail-Adresse '{email}' ist bereits registriert.")
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[dict]:
    """Gibt Benutzer-Dict zurück oder None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Gibt Benutzer-Dict zurück oder None."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_user_profile(user_id: int, name: str, email: str) -> None:
    """Aktualisiert Name und E-Mail eines Benutzers. Wirft ValueError bei Duplikat-E-Mail."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE users SET name = ?, email = ? WHERE id = ?",
            (name.strip(), email.strip().lower(), user_id),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"Die E-Mail-Adresse '{email}' wird bereits verwendet.")
    finally:
        conn.close()


def update_user_password(user_id: int, password_hash: str) -> None:
    """Setzt ein neues Passwort (als Hash)."""
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# Belege – Schreiben
# ═══════════════════════════════════════════════════════════════════

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


def save_beleg(
    quelle: str,
    quelle_id: Optional[str],
    data: dict,
    user_id: Optional[int] = None,
) -> Optional[int]:
    """
    Speichert einen analysierten Beleg.
    user_id=None → sichtbar für alle Benutzer (CLI-Modus).
    Gibt neue ID zurück oder None wenn Duplikat.
    """
    conn = _get_conn()
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO belege
                (user_id, quelle, quelle_id, haendler, datum, gesamtbetrag, waehrung,
                 kategorie, mwst, zahlungsart, artikel, beleg_typ, notizen,
                 roh_daten, erstellt_am)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                quelle,
                quelle_id,
                data.get("haendler"),
                data.get("datum"),
                data.get("gesamtbetrag"),
                data.get("waehrung", "CHF"),
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


# ═══════════════════════════════════════════════════════════════════
# Belege – Lesen (mit Datentrennung per user_id)
# ═══════════════════════════════════════════════════════════════════

def _user_filter(user_id: Optional[int]) -> tuple[str, list]:
    """Gibt WHERE-Snippet + params zurück die Datentrennung sicherstellen.
    user_id=None → alle Belege (CLI), sonst: eigene + unzugeordnete."""
    if user_id is None:
        return "1=1", []
    return "(user_id = ? OR user_id IS NULL)", [user_id]


def get_belege(
    limit: int = 50,
    kategorie: Optional[str] = None,
    monat: Optional[str] = None,
    user_id: Optional[int] = None,
) -> list[dict]:
    """Gibt Belege zurück, gefiltert nach Benutzer, Monat und Kategorie."""
    conn = _get_conn()
    try:
        base_filter, params = _user_filter(user_id)
        query = f"SELECT * FROM belege WHERE {base_filter}"
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


def get_zusammenfassung(
    monat: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict:
    """Ausgaben-Zusammenfassung nach Kategorien (benutzerspezifisch)."""
    conn = _get_conn()
    try:
        base_filter, params = _user_filter(user_id)

        date_extra = ""
        if monat:
            date_extra = "AND datum LIKE ?"
            params = params + [f"{monat}%"]

        kategorien = conn.execute(
            f"""
            SELECT  kategorie,
                    ROUND(SUM(gesamtbetrag), 2) AS gesamt,
                    COUNT(*) AS anzahl
            FROM    belege
            WHERE   {base_filter} AND gesamtbetrag IS NOT NULL {date_extra}
            GROUP   BY kategorie
            ORDER   BY gesamt DESC
            """,
            params,
        ).fetchall()

        # params re-apply for total query
        total = conn.execute(
            f"""
            SELECT  ROUND(SUM(gesamtbetrag), 2) AS gesamt,
                    COUNT(*) AS anzahl
            FROM    belege
            WHERE   {base_filter} AND gesamtbetrag IS NOT NULL {date_extra}
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


def get_alle_kategorien_for_user(user_id: Optional[int] = None) -> list[str]:
    conn = _get_conn()
    try:
        base_filter, params = _user_filter(user_id)
        rows = conn.execute(
            f"SELECT DISTINCT kategorie FROM belege WHERE {base_filter} AND kategorie IS NOT NULL ORDER BY kategorie",
            params,
        ).fetchall()
        return [r["kategorie"] for r in rows]
    finally:
        conn.close()


def get_alle_monate_for_user(user_id: Optional[int] = None) -> list[str]:
    conn = _get_conn()
    try:
        base_filter, params = _user_filter(user_id)
        rows = conn.execute(
            f"""
            SELECT DISTINCT substr(datum, 1, 7) AS monat
            FROM belege
            WHERE {base_filter} AND datum IS NOT NULL AND datum != ''
            ORDER BY monat DESC
            """,
            params,
        ).fetchall()
        return [r["monat"] for r in rows if r["monat"]]
    finally:
        conn.close()


def get_beleg_by_id(beleg_id: int, user_id: Optional[int] = None) -> Optional[dict]:
    """Gibt einen Beleg zurück – prüft Eigentümerschaft wenn user_id angegeben."""
    conn = _get_conn()
    try:
        base_filter, params = _user_filter(user_id)
        row = conn.execute(
            f"SELECT * FROM belege WHERE id = ? AND {base_filter}",
            [beleg_id] + params,
        ).fetchone()
        if not row:
            return None
        b = dict(row)
        b["artikel_list"] = json.loads(b.get("artikel") or "[]")
        return b
    finally:
        conn.close()


def get_belege_paginated(
    monat: Optional[str],
    kategorie: Optional[str],
    suche: Optional[str],
    page: int,
    per_page: int,
    user_id: Optional[int] = None,
) -> tuple[list[dict], int]:
    """Gibt Belege (paginiert) und Gesamtanzahl zurück."""
    conn = _get_conn()
    try:
        base_filter, params = _user_filter(user_id)
        extra = ""
        if monat:
            extra += " AND datum LIKE ?"
            params.append(f"{monat}%")
        if kategorie:
            extra += " AND kategorie = ?"
            params.append(kategorie)
        if suche:
            extra += " AND haendler LIKE ?"
            params.append(f"%{suche}%")

        total = conn.execute(
            f"SELECT COUNT(*) FROM belege WHERE {base_filter}{extra}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT * FROM belege WHERE {base_filter}{extra}
            ORDER BY COALESCE(datum, erstellt_am) DESC
            LIMIT ? OFFSET ?
            """,
            params + [per_page, (page - 1) * per_page],
        ).fetchall()

        return [dict(r) for r in rows], total
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# Export
# ═══════════════════════════════════════════════════════════════════

EXPORT_FELDER = [
    "id", "quelle", "haendler", "datum", "gesamtbetrag", "waehrung",
    "kategorie", "mwst", "zahlungsart", "beleg_typ", "notizen", "erstellt_am",
]


def export_csv(
    output_path: str,
    monat: Optional[str] = None,
    user_id: Optional[int] = None,
) -> int:
    """Exportiert Belege als CSV. Gibt Anzahl exportierter Zeilen zurück."""
    belege = get_belege(limit=100_000, monat=monat, user_id=user_id)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FELDER, extrasaction="ignore")
        writer.writeheader()
        for b in belege:
            writer.writerow({k: b.get(k) for k in EXPORT_FELDER})
    return len(belege)
