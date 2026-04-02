"""
Stash Web-Dashboard
Lokales Flask-Dashboard mit sicherem Mehrbenutzer-Login.

Starten:
    python web_app.py
    → http://localhost:5000

Erster Start – Konto erstellen:
    python stash.py user create
"""

import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask, flash, redirect, render_template,
    request, session, url_for,
)
from flask_login import (
    LoginManager, UserMixin,
    current_user, login_required, login_user, logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

import database as db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "stash-dev-secret-bitte-aendern")

# ─── Flask-Login ─────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = None  # Stille Weiterleitung


class User(UserMixin):
    def __init__(self, id, name, email, password_hash):
        self.id = id
        self.name = name
        self.email = email
        self.password_hash = password_hash

    @property
    def vorname(self) -> str:
        """Erster Vorname für Begrüssung."""
        return self.name.split()[0] if self.name else self.name


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    data = db.get_user_by_id(int(user_id))
    if data:
        return User(data["id"], data["name"], data["email"], data["password_hash"])
    return None


# ─── Jinja2 Filter ───────────────────────────────────────────────

@app.template_filter("betrag")
def fmt_betrag(value, waehrung="CHF"):
    if value is None:
        return "–"
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "'")
    return f"{formatted} {waehrung}"


@app.template_filter("datum_de")
def fmt_datum_de(value: str | None) -> str:
    if not value:
        return "–"
    try:
        dt = datetime.strptime(value[:10], "%Y-%m-%d")
        monate = ["", "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                  "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
        return f"{dt.day:02d}. {monate[dt.month]} {dt.year}"
    except Exception:
        return value


@app.template_filter("monat_de")
def fmt_monat_de(value: str | None) -> str:
    if not value or len(value) < 7:
        return value or "–"
    try:
        dt = datetime.strptime(value[:7], "%Y-%m")
        monate = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
                  "Juli", "August", "September", "Oktober", "November", "Dezember"]
        return f"{monate[dt.month]} {dt.year}"
    except Exception:
        return value


@app.template_filter("quelle_icon")
def quelle_icon(value: str | None) -> str:
    return {"foto": "foto", "email": "email", "pdf": "pdf"}.get(value or "", "beleg")


@app.template_filter("kategorie_color")
def kategorie_color(index: int) -> str:
    palette = [
        "#1DB584", "#175CD3", "#B54708", "#C01048", "#6941C6",
        "#0E7090", "#067647", "#B93815", "#3538CD", "#026AA2",
        "#344054", "#027A48",
    ]
    return palette[index % len(palette)]


@app.template_filter("betrag_zahl")
def fmt_betrag_zahl(value) -> str:
    """Nur die Zahl formatiert (ohne Währung), Swiss-Stil: 1'234,50"""
    if value is None:
        return "–"
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "'")


@app.template_filter("merchant_initial")
def fmt_merchant_initial(value: str | None) -> str:
    """'Migros' → 'Mi', 'Coop Pronto' → 'CP'"""
    if not value:
        return "?"
    words = str(value).strip().split()
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return str(value)[:2].upper()


@app.template_filter("merchant_color")
def fmt_merchant_color(value: str | None) -> str:
    """Konsistente Avatar-Farbe je Händlername (hash-basiert)."""
    palette = [
        "#1DB584", "#175CD3", "#B54708", "#C01048", "#6941C6",
        "#0E7090", "#067647", "#B93815", "#3538CD", "#026AA2",
    ]
    if not value:
        return palette[0]
    idx = sum(ord(c) for c in str(value)) % len(palette)
    return palette[idx]


@app.template_filter("tx_date_label")
def fmt_tx_date_label(value: str | None) -> str:
    """'2025-04-15' → 'Heute' / 'Gestern' / 'Dienstag, 15. April'"""
    if not value:
        return "Unbekannt"
    try:
        d = datetime.strptime(value[:10], "%Y-%m-%d").date()
        today = date.today()
        if d == today:
            return "Heute"
        if d == today - timedelta(days=1):
            return "Gestern"
        weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
                    "Freitag", "Samstag", "Sonntag"]
        monate   = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
                    "Juli", "August", "September", "Oktober", "November", "Dezember"]
        return f"{weekdays[d.weekday()]}, {d.day}. {monate[d.month]}"
    except Exception:
        return value


# ─── Monats-Helfer ───────────────────────────────────────────────

def _prev_month(ym: str) -> str:
    try:
        dt = datetime.strptime(ym, "%Y-%m")
        return f"{dt.year - 1}-12" if dt.month == 1 else f"{dt.year}-{dt.month - 1:02d}"
    except Exception:
        return ym


def _next_month(ym: str) -> str:
    try:
        dt = datetime.strptime(ym, "%Y-%m")
        return f"{dt.year + 1}-01" if dt.month == 12 else f"{dt.year}-{dt.month + 1:02d}"
    except Exception:
        return ym


# ─── Tagesgruss ──────────────────────────────────────────────────

def tagesgruss() -> str:
    h = datetime.now().hour
    if 5 <= h < 12:
        return "Guten Morgen"
    elif 12 <= h < 17:
        return "Guten Tag"
    else:
        return "Guten Abend"


# ─── Erster Start: Setup ─────────────────────────────────────────

@app.before_request
def check_setup():
    """Leitet beim ersten Start zur Einrichtungsseite weiter."""
    public = {"setup", "static", "login"}
    if request.endpoint and request.endpoint not in public:
        if db.user_count() == 0:
            return redirect(url_for("setup"))


# ─── Auth: Login / Logout ─────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    # Beim ersten Start direkt zur Einrichtung
    if db.user_count() == 0:
        return redirect(url_for("setup"))

    error = None
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            error = "Bitte E-Mail und Passwort eingeben."
        else:
            user_data = db.get_user_by_email(email)
            if user_data and check_password_hash(user_data["password_hash"], password):
                user = User(
                    user_data["id"], user_data["name"],
                    user_data["email"], user_data["password_hash"],
                )
                login_user(user, remember=True)
                return redirect(request.args.get("next") or url_for("dashboard"))
            else:
                error = "E-Mail-Adresse oder Passwort ist nicht korrekt."

    return render_template("login.html", error=error)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ─── Erster Start: Konto einrichten ──────────────────────────────

@app.route("/setup", methods=["GET", "POST"])
def setup():
    """Nur beim ersten Start sichtbar – legt den ersten Benutzer an."""
    if db.user_count() > 0:
        return redirect(url_for("login"))

    errors = {}
    form   = {}

    if request.method == "POST":
        form["name"]     = request.form.get("name", "").strip()
        form["email"]    = request.form.get("email", "").strip().lower()
        form["password"] = request.form.get("password", "")
        form["password2"] = request.form.get("password2", "")

        if not form["name"]:
            errors["name"] = "Name ist erforderlich."
        if not form["email"] or "@" not in form["email"]:
            errors["email"] = "Gültige E-Mail-Adresse eingeben."
        if len(form["password"]) < 8:
            errors["password"] = "Passwort muss mindestens 8 Zeichen haben."
        elif form["password"] != form["password2"]:
            errors["password2"] = "Passwörter stimmen nicht überein."

        if not errors:
            pw_hash = generate_password_hash(form["password"])
            try:
                user_data = db.create_user(form["name"], form["email"], pw_hash)
                user = User(user_data["id"], user_data["name"],
                            user_data["email"], user_data["password_hash"])
                login_user(user)
                return redirect(url_for("dashboard"))
            except ValueError as e:
                errors["email"] = str(e)

    return render_template("setup.html", errors=errors, form=form)


# ─── Profil ───────────────────────────────────────────────────────

@app.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    success = request.args.get("success")
    errors  = {}

    if request.method == "POST":
        action = request.form.get("action")

        # ── Profilangaben ändern ──────────────────────────────────
        if action == "profil":
            name  = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()

            if not name:
                errors["name"] = "Name darf nicht leer sein."
            if not email or "@" not in email:
                errors["email"] = "Gültige E-Mail-Adresse eingeben."

            if not errors:
                try:
                    db.update_user_profile(current_user.id, name, email)
                    # Session-User aktualisieren (reload via flask-login)
                    updated = db.get_user_by_id(current_user.id)
                    login_user(User(updated["id"], updated["name"],
                                    updated["email"], updated["password_hash"]),
                               remember=True)
                    return redirect(url_for("profil", success="profil"))
                except ValueError as e:
                    errors["email"] = str(e)

        # ── Passwort ändern ───────────────────────────────────────
        elif action == "passwort":
            current_pw = request.form.get("current_password", "")
            new_pw     = request.form.get("new_password", "")
            new_pw2    = request.form.get("new_password2", "")

            user_data = db.get_user_by_id(current_user.id)
            if not check_password_hash(user_data["password_hash"], current_pw):
                errors["current_password"] = "Aktuelles Passwort ist nicht korrekt."
            elif len(new_pw) < 8:
                errors["new_password"] = "Neues Passwort muss mindestens 8 Zeichen haben."
            elif new_pw != new_pw2:
                errors["new_password2"] = "Passwörter stimmen nicht überein."

            if not errors:
                db.update_user_password(current_user.id, generate_password_hash(new_pw))
                return redirect(url_for("profil", success="passwort"))

    return render_template("profil.html", errors=errors, success=success)


# ─── Passwort vergessen ───────────────────────────────────────────

@app.route("/passwort-vergessen")
def passwort_vergessen():
    return render_template("passwort_vergessen.html")


# ─── Dashboard ────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    today         = datetime.now()
    actual_month  = today.strftime("%Y-%m")
    selected_month = request.args.get("monat") or actual_month
    uid = current_user.id

    summary_month = db.get_zusammenfassung(monat=selected_month, user_id=uid)
    summary_prev  = db.get_zusammenfassung(monat=_prev_month(selected_month), user_id=uid)

    # Prozentuale Änderung zum Vormonat
    prev_total    = summary_prev.get("gesamt") or 0
    curr_total    = summary_month.get("gesamt") or 0
    if prev_total and prev_total != 0:
        change_pct = ((curr_total - prev_total) / prev_total) * 100
    else:
        change_pct = None

    # Durchschnitt pro Beleg
    anzahl = summary_month.get("anzahl") or 0
    avg_per_beleg = (curr_total / anzahl) if anzahl else None

    # Alle Belege des Monats, nach Datum gruppiert
    all_belege = db.get_belege(limit=500, user_id=uid, monat=selected_month)
    groups: dict[str, list] = defaultdict(list)
    for b in all_belege:
        key = (b.get("datum") or b.get("erstellt_am", "")[:10] or "0000-00-00")[:10]
        groups[key].append(b)
    grouped_tx = [{"date": d, "belege": groups[d]} for d in sorted(groups.keys(), reverse=True)]

    prev_month = _prev_month(selected_month)
    next_month = _next_month(selected_month)

    return render_template(
        "dashboard.html",
        gruss=tagesgruss(),
        vorname=current_user.vorname,
        summary_month=summary_month,
        current_month=selected_month,
        grouped_tx=grouped_tx,
        prev_month=prev_month,
        next_month=next_month,
        is_current_month=(selected_month == actual_month),
        change_pct=change_pct,
        avg_per_beleg=avg_per_beleg,
    )


# ─── Reports ──────────────────────────────────────────────────────

@app.route("/reports")
@login_required
def reports():
    uid = current_user.id
    summary_all = db.get_zusammenfassung(user_id=uid)
    alle_monate = db.get_alle_monate_for_user(uid)

    chart_labels = []
    chart_data   = []
    chart_colors = [
        "#1DB584", "#175CD3", "#B54708", "#C01048", "#6941C6",
        "#0E7090", "#067647", "#B93815", "#3538CD", "#026AA2",
        "#344054", "#027A48",
    ]
    for k in summary_all["nach_kategorie"][:10]:
        chart_labels.append(k["kategorie"] or "Sonstiges")
        chart_data.append(round(k["gesamt"] or 0, 2))

    return render_template(
        "reports.html",
        summary_all=summary_all,
        alle_monate=alle_monate,
        chart_labels=json.dumps(chart_labels),
        chart_data=json.dumps(chart_data),
        chart_colors=json.dumps(chart_colors[: len(chart_labels)]),
    )


# ─── Belege-Liste ─────────────────────────────────────────────────

@app.route("/belege")
@login_required
def belege_liste():
    monat     = request.args.get("monat") or None
    kategorie = request.args.get("kategorie") or None
    suche     = request.args.get("suche") or None
    page      = max(1, int(request.args.get("page", 1)))
    per_page  = 25
    uid       = current_user.id

    belege, total = db.get_belege_paginated(monat, kategorie, suche, page, per_page, user_id=uid)
    total_pages   = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "belege.html",
        belege=belege,
        monat=monat,
        kategorie=kategorie,
        suche=suche,
        alle_monate=db.get_alle_monate_for_user(uid),
        alle_kategorien=db.get_alle_kategorien_for_user(uid),
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


# ─── Beleg-Detail ─────────────────────────────────────────────────

@app.route("/beleg/<int:beleg_id>")
@login_required
def beleg_detail(beleg_id):
    beleg = db.get_beleg_by_id(beleg_id, user_id=current_user.id)
    if not beleg:
        return render_template("404.html"), 404
    return render_template("beleg.html", beleg=beleg)


# ─── Start ────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{'═' * 54}")
    print("  💰  Stash Web-Dashboard")
    print(f"  Datenbank : {db.DB_PATH}")
    print(f"  URL       : http://localhost:5000")
    if db.user_count() == 0:
        print(f"  Hinweis   : Noch kein Konto. Erstelle eines unter")
        print(f"              http://localhost:5000/setup")
        print(f"              oder: python stash.py user create")
    print(f"{'═' * 54}\n")
    app.run(debug=False, host="127.0.0.1", port=5000)
