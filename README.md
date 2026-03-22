# E-Mail Spam-Filter mit Claude AI

Filtert automatisch Spam aus **tim.baer@icloud.com** und **timbaer05@gmail.com** und benachrichtigt bei wichtigen Nachrichten.

## Setup

**1. Abhängigkeiten installieren:**
```bash
pip install -r requirements.txt
```

**2. Konfiguration:**
```bash
cp .env.example .env
# .env mit deinen Passwörtern befüllen
```

**3. Starten:**
```bash
python email_filter.py
```

---

## App-Passwörter erstellen (kein normales Passwort verwenden!)

### iCloud (tim.baer@icloud.com)
1. → [appleid.apple.com](https://appleid.apple.com)
2. Anmeldung & Sicherheit → App-spezifische Passwörter
3. „+" klicken → Name z.B. „Email Filter"
4. Das Passwort (`xxxx-xxxx-xxxx-xxxx`) in `.env` als `ICLOUD_PASSWORD` eintragen

### Gmail (timbaer05@gmail.com)
1. → [myaccount.google.com](https://myaccount.google.com) → Sicherheit
2. 2-Faktor-Authentifizierung aktivieren (falls noch nicht)
3. Sicherheit → App-Passwörter → „Mail" auswählen
4. Das Passwort (`xxxx xxxx xxxx xxxx`) in `.env` als `GMAIL_PASSWORD` eintragen

---

## Wie es funktioniert

Das Programm prüft **beide Konten nacheinander**:

1. Verbindet sich per IMAP mit iCloud und Gmail
2. Lädt ungelesene E-Mails (max. `BATCH_SIZE` pro Konto)
3. Claude AI klassifiziert alle E-Mails:
   - **🗑️ Spam** → wird in den Spam-Ordner verschoben
   - **📄 Normal** → wird als gelesen markiert
   - **⭐ Wichtig** → bleibt ungelesen + du bekommst eine Benachrichtigung
4. Sendet eine Zusammenfassungs-E-Mail an `NOTIFY_EMAIL` für wichtige Nachrichten

---

## Automatisch ausführen (Cron Job)

Jede Stunde automatisch laufen lassen:
```bash
crontab -e
# Folgendes einfügen (Pfad anpassen!):
0 * * * * cd /pfad/zum/projekt && python email_filter.py >> filter.log 2>&1
```

---

## Server-Einstellungen (bereits eingebaut)

| Anbieter | IMAP Server | SMTP Server |
|---|---|---|
| iCloud | `imap.mail.me.com` | `smtp.mail.me.com` |
| Gmail | `imap.gmail.com` | `smtp.gmail.com` |
