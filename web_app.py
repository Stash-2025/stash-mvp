"""
Stash Web-Dashboard
Lokales Flask-Dashboard zur Anzeige und Verwaltung von Belegen.

Starten:
    python web_app.py
    → http://localhost:5000
"""

import json
import os
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask, flash, redirect, render_template,
    request, session, url_for,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "stash-dev-secret-bitte-aendern")

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "stash")

# ─── Auth ─────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        if request.form.get("password") == DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        error = "Falsches Passwort. Bitte erneut versuchen."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─── Datenbank-Hilfsfunktionen ────────────────────────────────────────────────

def _db():
    """Gibt eine DB-Verbindung zurück (liest aus dem Stash-System)."""
    from database import _get_conn
    return _get_conn()


def get_alle_monate() -> list[str]:
    conn = _db()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT substr(datum, 1, 7) AS monat
            FROM belege
            WHERE datum IS NOT NULL AND datum != ''
            ORDER BY monat DESC
            """
        ).fetchall()
        return [r["monat"] for r in rows if r["monat"]]
    finally:
        conn.close()


def get_alle_kategorien() -> list[str]:
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT kategorie FROM belege WHERE kategorie IS NOT NULL ORDER BY kategorie"
        ).fetchall()
        return [r["kategorie"] for r in rows]
    finally:
        conn.close()


def get_beleg_by_id(beleg_id: int) -> dict | None:
    conn = _db()
    try:
        row = conn.execute("SELECT * FROM belege WHERE id = ?", (beleg_id,)).fetchone()
        if not row:
            return None
        b = dict(row)
        b["artikel_list"] = json.loads(b.get("artikel") or "[]")
        return b
    finally:
        conn.close()


def get_belege_paginated(
    monat: str | None,
    kategorie: str | None,
    suche: str | None,
    page: int,
    per_page: int,
) -> tuple[list[dict], int]:
    """Gibt Belege (paginiert) und Gesamtanzahl zurück."""
    conn = _db()
    try:
        conditions = ["1=1"]
        params: list = []
        if monat:
            conditions.append("datum LIKE ?")
            params.append(f"{monat}%")
        if kategorie:
            conditions.append("kategorie = ?")
            params.append(kategorie)
        if suche:
            conditions.append("haendler LIKE ?")
            params.append(f"%{suche}%")

        where = " AND ".join(conditions)
        total = conn.execute(
            f"SELECT COUNT(*) FROM belege WHERE {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT * FROM belege WHERE {where}
            ORDER BY COALESCE(datum, erstellt_am) DESC
            LIMIT ? OFFSET ?
            """,
            params + [per_page, (page - 1) * per_page],
        ).fetchall()

        return [dict(r) for r in rows], total
    finally:
        conn.close()


# ─── Jinja2 Filter ────────────────────────────────────────────────────────────

@app.template_filter("betrag")
def fmt_betrag(value, waehrung="EUR"):
    if value is None:
        return "–"
    return f"{value:,.2f} {waehrung}".replace(",", "X").replace(".", ",").replace("X", ".")


@app.template_filter("datum_de")
def fmt_datum_de(value: str | None) -> str:
    if not value:
        return "–"
    try:
        dt = datetime.strptime(value[:10], "%Y-%m-%d")
        monate = [
            "", "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember",
        ]
        return f"{dt.day}. {monate[dt.month]} {dt.year}"
    except Exception:
        return value


@app.template_filter("monat_de")
def fmt_monat_de(value: str | None) -> str:
    if not value or len(value) < 7:
        return value or "–"
    try:
        dt = datetime.strptime(value[:7], "%Y-%m")
        monate = [
            "", "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember",
        ]
        return f"{monate[dt.month]} {dt.year}"
    except Exception:
        return value


@app.template_filter("quelle_icon")
def quelle_icon(value: str | None) -> str:
    return {"foto": "📷", "email": "📧", "pdf": "📄"}.get(value or "", "🧾")


@app.template_filter("kategorie_color")
def kategorie_color(index: int) -> str:
    palette = [
        "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
        "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#14b8a6",
        "#64748b", "#a78bfa", "#34d399",
    ]
    return palette[index % len(palette)]


# ─── Routen ───────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    current_month = datetime.now().strftime("%Y-%m")
    from database import get_zusammenfassung, get_belege

    summary_month = get_zusammenfassung(monat=current_month)
    summary_all = get_zusammenfassung()
    recent = get_belege(limit=6)

    # Chart-Daten: Top-Kategorien diesen Monat
    chart_labels = []
    chart_data = []
    chart_colors = [
        "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
        "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#14b8a6",
        "#64748b", "#a78bfa", "#34d399",
    ]
    for i, k in enumerate(summary_month["nach_kategorie"][:10]):
        chart_labels.append(k["kategorie"] or "Sonstiges")
        chart_data.append(round(k["gesamt"] or 0, 2))

    return render_template(
        "dashboard.html",
        summary_month=summary_month,
        summary_all=summary_all,
        recent=recent,
        current_month=current_month,
        chart_labels=json.dumps(chart_labels),
        chart_data=json.dumps(chart_data),
        chart_colors=json.dumps(chart_colors[: len(chart_labels)]),
    )


@app.route("/belege")
@login_required
def belege_liste():
    monat = request.args.get("monat") or None
    kategorie = request.args.get("kategorie") or None
    suche = request.args.get("suche") or None
    page = max(1, int(request.args.get("page", 1)))
    per_page = 25

    belege, total = get_belege_paginated(monat, kategorie, suche, page, per_page)
    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "belege.html",
        belege=belege,
        monat=monat,
        kategorie=kategorie,
        suche=suche,
        alle_monate=get_alle_monate(),
        alle_kategorien=get_alle_kategorien(),
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@app.route("/beleg/<int:beleg_id>")
@login_required
def beleg_detail(beleg_id):
    beleg = get_beleg_by_id(beleg_id)
    if not beleg:
        return render_template("404.html"), 404
    return render_template("beleg.html", beleg=beleg)


# ─── Start ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from database import DB_PATH
    print(f"\n{'═' * 52}")
    print("  💰  Stash Web-Dashboard")
    print(f"  Datenbank : {DB_PATH}")
    print(f"  URL       : http://localhost:5000")
    print(f"  Passwort  : (aus .env → DASHBOARD_PASSWORD)")
    print(f"{'═' * 52}\n")
    app.run(debug=False, host="127.0.0.1", port=5000)
