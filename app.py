"""
Argos — piattaforma di security awareness (con consenso) + analizzatore .eml.

Avvio:
    python app.py
    -> http://127.0.0.1:5000

Di default NON invia email: le scrive in ./outbox. Vedi config.py.
"""
from datetime import datetime, timezone

from flask import (Flask, Response, flash, redirect, render_template,
                   request, url_for)

from config import Config
from models import Campaign, Participant, Target, db, log_event
from simulator.mailer import SendRefused, deliver
from simulator.templates_catalog import list_templates, get_template
from simulator.tracking import PIXEL_GIF
from markupsafe import escape

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Reso disponibile a TUTTI i template: alimenta il banner di stato.
    @app.context_processor
    def inject_globals():
        return {
            "sending_is_live": Config.sending_is_live(),
            "email_backend": Config.EMAIL_BACKEND,
            "allowed_domains": Config.ALLOWED_RECIPIENT_DOMAINS,
        }

    # ----------------------------- Dashboard ---------------------------- #
    @app.route("/")
    def dashboard():
        campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
        participants = Participant.query.all()
        totals = {
            "participants": len(participants),
            "consented": sum(1 for p in participants if p.consent_given),
            "campaigns": len(campaigns),
        }
        agg = {"sent": 0, "opened": 0, "clicked": 0, "reported": 0}
        for c in campaigns:
            s = c.stats()
            for k in agg:
                agg[k] += s[k]
        return render_template("dashboard.html", campaigns=campaigns,
                               totals=totals, agg=agg)

    # ---------------------------- Partecipanti -------------------------- #
    @app.route("/participants", methods=["GET", "POST"])
    def participants():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            dept = request.form.get("department", "").strip()
            consent = request.form.get("consent") == "on"
            if not name or not email:
                flash("Nome ed email sono obbligatori.", "error")
            elif Participant.query.filter_by(email=email).first():
                flash("Esiste gia un partecipante con questa email.", "error")
            else:
                p = Participant(name=name, email=email, department=dept) # type: ignore
                if consent:
                    p.grant_consent()
                db.session.add(p)
                db.session.commit()
                flash(f"Partecipante '{name}' aggiunto.", "ok")
            return redirect(url_for("participants"))

        people = Participant.query.order_by(Participant.created_at.desc()).all()
        return render_template("participants.html", people=people)

    @app.route("/participants/<int:pid>/consent", methods=["POST"])
    def toggle_consent(pid):
        p = Participant.query.get_or_404(pid)
        if p.consent_given:
            p.consent_given = False
            p.consent_at = None
            flash(f"Consenso revocato per {p.name}.", "ok")
        else:
            p.grant_consent()
            flash(f"Consenso registrato per {p.name}.", "ok")
        db.session.commit()
        return redirect(url_for("participants"))

    # ------------------------------ Campagne ---------------------------- #
    @app.route("/campaigns", methods=["GET", "POST"])
    def campaigns():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            template_key = request.form.get("template_key", "")
            pids = request.form.getlist("participants")
            if not name or not template_key or not pids:
                flash("Nome, template e almeno un partecipante sono richiesti.", "error")
                return redirect(url_for("campaigns"))

            c = Campaign(name=name, template_key=template_key)  # type: ignore
            db.session.add(c)
            db.session.flush()
            skipped = []
            for pid in pids:
                p = Participant.query.get(int(pid))
                if not p:
                    continue
                if not p.consent_given:
                    skipped.append(p.email)   # mai bersagliare senza consenso
                    continue
                db.session.add(Target(campaign_id=c.id, participant_id=p.id)) # type: ignore
            db.session.commit()
            msg = f"Campagna '{name}' creata."
            if skipped:
                msg += f" Esclusi (senza consenso): {', '.join(skipped)}."
            flash(msg, "ok")
            return redirect(url_for("campaign_detail", cid=c.id))

        all_campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
        consented = Participant.query.filter_by(consent_given=True).all()
        return render_template("campaigns.html", campaigns=all_campaigns,
                               templates=list_templates(), consented=consented)

    @app.route("/campaigns/<int:cid>")
    def campaign_detail(cid):
        c = Campaign.query.get_or_404(cid)
        return render_template("campaign_detail.html", c=c, stats=c.stats())

    @app.route("/campaigns/<int:cid>/launch", methods=["POST"])
    def launch_campaign(cid):
        c = Campaign.query.get_or_404(cid)
        sent, errors = 0, []
        for t in c.targets:
            try:
                mode, detail = deliver(t.participant, c)
                t.sent_at = datetime.now(timezone.utc)
                log_event(t, "sent", f"{mode}: {detail}")
                sent += 1
            except SendRefused as e:
                errors.append(str(e))
        if not c.launched_at and sent:
            c.launched_at = datetime.now(timezone.utc)
        db.session.commit()

        if Config.EMAIL_BACKEND == "console":
            flash(f"{sent} email scritte in ./outbox (nessun invio reale).", "ok")
        else:
            flash(f"{sent} email inviate via SMTP.", "ok")
        for e in errors:
            flash("Saltata: " + e, "error")
        return redirect(url_for("campaign_detail", cid=cid))

    # --------------------------- Tracciamento --------------------------- #
    @app.route("/t/<token>/pixel.png")
    def track_open(token):
        t = Target.query.filter_by(token=token).first()
        if t:
            t.mark_opened()
            log_event(t, "opened", request.user_agent.string[:200])
            db.session.commit()
        return Response(PIXEL_GIF, mimetype="image/gif")

    @app.route("/c/<token>")
    def track_click(token):
        t = Target.query.filter_by(token=token).first_or_404()
        t.mark_clicked()
        log_event(t, "clicked", request.user_agent.string[:200])
        db.session.commit()
        tpl = next((x for x in list_templates()
                    if x["key"] == t.campaign.template_key), None)
        return render_template("landing.html", target=t, template=tpl)

    @app.route("/r/<token>", methods=["POST"])
    def report_phish(token):
        """Il partecipante segnala l'email come sospetta: comportamento virtuoso."""
        t = Target.query.filter_by(token=token).first_or_404()
        t.mark_reported()
        log_event(t, "reported", "")
        db.session.commit()
        return render_template("reported.html", target=t)

    # ---------------------------- Analizzatore -------------------------- #
    @app.route("/analyzer", methods=["GET", "POST"])
    def analyzer():
        # Import "pigro": caricato solo quando serve, cosi l'app parte
        # anche prima che il modulo analyzer esista (lo creeremo dopo).
        from analyzer.eml_analyzer import analyze_bytes

        if request.method == "POST":
            raw = b""
            f = request.files.get("eml")
            if f and f.filename:
                raw = f.read()
            else:
                raw = request.form.get("raw", "").encode("utf-8", errors="replace")
            if not raw.strip():
                flash("Carica un file .eml oppure incolla l'email grezza.", "error")
                return redirect(url_for("analyzer"))
            try:
                result = analyze_bytes(raw)
            except Exception as e:
                flash(f"Impossibile analizzare il messaggio: {e}", "error")
                return redirect(url_for("analyzer"))
            return render_template("analyzer_result.html", r=result)
        return render_template("analyzer.html")


    # ---------------------------- Visualizzatore -------------------------- #
    @app.route("/campaigns/<int:cid>/preview/<int:tid>")
    def email_preview(cid, tid):
        """Mostra l'email renderizzata, come la vedrebbe il destinatario."""
        t = Target.query.get_or_404(tid)
        tpl = get_template(t.campaign.template_key)
        if not tpl:
            flash("Template non trovato.", "error")
            return redirect(url_for("campaign_detail", cid=cid))

        link = f"{Config.BASE_URL}/c/{t.token}"
        # Pixel 1x1 trasparente "inerte": in anteprima NON registra un'apertura.
        transparent = ("data:image/gif;base64,"
                       "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
        # escape() sul nome: evita che un nome con HTML dentro rompa/inietti la pagina.
        safe_name = escape(t.participant.name)
        body = tpl["body"].format(name=safe_name, link=link, pixel=transparent)

        from_display = f"{Config.FROM_NAME} <{Config.FROM_ADDRESS}>"
        return render_template("email_preview.html", t=t, tpl=tpl,
                               body=body, from_display=from_display)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)