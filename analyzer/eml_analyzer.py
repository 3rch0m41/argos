"""
Analizzatore difensivo di email sospette (.eml / raw RFC822).

Non invia e non contatta nulla: solo parsing locale e analisi euristica.
Produce un elenco di findings (ciascuno con severita e spiegazione) e un
punteggio di rischio 0-100.
"""
import re
from email import message_from_bytes, policy
from email.utils import parseaddr
from html.parser import HTMLParser
from urllib.parse import urlparse

# TLD a due livelli piu comuni, per approssimare il dominio "registrabile".
_TWO_LEVEL_TLDS = {
    "co.uk", "org.uk", "gov.uk", "ac.uk", "co.jp", "com.au", "co.it",
    "com.br", "co.in", "com.mx", "co.za", "com.tr", "gov.it",
}

_SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly",
    "rebrand.ly", "cutt.ly", "shorturl.at", "rb.gy", "t.ly",
}

_URGENCY_WORDS = [
    "urgente", "immediat", "scad", "sospension", "sospeso", "bloccat",
    "verifica subito", "entro oggi", "ultima possibilita", "agire ora",
    "azione richiesta", "conferma i tuoi dati", "account compromesso",
    "urgent", "immediately", "verify now", "suspend", "within 24",
    "act now", "final notice", "password expire",
]

_RISKY_EXT = {
    "exe", "scr", "com", "pif", "bat", "cmd", "js", "jse", "vbs", "vbe",
    "wsf", "hta", "jar", "ps1", "msi", "iso", "img", "lnk", "reg",
}
_MACRO_EXT = {"docm", "xlsm", "pptm", "dotm", "xlam"}


# --------------------------- helper di dominio --------------------------- #
def _is_ip(host):
    return bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host or "")) or ":" in (host or "")


def registrable_domain(host):
    host = (host or "").lower().strip().rstrip(".")
    if not host or _is_ip(host):
        return host
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if ".".join(parts[-2:]) in _TWO_LEVEL_TLDS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _domain_of_email(addr):
    _, email_addr = parseaddr(addr or "")
    return email_addr.rsplit("@", 1)[-1].lower() if "@" in email_addr else ""


# --------------------------- estrazione link ---------------------------- #
class _LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._href = href
                self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._text).strip()))
            self._href = None
            self._text = []


_URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)


def _extract_links(html_body, text_body):
    links = []
    if html_body:
        p = _LinkExtractor()
        try:
            p.feed(html_body)
        except Exception:
            pass
        links.extend(p.links)
    if text_body:
        for m in _URL_RE.findall(text_body):
            links.append((m, ""))
    seen, out = set(), []
    for href, text in links:
        if href not in seen:
            seen.add(href)
            out.append((href, text))
    return out


# ------------------------------- finding -------------------------------- #
_WEIGHT = {"high": 35, "medium": 18, "low": 7}


def _finding(level, title, detail):
    return {"level": level, "title": title, "detail": detail, "weight": _WEIGHT[level]}


# ------------------------------- corpo ---------------------------------- #
def _bodies(msg):
    html_body, text_body = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart" or part.get_filename():
                continue
            try:
                payload = part.get_content()
            except Exception:
                continue
            if part.get_content_type() == "text/html" and not html_body:
                html_body = payload
            elif part.get_content_type() == "text/plain" and not text_body:
                text_body = payload
    else:
        try:
            content = msg.get_content()
        except Exception:
            content = ""
        if msg.get_content_type() == "text/html":
            html_body = content
        else:
            text_body = content
    return html_body, text_body


def _strip_html(html):
    return re.sub(r"<[^>]+>", " ", html or "")


# --------------------------- sotto-analisi ------------------------------ #
def _parse_auth(auth_results, received_spf):
    out = {"spf": None, "dkim": None, "dmarc": None}
    ar = auth_results.lower()
    for mech in out:
        m = re.search(rf"{mech}=(\w+)", ar)
        if m:
            out[mech] = m.group(1)
    if out["spf"] is None and received_spf:
        m = re.match(r"\s*(\w+)", received_spf.lower())
        if m:
            out["spf"] = m.group(1)
    return out


def _display_name_domain(name):
    if not name:
        return ""
    m = re.search(r"([a-z0-9-]+\.[a-z]{2,}(?:\.[a-z]{2,})?)", name.lower())
    return m.group(1) if m else ""


def _analyze_links(links, from_domain):
    findings = []
    for href, text in links:
        try:
            host = (urlparse(href).hostname or "").lower()
        except Exception:
            continue
        if not host:
            continue
        if _is_ip(host):
            findings.append(_finding("high", "Link verso indirizzo IP",
                f"Il link punta a un IP ({host}) invece che a un dominio."))
        if "xn--" in host:
            findings.append(_finding("high", "Dominio punycode (possibile omografo)",
                f"Il link usa punycode ({host}): puo imitare un dominio noto."))
        if registrable_domain(host) in _SHORTENERS:
            findings.append(_finding("medium", "URL shortener",
                f"Link accorciato ({host}): nasconde la vera destinazione."))
        anchor_dom = _display_name_domain(text)
        if anchor_dom and registrable_domain(anchor_dom) != registrable_domain(host):
            findings.append(_finding("high", "Testo del link ingannevole",
                f"Il link mostra '{anchor_dom}' ma porta a '{host}'."))
        if host.count(".") >= 4:
            findings.append(_finding("low", "Molti sottodomini",
                f"Host con molti livelli ({host}): spesso usato per confondere."))
    return findings


def _analyze_attachments(msg):
    findings = []
    for part in msg.iter_attachments():
        fname = (part.get_filename() or "").lower()
        ext = fname.rsplit(".", 1)[-1] if "." in fname else ""
        parts = fname.split(".")
        if ext in _RISKY_EXT:
            findings.append(_finding("high", "Allegato eseguibile",
                f"'{fname}' ha estensione a rischio (.{ext}): puo eseguire codice."))
        elif ext in _MACRO_EXT:
            findings.append(_finding("medium", "Documento Office con macro",
                f"'{fname}' puo contenere macro (.{ext}), vettore comune di malware."))
        if len(parts) >= 3 and parts[-2] in {"pdf", "doc", "docx", "xls", "jpg", "txt"}:
            findings.append(_finding("high", "Doppia estensione",
                f"'{fname}' usa una doppia estensione per mascherare il tipo reale."))
    return findings


# --------------------------- analisi principale ------------------------- #
def analyze_bytes(raw):
    msg = message_from_bytes(raw, policy=policy.default)
    findings = []

    from_hdr = str(msg.get("From", ""))
    reply_to = str(msg.get("Reply-To", ""))
    return_path = str(msg.get("Return-Path", ""))
    subject = str(msg.get("Subject", ""))
    auth_results = str(msg.get("Authentication-Results", ""))
    received_spf = str(msg.get("Received-SPF", ""))

    from_name, _ = parseaddr(from_hdr)
    from_domain = _domain_of_email(from_hdr)

    # 1) Autenticazione SPF/DKIM/DMARC
    auth = _parse_auth(auth_results, received_spf)
    for mech in ("spf", "dkim", "dmarc"):
        v = auth.get(mech)
        if v == "fail":
            findings.append(_finding("high", f"{mech.upper()} fallito",
                f"Il server ricevente riporta {mech.upper()}=fail: forte indizio di mittente contraffatto."))
        elif v == "softfail":
            findings.append(_finding("medium", f"{mech.upper()} softfail",
                f"{mech.upper()} in softfail: mittente non pienamente autorizzato."))
        elif v is None:
            findings.append(_finding("low", f"{mech.upper()} non verificabile",
                f"Nessun risultato {mech.upper()} negli header."))

    # 2) Mismatch From / Reply-To / Return-Path
    rt = _domain_of_email(reply_to)
    if rt and registrable_domain(rt) != registrable_domain(from_domain):
        findings.append(_finding("medium", "Reply-To diverso dal From",
            f"Le risposte andrebbero a '{rt}', diverso dal mittente '{from_domain}'."))
    rp = _domain_of_email(return_path)
    if rp and registrable_domain(rp) != registrable_domain(from_domain):
        findings.append(_finding("low", "Return-Path diverso dal From",
            f"Il percorso di ritorno '{rp}' non combacia con '{from_domain}'."))

    # 3) Spoofing del display name
    dn = _display_name_domain(from_name)
    if dn and from_domain and registrable_domain(dn) != registrable_domain(from_domain):
        findings.append(_finding("high", "Display name ingannevole",
            f"Il nome mostrato richiama '{dn}' ma l'indirizzo reale e su '{from_domain}'."))

    # 4) Link
    html_body, text_body = _bodies(msg)
    links = _extract_links(html_body, text_body)
    findings.extend(_analyze_links(links, from_domain))

    # 5) Urgenza
    blob = f"{subject}\n{text_body}\n{_strip_html(html_body)}".lower()
    hits = sorted({w for w in _URGENCY_WORDS if w in blob})
    if len(hits) >= 2:
        findings.append(_finding("medium", "Linguaggio di urgenza/pressione",
            "Termini che spingono all'azione impulsiva: " + ", ".join(hits[:6]) + "."))
    elif hits:
        findings.append(_finding("low", "Possibile leva emotiva",
            f"Presente linguaggio di urgenza: {hits[0]}."))

    # 6) Allegati
    findings.extend(_analyze_attachments(msg))

    # Punteggio
    score = min(100, sum(f["weight"] for f in findings))
    level = "Alto" if score >= 55 else "Medio" if score >= 25 else "Basso"
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: order[f["level"]])

    return {
        "headers": {
            "from": from_hdr, "from_domain": from_domain,
            "reply_to": reply_to, "return_path": return_path,
            "subject": subject, "auth": auth,
        },
        "links": [{"href": h, "text": t} for h, t in links],
        "findings": findings,
        "score": score,
        "level": level,
    }