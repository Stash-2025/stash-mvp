---
name: swiss-kmu-web
description: "Build complete, professional websites and web presences for Swiss SMEs (KMU) — including landing pages, service pages, contact forms, pricing tables, automation product pages, and full multi-page sites. USE THIS SKILL whenever the user mentions building anything for a Swiss KMU customer, wants a landing page, wants to present an automation product (e.g. n8n workflows, Bexio integrations), needs a professional business website, or asks for anything web-related in a Swiss business context. This skill combines production-grade frontend design with Swiss market knowledge: correct German business terminology, local trust signals (CHF pricing, Swiss data protection, quality/Qualität framing), and conversion-optimized copy for Handwerk, Treuhand, and other KMU sectors."
---

# Swiss KMU Web Skill

Build complete, conversion-optimized web presences for Swiss small and medium businesses. The output is production-ready HTML/CSS/JS or React code — visually striking, Swiss-market appropriate, and optimized to generate trust and leads from KMU decision-makers.

---

## Context: Swiss KMU Market

Swiss KMU decision-makers (Inhaber, Geschäftsführer, Handwerksmeister) have specific psychological and cultural buying triggers:

**Trust signals that work:**
- CHF pricing (never EUR) — always show prices in CHF
- "Schweizer Qualität" / Swiss-made framing
- DSGVO/DSG compliance mentions (Swiss data protection)
- Local references (Bern, Zürich, Schweiz — not "international")
- Specific results: "3 Stunden pro Woche gespart" beats "more efficient"
- No-risk framing: "30 Tage kostenlos testen", "Keine Einrichtungsgebühr"

**What KMU owners fear (address these):**
- Komplizierte Technik / complexity
- Datenverlust / losing control of their data
- Abhängigkeit von einem Anbieter / vendor lock-in
- Hohe Fixkosten / high fixed costs

**Effective copy patterns:**
- Problem-first: "Noch immer Quittungen per Hand eintippen?"
- Specific time/money savings: "CHF 400 pro Monat sparen"
- Social proof with sector + location: "Sanitärbetrieb, Thun"
- Simple 3-step process visuals

**Sectors to know:**
- Handwerk: Sanitär, Elektro, Schreiner, Maler, Gipser
- Treuhand / Buchhaltung
- Immobilien
- Gastronomie
- Detailhandel (local retail)

---

## Design Philosophy for Swiss KMU

Swiss business aesthetic: **clean, trustworthy, precise** — not flashy or overly designed.

**Color palette defaults (Stash brand):**
- Primary: Stash Green (#1DB584) — Hauptfarbe, CTAs, Akzente
- Text/Secondary: Dark Navy (#0A1628) — Headlines, Navigation, ernsthafte UI-Elemente
- Background: White (#FFFFFF) mit leichten off-white Sektionen (#F7FAF9)
- Accent: Helles Grün (#E8F8F3) für Hover-States, Cards, Badges
- Text: Near-black (#1a1a1a) — Fliesstext, hoher Kontrast

**Typography:**
- Headlines: A slightly characterful sans (e.g. DM Sans, Plus Jakarta Sans, Sora)
- Body: Clean, highly readable (e.g. Source Sans 3, Lato)
- Swiss German uses longer words — ensure line-height and width accommodate

**Layout principles:**
- Generous whitespace — KMU owners are not gamers, don't overwhelm
- Clear visual hierarchy: Problem → Solution → Proof → Price → CTA
- Mobile-first — many Handwerker check things on their phone between jobs
- CTAs: Prominent, action-verb buttons ("Jetzt kostenlos starten", "Demo buchen")

---

## Standard Page Structure (Landing Page)

Use this flow for single-product or service landing pages:

```
1. HERO
   - Headline: Specific problem or outcome (not company name)
   - Subline: Who it's for + the core promise
   - CTA button (primary) + secondary link ("Wie es funktioniert")
   - Optional: Trust badge row (🇨🇭 Schweizer Anbieter | DSGVO-konform | Keine Einrichtungsgebühr)

2. PROBLEM SECTION
   - "Kennen Sie das?" — 3-4 relatable pain points with icons
   - Emotional resonance: lost time, manual errors, stress

3. SOLUTION / HOW IT WORKS
   - 3-step visual process (numbered, icon + short text)
   - Keep it simple: Step 1 / Step 2 / Step 3

4. FEATURES / BENEFITS
   - 3-6 feature cards with icons
   - Lead with benefit, follow with feature: "Mehr Zeit für Kunden — automatische Belegverarbeitung via WhatsApp"

5. SOCIAL PROOF
   - 2-3 testimonials: Name, Berufsbezeichnung, Ort (e.g. "Hans M., Sanitärmeister, Thun")
   - If no real testimonials: use placeholder with realistic Swiss names/sectors

6. PRICING
   - CHF, monthly/yearly toggle
   - 2-3 tiers max (Starter / Professional / Enterprise)
   - Highlight recommended plan
   - Include: "Keine Kreditkarte nötig", "Jederzeit kündbar"

7. FAQ
   - 5-7 questions addressing the fears listed above
   - Accordion component

8. FINAL CTA
   - Repeat headline/CTA
   - Add urgency or reassurance: "Kostenlos starten — in 5 Minuten eingerichtet"

9. FOOTER
   - Impressum link (required in CH)
   - Datenschutz link
   - Contact info
```

---

## Component Library (reusable patterns)

### Trust Badge Row
```html
<div class="trust-badges">
  <span>🇨🇭 Schweizer Anbieter</span>
  <span>🔒 DSGVO-konform</span>
  <span>⚡ In 5 Min. eingerichtet</span>
  <span>✓ Keine Einrichtungsgebühr</span>
</div>
```

### Testimonial Card
```html
<!-- Name + Sector + Location format -->
"[Product] spart mir jede Woche rund 4 Stunden. Die Einrichtung war einfacher als erwartet."
— [Vorname] [Nachname initial]., [Berufsbezeichnung], [Ort]
```

### Pricing Card
- Always show: CHF X / Monat
- Strike through yearly price to show savings: ~~CHF 99~~ CHF 79/Monat (bei Jahresabo)
- "Am beliebtesten" badge on recommended plan

---

## n8n Automation Product Pages (Tim's use case)

When building pages for n8n automation products targeting Swiss KMU:

**Hero copy pattern:**
- Bad: "KI-gestützte Automatisierungslösung für Unternehmen"
- Good: "Schluss mit Belegen abtippen — Ihre Buchhaltungsvorbereitung läuft jetzt automatisch"

**Key features to highlight for Handwerk/Treuhand:**
- Input channels: WhatsApp, E-Mail — channels they already use
- Output: Bexio-ready, DATEV-kompatibel, Google Sheets
- Zero technical knowledge required
- Swiss data storage / Schweizer Server (if applicable)

**Automation flow visualization:**
Show a simple visual: WhatsApp/Email → [Logo] → Bexio/Google Sheets
Use SVG arrows or a CSS step diagram — not complex, just clear.

---

## Implementation Checklist

Before delivering any page, verify:
- [ ] All prices in CHF
- [ ] German copy — correct Swiss German (no "ss" → "ß", use "ss" throughout)
- [ ] Mobile responsive (test at 375px)
- [ ] CTA buttons have hover states
- [ ] Contact/impressum section present
- [ ] No placeholder lorem ipsum in final output
- [ ] Images: use realistic placeholder descriptions or unsplash URLs for Handwerk imagery
- [ ] Font loaded from Google Fonts or system stack (no paid fonts)
- [ ] Accessibility: sufficient color contrast, alt attributes

---

## Swiss German Copy Reference

Common Swiss German business phrases to use naturally:

| Standard | Swiss business preferred |
|---|---|
| Kunden | Kunden / Auftraggeber |
| Rechnung | Rechnung / Faktura |
| Buchhaltung | Buchhaltung / Finanzbuchhaltung |
| günstig | kosteneffizient / preislich attraktiv |
| einfach | unkompliziert / ohne Vorkenntnisse |
| schnell | sofort / in wenigen Minuten |
| Firma | Unternehmen / Betrieb / KMU |

Avoid German idioms that sound foreign in CH context. Keep sentences short and concrete.

---

## Output Format

Default output: **Single-file HTML** (HTML + embedded CSS + minimal JS)
- Self-contained, no build step required
- Can be opened in browser immediately
- Easy to hand off to KMU customer or upload to any hosting

For React requests: Standard React component with Tailwind utility classes.

Always include a comment block at the top:
```html
<!-- 
  Swiss KMU Landing Page
  Sector: [sector]
  Product: [product name]
  Generated: [date]
  Tim Zbinden / [business name]
-->
```
