"""
Stash – Beleg-Analyse-Modul
Analysiert Belege und Rechnungen via Claude AI:
  - Fotos / Bilder  (JPG, PNG, GIF, WEBP) → Claude Vision
  - PDF-Dokumente   (auch gescannte)       → Claude Documents API
  - E-Mail-Text     (Bestellbestätigungen) → Claude Text
"""

import base64
import json
import re
from email.message import Message
from pathlib import Path
from typing import Optional

import anthropic

# ─── Konfiguration ─────────────────────────────────────────────────────────────

SUPPORTED_IMAGE_TYPES = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".gif":  "image/gif",
    ".webp": "image/webp",
}

# Schlüsselwörter, die auf einen Beleg/eine Rechnung hinweisen
BELEG_KEYWORDS = [
    "rechnung", "beleg", "quittung", "kassenbon", "invoice", "receipt",
    "bestellung", "order confirmation", "kaufbestätigung", "order #", "order nr",
    "payment confirmation", "zahlungsbestätigung", "ihre bestellung",
    "vielen dank für ihren kauf", "thank you for your purchase",
    "lieferschein", "delivery note", "booking confirmation", "buchungsbestätigung",
    "reservierungsbestätigung", "ihre rechnung", "your invoice",
    "kontoauszug", "transaction", "transaktion", "paypal", "klarna",
]

# ─── Prompts ───────────────────────────────────────────────────────────────────

BELEG_PROMPT = """Du bist ein Experte für die Analyse von deutschen und internationalen Belegen, Rechnungen und Quittungen.

Analysiere den vorliegenden Beleg und extrahiere alle Informationen.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt – kein Text davor oder danach:

{
  "haendler": "Name des Geschäfts oder Unternehmens",
  "datum": "YYYY-MM-DD",
  "gesamtbetrag": 12.99,
  "waehrung": "EUR",
  "kategorie": "Kategorie des Einkaufs",
  "mwst": 1.99,
  "zahlungsart": "Bar/EC-Karte/Kreditkarte/PayPal/Klarna/Rechnung/Sonstiges",
  "artikel": [
    {"bezeichnung": "Artikelname", "menge": 1, "einzelpreis": 5.99, "gesamtpreis": 5.99}
  ],
  "beleg_typ": "Kassenbon/Rechnung/Quittung/Online-Bestellung/Buchungsbestätigung/Sonstiges",
  "notizen": "Weitere relevante Informationen oder null"
}

Wähle eine dieser Kategorien:
Lebensmittel & Drogerie | Restaurant & Café | Transport & Mobilität |
Unterkunft & Reise | Kleidung & Mode | Elektronik & Technik |
Gesundheit & Apotheke | Unterhaltung & Freizeit | Wohnen & Haushalt |
Büro & Arbeit | Online-Shopping | Dienstleistungen | Sonstiges

Nicht erkennbare Werte → null. Nur JSON zurückgeben."""


# ─── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _parse_claude_json(response_text: str) -> dict:
    """Extrahiert und parst das JSON aus Claudes Antwort."""
    text = response_text.strip()
    # Markdown-Codeblock entfernen falls vorhanden
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "haendler": None,
            "datum": None,
            "gesamtbetrag": None,
            "waehrung": "EUR",
            "kategorie": "Sonstiges",
            "notizen": f"Analyse fehlgeschlagen: {response_text[:300]}",
        }


def _call_claude(client: anthropic.Anthropic, messages: list) -> dict:
    """Sendet eine Anfrage an Claude und gibt das geparste Ergebnis zurück."""
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=messages,
    )
    return _parse_claude_json(response.content[0].text)


# ─── Analyse-Funktionen ────────────────────────────────────────────────────────

def analyze_image_file(image_path: str, client: anthropic.Anthropic) -> dict:
    """
    Analysiert ein Beleg-Foto (JPG, PNG, GIF, WEBP) per Claude Vision.
    Gibt ein dict mit den extrahierten Beleg-Daten zurück.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Bild nicht gefunden: {image_path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_TYPES:
        supported = ", ".join(SUPPORTED_IMAGE_TYPES.keys())
        raise ValueError(f"Nicht unterstützt: {suffix}. Unterstützt: {supported}")

    media_type = SUPPORTED_IMAGE_TYPES[suffix]
    image_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")

    return _call_claude(client, [{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data,
                },
            },
            {"type": "text", "text": BELEG_PROMPT},
        ],
    }])


def analyze_image_bytes(
    image_bytes: bytes,
    media_type: str,
    client: anthropic.Anthropic,
) -> dict:
    """
    Analysiert ein Bild aus Bytes (z.B. E-Mail-Anhang).
    media_type: z.B. 'image/jpeg', 'image/png'
    """
    image_data = base64.standard_b64encode(image_bytes).decode("utf-8")
    return _call_claude(client, [{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data,
                },
            },
            {"type": "text", "text": BELEG_PROMPT},
        ],
    }])


def analyze_pdf_bytes(pdf_bytes: bytes, client: anthropic.Anthropic) -> dict:
    """
    Analysiert ein PDF-Dokument (auch gescannte PDFs) über die Claude Documents API.
    Unterstützt sowohl text-basierte als auch bild-basierte PDFs.
    """
    pdf_data = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    return _call_claude(client, [{
        "role": "user",
        "content": [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_data,
                },
            },
            {"type": "text", "text": BELEG_PROMPT},
        ],
    }])


def analyze_text(text: str, client: anthropic.Anthropic) -> dict:
    """
    Analysiert einen Beleg-Text (z.B. aus einer Bestätigungs-E-Mail).
    text wird auf 6000 Zeichen begrenzt.
    """
    return _call_claude(client, [{
        "role": "user",
        "content": f"{BELEG_PROMPT}\n\nBeleg-Text:\n{text[:6000]}",
    }])


# ─── E-Mail-Erkennung und -Verarbeitung ────────────────────────────────────────

def is_receipt_email(subject: str, body: str) -> bool:
    """Prüft ob eine E-Mail wahrscheinlich einen Beleg enthält."""
    combined = (subject + " " + body[:1000]).lower()
    return any(kw in combined for kw in BELEG_KEYWORDS)


def extract_attachments(msg: Message) -> list[dict]:
    """
    Extrahiert relevante Anhänge (PDF, Bilder) aus einer E-Mail.
    Gibt eine Liste von dicts zurück: {filename, content_type, data (bytes)}
    """
    attachments = []
    for part in msg.walk():
        content_type = part.get_content_type()
        disposition = part.get("Content-Disposition", "")

        is_attachment = "attachment" in disposition or "inline" in disposition
        is_pdf = content_type == "application/pdf"
        is_image = content_type.startswith("image/") and content_type in {
            "image/jpeg", "image/png", "image/gif", "image/webp"
        }

        if (is_pdf or is_image) and (is_attachment or part.get_filename()):
            payload = part.get_payload(decode=True)
            if payload:
                attachments.append({
                    "filename": part.get_filename() or f"anhang.{content_type.split('/')[-1]}",
                    "content_type": content_type,
                    "data": payload,
                })
    return attachments


def analyze_email_message(
    msg: Message,
    client: anthropic.Anthropic,
    message_id: Optional[str] = None,
) -> list[dict]:
    """
    Analysiert eine vollständige E-Mail auf Belege.
    Prüft Anhänge (PDF + Bilder) und E-Mail-Text.
    Gibt eine Liste von Ergebnissen zurück (ein Beleg pro Anhang bzw. E-Mail-Text).
    """
    from email_filter import get_email_body  # Lokaler Import um Zirkularimporte zu vermeiden

    subject = msg.get("Subject", "")
    body = get_email_body(msg)

    if not is_receipt_email(subject, body):
        return []

    results = []
    attachments = extract_attachments(msg)

    # Anhänge analysieren (PDFs und Bilder bevorzugt)
    for i, attachment in enumerate(attachments):
        try:
            ct = attachment["content_type"]
            suffix = f"_anhang{i}"
            quelle_id = f"{message_id}{suffix}" if message_id else None

            if ct == "application/pdf":
                data = analyze_pdf_bytes(attachment["data"], client)
                data["_quelle_id"] = quelle_id
                data["_quelle"] = "email"
                results.append(data)

            elif ct.startswith("image/"):
                data = analyze_image_bytes(attachment["data"], ct, client)
                data["_quelle_id"] = quelle_id
                data["_quelle"] = "email"
                results.append(data)

        except Exception as e:
            print(f"   ⚠️  Anhang konnte nicht analysiert werden ({attachment['filename']}): {e}")

    # Falls keine Anhänge → E-Mail-Text analysieren
    if not results and body:
        try:
            data = analyze_text(body, client)
            data["_quelle_id"] = message_id
            data["_quelle"] = "email"
            results.append(data)
        except Exception as e:
            print(f"   ⚠️  E-Mail-Text konnte nicht analysiert werden: {e}")

    return results
