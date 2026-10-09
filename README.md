# Argos

> *The hundred-eyed watcher.* A consent-based phishing **simulation** platform
> and a defensive **email analyzer**, built for security-awareness training.

**[🇮🇹 Leggi in italiano](README.it.md)**

Argos helps a security/Blue Team run ethical phishing-awareness campaigns against
**consenting** participants and teaches recipients to recognize attacks — paired
with a tool that dissects suspicious `.eml` files and explains *why* they look
malicious.

> ⚠️ **This is a training tool, not an attack tool.** It is safe-by-default: out
> of the box it sends nothing. See [Safety & Ethics](#safety--ethics).

---

## Why this project

Phishing is the entry point of most breaches. Argos sits firmly on the
**defensive** side: it does not try to deceive people as effectively as possible —
it trains them to spot the patterns, and gives analysts a way to triage reported
emails. It demonstrates awareness of the line between offensive and defensive
security, and a deliberate choice to build on the right side of it.

## Features

- **Awareness campaigns (consent-first).** Register participants, record explicit
  consent, build campaigns from didactic templates, and track opens / clicks /
  reports per recipient.
- **Educational landing page.** Anyone who clicks lands on a page that reveals the
  red flags of the message they just fell for — turning a mistake into a lesson.
  **No credentials are ever collected.**
- **Email viewer.** Preview exactly what a recipient would see, rendered in a
  mock mail client (tracking pixel disabled in preview).
- **`.eml` analyzer.** Upload or paste a suspicious email and get a 0–100 risk
  score with explained findings: SPF/DKIM/DMARC verdicts, From/Reply-To/Return-Path
  mismatches, display-name spoofing, deceptive links (IP hosts, punycode
  homographs, shorteners, anchor-vs-destination mismatch), urgency language, and
  risky attachments.

## Safety & Ethics

Argos is **safe-by-default** and enforces its guarantees in code, not just docs:

- **No real sending by default.** The default backend (`console`) writes generated
  emails to `./outbox` as `.eml` files. Nothing is transmitted.
- **Consent is mandatory.** A participant without explicit consent cannot be added
  to a campaign — enforced at campaign creation *and* at send time.
- **Recipient allowlist.** Emails are only produced for domains you explicitly
  authorize (`ALLOWED_RECIPIENT_DOMAINS`).
- **Explicit authorization gate.** Real SMTP sending is refused unless you set
  `EMAIL_BACKEND=smtp` **and** `AUTHORIZED_USE_ACK=I_AM_AUTHORIZED`.
- **Transparency.** Every generated message carries `X-Argos-Simulation: true`
  headers, and the UI always shows whether sending is live.

Use Argos **only** against recipients you are authorized to test.

## Tech stack

Python · Flask · Flask-SQLAlchemy (SQLite) · standard-library `email` parser.
No external services, no telemetry.

## Getting started

```bash
# 1. Clone
git clone https://github.com/Erchomai/argos.git
cd argos

# 2. Create an isolated environment (uv)
uv venv
# Windows:        .venv\Scripts\activate
# macOS/Linux:    source .venv/bin/activate
uv pip install -r requirements.txt

# 3. Run (safe mode by default)
python app.py
# open http://127.0.0.1:5000
```

### Trying it out

1. **Participants** → add a few with emails ending in `@example.com` (an
   address range reserved for documentation/testing) and tick consent.
2. **Campaigns** → pick a template, select recipients, create, then **Launch**.
3. In safe mode the generated emails appear in `./outbox/` as `.eml` files, and
   you can preview each from the campaign page.
4. **Analyze email** → paste a suspicious message and read the risk report.

## Configuration

All settings are environment variables (safe defaults shown):

| Variable | Default | Purpose |
|---|---|---|
| `EMAIL_BACKEND` | `console` | `console` (write to file) or `smtp` (real send) |
| `ALLOWED_RECIPIENT_DOMAINS` | `example.com` | Comma-separated recipient allowlist |
| `AUTHORIZED_USE_ACK` | *(unset)* | Must equal `I_AM_AUTHORIZED` to send via SMTP |
| `BASE_URL` | `http://127.0.0.1:5000` | Base URL for tracking links |
| `SMTP_HOST` / `SMTP_PORT` | `localhost` / `1025` | SMTP server (e.g. MailHog) |

## Project structure

```
argos/
├── app.py                 # Flask app + routes
├── config.py              # central config, safe-by-default
├── models.py              # Participant, Campaign, Target, Event
├── simulator/
│   ├── templates_catalog.py   # didactic phishing templates
│   ├── mailer.py              # consent + allowlist enforcement, delivery
│   └── tracking.py            # tracking pixel
├── analyzer/
│   └── eml_analyzer.py        # defensive .eml heuristics + scoring
├── templates/             # Jinja2 pages
├── static/                # CSS
└── outbox/                # generated emails (safe mode)
```

## Roadmap

- Pluggable, data-driven template packs
- Full DKIM signature verification (DNS-based)
- CSV import/export of participants and results
- Per-campaign scheduling

## Disclaimer

Argos is provided for **authorized security-awareness training and research
only**. You are responsible for using it lawfully and only against systems and
people you have explicit permission to test. The author assumes no liability for
misuse.

## License

Released under the [MIT License](LICENSE).

## Author

**Giulio Malini** ([@Erchomai](https://github.com/Erchomai))
security engineer.