"""
E-Mail Spam-Filter mit Claude AI
- Liest E-Mails per IMAP
- Klassifiziert sie mit Claude (Spam / Normal / Wichtig)
- Verschiebt Spam automatisch in den Spam-Ordner
- Sendet Benachrichtigung für wichtige E-Mails
"""

import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import anthropic

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", EMAIL_ADDRESS)
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def decode_str(value: str) -> str:
    """Dekodiert E-Mail-Header (z.B. UTF-8, Base64)."""
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                decoded.append(part.decode("latin-1", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def get_email_body(msg) -> str:
    """Extrahiert den Text-Body einer E-Mail (max. 2000 Zeichen)."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
                except Exception:
                    pass
            elif content_type == "text/html" and not body:
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            body = ""
    return body[:2000]


def classify_emails_with_claude(emails: list[dict]) -> list[dict]:
    """
    Klassifiziert mehrere E-Mails auf einmal mit Claude.
    Gibt für jede E-Mail zurück: kategorie (spam/normal/wichtig) + begruendung
    """
    email_list_text = ""
    for i, e in enumerate(emails):
        email_list_text += f"""
--- E-Mail {i+1} ---
Von: {e['from']}
Betreff: {e['subject']}
Datum: {e['date']}
Inhalt (Auszug): {e['body'][:500]}
"""

    prompt = f"""Du bist ein intelligenter E-Mail-Filter. Analysiere die folgenden E-Mails und klassifiziere jede als:
- "spam": Werbung, Newsletter ohne Relevanz, verdächtige Absender, Phishing, automatische Benachrichtigungen ohne Handlungsbedarf
- "normal": Normale E-Mails, die gelesen werden können, aber keine sofortige Reaktion erfordern
- "wichtig": E-Mails, die sofortige Aufmerksamkeit erfordern (persönliche Nachrichten, wichtige Termine, finanzielle Angelegenheiten, dringende Anfragen, Sicherheitswarnungen)

Antworte NUR mit einem JSON-Array. Für jede E-Mail ein Objekt mit:
- "index": Nummer der E-Mail (beginnend bei 0)
- "kategorie": "spam", "normal" oder "wichtig"
- "begruendung": Kurze Begründung (1 Satz)

Beispiel: [{{"index": 0, "kategorie": "spam", "begruendung": "Newsletter von Online-Shop"}}, ...]

E-Mails zum Analysieren:
{email_list_text}

JSON-Antwort:"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    result_text = response.content[0].text.strip()

    # JSON aus der Antwort extrahieren
    if "```" in result_text:
        result_text = result_text.split("```")[1]
        if result_text.startswith("json"):
            result_text = result_text[4:]

    classifications = json.loads(result_text)

    for item in classifications:
        idx = item["index"]
        emails[idx]["kategorie"] = item["kategorie"]
        emails[idx]["begruendung"] = item["begruendung"]

    return emails


def move_to_spam(imap: imaplib.IMAP4_SSL, email_id: bytes):
    """Verschiebt eine E-Mail in den Spam-Ordner."""
    spam_folders = ["[Gmail]/Spam", "Junk", "Spam", "SPAM", "Junk E-Mail"]
    for folder in spam_folders:
        try:
            result = imap.copy(email_id, folder)
            if result[0] == "OK":
                imap.store(email_id, "+FLAGS", "\\Deleted")
                return True
        except Exception:
            continue
    # Falls kein Spam-Ordner gefunden: nur als gelesen markieren
    imap.store(email_id, "+FLAGS", "\\Seen")
    return False


def send_notification(wichtige_emails: list[dict]):
    """Sendet eine Benachrichtigungs-E-Mail für wichtige Mails."""
    if not wichtige_emails:
        return

    subject = f"🔔 {len(wichtige_emails)} wichtige E-Mail(s) erhalten"

    body_lines = ["Du hast folgende wichtige E-Mails erhalten:\n"]
    for i, e in enumerate(wichtige_emails, 1):
        body_lines.append(f"{i}. Von: {e['from']}")
        body_lines.append(f"   Betreff: {e['subject']}")
        body_lines.append(f"   Datum: {e['date']}")
        body_lines.append(f"   Grund: {e['begruendung']}")
        body_lines.append("")

    body = "\n".join(body_lines)

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

    print(f"✉️  Benachrichtigung gesendet an {NOTIFY_EMAIL}")


def run_filter():
    """Hauptfunktion: E-Mails lesen, klassifizieren, verarbeiten."""
    print(f"\n{'='*60}")
    print(f"E-Mail Spam-Filter gestartet: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"{'='*60}\n")

    # IMAP-Verbindung aufbauen
    print(f"🔌 Verbinde mit {IMAP_SERVER}...")
    imap = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    imap.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

    # Posteingang öffnen
    imap.select("INBOX")
    print("📬 Posteingang geöffnet\n")

    # Ungelesene E-Mails suchen
    _, message_ids = imap.search(None, "UNSEEN")
    all_ids = message_ids[0].split()

    if not all_ids:
        print("✅ Keine ungelesenen E-Mails gefunden.")
        imap.logout()
        return

    # Nur die letzten BATCH_SIZE E-Mails verarbeiten
    ids_to_process = all_ids[-BATCH_SIZE:]
    print(f"📧 {len(all_ids)} ungelesene E-Mail(s) gefunden.")
    print(f"🔍 Verarbeite {len(ids_to_process)} E-Mail(s) (neueste zuerst)...\n")

    # E-Mails laden
    emails_data = []
    for email_id in reversed(ids_to_process):
        _, msg_data = imap.fetch(email_id, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        emails_data.append({
            "id": email_id,
            "from": decode_str(msg.get("From", "")),
            "subject": decode_str(msg.get("Subject", "(kein Betreff)")),
            "date": msg.get("Date", ""),
            "body": get_email_body(msg),
            "kategorie": "normal",
            "begruendung": "",
        })

    # Claude klassifiziert alle E-Mails auf einmal
    print("🤖 Claude analysiert E-Mails...")
    classified = classify_emails_with_claude(emails_data)

    # Statistik
    stats = {"spam": 0, "normal": 0, "wichtig": 0}
    wichtige_emails = []

    print("\n📊 Ergebnis:\n")
    for e in classified:
        kategorie = e["kategorie"]
        stats[kategorie] = stats.get(kategorie, 0) + 1

        icon = {"spam": "🗑️ SPAM", "normal": "📄 Normal", "wichtig": "⭐ WICHTIG"}[kategorie]
        print(f"{icon} | Von: {e['from'][:40]}")
        print(f"        Betreff: {e['subject'][:50]}")
        print(f"        Grund: {e['begruendung']}\n")

        if kategorie == "spam":
            move_to_spam(imap, e["id"])
        elif kategorie == "wichtig":
            wichtige_emails.append(e)
            # Wichtige E-Mails als ungelesen lassen
        else:
            # Normale E-Mails als gelesen markieren
            imap.store(e["id"], "+FLAGS", "\\Seen")

    # Gelöschte Mails endgültig entfernen
    imap.expunge()
    imap.logout()

    # Zusammenfassung
    print(f"\n{'='*60}")
    print("📈 Zusammenfassung:")
    print(f"   ⭐ Wichtig:  {stats.get('wichtig', 0)}")
    print(f"   📄 Normal:   {stats.get('normal', 0)}")
    print(f"   🗑️  Spam:     {stats.get('spam', 0)}")
    print(f"{'='*60}\n")

    # Benachrichtigung senden
    if wichtige_emails:
        print("📨 Sende Benachrichtigung für wichtige E-Mails...")
        send_notification(wichtige_emails)

    print("✅ Fertig!\n")


if __name__ == "__main__":
    # Konfiguration prüfen
    missing = []
    for var in ["ANTHROPIC_API_KEY", "EMAIL_ADDRESS", "EMAIL_PASSWORD"]:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        print("❌ Fehlende Konfiguration in der .env Datei:")
        for var in missing:
            print(f"   - {var}")
        print("\nBitte kopiere .env.example nach .env und fülle die Werte aus.")
        exit(1)

    run_filter()
