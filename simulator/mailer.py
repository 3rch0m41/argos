"""
Costruzione e invio dei messaggi di simulazione.

Due backend:
  - "console" (default): scrive il .eml in ./outbox, NON invia nulla.
  - "smtp": invia davvero, ma solo se Config.sending_is_live() e True.

Prima di costruire qualsiasi messaggio vengono applicati due controlli non
negoziabili:
  1. il partecipante deve avere il consenso;
  2. il dominio del destinatario deve essere nell'allowlist.
"""
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from config import Config
from .templates_catalog import get_template


class SendRefused(Exception):
    """Sollevata quando un invio viola consenso o allowlist."""


def _recipient_domain(email_addr: str) -> str:
    """Estrae il dominio da un indirizzo email (la parte dopo la @)."""
    return email_addr.rsplit("@", 1)[-1].lower() if "@" in email_addr else ""


def check_allowed(participant):
    """Verifica consenso + allowlist. Solleva SendRefused se non consentito."""
    if not participant.consent_given:
        raise SendRefused(
            f"{participant.email}: consenso non concesso. "
            "Nessun invio senza opt-in esplicito."
        )
    domain = _recipient_domain(participant.email)
    if domain not in Config.ALLOWED_RECIPIENT_DOMAINS:
        raise SendRefused(
            f"{participant.email}: dominio '{domain}' non in allowlist "
            f"{Config.ALLOWED_RECIPIENT_DOMAINS}. "
            "Si possono testare solo domini autorizzati."
        )


def build_message(participant, campaign):
    """Costruisce l'email per un target. Applica PRIMA i controlli di sicurezza."""
    check_allowed(participant)   # <-- il cancello: se fallisce, non si va avanti

    tpl = get_template(campaign.template_key)
    if not tpl:
        raise SendRefused(f"Template sconosciuto: {campaign.template_key}")

    target = next(
        (t for t in campaign.targets if t.participant_id == participant.id), None
    )
    if target is None:
        raise SendRefused("Target non trovato per questo partecipante/campagna.")

    # Costruisco i link personalizzati usando il token segreto del target.
    link = f"{Config.BASE_URL}/c/{target.token}"
    pixel = f"{Config.BASE_URL}/t/{target.token}/pixel.png"
    html = tpl["body"].format(name=participant.name, link=link, pixel=pixel)

    msg = EmailMessage()
    msg["Subject"] = tpl["subject"]
    msg["From"] = formataddr((Config.FROM_NAME, Config.FROM_ADDRESS))
    msg["To"] = formataddr((participant.name, participant.email))
    msg["Message-ID"] = make_msgid(domain="argos.local")
    # Header di trasparenza: dichiara apertamente che e una simulazione.
    msg["X-Argos-Simulation"] = "true"
    msg["X-Argos-Campaign"] = str(campaign.id)

    text_fallback = (
        f"Simulazione di security awareness per {participant.name}.\n"
        f"Apri: {link}\n"
    )
    msg.set_content(text_fallback)           # versione testo
    msg.add_alternative(html, subtype="html")  # versione HTML
    return msg, target


def _write_to_outbox(msg, target):
    """Modalita sicura: scrive l'email su file invece di inviarla."""
    os.makedirs("outbox", exist_ok=True)
    path = os.path.join("outbox", f"campaign_{target.campaign_id}_target_{target.id}.eml")
    with open(path, "wb") as fh:
        fh.write(bytes(msg))
    return path


def _send_smtp(msg):
    """Invio reale via SMTP. Chiamato solo dopo tutti i controlli."""
    server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15)
    try:
        if Config.SMTP_USE_TLS:
            server.starttls()
        if Config.SMTP_USER:
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        server.send_message(msg)
    finally:
        server.quit()


def deliver(participant, campaign):
    """Consegna il messaggio secondo il backend configurato.

    Ritorna (mode, detail): mode e 'console' oppure 'smtp'.
    """
    msg, target = build_message(participant, campaign)

    if Config.EMAIL_BACKEND == "console":
        path = _write_to_outbox(msg, target)
        return "console", path

    # backend == "smtp": ultimo cancello prima dell'invio reale
    if not Config.AUTHORIZED_USE_ACK:
        raise SendRefused(
            "Invio SMTP rifiutato. Per inviare davvero imposta la variabile "
            "d'ambiente AUTHORIZED_USE_ACK=I_AM_AUTHORIZED, confermando di "
            "essere autorizzato a testare questi destinatari."
        )
    _send_smtp(msg)
    return "smtp", f"inviata a {participant.email}"