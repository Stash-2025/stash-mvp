"""
Stash – E-Mail Spam-Filter mit Claude AI
Unterstützt mehrere Konten gleichzeitig (iCloud + Gmail).

Funktionen:
  - Liest ungelesene E-Mails per IMAP
  - Klassifiziert sie mit Claude (Spam / Normal / Wichtig)
  - Verschiebt Spam automatisch in den Spam-Ordner
  - Sendet Benachrichtigung für wichtige E-Mails
  - Erkennt Belege/Rechnungen und speichert sie automatisch
"""

import email
import imaplib
import json
import os
import smtplib
from datetime import datetime
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20"))
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "tim.baer@icloud.com")

# Belege automatisch aus gefilterten E-Mails extrahieren?
AUTO_BELEG_SCAN = os.getenv("AUTO_BELEG_SCAN", "true").lower() == "true"

# Vorkonfigurierte Server-Einstellungen
PROVIDER_SETTINGS = {
    "icloud": {
        "imap_server": "imap.mail.me.com",
        "imap_port": 993,
        "smtp_server": "smtp.mail.me.com",
        "smtp_port": 587,
    },
    "gmail": {
        "imap_server": "imap.gmail.com",
        "imap_port": 993,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
    },
}

ACCOUNTS = []

if os.getenv("ICLOUD_PASSWORD"):
    ACCOUNTS.append({
        "name": "iCloud (tim.baer@icloud.com)",
        "address": "tim.baer@icloud.com",
        "password": os.getenv("ICLOUD_PASSWORD"),
        **PROVIDER_SETTINGS["icloud"],
    })

if os.getenv("GMAIL_PASSWORD"):
    ACCOUNTS.append({
        "name": "Gmail (timbaer05@gmail.com)",
        "address": "timbaer05@gmail.com",
        "password": os.getenv("GMAIL_PASSWORD"),
        **PROVIDER_SETTINGS["gmail"],
    })


# ─── E-Mail Hilfsfunktionen ───────────────────────────────────────────────────

def decode_str(value: str) -> str:
    """Dekodiert E-Mail-Header (UTF-8, Base64, etc.)."""
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
    """Extrahiert den Text-Body einer E-Mail (max. 3000 Zeichen)."""
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
    return body[:3000]


# ─── Spam-Klassifikation ──────────────────────────────────────────────────────

def classify_emails_with_claude(emails: list[dict]) -> list[dict]:
    """
    Klassifiziert mehrere E-Mails auf einmal mit Claude.
    Kategorien: spam / normal / wichtig
    """
    email_list_text = ""
    for i, e in enumerate(emails):
        email_list_text += f"""
--- E-Mail {i+1} ---
Konto: {e['account']}
Von: {e['from']}
Betreff: {e['subject']}
Datum: {e['date']}
Inhalt (Auszug): {e['body'][:500]}
"""

    prompt = f"""Du bist ein intelligenter E-Mail-Filter für Tim Bär. Analysiere die folgenden E-Mails und klassifiziere jede als:
- "spam": Werbung, Newsletter ohne Relevanz, verdächtige Absender, Phishing, automatische Benachrichtigungen ohne Handlungsbedarf
- "normal": Normale E-Mails, die gelesen werden können, aber keine sofortige Reaktion erfordern
- "wichtig": E-Mails, die sofortige Aufmerksamkeit erfordern (persönliche Nachrichten, wichtige Termine, finanzielle Angelegenheiten, dringende Anfragen, Sicherheitswarnungen, Bestellbestätigungen, Rechnungen)

Antworte NUR mit einem JSON-Array. Für jede E-Mail ein Objekt mit:
- "index": Nummer der E-Mail (beginnend bei 0)
- "kategorie": "spam", "normal" oder "wichtig"
- "begruendung": Kurze Begründung auf Deutsch (1 Satz)

Beispiel: [{{"index": 0, "kategorie": "spam", "begruendung": "Newsletter von Online-Shop ohne persönlichen Bezug"}}]

E-Mails zum Analysieren:
{email_list_text}

JSON-Antwort:"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    result_text = response.content[0].text.strip()
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


# ─── Beleg-Erkennung (integriert in Spam-Filter) ─────────────────────────────

def _try_save_receipt_from_email(msg, message_id: str, account_name: str) -> int:
    """
    Prüft ob diese E-Mail einen Beleg enthält und speichert ihn falls ja.
    Gibt die Anzahl gespeicherter Belege zurück.
    """
    try:
        from database import beleg_exists, save_beleg
        from receipt_analyzer import analyze_email_message

        if beleg_exists(message_id):
            return 0

        results = analyze_email_message(msg, client, message_id=message_id)
        saved = 0
        for data in results:
            quelle_id = data.pop("_quelle_id", message_id)
            data.pop("_quelle", None)
            beleg_id = save_beleg("email", quelle_id, data)
            if beleg_id:
                haendler = data.get("haendler") or "Unbekannt"
                betrag = data.get("gesamtbetrag")
                betrag_str = f"{betrag:.2f} {data.get('waehrung', 'EUR')}" if betrag else "Betrag unbekannt"
                print(f"   🧾 Beleg gespeichert: {haendler} – {betrag_str}")
                saved += 1
        return saved

    except Exception as e:
        print(f"   ⚠️  Beleg-Analyse fehlgeschlagen: {e}")
        return 0


# ─── Spam-Ordner / Benachrichtigungen ─────────────────────────────────────────

def move_to_spam(imap: imaplib.IMAP4_SSL, email_id: bytes, provider: str) -> bool:
    """Verschiebt eine E-Mail in den Spam-Ordner (providerspezifisch)."""
    spam_folders = {
        "gmail": ["[Gmail]/Spam", "[Gmail]/Trash"],
        "icloud": ["Junk", "JUNK", "Spam"],
    }.get(provider, ["Junk", "Spam", "[Gmail]/Spam"])

    for folder in spam_folders:
        try:
            if imap.copy(email_id, folder)[0] == "OK":
                imap.store(email_id, "+FLAGS", "\\Deleted")
                return True
        except Exception:
            continue

    imap.store(email_id, "+FLAGS", "\\Seen")
    return False


def send_notification(wichtige_emails: list[dict], notify_account: dict) -> None:
    """Sendet eine Benachrichtigungs-E-Mail für wichtige Mails."""
    if not wichtige_emails:
        return

    subject = f"🔔 {len(wichtige_emails)} wichtige E-Mail(s) – Tim Bär"
    lines = ["Hallo Tim,\n", "du hast folgende wichtige E-Mails erhalten:\n"]
    for i, e in enumerate(wichtige_emails, 1):
        lines += [
            f"{i}. Konto: {e['account']}",
            f"   Von: {e['from']}",
            f"   Betreff: {e['subject']}",
            f"   Datum: {e['date']}",
            f"   Warum wichtig: {e['begruendung']}",
            "",
        ]
    lines.append("Bitte prüfe diese E-Mails zeitnah.")

    msg = MIMEMultipart()
    msg["From"] = notify_account["address"]
    msg["To"] = NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText("\n".join(lines), "plain", "utf-8"))

    with smtplib.SMTP(notify_account["smtp_server"], notify_account["smtp_port"]) as server:
        server.starttls()
        server.login(notify_account["address"], notify_account["password"])
        server.send_message(msg)

    print(f"✉️  Benachrichtigung gesendet an {NOTIFY_EMAIL}")


# ─── Konto-Verarbeitung ───────────────────────────────────────────────────────

def get_provider(address: str) -> str:
    """Ermittelt den E-Mail-Provider anhand der Adresse."""
    domain = address.split("@")[-1].lower()
    if "icloud" in domain or "me.com" in domain or "mac.com" in domain:
        return "icloud"
    elif "gmail" in domain:
        return "gmail"
    return "unknown"


def process_account(account: dict) -> tuple[list[dict], int, int, int]:
    """
    Verarbeitet ein E-Mail-Konto:
      1. Klassifiziert ungelesene E-Mails (Spam / Normal / Wichtig)
      2. Erkennt Belege in nicht-Spam E-Mails und speichert sie (falls AUTO_BELEG_SCAN)
    Gibt wichtige E-Mails + Statistik zurück.
    """
    provider = get_provider(account["address"])
    wichtige_emails = []
    stats = {"spam": 0, "normal": 0, "wichtig": 0}
    belege_gespeichert = 0

    print(f"\n{'─'*60}")
    print(f"📬 {account['name']}")
    print(f"{'─'*60}")
    print(f"🔌 Verbinde mit {account['imap_server']}...")

    imap = imaplib.IMAP4_SSL(account["imap_server"], account["imap_port"])
    imap.login(account["address"], account["password"])
    imap.select("INBOX")

    _, message_ids = imap.search(None, "UNSEEN")
    all_ids = message_ids[0].split()

    if not all_ids:
        print("✅ Keine ungelesenen E-Mails.")
        imap.logout()
        return [], 0, 0, 0

    ids_to_process = all_ids[-BATCH_SIZE:]
    print(f"📧 {len(all_ids)} ungelesene E-Mail(s) – verarbeite {len(ids_to_process)} neueste\n")

    # E-Mails laden
    emails_data = []
    raw_msgs = {}  # email_id → parsed Message (für Beleg-Scan)
    for email_id in reversed(ids_to_process):
        _, msg_data = imap.fetch(email_id, "(RFC822)")
        raw_bytes = msg_data[0][1]
        msg = email.message_from_bytes(raw_bytes)
        raw_msgs[email_id] = msg
        emails_data.append({
            "id": email_id,
            "account": account["name"],
            "from": decode_str(msg.get("From", "")),
            "subject": decode_str(msg.get("Subject", "(kein Betreff)")),
            "date": msg.get("Date", ""),
            "body": get_email_body(msg),
            "message_id": msg.get("Message-ID", "").strip(),
            "kategorie": "normal",
            "begruendung": "",
        })

    # Claude klassifiziert
    print("🤖 Claude analysiert E-Mails...")
    classified = classify_emails_with_claude(emails_data)

    print("\n📊 Ergebnis:\n")
    for e in classified:
        kategorie = e["kategorie"]
        stats[kategorie] = stats.get(kategorie, 0) + 1

        icons = {"spam": "🗑️  SPAM  ", "normal": "📄 Normal", "wichtig": "⭐ WICHTIG"}
        print(f"  {icons[kategorie]} | {e['from'][:38]}")
        print(f"           {e['subject'][:48]}")
        print(f"           → {e['begruendung']}\n")

        if kategorie == "spam":
            move_to_spam(imap, e["id"], provider)
        elif kategorie == "wichtig":
            wichtige_emails.append(e)
            imap.store(e["id"], "-FLAGS", "\\Seen")  # wichtige E-Mails ungelesen lassen
        else:
            imap.store(e["id"], "+FLAGS", "\\Seen")

        # Belege aus nicht-Spam E-Mails extrahieren
        if AUTO_BELEG_SCAN and kategorie != "spam":
            msg = raw_msgs.get(e["id"])
            message_id = e.get("message_id") or f"{account['address']}_{e['id'].decode()}"
            if msg:
                belege_gespeichert += _try_save_receipt_from_email(msg, message_id, account["name"])

    imap.expunge()
    imap.logout()

    if belege_gespeichert:
        print(f"   💾 {belege_gespeichert} Beleg(e) automatisch gespeichert\n")

    return wichtige_emails, stats["spam"], stats["normal"], stats["wichtig"]


# ─── Dedizierter E-Mail-Beleg-Scan ────────────────────────────────────────────

def scan_account_for_receipts(account: dict, days: int = 30) -> int:
    """
    Scannt alle E-Mails der letzten `days` Tage nach Belegen.
    Gibt die Anzahl neu gespeicherter Belege zurück.
    """
    from database import beleg_exists, save_beleg
    from receipt_analyzer import analyze_email_message

    provider = get_provider(account["address"])
    print(f"\n{'─'*60}")
    print(f"🔍 Scanne nach Belegen: {account['name']}")
    print(f"{'─'*60}")
    print(f"🔌 Verbinde mit {account['imap_server']}...")

    imap = imaplib.IMAP4_SSL(account["imap_server"], account["imap_port"])
    imap.login(account["address"], account["password"])
    imap.select("INBOX")

    # Datum-Filter: letzte N Tage
    from datetime import timedelta
    since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
    _, message_ids = imap.search(None, f'SINCE "{since_date}"')
    all_ids = message_ids[0].split()

    print(f"📧 {len(all_ids)} E-Mail(s) der letzten {days} Tage gefunden\n")

    new_receipts = 0
    for email_id in all_ids:
        try:
            _, msg_data = imap.fetch(email_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            message_id = msg.get("Message-ID", "").strip()
            if not message_id:
                message_id = f"{account['address']}_{email_id.decode()}"

            # Beleg-Scan (mit Duplikat-Schutz)
            results = analyze_email_message(msg, client, message_id=message_id)
            for data in results:
                quelle_id = data.pop("_quelle_id", message_id)
                data.pop("_quelle", None)
                beleg_id = save_beleg("email", quelle_id, data)
                if beleg_id:
                    haendler = data.get("haendler") or "Unbekannt"
                    betrag = data.get("gesamtbetrag")
                    betrag_str = f"{betrag:.2f} {data.get('waehrung', 'EUR')}" if betrag else "?"
                    subj = decode_str(msg.get("Subject", ""))[:45]
                    print(f"  🧾 {haendler} – {betrag_str}  ({subj})")
                    new_receipts += 1

        except Exception as e:
            print(f"  ⚠️  Fehler bei E-Mail {email_id}: {e}")
            continue

    imap.logout()
    return new_receipts


# ─── Hauptfunktionen ──────────────────────────────────────────────────────────

def run_filter() -> None:
    """Spam-Filter: Alle konfigurierten Konten verarbeiten."""
    print(f"\n{'='*60}")
    print(f"  📬 E-Mail Spam-Filter  |  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"  Tim Bär – {len(ACCOUNTS)} Konto(s) konfiguriert")
    if AUTO_BELEG_SCAN:
        print("  🧾 Auto-Beleg-Erkennung: aktiv")
    print(f"{'='*60}")

    if not ACCOUNTS:
        print("\n❌ Keine Konten konfiguriert. Bitte .env befüllen.")
        return

    alle_wichtigen = []
    gesamt_stats = {"spam": 0, "normal": 0, "wichtig": 0}
    notify_account = ACCOUNTS[0]

    for account in ACCOUNTS:
        wichtige, spam, normal, wichtig = process_account(account)
        alle_wichtigen.extend(wichtige)
        gesamt_stats["spam"] += spam
        gesamt_stats["normal"] += normal
        gesamt_stats["wichtig"] += wichtig

    print(f"\n{'='*60}")
    print("📈 Gesamtzusammenfassung (alle Konten):")
    print(f"   ⭐ Wichtig:  {gesamt_stats['wichtig']}")
    print(f"   📄 Normal:   {gesamt_stats['normal']}")
    print(f"   🗑️  Spam:     {gesamt_stats['spam']}")
    print(f"{'='*60}\n")

    if alle_wichtigen:
        print(f"📨 Sende Benachrichtigung für {len(alle_wichtigen)} wichtige E-Mail(s)...")
        send_notification(alle_wichtigen, notify_account)

    print("✅ Fertig!\n")


def run_receipt_scan(days: int = 30) -> None:
    """Dedizierter Beleg-Scan für alle Konten."""
    print(f"\n{'='*60}")
    print(f"  🧾 Beleg-Scanner  |  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"  Zeitraum: letzte {days} Tage")
    print(f"{'='*60}")

    if not ACCOUNTS:
        print("\n❌ Keine Konten konfiguriert. Bitte .env befüllen.")
        return

    total = 0
    for account in ACCOUNTS:
        total += scan_account_for_receipts(account, days=days)

    print(f"\n{'='*60}")
    print(f"✅ Scan abgeschlossen – {total} neue Beleg(e) gespeichert")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    missing = []
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not os.getenv("ICLOUD_PASSWORD") and not os.getenv("GMAIL_PASSWORD"):
        missing.append("ICLOUD_PASSWORD und/oder GMAIL_PASSWORD")

    if missing:
        print("❌ Fehlende Konfiguration in der .env Datei:")
        for var in missing:
            print(f"   - {var}")
        print("\nBitte kopiere .env.example nach .env und fülle die Werte aus.")
        exit(1)

    run_filter()
