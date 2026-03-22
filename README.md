# E-Mail Spam-Filter mit Claude AI

Filtert automatisch Spam-E-Mails und benachrichtigt dich bei wichtigen Nachrichten.

## Setup

**1. Abhängigkeiten installieren:**
```bash
pip install -r requirements.txt
```

**2. Konfiguration:**
```bash
cp .env.example .env
# .env mit deinen Daten befüllen
```

**3. Starten:**
```bash
python email_filter.py
```

## .env Konfiguration

| Variable | Beschreibung |
|---|---|
| `ANTHROPIC_API_KEY` | Dein Anthropic API Key |
| `EMAIL_ADDRESS` | Deine E-Mail-Adresse |
| `EMAIL_PASSWORD` | App-Passwort (nicht dein normales Passwort!) |
| `IMAP_SERVER` | IMAP Server (z.B. `imap.gmail.com`) |
| `SMTP_SERVER` | SMTP Server (z.B. `smtp.gmail.com`) |
| `NOTIFY_EMAIL` | Wohin Benachrichtigungen gesendet werden |
| `BATCH_SIZE` | Wie viele E-Mails auf einmal geprüft werden (Standard: 20) |

## Gmail App-Passwort erstellen

1. Google Konto → Sicherheit → 2-Faktor-Authentifizierung aktivieren
2. Sicherheit → App-Passwörter → "Mail" + "Windows-Computer" auswählen
3. Das generierte Passwort in `.env` als `EMAIL_PASSWORD` eintragen

## Wie es funktioniert

1. Verbindet sich per IMAP mit deinem Posteingang
2. Lädt ungelesene E-Mails (max. `BATCH_SIZE`)
3. Claude AI klassifiziert alle E-Mails auf einmal:
   - **🗑️ Spam**: Wird in den Spam-Ordner verschoben
   - **📄 Normal**: Wird als gelesen markiert
   - **⭐ Wichtig**: Bleibt ungelesen + du bekommst eine Benachrichtigung
4. Sendet eine Zusammenfassungs-E-Mail für wichtige Nachrichten

## Automatisch ausführen (Cron Job)

Jede Stunde automatisch ausführen:
```bash
crontab -e
# Folgendes hinzufügen:
0 * * * * cd /pfad/zum/projekt && python email_filter.py >> filter.log 2>&1
```
