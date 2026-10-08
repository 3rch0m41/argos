"""Modelli dati di Argos (database SQLite gestito con SQLAlchemy)."""
import secrets
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _utcnow():
    """Orario attuale in UTC (fuso neutro, buona pratica per i database)."""
    return datetime.now(timezone.utc)


def _token():
    """Genera un codice casuale e imprevedibile, usato nei link di tracciamento."""
    return secrets.token_urlsafe(24)


class Participant(db.Model):
    """Una persona iscritta al programma di security awareness.

    Il consenso è un requisito di primo livello: senza consent_given=True
    la persona non può entrare in nessuna campagna.
    """
    __tablename__ = "participants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    department = db.Column(db.String(120), default="")

    consent_given = db.Column(db.Boolean, default=False, nullable=False)
    consent_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=_utcnow)

    # Collegamento: da un partecipante posso risalire a tutti i suoi "target".
    targets = db.relationship("Target", backref="participant", lazy=True)

    def grant_consent(self):
        """Registra il consenso e il momento in cui è stato dato."""
        self.consent_given = True
        self.consent_at = _utcnow()


class Campaign(db.Model):
    """Una campagna di simulazione: un template inviato a N partecipanti."""
    __tablename__ = "campaigns"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    template_key = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    launched_at = db.Column(db.DateTime)

    targets = db.relationship("Target", backref="campaign", lazy=True)

    @property
    def is_launched(self):
        """True se la campagna è già stata lanciata almeno una volta."""
        return self.launched_at is not None

    def stats(self):
        """Calcola i numeri della campagna: inviate, aperte, cliccate, segnalate."""
        total = len(self.targets) # type: ignore
        sent = sum(1 for t in self.targets if t.sent_at) # type: ignore
        opened = sum(1 for t in self.targets if t.opened_at) # type: ignore
        clicked = sum(1 for t in self.targets if t.clicked_at) # type: ignore
        reported = sum(1 for t in self.targets if t.reported_at) # type: ignore
        pct = lambda n: round(100 * n / total, 1) if total else 0.0
        return {
            "total": total, "sent": sent,
            "opened": opened, "opened_pct": pct(opened),
            "clicked": clicked, "clicked_pct": pct(clicked),
            "reported": reported, "reported_pct": pct(reported),
        }


class Target(db.Model):
    """L'invio di UNA campagna a UN partecipante, con il suo stato nel tempo."""
    __tablename__ = "targets"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey("participants.id"), nullable=False)

    # Codice univoco e segreto nel link: identifica QUESTO invio.
    token = db.Column(db.String(64), unique=True, index=True, default=_token)

    # La "timeline" degli stati: ogni tappa ha la sua data (o resta vuota).
    sent_at = db.Column(db.DateTime)      # email generata/inviata
    opened_at = db.Column(db.DateTime)    # pixel caricato -> email aperta
    clicked_at = db.Column(db.DateTime)   # link cliccato -> landing educativa
    reported_at = db.Column(db.DateTime)  # il partecipante l'ha segnalata (bravo!)

    def mark_opened(self):
        if not self.opened_at:
            self.opened_at = _utcnow()

    def mark_clicked(self):
        self.mark_opened()                # un click implica l'apertura
        if not self.clicked_at:
            self.clicked_at = _utcnow()

    def mark_reported(self):
        if not self.reported_at:
            self.reported_at = _utcnow()


class Event(db.Model):
    """Registro cronologico (append-only) di tutto ciò che accade. Utile per audit."""
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    target_id = db.Column(db.Integer, db.ForeignKey("targets.id"))
    kind = db.Column(db.String(40), nullable=False)  # sent/opened/clicked/reported
    at = db.Column(db.DateTime, default=_utcnow)
    detail = db.Column(db.String(255), default="")


def log_event(target, kind, detail=""):
    """Scorciatoia per aggiungere una riga al registro eventi.""" # type: ignore
    db.session.add(Event(target_id=target.id if target else None,  # type: ignore
                         kind=kind, detail=detail)) # type: ignore

    