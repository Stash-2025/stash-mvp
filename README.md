# Stash – Intelligentes Ausgaben-Management

**Belege automatisch erfassen, analysieren und verwalten** – powered by Claude AI.

Stash kombiniert einen smarten E-Mail Spam-Filter mit automatischer Beleg-Erkennung. Kassenbons, Rechnungen und Bestellbestätigungen werden per Foto oder direkt aus dem E-Mail-Postfach analysiert, strukturiert und gespeichert.

---

## Web-Dashboard

```bash
python web_app.py
# → http://localhost:5000
```

Login mit `DASHBOARD_PASSWORD` aus `.env` (Standard: `stash`). Das Dashboard zeigt alle gespeicherten Belege mit Statistiken, Kategorie-Diagramm, Filterfunktion und Detailansicht pro Beleg.

---

## Features

| Feature | Beschreibung |
|---|---|
| 🌐 **Web-Dashboard** | Lokales Flask-Dashboard mit Login, Übersicht, Filter & Detail |
| 📧 **Spam-Filter** | Klassifiziert E-Mails automatisch als Spam / Normal / Wichtig |
| 🧾 **E-Mail-Belege** | Erkennt Rechnungen & Bestellbestätigungen (mit PDF/Bild-Anhängen) |
| 📷 **Foto-Belege** | Analysiert Kassenbons und Rechnungsfotos per Claude Vision |
| 📄 **PDF-Belege** | Verarbeitet PDF-Rechnungen (auch gescannte) direkt via Claude |
| 💾 **Datenbank** | Speichert alle Belege lokal in SQLite (`~/.stash/belege.db`) |
| 📊 **Übersicht** | Ausgaben-Zusammenfassung nach Kategorie und Monat |
| 📤 **CSV-Export** | Export für Excel / Buchhaltung |

---

## Setup

**1. Abhängigkeiten installieren:**
```bash
pip install -r requirements.txt
```

**2. Konfiguration:**
```bash
cp .env.example .env
# .env mit deinen Passwörtern und API-Key befüllen
```

**3. Fertig! Stash nutzen:**
```bash
python stash.py --help
```

---

## Befehle

### `filter` – Spam-Filter + automatische Beleg-Erkennung
```bash
python stash.py filter
```
- Prüft alle ungelesenen E-Mails in iCloud und Gmail
- Spam → Spam-Ordner, Normal → als gelesen markieren, Wichtig → Benachrichtigung
- Erkennt automatisch Belege in wichtigen/normalen E-Mails (einstellbar via `AUTO_BELEG_SCAN`)

---

### `scan` – Gezielter Beleg-Scan
```bash
python stash.py scan                # Letzte 30 Tage (Standard)
python stash.py scan --tage 60      # Letzte 60 Tage
```
- Durchsucht alle E-Mails des Zeitraums nach Belegen
- Analysiert PDF- und Bild-Anhänge mit Claude
- Bereits gespeicherte Belege werden übersprungen (kein Duplikat)

---

### `foto` – Beleg-Foto oder PDF analysieren
```bash
python stash.py foto kassenbon.jpg
python stash.py foto rechnung.pdf
python stash.py foto screenshot.png --kategorie "Restaurant & Café"
```
Unterstützte Formate: `JPG`, `PNG`, `GIF`, `WEBP`, `PDF`

**Was wird extrahiert:**
- Händler, Datum, Gesamtbetrag, Währung
- Kategorie (automatisch erkannt)
- MwSt, Zahlungsart
- Einzelne Artikel mit Preisen
- Beleg-Typ (Kassenbon / Rechnung / Online-Bestellung / …)

---

### `liste` – Gespeicherte Belege anzeigen
```bash
python stash.py liste                             # Letzte 20 Belege
python stash.py liste --monat 2025-03             # Nur März 2025
python stash.py liste --kategorie "Lebensmittel & Drogerie"
python stash.py liste --limit 50 --detail         # Mit Artikel-Details
```

---

### `zusammenfassung` – Ausgaben nach Kategorie
```bash
python stash.py zusammenfassung                   # Alle Belege
python stash.py zusammenfassung --monat 2025-03   # Nur März 2025
```

Beispiel-Output:
```
  Kategorie                     Anzahl        Gesamt
  ────────────────────────────  ──────  ────────────
  Lebensmittel & Drogerie           12       243,80 EUR
  Restaurant & Café                  8       156,40 EUR
  Transport & Mobilität              5        89,20 EUR
  ──────────────────────────────────────────────────
  GESAMT                            25       489,40 EUR
```

---

### `export` – CSV-Export für Buchhaltung
```bash
python stash.py export
python stash.py export --output ausgaben_2025_q1.csv --monat 2025-03
```

---

## App-Passwörter erstellen

### iCloud (tim.baer@icloud.com)
1. → [appleid.apple.com](https://appleid.apple.com)
2. Anmeldung & Sicherheit → App-spezifische Passwörter → `+`
3. Name: „Stash" → Passwort in `.env` als `ICLOUD_PASSWORD` eintragen

### Gmail (timbaer05@gmail.com)
1. → [myaccount.google.com](https://myaccount.google.com) → Sicherheit
2. 2-Faktor-Authentifizierung aktivieren (falls noch nicht)
3. App-Passwörter → „Mail" → Passwort in `.env` als `GMAIL_PASSWORD` eintragen

---

## Automatisch ausführen (Cron Job)

```bash
crontab -e
```

```cron
# Spam-Filter stündlich
0 * * * * cd /pfad/zum/projekt && python stash.py filter >> stash.log 2>&1

# Beleg-Scan täglich um 20:00 Uhr
0 20 * * * cd /pfad/zum/projekt && python stash.py scan --tage 2 >> stash.log 2>&1
```

---

## Datenspeicherung

Alle Belege werden lokal in einer SQLite-Datenbank gespeichert:
```
~/.stash/belege.db
```

Kein Cloud-Sync, keine externen Server – alle Daten bleiben auf deinem Gerät.

---

## Kategorien

| Kategorie | Beispiele |
|---|---|
| Lebensmittel & Drogerie | Supermarkt, Drogerie, Bäckerei |
| Restaurant & Café | Restaurants, Cafés, Imbiss, Lieferdienste |
| Transport & Mobilität | Tanken, ÖV-Tickets, Taxi, Parkhaus |
| Unterkunft & Reise | Hotel, Airbnb, Flug, Bahn |
| Kleidung & Mode | Kleidung, Schuhe, Accessoires |
| Elektronik & Technik | Computer, Handys, Software |
| Gesundheit & Apotheke | Arzt, Apotheke, Fitness |
| Unterhaltung & Freizeit | Kino, Konzerte, Sport, Bücher |
| Wohnen & Haushalt | Möbel, Heimwerk, Haushaltswaren |
| Büro & Arbeit | Büromaterial, Fachliteratur |
| Online-Shopping | Amazon, Zalando, etc. |
| Dienstleistungen | Handwerker, Friseur, Reinigung |
| Sonstiges | Alles andere |

---

## Server-Einstellungen

| Anbieter | IMAP Server | SMTP Server |
|---|---|---|
| iCloud | `imap.mail.me.com` | `smtp.mail.me.com` |
| Gmail | `imap.gmail.com` | `smtp.gmail.com` |
