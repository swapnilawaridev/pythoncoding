"""
Business lead finder for Sawari Travel.

Finds businesses that buy group travel (companies, colleges, schools, wedding
planners, housing societies ...) in any city using the Google Places API, and
gives you a simple sales pipeline to track who you've called or messaged.

Standard library only, nothing to install. Runs on your own computer:

    GOOGLE_MAPS_API_KEY=your-key python finder.py
    open http://localhost:8001
"""

import csv
import html
import io
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen

# ---------------------------------------------------------------- settings
API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
PLACES_API = os.environ.get("PLACES_API_URL", "https://places.googleapis.com/v1")
PORT = int(os.environ.get("PORT", "8001"))
DB_FILE = os.environ.get("PROSPECTS_DB", "prospects.db")
SITE_URL = os.environ.get("SITE_URL", "https://sawaritravel.com")
PLANNER_URL = os.environ.get("PLANNER_URL", SITE_URL + "/trip-planner")
MAX_PAGES = 3  # Google returns 20 results per page, so up to 60 per search
# Google's terms limit how long Places details may be kept. Details older than
# this are cleared (your status and notes stay) and can be re-downloaded.
KEEP_DETAILS_DAYS = 30
STATUSES = ["New", "Contacted", "Interested", "Quoted", "Won", "Not interested"]

# Who buys group trips, what to search for, and what to say to them.
# Edit the pitches to match your offers.
SEGMENTS = {
    "Companies": {
        "query": "IT companies",
        "pitch": "Hi, this is {agent} from Sawari Travel ({site}). We plan corporate offsites, "
                 "team outings and business travel for companies in {city}, with one point of "
                 "contact and GST invoices. Could I share a few team trip ideas and prices?",
    },
    "Colleges": {
        "query": "engineering colleges",
        "pitch": "Hello, this is {agent} from Sawari Travel ({site}). We organise industrial "
                 "visits and educational tours for colleges in {city}: travel, stay, food and "
                 "permissions handled end to end. May I send you our student tour packages?",
    },
    "Schools": {
        "query": "schools",
        "pitch": "Hello, this is {agent} from Sawari Travel ({site}). We arrange safe, fully "
                 "supervised school excursions and study tours from {city}. Can I share a few "
                 "options for your next school trip?",
    },
    "Wedding planners": {
        "query": "wedding planners",
        "pitch": "Hi, this is {agent} from Sawari Travel ({site}). We handle honeymoon packages, "
                 "destination weddings and guest travel. Would you be open to a referral "
                 "partnership for your couples in {city}?",
    },
    "Housing societies": {
        "query": "housing society",
        "pitch": "Namaste, this is {agent} from Sawari Travel ({site}). We organise group tours "
                 "and pilgrimage trips for residents and senior citizens in {city}, with special "
                 "group prices. Could I share some upcoming trip plans for your society?",
    },
    "Banks & insurance": {
        "query": "insurance office",
        "pitch": "Hi, this is {agent} from Sawari Travel ({site}). We plan incentive trips and "
                 "reward holidays for top-performing sales teams in {city}. May I share a few "
                 "domestic and international options?",
    },
    "Gyms & clubs": {
        "query": "sports club",
        "pitch": "Hi, this is {agent} from Sawari Travel ({site}). We plan adventure trips "
                 "(treks, rafting, Ladakh bike tours) for groups from {city}. Would your members "
                 "be interested in a group trip?",
    },
}
AGENT_NAME = os.environ.get("AGENT_NAME", "Sawari Travel team")


# ---------------------------------------------------------------- database
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prospects (
                place_id      TEXT PRIMARY KEY,
                segment       TEXT,
                city          TEXT,
                name          TEXT,
                address       TEXT,
                phone         TEXT,
                website       TEXT,
                rating        REAL,
                reviews       INTEGER,
                maps_url      TEXT,
                fetched_at    TEXT,
                status        TEXT DEFAULT 'New',
                notes         TEXT DEFAULT '',
                contacted_at  TEXT,
                added_at      TEXT
            )""")


def expire_old_details():
    """Delete untouched old results; for prospects you worked on, keep only your own data."""
    cutoff = (datetime.now() - timedelta(days=KEEP_DETAILS_DAYS)).isoformat(timespec="seconds")
    with get_db() as conn:
        conn.execute("DELETE FROM prospects WHERE fetched_at < ? AND status = 'New' AND notes = ''", (cutoff,))
        conn.execute("""UPDATE prospects SET name=NULL, address=NULL, phone=NULL, website=NULL,
                        rating=NULL, reviews=NULL, maps_url=NULL, fetched_at=NULL
                        WHERE fetched_at < ?""", (cutoff,))


def save_places(places, segment, city):
    now = datetime.now().isoformat(timespec="seconds")
    added = 0
    with get_db() as conn:
        for p in places:
            added += not conn.execute("SELECT 1 FROM prospects WHERE place_id=?", (p["id"],)).fetchone()
            conn.execute("""
                INSERT INTO prospects (place_id, segment, city, name, address, phone, website,
                                       rating, reviews, maps_url, fetched_at, added_at)
                VALUES (:id, :segment, :city, :name, :address, :phone, :website,
                        :rating, :reviews, :maps_url, :now, :now)
                ON CONFLICT(place_id) DO UPDATE SET
                    name=excluded.name, address=excluded.address, phone=excluded.phone,
                    website=excluded.website, rating=excluded.rating, reviews=excluded.reviews,
                    maps_url=excluded.maps_url, fetched_at=excluded.fetched_at""",
                dict(p, segment=segment, city=city, now=now))
    return added


def list_prospects(status="", segment="", text=""):
    sql, args = "SELECT * FROM prospects WHERE 1=1", []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if segment:
        sql += " AND segment = ?"
        args.append(segment)
    if text:
        sql += " AND (name LIKE ? OR address LIKE ? OR notes LIKE ? OR city LIKE ?)"
        args += [f"%{text}%"] * 4
    sql += """ ORDER BY CASE status WHEN 'Interested' THEN 0 WHEN 'Quoted' THEN 1 WHEN 'Contacted' THEN 2
               WHEN 'New' THEN 3 WHEN 'Won' THEN 4 ELSE 5 END, COALESCE(phone, '') = '', reviews DESC"""
    with get_db() as conn:
        return conn.execute(sql, args).fetchall()


def update_prospect(place_id, status, notes):
    with get_db() as conn:
        old = conn.execute("SELECT status FROM prospects WHERE place_id=?", (place_id,)).fetchone()
        if not old:
            return
        contacted = datetime.now().isoformat(timespec="seconds") if status != old["status"] and status != "New" else None
        conn.execute("UPDATE prospects SET status=?, notes=?, contacted_at=COALESCE(?, contacted_at) WHERE place_id=?",
                     (status, notes[:2000], contacted, place_id))


# ---------------------------------------------------------------- google places
FIELDS = ["id", "displayName", "formattedAddress", "nationalPhoneNumber", "internationalPhoneNumber",
          "websiteUri", "rating", "userRatingCount", "googleMapsUri", "businessStatus"]


class PlacesError(Exception):
    pass


def places_request(path, body=None, field_mask=""):
    if not API_KEY:
        raise PlacesError("Set the GOOGLE_MAPS_API_KEY environment variable first (see README).")
    request = Request(f"{PLACES_API}{path}", data=json.dumps(body).encode() if body else None,
                      method="POST" if body else "GET",
                      headers={"Content-Type": "application/json", "X-Goog-Api-Key": API_KEY,
                               "X-Goog-FieldMask": field_mask})
    try:
        with urlopen(request, timeout=20) as res:
            return json.load(res)
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        try:
            detail = json.loads(detail)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            pass
        raise PlacesError(f"Google Places API error {exc.code}: {detail}") from None
    except URLError as exc:
        raise PlacesError(f"Could not reach Google: {exc.reason}") from None


def to_prospect(place):
    return {
        "id": place["id"],
        "name": place.get("displayName", {}).get("text", ""),
        "address": place.get("formattedAddress", ""),
        "phone": place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber", ""),
        "website": place.get("websiteUri", ""),
        "rating": place.get("rating"),
        "reviews": place.get("userRatingCount", 0),
        "maps_url": place.get("googleMapsUri", ""),
    }


def search_places(query):
    """Text search, following pages. Skips businesses that have closed down."""
    mask = ",".join(f"places.{f}" for f in FIELDS) + ",nextPageToken"
    body = {"textQuery": query, "pageSize": 20, "regionCode": "IN", "languageCode": "en"}
    results = []
    for _ in range(MAX_PAGES):
        data = places_request("/places:searchText", body, mask)
        results += [to_prospect(p) for p in data.get("places", [])
                    if p.get("businessStatus", "OPERATIONAL") == "OPERATIONAL"]
        if not data.get("nextPageToken"):
            break
        body["pageToken"] = data["nextPageToken"]
    return results


def refresh_place(place_id):
    place = places_request(f"/places/{quote(place_id)}", field_mask=",".join(FIELDS))
    now = datetime.now().isoformat(timespec="seconds")
    p = to_prospect(place)
    with get_db() as conn:
        conn.execute("""UPDATE prospects SET name=?, address=?, phone=?, website=?, rating=?, reviews=?,
                        maps_url=?, fetched_at=? WHERE place_id=?""",
                     (p["name"], p["address"], p["phone"], p["website"], p["rating"], p["reviews"],
                      p["maps_url"], now, place_id))


# ---------------------------------------------------------------- helpers
def whatsapp_number(phone):
    """Indian mobile numbers only; landlines are not on WhatsApp."""
    digits = re.sub(r"\D", "", phone or "")
    digits = re.sub(r"^(91|0)(?=[6-9]\d{9}$)", "", digits)
    return "91" + digits if re.fullmatch(r"[6-9]\d{9}", digits) else ""


def pitch_for(row):
    template = SEGMENTS.get(row["segment"], {}).get(
        "pitch", "Hi, this is {agent} from Sawari Travel ({site}). We plan group trips from {city}. "
                 "Could I share a few options with you?")
    return template.format(agent=AGENT_NAME, site=SITE_URL.replace("https://", ""), city=row["city"] or "your city",
                           planner=PLANNER_URL)


def esc(value):
    return html.escape(str(value)) if value not in (None, "") else ""


# ---------------------------------------------------------------- pages
STYLE = """
:root{--brand:#f28c28;--sea:#0b6e8a;--ink:#1d2b36;--muted:#5d6d7e;--line:#e3e9ee;--bg:#f2f6f9}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,sans-serif;color:var(--ink);background:var(--bg)}
header{background:linear-gradient(120deg,#0b6e8a,#1aa39a);color:#fff;padding:22px 16px}
header h1{margin:0;font-size:22px}header p{margin:4px 0 0;opacity:.9}
main{max-width:1200px;margin:0 auto;padding:16px}
.card{background:#fff;border-radius:12px;padding:18px;box-shadow:0 3px 14px #0b2a3a12;margin-bottom:16px}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:end}.row label{flex:1 1 180px;font-size:13px;font-weight:600}
input,select,textarea{width:100%;padding:9px;border:1px solid #c7d3dc;border-radius:8px;font:inherit;margin-top:3px;background:#fff}
button,.btn{background:var(--brand);color:#fff;border:0;border-radius:8px;padding:10px 16px;font:600 14px system-ui,sans-serif;cursor:pointer;text-decoration:none;display:inline-block}
.btn.small{padding:5px 10px;font-size:13px}.btn.wa{background:#1f9d55}.btn.call{background:var(--sea)}.btn.ghost{background:#fff;color:var(--sea);border:1px solid var(--sea)}
.msg{padding:12px;border-radius:8px;margin-bottom:14px}.ok{background:#e5f6ec;color:#17643a}.bad{background:#fde8e8;color:#9b1c1c}
.stats{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}.stats a{background:#fff;border-radius:20px;padding:6px 14px;color:var(--ink);text-decoration:none;box-shadow:0 1px 5px #0001;font-size:14px}
.stats a.on{background:var(--sea);color:#fff}
.p{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1.3fr) minmax(0,1.6fr);gap:14px;padding:14px 0;border-top:1px solid var(--line)}
.p h3{margin:0;font-size:16px}.muted{color:var(--muted);font-size:13px}.acts{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.tag{display:inline-block;background:#eef3f7;border-radius:10px;padding:1px 8px;font-size:12px;margin-right:4px}
.p form{display:grid;gap:6px}.p textarea{min-height:58px}
@media(max-width:800px){.p{grid-template-columns:1fr}}
"""


def page(body):
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Business Lead Finder | Sawari Travel</title><style>{STYLE}</style></head><body>"
            f"<header><h1>Business Lead Finder</h1><p>Find companies, colleges and groups that need travel, "
            f"then track every call and message.</p></header><main>{body}</main></body></html>")


def options(values, selected, blank=None):
    out = f"<option value=''>{blank}</option>" if blank else ""
    return out + "".join(f"<option{' selected' if v == selected else ''}>{esc(v)}</option>" for v in values)


def prospect_html(row):
    pid = esc(row["place_id"])
    if not row["name"]:
        details = (f"<h3 class='muted'>Details expired</h3><div class='muted'>Google details are cleared after "
                   f"{KEEP_DETAILS_DAYS} days. Your status and notes are kept.</div>"
                   f"<form method='post' action='/refresh' class='acts'><input type='hidden' name='id' value='{pid}'>"
                   f"<button class='btn small ghost'>Refresh details</button></form>")
    else:
        rating = f"★ {row['rating']} ({row['reviews']} reviews)" if row["rating"] else "No rating"
        wa = whatsapp_number(row["phone"])
        actions = []
        if row["phone"]:
            actions.append(f"<a class='btn small call' href='tel:{esc(re.sub(r'[^0-9+]', '', row['phone']))}'>Call</a>")
        if wa:
            actions.append(f"<a class='btn small wa' target='_blank' rel='noopener' "
                           f"href='https://wa.me/{wa}?text={quote(pitch_for(row))}'>WhatsApp</a>")
        if row["website"]:
            actions.append(f"<a class='btn small ghost' target='_blank' rel='noopener' href='{esc(row['website'])}'>Website</a>")
        if row["maps_url"]:
            actions.append(f"<a class='btn small ghost' target='_blank' rel='noopener' href='{esc(row['maps_url'])}'>Map</a>")
        details = (f"<h3>{esc(row['name'])}</h3><div class='muted'>{esc(row['address'])}</div>"
                   f"<div class='muted'>{rating}</div><div class='acts'>{''.join(actions)}</div>")
    phone = esc(row["phone"]) or "<span class='muted'>No phone listed</span>"
    contacted = f"Last update: {esc(row['contacted_at']).replace('T', ' ')}" if row["contacted_at"] else ""
    return f"""<div class="p">
<div>{details}</div>
<div><span class="tag">{esc(row['segment'])}</span><span class="tag">{esc(row['city'])}</span>
<div style="margin-top:6px">{phone}</div><div class="muted">{contacted}</div>
<details style="margin-top:6px"><summary class="muted">Suggested pitch</summary><p class="muted">{esc(pitch_for(row))}</p></details></div>
<form method="post" action="/update"><input type="hidden" name="id" value="{pid}">
<select name="status">{options(STATUSES, row['status'])}</select>
<textarea name="notes" placeholder="Notes: who you spoke to, follow-up date...">{esc(row['notes'])}</textarea>
<button class="btn small">Save</button></form>
</div>"""


def home_page(query, message=""):
    status = query.get("status", [""])[0]
    segment = query.get("segment", [""])[0]
    text = query.get("q", [""])[0]
    rows = list_prospects(status, segment, text)
    with get_db() as conn:
        counts = dict(conn.execute("SELECT status, COUNT(*) FROM prospects GROUP BY status").fetchall())
    total = sum(counts.values())

    def link(s):
        params = urlencode({k: v for k, v in {"status": s, "segment": segment, "q": text}.items() if v})
        label = f"{s or 'All'} ({counts.get(s, 0) if s else total})"
        return f"<a class='{'on' if s == status else ''}' href='/?{params}'>{esc(label)}</a>"

    notice = ""
    if message:
        kind, _, text_msg = message.partition(":")
        notice = f"<div class='msg {'ok' if kind == 'ok' else 'bad'}'>{esc(text_msg)}</div>"
    key_warning = "" if API_KEY else (
        "<div class='msg bad'>No Google Maps API key set. Start the app with GOOGLE_MAPS_API_KEY=your-key "
        "(see README).</div>")
    shown = "".join(prospect_html(r) for r in rows) or "<p class='muted'>No businesses yet. Search above to find some.</p>"
    return page(f"""{notice}{key_warning}
<div class="card"><form method="post" action="/search" class="row">
  <label>City or area<input name="city" placeholder="e.g. Pune, Hinjewadi, Nashik" required></label>
  <label>Type of business<select name="segment">{options(list(SEGMENTS), '')}<option value="Custom">Custom search…</option></select></label>
  <label>Custom search (optional)<input name="custom" placeholder="e.g. pharma companies, CA firms"></label>
  <button type="submit">Find businesses</button>
</form><p class="muted" style="margin:10px 0 0">Finds up to {MAX_PAGES * 20} businesses per search from Google Maps.
Results you've already found are updated, not duplicated.</p></div>

<div class="stats">{''.join(link(s) for s in [''] + STATUSES)}</div>
<div class="card">
  <form method="get" class="row" style="margin-bottom:6px">
    <input type="hidden" name="status" value="{esc(status)}">
    <label>Search your list<input name="q" value="{esc(text)}" placeholder="Name, area or notes"></label>
    <label>Type<select name="segment">{options(sorted(set(list(SEGMENTS) + ['Custom'])), segment, 'All types')}</select></label>
    <button type="submit" class="btn ghost">Filter</button>
    <a class="btn ghost" href="/export.csv">Download CSV</a>
  </form>
  {shown}
</div>
<p class="muted">Contact businesses one at a time with a personal message. Don't send bulk messages:
WhatsApp bans numbers that many people report or block.</p>""")


def prospects_csv():
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Business", "Type", "City", "Phone", "Website", "Address", "Status", "Notes", "Last update"])
    for r in list_prospects():
        writer.writerow([r["name"] or "(details expired)", r["segment"], r["city"], r["phone"], r["website"],
                         r["address"], r["status"], r["notes"], r["contacted_at"]])
    return "﻿" + out.getvalue()  # BOM so Excel shows ₹ and Hindi/Marathi names correctly


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

    def redirect(self, location):
        self.send("", 303, headers={"Location": location})

    def read_form(self):
        length = min(int(self.headers.get("Content-Length", 0)), 20000)
        return {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode("utf-8", "replace")).items()}

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self.send(home_page(parse_qs(url.query), parse_qs(url.query).get("msg", [""])[0]))
        elif url.path == "/export.csv":
            self.send(prospects_csv(), content_type="text/csv; charset=utf-8",
                      headers={"Content-Disposition": "attachment; filename=sawari-prospects.csv"})
        else:
            self.send("Not found", 404, "text/plain")

    def do_POST(self):
        path = urlparse(self.path).path
        form = self.read_form()
        if path == "/search":
            city = form.get("city", "").strip()[:80]
            segment = form.get("segment", "")
            custom = form.get("custom", "").strip()[:80]
            if custom or segment not in SEGMENTS:
                segment = "Custom"
            what = custom or SEGMENTS.get(segment, {}).get("query", "")
            if not city or not what:
                return self.redirect("/?" + urlencode({"msg": "bad:Enter a city and choose a type of business."}))
            try:
                found = search_places(f"{what} in {city}, India")
                added = save_places(found, segment, city)
                msg = f"ok:Found {len(found)} businesses for “{what} in {city}”, {added} new."
            except PlacesError as exc:
                msg = f"bad:{exc}"
            self.redirect("/?" + urlencode({"msg": msg, "segment": segment}))
        elif path == "/update":
            if form.get("status") in STATUSES:
                update_prospect(form.get("id", ""), form["status"], form.get("notes", ""))
            # Back to the same filtered list, without repeating an old message.
            back = parse_qs(urlparse(self.headers.get("Referer", "")).query)
            back.pop("msg", None)
            self.redirect("/?" + urlencode(back, doseq=True))
        elif path == "/refresh":
            try:
                refresh_place(form.get("id", ""))
                msg = "ok:Details refreshed."
            except PlacesError as exc:
                msg = f"bad:{exc}"
            self.redirect("/?" + urlencode({"msg": msg}))
        else:
            self.send("Not found", 404, "text/plain")


if __name__ == "__main__":
    init_db()
    expire_old_details()
    if not API_KEY:
        print("WARNING: set GOOGLE_MAPS_API_KEY to search for businesses (see README).")
    print(f"Business Lead Finder: http://localhost:{PORT}")
    # Only reachable from this computer: your prospect list is private.
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
