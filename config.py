"""
Configurazione centrale di Argos.

Principio guida: SICURO DI DEFAULT.
Appena scaricato, il tool NON invia email reali a nessuno. Scrive i messaggi
generati nella cartella ./outbox come file ispezionabili. L'invio SMTP reale
va abilitato in modo esplicito tramite variabili d'ambiente E un flag di
"uso autorizzato", pensato come un dosso di rallentamento consapevole.
"""
import os


def _as_bool(value: str) -> bool:
    """Converte una stringa ('1', 'true', 'yes'...) in un vero booleano."""
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # --- Flask / Database ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///phishguard.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # URL base per costruire i link di tracciamento nelle email.
    BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000").rstrip("/")

    # ------------------------------------------------------------------ #
    #  INVIO EMAIL — SICURO DI DEFAULT                                    #
    # ------------------------------------------------------------------ #
    # "console": scrive l'email in ./outbox e basta. NON invia nulla. (default)
    # "smtp":    invia davvero via SMTP. Richiede le conferme qui sotto.
    EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "console").lower()

    SMTP_HOST = os.environ.get("SMTP_HOST", "localhost")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "1025"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = _as_bool(os.environ.get("SMTP_USE_TLS", "false"))

    FROM_ADDRESS = os.environ.get("FROM_ADDRESS", "security-training@example.com")
    FROM_NAME = os.environ.get("FROM_NAME", "Security Awareness Team")

    # Allowlist dei domini destinatari. Un partecipante può essere bersaglio
    # SOLO se il dominio della sua email è in questa lista.
    ALLOWED_RECIPIENT_DOMAINS = [
        d.strip().lower()
        for d in os.environ.get("ALLOWED_RECIPIENT_DOMAINS", "example.com").split(",")
        if d.strip()
    ]

    # Gate finale: l'invio reale è rifiutato finché l'operatore non dichiara
    # esplicitamente di essere autorizzato.
    AUTHORIZED_USE_ACK = os.environ.get("AUTHORIZED_USE_ACK", "") == "I_AM_AUTHORIZED"

    @classmethod
    def sending_is_live(cls) -> bool:
        """True SOLO se il tool invierà davvero email via SMTP."""
        return cls.EMAIL_BACKEND == "smtp" and cls.AUTHORIZED_USE_ACK