#!/usr/bin/env python3
"""
Stash – Intelligentes Ausgaben-Management mit Claude AI

Befehle:
  filter          E-Mail Spam-Filter ausführen (+ automatische Beleg-Erkennung)
  scan            E-Mails gezielt nach Belegen/Rechnungen durchsuchen
  foto            Beleg-Foto oder PDF analysieren und speichern
  liste           Gespeicherte Belege anzeigen
  zusammenfassung Ausgaben-Zusammenfassung nach Kategorie
  export          Belege als CSV exportieren

Beispiele:
  python stash.py filter
  python stash.py scan --tage 60
  python stash.py foto kassenbon.jpg
  python stash.py foto rechnung.pdf
  python stash.py liste --monat 2025-03
  python stash.py zusammenfassung
  python stash.py export --output ausgaben_2025.csv
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv

load_dotenv()


def _check_api_key() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        click.echo("❌ ANTHROPIC_API_KEY fehlt in der .env Datei.", err=True)
        sys.exit(1)


def _get_client():
    import anthropic
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _fmt_betrag(betrag, waehrung: str = "EUR") -> str:
    if betrag is None:
        return "–"
    return f"{betrag:,.2f} {waehrung}"


def _print_header(titel: str) -> None:
    click.echo(f"\n{'═'*60}")
    click.echo(f"  💰 STASH  |  {titel}")
    click.echo(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    click.echo(f"{'═'*60}")


# ─── CLI Gruppe ───────────────────────────────────────────────────────────────

@click.group(help="Stash – Intelligentes Ausgaben-Management mit Claude AI")
def cli():
    pass


# ─── filter ──────────────────────────────────────────────────────────────────

@cli.command(name="filter", help="E-Mail Spam-Filter ausführen (+ automatische Beleg-Erkennung).")
def cmd_filter():
    _check_api_key()
    from email_filter import run_filter, ACCOUNTS
    if not ACCOUNTS:
        click.echo("❌ Keine E-Mail-Konten konfiguriert. Bitte .env befüllen.")
        sys.exit(1)
    run_filter()


# ─── scan ─────────────────────────────────────────────────────────────────────

@cli.command(name="scan", help="E-Mails der letzten N Tage gezielt nach Belegen scannen.")
@click.option("--tage", default=30, show_default=True, help="Wie viele Tage zurück scannen?")
def cmd_scan(tage: int):
    _check_api_key()
    from email_filter import run_receipt_scan, ACCOUNTS
    if not ACCOUNTS:
        click.echo("❌ Keine E-Mail-Konten konfiguriert. Bitte .env befüllen.")
        sys.exit(1)
    run_receipt_scan(days=tage)


# ─── foto ─────────────────────────────────────────────────────────────────────

@cli.command(name="foto", help="Beleg-Foto (JPG/PNG/WEBP) oder PDF analysieren und speichern.")
@click.argument("pfad", type=click.Path(exists=True, dir_okay=False))
@click.option("--kategorie", default=None, help="Kategorie manuell überschreiben.")
def cmd_foto(pfad: str, kategorie: str | None):
    _check_api_key()
    client = _get_client()

    path = Path(pfad)
    suffix = path.suffix.lower()

    _print_header(f"Beleg-Analyse: {path.name}")

    click.echo(f"\n📂 Datei: {path.resolve()}")
    click.echo("🤖 Claude analysiert den Beleg...\n")

    from receipt_analyzer import analyze_image_file, analyze_pdf_bytes, SUPPORTED_IMAGE_TYPES
    from database import save_beleg, beleg_exists

    quelle_id = str(path.resolve())

    if beleg_exists(quelle_id):
        click.echo("ℹ️  Dieser Beleg wurde bereits gespeichert.\n")
        click.echo("   Nutze 'stash liste' um ihn anzusehen.")
        return

    try:
        if suffix == ".pdf":
            data = analyze_pdf_bytes(path.read_bytes(), client)
            quelle = "pdf"
        elif suffix in SUPPORTED_IMAGE_TYPES:
            data = analyze_image_file(pfad, client)
            quelle = "foto"
        else:
            supported = ", ".join(list(SUPPORTED_IMAGE_TYPES.keys()) + [".pdf"])
            click.echo(f"❌ Nicht unterstütztes Format: {suffix}")
            click.echo(f"   Unterstützt: {supported}")
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Analyse fehlgeschlagen: {e}", err=True)
        sys.exit(1)

    if kategorie:
        data["kategorie"] = kategorie

    # Ergebnis anzeigen
    _print_beleg_detail(data)

    # Speichern
    beleg_id = save_beleg(quelle, quelle_id, data)
    if beleg_id:
        click.echo(f"\n✅ Beleg gespeichert (ID: {beleg_id})\n")
    else:
        click.echo("\nℹ️  Beleg war bereits gespeichert.\n")


def _print_beleg_detail(data: dict) -> None:
    """Gibt einen Beleg detailliert in der Konsole aus."""
    def row(label: str, value) -> None:
        if value is not None:
            click.echo(f"  {label:<18} {value}")

    click.echo(f"\n{'─'*60}")
    row("🏪 Händler:",        data.get("haendler") or "–")
    row("📅 Datum:",          data.get("datum") or "–")
    row("💶 Betrag:",         _fmt_betrag(data.get("gesamtbetrag"), data.get("waehrung", "EUR")))
    row("🏷️  Kategorie:",     data.get("kategorie") or "–")
    row("💳 Zahlungsart:",    data.get("zahlungsart") or "–")
    row("🧾 Beleg-Typ:",      data.get("beleg_typ") or "–")

    if data.get("mwst") is not None:
        row("📊 MwSt:",       _fmt_betrag(data.get("mwst"), data.get("waehrung", "EUR")))

    artikel = data.get("artikel")
    if artikel and isinstance(artikel, list) and len(artikel) > 0:
        click.echo(f"\n  {'Artikel':<30} {'Menge':>6}  {'Preis':>10}")
        click.echo(f"  {'─'*50}")
        for a in artikel[:15]:  # max 15 Artikel anzeigen
            name = str(a.get("bezeichnung") or "")[:30]
            menge = a.get("menge", 1)
            preis = a.get("gesamtpreis") or a.get("einzelpreis")
            preis_str = _fmt_betrag(preis, "") if preis else "–"
            click.echo(f"  {name:<30} {str(menge):>6}  {preis_str:>10}")
        if len(artikel) > 15:
            click.echo(f"  ... und {len(artikel) - 15} weitere Artikel")

    if data.get("notizen"):
        click.echo(f"\n  📝 {data['notizen']}")

    click.echo(f"{'─'*60}")


# ─── liste ────────────────────────────────────────────────────────────────────

@cli.command(name="liste", help="Gespeicherte Belege anzeigen.")
@click.option("--monat",     default=None, help="Monat filtern, Format: YYYY-MM")
@click.option("--kategorie", default=None, help="Kategorie filtern")
@click.option("--limit",     default=20,   show_default=True, help="Anzahl Belege")
@click.option("--detail",    is_flag=True, help="Detailansicht mit Artikeln")
def cmd_liste(monat: str | None, kategorie: str | None, limit: int, detail: bool):
    from database import get_belege

    filter_info = []
    if monat:
        filter_info.append(f"Monat: {monat}")
    if kategorie:
        filter_info.append(f"Kategorie: {kategorie}")

    _print_header("Belege" + (f" – {', '.join(filter_info)}" if filter_info else ""))

    belege = get_belege(limit=limit, kategorie=kategorie, monat=monat)

    if not belege:
        click.echo("\n  Keine Belege gefunden.\n")
        return

    click.echo(f"\n  {len(belege)} Beleg(e) gefunden:\n")
    click.echo(f"  {'ID':>4}  {'Datum':<12}  {'Händler':<25}  {'Betrag':>12}  {'Kategorie'}")
    click.echo(f"  {'─'*4}  {'─'*12}  {'─'*25}  {'─'*12}  {'─'*20}")

    for b in belege:
        datum = b.get("datum") or b.get("erstellt_am", "")[:10]
        haendler = (b.get("haendler") or "–")[:25]
        betrag = _fmt_betrag(b.get("gesamtbetrag"), b.get("waehrung", "EUR"))
        kat = (b.get("kategorie") or "–")[:20]
        quelle_icon = {"foto": "📷", "email": "📧", "pdf": "📄"}.get(b.get("quelle", ""), "📋")
        click.echo(f"  {b['id']:>4}  {datum:<12}  {haendler:<25}  {betrag:>12}  {kat}  {quelle_icon}")

        if detail:
            import json as _json
            raw = _json.loads(b.get("roh_daten") or "{}")
            _print_beleg_detail(raw)

    click.echo()


# ─── zusammenfassung ─────────────────────────────────────────────────────────

@cli.command(name="zusammenfassung", help="Ausgaben-Zusammenfassung nach Kategorie.")
@click.option("--monat", default=None, help="Monat filtern, Format: YYYY-MM (z.B. 2025-03)")
def cmd_zusammenfassung(monat: str | None):
    from database import get_zusammenfassung

    titel = f"Zusammenfassung – {monat}" if monat else "Zusammenfassung – Gesamt"
    _print_header(titel)

    summary = get_zusammenfassung(monat=monat)

    if summary["anzahl"] == 0:
        click.echo("\n  Keine Belege gefunden.\n")
        return

    click.echo(f"\n  {'Kategorie':<28}  {'Anzahl':>6}  {'Gesamt':>12}")
    click.echo(f"  {'─'*28}  {'─'*6}  {'─'*12}")

    for k in summary["nach_kategorie"]:
        kat = (k.get("kategorie") or "Ohne Kategorie")[:28]
        anzahl = k.get("anzahl", 0)
        gesamt = _fmt_betrag(k.get("gesamt"))
        click.echo(f"  {kat:<28}  {anzahl:>6}  {gesamt:>12}")

    click.echo(f"\n  {'─'*50}")
    click.echo(f"  {'GESAMT':<28}  {summary['anzahl']:>6}  {_fmt_betrag(summary['gesamt']):>12}")
    click.echo()


# ─── export ──────────────────────────────────────────────────────────────────

@cli.command(name="export", help="Belege als CSV-Datei exportieren.")
@click.option("--output", default="belege_export.csv", show_default=True, help="Ausgabedatei")
@click.option("--monat",  default=None, help="Monat filtern, Format: YYYY-MM")
def cmd_export(output: str, monat: str | None):
    from database import export_csv

    _print_header("CSV-Export")

    filter_info = f" (Monat: {monat})" if monat else ""
    click.echo(f"\n📤 Exportiere Belege{filter_info} → {output}\n")

    try:
        count = export_csv(output, monat=monat)
        click.echo(f"✅ {count} Beleg(e) exportiert nach: {Path(output).resolve()}\n")
    except Exception as e:
        click.echo(f"❌ Export fehlgeschlagen: {e}", err=True)
        sys.exit(1)


# ─── Einstiegspunkt ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
