"""
Automatic lead generation for Sawari Travel (https://sawaritravel.com).

Runs a small web server (standard library only, no pip install needed) that:
  1. Shows a "Plan my trip" enquiry form visitors can fill in
  2. Validates and saves every enquiry as a lead in SQLite
  3. Scores each lead HOT / WARM / COLD so you call the best ones first
  4. Emails the visitor an instant reply and alerts you about the new lead
     by email and WhatsApp
  5. Gives you a password-protected dashboard and a CSV export

Run:   python lead_generator.py
Open:  http://localhost:8000          (enquiry form)
       http://localhost:8000/admin    (dashboard, login admin / ADMIN_PASSWORD)

On the live site, host this at https://leads.sawaritravel.com and add one line
to every page of sawaritravel.com to get a "Plan my trip" popup form:
    <script src="https://leads.sawaritravel.com/widget.js" defer></script>
"""

import base64
import csv
import html
import io
import json
import os
import re
import smtplib
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

# ---------------------------------------------------------------- settings
# Change these with environment variables instead of editing the code.
SITE_NAME = os.environ.get("SITE_NAME", "Sawari Travel")
SITE_URL = os.environ.get("SITE_URL", "https://sawaritravel.com")
# Websites allowed to send leads to /api/leads from the browser (the widget).
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "https://sawaritravel.com,https://www.sawaritravel.com").split(",")
OWN_DOMAINS = {urlparse(o.strip()).netloc for o in ALLOWED_ORIGINS + [SITE_URL]}
PORT = int(os.environ.get("PORT", "8000"))
DB_FILE = os.environ.get("LEADS_DB", "leads.db")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me")

# Email (optional). If SMTP_HOST is empty, emails are written to outbox.log.
SMTP_HOST = os.environ.get("SMTP_HOST", "")          # e.g. smtp.gmail.com
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")  # Gmail: use an App Password
SALES_EMAIL = os.environ.get("SALES_EMAIL", SMTP_USER or "sales@example.com")

# WhatsApp alerts (optional) via the WhatsApp Business Cloud API from Meta.
# If WHATSAPP_TOKEN is empty, alerts are written to whatsapp_outbox.log.
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
# Numbers to alert, with country code and no "+", comma separated: 919876543210,918765432109
WHATSAPP_ALERT_TO = [n.strip().lstrip("+") for n in os.environ.get("WHATSAPP_ALERT_TO", "").split(",") if n.strip()]
# Approved template name. Needed to message someone who has not written to your
# business number in the last 24 hours. Its body must have 1 variable: {{1}}.
WHATSAPP_TEMPLATE = os.environ.get("WHATSAPP_TEMPLATE", "")
WHATSAPP_TEMPLATE_LANG = os.environ.get("WHATSAPP_TEMPLATE_LANG", "en")
# Only alert for leads at or above this rating: HOT, WARM or COLD (= every lead)
WHATSAPP_MIN_RATING = os.environ.get("WHATSAPP_MIN_RATING", "COLD").upper()
WHATSAPP_API_VERSION = "v21.0"

TRIP_TYPES = ["Honeymoon", "Family", "Adventure", "Pilgrimage", "Beach", "Corporate", "Other"]
BUDGETS = {  # label -> budget per person in INR (used for scoring)
    "Under 20,000": 15000,
    "20,000 - 50,000": 35000,
    "50,000 - 1,00,000": 75000,
    "Above 1,00,000": 150000,
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
PHONE_RE = re.compile(r"^[6-9][0-9]{9}$")  # Indian mobile number


# ---------------------------------------------------------------- database
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at   TEXT NOT NULL,
                name         TEXT NOT NULL,
                email        TEXT NOT NULL,
                phone        TEXT NOT NULL,
                destination  TEXT NOT NULL,
                travel_date  TEXT,
                travelers    INTEGER,
                budget       TEXT,
                trip_type    TEXT,
                message      TEXT,
                source       TEXT,
                score        INTEGER,
                rating       TEXT,
                status       TEXT DEFAULT 'New'
            )""")


def find_recent_duplicate(email, destination):
    """Same person asking about the same place within 24 hours = same lead."""
    since = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
    with get_db() as conn:
        return conn.execute(
            "SELECT id FROM leads WHERE lower(email)=lower(?) AND lower(destination)=lower(?)"
            " AND created_at >= ?", (email, destination, since)).fetchone()


def save_lead(lead):
    columns = ", ".join(lead)
    marks = ", ".join("?" for _ in lead)
    with get_db() as conn:
        cur = conn.execute(f"INSERT INTO leads ({columns}) VALUES ({marks})", list(lead.values()))
        return cur.lastrowid


def all_leads():
    with get_db() as conn:
        return conn.execute("SELECT * FROM leads ORDER BY score DESC, created_at DESC").fetchall()


def update_status(lead_id, status):
    with get_db() as conn:
        conn.execute("UPDATE leads SET status=? WHERE id=?", (status, lead_id))


# ---------------------------------------------------------------- lead logic
def validate(form):
    """Return (clean_lead, errors)."""
    get = lambda key: form.get(key, [""])[0].strip()
    lead = {
        "name": get("name"),
        "email": get("email"),
        "phone": re.sub(r"[\s-]", "", get("phone")).removeprefix("+91"),
        "destination": get("destination"),
        "travel_date": get("travel_date"),
        "travelers": get("travelers") or "1",
        "budget": get("budget"),
        "trip_type": get("trip_type"),
        "message": get("message")[:1000],
        "source": get("source")[:100],
    }
    errors = []
    if len(lead["name"]) < 2:
        errors.append("Please enter your name.")
    if not EMAIL_RE.match(lead["email"]):
        errors.append("Please enter a valid email address.")
    if not PHONE_RE.match(lead["phone"]):
        errors.append("Please enter a valid 10-digit mobile number.")
    if not lead["destination"]:
        errors.append("Where would you like to go?")
    if lead["travel_date"]:
        try:
            if date.fromisoformat(lead["travel_date"]) < date.today():
                errors.append("Travel date cannot be in the past.")
        except ValueError:
            errors.append("Please pick a valid travel date.")
    if not lead["travelers"].isdigit() or not 1 <= int(lead["travelers"]) <= 100:
        errors.append("Number of travellers must be between 1 and 100.")
    else:
        lead["travelers"] = int(lead["travelers"])
    if lead["budget"] and lead["budget"] not in BUDGETS:
        errors.append("Please choose a budget from the list.")
    if lead["trip_type"] and lead["trip_type"] not in TRIP_TYPES:
        errors.append("Please choose a trip type from the list.")
    if form.get("website", [""])[0]:  # hidden honeypot field: only bots fill it
        errors.append("Spam detected.")
    return lead, errors


def score_lead(lead):
    """0-100 score: bigger budget, bigger group, sooner trip and detail = hotter lead."""
    score = 10  # they enquired and gave a valid phone number
    per_person = BUDGETS.get(lead["budget"], 0)
    total_value = per_person * lead["travelers"]
    if total_value >= 300000:
        score += 35
    elif total_value >= 100000:
        score += 25
    elif total_value >= 40000:
        score += 15
    elif total_value:
        score += 5

    if lead["travel_date"]:
        days_away = (date.fromisoformat(lead["travel_date"]) - date.today()).days
        if days_away <= 30:
            score += 30
        elif days_away <= 90:
            score += 20
        else:
            score += 10

    if lead["trip_type"] in ("Honeymoon", "Corporate", "Family"):
        score += 10
    if len(lead["message"]) > 20:
        score += 10
    if lead["source"]:
        score += 5

    score = min(score, 100)
    rating = "HOT" if score >= 70 else "WARM" if score >= 40 else "COLD"
    return score, rating


# ---------------------------------------------------------------- email
def send_email(to, subject, body):
    msg = EmailMessage()
    msg["From"] = SMTP_USER or SALES_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if not SMTP_HOST:
        with open("outbox.log", "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\n{msg}")
        return
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as exc:  # never lose a lead because email failed
        print(f"[email] could not send to {to}: {exc}")


# ---------------------------------------------------------------- whatsapp
RATING_RANK = {"COLD": 0, "WARM": 1, "HOT": 2}


def whatsapp_link(phone, text=""):
    """Click-to-chat link that opens WhatsApp with the lead (10-digit Indian number)."""
    return f"https://wa.me/91{phone}" + (f"?text={quote(text)}" if text else "")


def send_whatsapp(to, text):
    if not (WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID):
        with open("whatsapp_outbox.log", "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\nTo: {to}\n{text}\n")
        return
    if WHATSAPP_TEMPLATE:
        # Template variables cannot contain new lines, tabs or 4+ spaces.
        summary = re.sub(r"\s+", " ", text)[:1000]
        payload = {"type": "template", "template": {
            "name": WHATSAPP_TEMPLATE,
            "language": {"code": WHATSAPP_TEMPLATE_LANG},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": summary}]}]}}
    else:
        payload = {"type": "text", "text": {"body": text, "preview_url": False}}
    payload.update(messaging_product="whatsapp", to=to)
    request = Request(
        f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=15):
            pass
    except HTTPError as exc:  # never lose a lead because WhatsApp failed
        print(f"[whatsapp] could not send to {to}: {exc.code} {exc.read().decode(errors='replace')[:300]}")
    except URLError as exc:
        print(f"[whatsapp] could not send to {to}: {exc.reason}")


def whatsapp_alert(lead_id, lead):
    if RATING_RANK[lead["rating"]] < RATING_RANK.get(WHATSAPP_MIN_RATING, 0):
        return
    greeting = f"Hi {lead['name']}, thanks for your {lead['destination']} trip enquiry with {SITE_NAME}!"
    text = (f"New {lead['rating']} lead #{lead_id} (score {lead['score']}/100)\n"
            f"Name: {lead['name']}\n"
            f"Phone: +91 {lead['phone']}\n"
            f"Trip: {lead['destination']}, {lead['travel_date'] or 'flexible date'}, "
            f"{lead['travelers']} pax\n"
            f"Budget: {lead['budget'] or 'not given'} | {lead['trip_type'] or 'any'}\n"
            f"Source: {lead['source'] or 'direct'}\n"
            f"Chat now: {whatsapp_link(lead['phone'], greeting)}")
    for number in WHATSAPP_ALERT_TO or ["(set WHATSAPP_ALERT_TO)"]:
        send_whatsapp(number, text)


def notify(lead_id, lead):
    send_email(
        lead["email"],
        f"Your {lead['destination']} trip enquiry - {SITE_NAME}",
        f"Hi {lead['name']},\n\n"
        f"Thank you for your interest in travelling to {lead['destination']}! "
        f"Our travel expert will call you on {lead['phone']} within 24 hours "
        f"with a personalised itinerary and the best price.\n\n"
        f"Your reference number is #{lead_id}.\n\nHappy travels,\nTeam {SITE_NAME}\n{SITE_URL}\n")
    send_email(
        SALES_EMAIL,
        f"[{lead['rating']} LEAD #{lead_id}] {lead['name']} -> {lead['destination']}",
        "\n".join(f"{k:12}: {v}" for k, v in lead.items()))
    whatsapp_alert(lead_id, lead)


def capture_lead(form):
    """Full pipeline. Returns (lead_id or None, errors)."""
    lead, errors = validate(form)
    if errors:
        return None, errors
    duplicate = find_recent_duplicate(lead["email"], lead["destination"])
    if duplicate:
        return duplicate["id"], []
    lead["score"], lead["rating"] = score_lead(lead)
    lead["created_at"] = datetime.now().isoformat(timespec="seconds")
    lead_id = save_lead(lead)
    notify(lead_id, lead)
    print(f"[lead] #{lead_id} {lead['rating']} ({lead['score']}) {lead['name']} -> {lead['destination']}")
    return lead_id, []


# ---------------------------------------------------------------- pages
STYLE = """
body{font-family:system-ui,sans-serif;margin:0;background:#f2f6f9;color:#1d2b36}
header{background:linear-gradient(120deg,#0b6e8a,#1aa39a);color:#fff;padding:40px 16px;text-align:center}
header h1{margin:0 0 8px}main{max-width:960px;margin:-24px auto 40px;padding:0 16px}
.card{background:#fff;border-radius:12px;padding:24px;box-shadow:0 4px 20px #0001}
form{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{font-size:14px;font-weight:600}
input,select,textarea{width:100%;box-sizing:border-box;padding:10px;border:1px solid #c7d3dc;border-radius:8px;font:inherit;margin-top:4px}
.full{grid-column:1/-1}button{background:#f28c28;color:#fff;border:0;padding:14px;border-radius:8px;font-size:16px;font-weight:700;cursor:pointer}
.err{background:#fde8e8;color:#9b1c1c;padding:12px;border-radius:8px;margin-bottom:14px}
.hp{display:none}table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:8px;border-bottom:1px solid #e3e9ee;vertical-align:top}
.HOT{color:#c0392b;font-weight:700}.WARM{color:#d68910;font-weight:700}.COLD{color:#5d6d7e}
.stats{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}.stats div{background:#fff;border-radius:10px;padding:12px 18px;box-shadow:0 2px 8px #0001}
@media(max-width:640px){form{grid-template-columns:1fr}}
"""


def page(title, body):
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>{body}</body></html>")


def options(values, selected):
    return "".join(f"<option{' selected' if v == selected else ''}>{html.escape(v)}</option>" for v in values)


def form_page(errors=(), values=None, source=""):
    v = {k: html.escape(str(x)) for k, x in (values or {}).items()}
    error_box = ("<div class='err'>" + "<br>".join(map(html.escape, errors)) + "</div>") if errors else ""
    return page(SITE_NAME, f"""
<header><h1>Plan your dream holiday</h1><p>Tell us where you want to go - get a free custom itinerary within 24 hours.</p></header>
<main><div class="card">{error_box}
<form method="post" action="/enquiry">
  <label>Full name<input name="name" value="{v.get('name', '')}" required></label>
  <label>Email<input type="email" name="email" value="{v.get('email', '')}" required></label>
  <label>Mobile number<input name="phone" value="{v.get('phone', '')}" placeholder="10-digit mobile" required></label>
  <label>Destination<input name="destination" value="{v.get('destination', '')}" placeholder="e.g. Goa, Kerala, Dubai" required></label>
  <label>Travel date<input type="date" name="travel_date" value="{v.get('travel_date', '')}" min="{date.today()}"></label>
  <label>Travellers<input type="number" name="travelers" min="1" max="100" value="{v.get('travelers', '2')}"></label>
  <label>Budget per person (INR)<select name="budget"><option value="">Select</option>{options(BUDGETS, (values or {}).get('budget'))}</select></label>
  <label>Trip type<select name="trip_type"><option value="">Select</option>{options(TRIP_TYPES, (values or {}).get('trip_type'))}</select></label>
  <label class="full">Anything else we should know?<textarea name="message" rows="3">{v.get('message', '')}</textarea></label>
  <input class="hp" name="website" tabindex="-1" autocomplete="off">
  <input type="hidden" name="source" value="{html.escape(source or v.get('source', ''))}">
  <button class="full" type="submit">Get my free itinerary</button>
</form></div></main>""")


def thank_you_page(lead_id):
    return page("Thank you", f"""
<header><h1>Thank you!</h1><p>Your enquiry reference is #{lead_id}. Our travel expert will contact you within 24 hours.</p></header>
<main><div class="card"><p>We've also sent a confirmation to your email. <a href="{SITE_URL}">Back to {html.escape(SITE_NAME)}</a></p></div></main>""")


def admin_page():
    leads = all_leads()
    counts = {r: sum(1 for l in leads if l["rating"] == r) for r in ("HOT", "WARM", "COLD")}
    rows = "".join(f"""<tr>
<td>#{l['id']}<br><small>{l['created_at'].replace('T', ' ')}</small></td>
<td class="{l['rating']}">{l['rating']}<br><small>{l['score']}/100</small></td>
<td>{html.escape(l['name'])}<br><a href="tel:{l['phone']}">{l['phone']}</a> &middot; <a href="{html.escape(whatsapp_link(l['phone']))}" target="_blank">WhatsApp</a><br><a href="mailto:{html.escape(l['email'])}">{html.escape(l['email'])}</a></td>
<td>{html.escape(l['destination'])}<br><small>{l['travel_date'] or 'Flexible'} &middot; {l['travelers']} pax</small></td>
<td>{html.escape(l['budget'] or '-')}<br><small>{html.escape(l['trip_type'] or '')}</small></td>
<td>{html.escape(l['source'] or 'direct')}</td>
<td><form method="post" action="/admin/status" style="display:block">
<input type="hidden" name="id" value="{l['id']}">
<select name="status" onchange="this.form.submit()">{options(['New', 'Contacted', 'Quoted', 'Booked', 'Lost'], l['status'])}</select></form></td>
</tr>""" for l in leads)
    return page("Leads dashboard", f"""
<header><h1>Leads dashboard</h1><p>{len(leads)} total leads &middot; <a style="color:#fff" href="/admin/export.csv">Download CSV</a></p></header>
<main><div class="stats"><div class="HOT">HOT: {counts['HOT']}</div><div class="WARM">WARM: {counts['WARM']}</div><div class="COLD">COLD: {counts['COLD']}</div></div>
<div class="card" style="overflow-x:auto"><table><tr><th>Lead</th><th>Rating</th><th>Contact</th><th>Trip</th><th>Budget</th><th>Source</th><th>Status</th></tr>
{rows or '<tr><td colspan=7>No leads yet.</td></tr>'}</table></div></main>""")


def widget_js():
    config = {"siteName": SITE_NAME, "budgets": list(BUDGETS), "tripTypes": TRIP_TYPES}
    template = (Path(__file__).parent / "widget.js").read_text(encoding="utf-8")
    return template.replace("__CONFIG__", json.dumps(config))


def leads_csv():
    out = io.StringIO()
    leads = all_leads()
    writer = csv.writer(out)
    if leads:
        writer.writerow(leads[0].keys())
        writer.writerows(tuple(l) for l in leads)
    return out.getvalue()


# ---------------------------------------------------------------- web server
class Handler(BaseHTTPRequestHandler):
    def send(self, body, status=200, content_type="text/html; charset=utf-8", headers=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def cors_headers(self):
        origin = self.headers.get("Origin", "")
        if origin not in ALLOWED_ORIGINS:
            return {}
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"}

    def redirect(self, location):
        self.send("", 303, headers={"Location": location})

    def is_admin(self):
        expected = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()
        if self.headers.get("Authorization") == f"Basic {expected}":
            return True
        self.send("Login required", 401, "text/plain", {"WWW-Authenticate": 'Basic realm="Leads"'})
        return False

    def read_form(self):
        length = min(int(self.headers.get("Content-Length", 0)), 20000)
        raw = self.rfile.read(length).decode("utf-8", "replace")
        if self.headers.get("Content-Type", "").startswith("application/json"):
            try:
                return {k: [str(v)] for k, v in json.loads(raw or "{}").items()}
            except (json.JSONDecodeError, AttributeError):
                return {}
        return parse_qs(raw)

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/":
            # Remember where the visitor came from (Google ads, Instagram, ...)
            referrer = urlparse(self.headers.get("Referer", "")).netloc
            source = (query.get("utm_source", [""])[0] or query.get("ref", [""])[0]
                      or ("" if referrer in OWN_DOMAINS else referrer))
            self.send(form_page(source=source))
        elif url.path == "/widget.js":
            self.send(widget_js(), content_type="application/javascript; charset=utf-8",
                      headers={"Cache-Control": "public, max-age=3600"})
        elif url.path == "/thank-you":
            self.send(thank_you_page(html.escape(query.get("id", [""])[0])))
        elif url.path == "/admin" and self.is_admin():
            self.send(admin_page())
        elif url.path == "/admin/export.csv" and self.is_admin():
            self.send(leads_csv(), content_type="text/csv",
                      headers={"Content-Disposition": "attachment; filename=leads.csv"})
        elif not url.path.startswith("/admin"):
            self.send(page("Not found", "<main><h1>Page not found</h1></main>"), 404)

    def do_OPTIONS(self):  # browser "preflight" check before the widget posts a lead
        self.send("", 204, "text/plain", self.cors_headers())

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/enquiry":
            form = self.read_form()
            lead_id, errors = capture_lead(form)
            if errors:
                values = {k: v[0] for k, v in form.items()}
                self.send(form_page(errors, values), 400)
            else:
                self.redirect(f"/thank-you?id={lead_id}")
        elif path == "/api/leads":
            # Used by widget.js on sawaritravel.com, or any other form: POST JSON here.
            lead_id, errors = capture_lead(self.read_form())
            self.send(json.dumps({"ok": not errors, "id": lead_id, "errors": errors}),
                      400 if errors else 201, "application/json", self.cors_headers())
        elif path == "/admin/status" and self.is_admin():
            form = self.read_form()
            lead_id = form.get("id", [""])[0]
            status = form.get("status", [""])[0]
            if lead_id.isdigit() and status in ("New", "Contacted", "Quoted", "Booked", "Lost"):
                update_status(int(lead_id), status)
            self.redirect("/admin")
        elif not path.startswith("/admin"):
            self.send("Not found", 404, "text/plain")


if __name__ == "__main__":
    init_db()
    if ADMIN_PASSWORD == "change-me":
        print("WARNING: set the ADMIN_PASSWORD environment variable before going live.")
    print(f"Enquiry form:  http://localhost:{PORT}")
    print(f"Dashboard:     http://localhost:{PORT}/admin  (user: {ADMIN_USER})")
    print(f"Widget:        http://localhost:{PORT}/widget.js  (add to {SITE_URL})")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
