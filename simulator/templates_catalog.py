"""
Catalogo dei template di simulazione.

Ogni template è uno scenario didattico. Il campo `indicators` elenca i
campanelli d'allarme DELIBERATAMENTE inseriti nel messaggio: sono gli stessi
che la landing page educativa mostrerà al partecipante dopo il click,
trasformando l'errore in una micro-lezione.

Nota di design: questi template sono volutamente riconoscibili e generici.
Lo scopo è addestrare a riconoscere pattern, non massimizzare l'inganno.

Placeholder disponibili nel corpo:
  {name}  -> nome del partecipante
  {link}  -> URL di tracciamento (porta alla landing educativa)
  {pixel} -> URL del pixel di apertura (immagine 1x1)
"""

TEMPLATES = {
    "reset_password": {
        "name": "Reset password urgente (IT Helpdesk)",
        "subject": "[Azione richiesta] La tua password scade tra 2 ore",
        "indicators": [
            "Urgenza artificiale: scadenza improvvisa e minacciosa ('tra 2 ore').",
            "Mittente generico che si spaccia per l'IT interno.",
            "Richiesta di cliccare un link per 'verificare' le credenziali.",
            "Saluto impersonale e tono allarmistico.",
        ],
        "body": """\
<p>Gentile {name},</p>
<p>Il nostro sistema ha rilevato che la tua password <b>scadra tra 2 ore</b>.
Per evitare il blocco dell'account, verifica immediatamente le credenziali:</p>
<p><a href="{link}">Verifica ora il tuo account</a></p>
<p>Se non completi la verifica, l'accesso verra sospeso senza preavviso.</p>
<p>Supporto IT</p>
<img src="{pixel}" width="1" height="1" alt="">
""",
    },
    "invoice": {
        "name": "Fattura in sospeso (fornitore)",
        "subject": "Fattura n. 2026-0487 scaduta - sollecito di pagamento",
        "indicators": [
            "Allegato/link a una 'fattura' inattesa da un fornitore sconosciuto.",
            "Pressione sul pagamento immediato per evitare 'more'.",
            "Numero di fattura verosimile ma non verificabile.",
            "Link che non corrisponde al dominio del presunto fornitore.",
        ],
        "body": """\
<p>Buongiorno {name},</p>
<p>Risulta ancora non saldata la fattura <b>n. 2026-0487</b> con scadenza
superata. La invitiamo a regolarizzare il pagamento per evitare more e la
sospensione del servizio.</p>
<p><a href="{link}">Visualizza e scarica la fattura</a></p>
<p>Cordiali saluti,<br>Ufficio Amministrazione</p>
<img src="{pixel}" width="1" height="1" alt="">
""",
    },
    "shared_file": {
        "name": "Documento condiviso (cloud)",
        "subject": "Un collega ha condiviso un documento con te",
        "indicators": [
            "Notifica di condivisione che imita un servizio cloud noto.",
            "Nessun contesto: non si sa chi ha condiviso ne cosa.",
            "Pulsante 'Apri' che maschera la vera destinazione del link.",
            "Fa leva sulla curiosita ('documento riservato').",
        ],
        "body": """\
<p>Ciao {name},</p>
<p>Un collega ha condiviso con te un documento riservato tramite la
piattaforma cloud aziendale.</p>
<p><a href="{link}">Apri il documento</a></p>
<p>Il link scade tra 24 ore per motivi di sicurezza.</p>
<img src="{pixel}" width="1" height="1" alt="">
""",
    },
    "hr_bonus": {
        "name": "Comunicazione HR - premio di produzione",
        "subject": "Conferma dati per erogazione premio di produzione",
        "indicators": [
            "Fa leva su un incentivo economico desiderabile (il premio).",
            "Richiesta di 'confermare i dati' su un portale esterno.",
            "Si spaccia per le Risorse Umane senza canali ufficiali.",
            "Tempistica stretta per spingere all'azione impulsiva.",
        ],
        "body": """\
<p>Gentile {name},</p>
<p>E stato approvato il premio di produzione del trimestre. Per procedere
all'erogazione e necessario confermare i tuoi dati entro oggi:</p>
<p><a href="{link}">Conferma i dati e sblocca il premio</a></p>
<p>Risorse Umane</p>
<img src="{pixel}" width="1" height="1" alt="">
""",
    },
}


def get_template(key):
    """Restituisce un template dato il suo identificativo, o None se non esiste."""
    return TEMPLATES.get(key)


def list_templates():
    """Restituisce tutti i template come lista, ciascuno con la sua chiave."""
    return [{"key": k, **v} for k, v in TEMPLATES.items()]