"""Corporate Travel Portal for a travel agency.

Three parts in one Flask app:
  * Public website   - corporate companies discover the agency and submit an enquiry (lead).
  * Agency console   - the agency tracks leads, converts them into corporate clients,
                       quotes and books the travel those clients request.
  * Client portal    - each corporate client's travel manager and employees raise travel
                       requests, approve them against company policy and accept quotes.

Run:  python app.py   (see README.md)
"""
import os
import secrets
import sqlite3
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LEAD_STATUSES = ["new", "contacted", "proposal", "won", "lost"]
TRIP_TYPES = {
    "flight": "Flight",
    "hotel": "Hotel",
    "flight_hotel": "Flight + Hotel",
    "train": "Train",
    "cab": "Cab / Transfer",
    "visa": "Visa assistance",
}
TRAVEL_CLASSES = ["economy", "premium_economy", "business", "first"]
REQUEST_STATUSES = {
    "pending_approval": "Pending approval",
    "approved": "Approved - awaiting quote",
    "quoted": "Quote received",
    "quote_accepted": "Quote accepted - booking",
    "booked": "Booked",
    "rejected": "Rejected",
    "cancelled": "Cancelled",
}
OPEN_STATUSES = ("pending_approval", "approved", "quoted", "quote_accepted")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-me-in-production"),
        DATABASE=os.environ.get("DATABASE", os.path.join(BASE_DIR, "travel.db")),
        AGENCY_NAME=os.environ.get("AGENCY_NAME", "SkyBridge Corporate Travel"),
        AGENCY_PHONE=os.environ.get("AGENCY_PHONE", "+91 98765 43210"),
        AGENCY_EMAIL=os.environ.get("AGENCY_EMAIL", "corporate@skybridge.example"),
        ADMIN_EMAIL=os.environ.get("ADMIN_EMAIL", "admin@agency.local"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "admin123"),
    )
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    register_helpers(app)
    register_public_routes(app)
    register_agency_routes(app)
    register_portal_routes(app)
    return app


# --------------------------------------------------------------------------- database

def get_db():
    if "db" not in g:
        from flask import current_app
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    from flask import current_app
    db = get_db()
    with open(os.path.join(BASE_DIR, "schema.sql")) as f:
        db.executescript(f.read())
    # Seed the first agency admin so the agency can log in.
    if not db.execute("SELECT 1 FROM users WHERE role = 'agency_admin'").fetchone():
        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'agency_admin')",
            ("Agency Admin", current_app.config["ADMIN_EMAIL"].lower(),
             generate_password_hash(current_app.config["ADMIN_PASSWORD"])),
        )
    db.commit()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def log_event(request_id, action, comment=""):
    user = g.get("user")
    execute(
        "INSERT INTO request_events (request_id, user_id, action, comment) VALUES (?, ?, ?, ?)",
        (request_id, user["id"] if user else None, action, comment),
    )


def set_request_status(request_id, status, comment="", **fields):
    assignments = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    values = [status]
    for column, value in fields.items():
        assignments.append(f"{column} = ?")
        values.append(value)
    values.append(request_id)
    execute(f"UPDATE travel_requests SET {', '.join(assignments)} WHERE id = ?", values)
    log_event(request_id, REQUEST_STATUSES[status], comment)


def temp_password():
    return secrets.token_urlsafe(8)


def to_float(value, default=0.0):
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


# --------------------------------------------------------------------------- auth & helpers

def login_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login", next=request.path))
            if roles and g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def home_for(user):
    return url_for("agency_dashboard") if user["role"] == "agency_admin" else url_for("portal_dashboard")


def register_helpers(app):
    @app.before_request
    def load_user_and_check_csrf():
        user_id = session.get("user_id")
        g.user = query("SELECT * FROM users WHERE id = ? AND active = 1", (user_id,), one=True) if user_id else None
        if request.method == "POST" and not app.config.get("TESTING_SKIP_CSRF"):
            token = session.get("csrf_token")
            if not token or token != request.form.get("csrf_token"):
                abort(400, "Invalid or missing form token. Please reload the page and try again.")

    @app.context_processor
    def inject_globals():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return {
            "csrf_token": session["csrf_token"],
            "agency": {
                "name": app.config["AGENCY_NAME"],
                "phone": app.config["AGENCY_PHONE"],
                "email": app.config["AGENCY_EMAIL"],
            },
            "TRIP_TYPES": TRIP_TYPES,
            "REQUEST_STATUSES": REQUEST_STATUSES,
            "LEAD_STATUSES": LEAD_STATUSES,
            "TRAVEL_CLASSES": TRAVEL_CLASSES,
        }

    @app.template_filter("money")
    def money(value):
        if value is None:
            return "-"
        return "₹{:,.0f}".format(value)

    @app.template_filter("label")
    def label(value):
        return (value or "").replace("_", " ").title()

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("error.html", code=403, message="You don't have access to this page."), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", code=400, message=e.description), 400


# --------------------------------------------------------------------------- public site

def register_public_routes(app):
    @app.route("/")
    def index():
        return render_template("index.html", form={})

    @app.route("/enquiry", methods=["POST"])
    def enquiry():
        form = request.form
        required = ["company_name", "contact_name", "email"]
        missing = [f for f in required if not form.get(f, "").strip()]
        if missing or "@" not in form.get("email", ""):
            flash("Please fill in company name, your name and a valid email.", "error")
            return render_template("index.html", form=form), 400
        execute(
            """INSERT INTO leads (company_name, contact_name, email, phone, company_size,
                                  monthly_trips, message, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'website')""",
            (form["company_name"].strip(), form["contact_name"].strip(), form["email"].strip().lower(),
             form.get("phone", "").strip(), form.get("company_size", ""), form.get("monthly_trips", ""),
             form.get("message", "").strip()),
        )
        return render_template("thanks.html", name=form["contact_name"].strip())

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(home_for(g.user))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = query("SELECT * FROM users WHERE email = ? AND active = 1", (email,), one=True)
            if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
                session.clear()
                session["user_id"] = user["id"]
                nxt = request.args.get("next", "")
                return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else home_for(user))
            flash("Invalid email or password.", "error")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("index"))

    @app.route("/account/password", methods=["GET", "POST"])
    @login_required()
    def change_password():
        if request.method == "POST":
            current = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            if not check_password_hash(g.user["password_hash"], current):
                flash("Current password is incorrect.", "error")
            elif len(new) < 8:
                flash("New password must be at least 8 characters.", "error")
            else:
                execute("UPDATE users SET password_hash = ? WHERE id = ?",
                        (generate_password_hash(new), g.user["id"]))
                flash("Password updated.", "success")
                return redirect(home_for(g.user))
        return render_template("change_password.html")


# --------------------------------------------------------------------------- agency console

def register_agency_routes(app):
    agency_only = login_required("agency_admin")

    @app.route("/agency")
    @agency_only
    def agency_dashboard():
        lead_counts = {s: 0 for s in LEAD_STATUSES}
        for row in query("SELECT status, COUNT(*) AS n FROM leads GROUP BY status"):
            lead_counts[row["status"]] = row["n"]
        stats = query(
            """SELECT
                 (SELECT COUNT(*) FROM companies) AS clients,
                 (SELECT COUNT(*) FROM travel_requests WHERE status = 'approved') AS to_quote,
                 (SELECT COUNT(*) FROM travel_requests WHERE status = 'quote_accepted') AS to_book,
                 (SELECT COALESCE(SUM(quote_amount), 0) FROM travel_requests WHERE status = 'booked') AS booked_value,
                 (SELECT COUNT(*) FROM travel_requests WHERE status = 'booked') AS bookings""",
            one=True,
        )
        action_items = query(
            f"""SELECT r.*, c.name AS company_name, u.name AS requester
                FROM travel_requests r JOIN companies c ON c.id = r.company_id
                JOIN users u ON u.id = r.requested_by
                WHERE r.status IN ('approved', 'quote_accepted') ORDER BY r.depart_date""")
        new_leads = query("SELECT * FROM leads WHERE status = 'new' ORDER BY created_at DESC LIMIT 5")
        return render_template("agency/dashboard.html", lead_counts=lead_counts, stats=stats,
                               action_items=action_items, new_leads=new_leads)

    # ---- leads
    @app.route("/agency/leads")
    @agency_only
    def agency_leads():
        status = request.args.get("status", "")
        if status in LEAD_STATUSES:
            leads = query("SELECT * FROM leads WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            status = ""
            leads = query("SELECT * FROM leads ORDER BY created_at DESC")
        return render_template("agency/leads.html", leads=leads, status=status)

    @app.route("/agency/leads/new", methods=["GET", "POST"])
    @agency_only
    def agency_lead_new():
        if request.method == "POST":
            form = request.form
            if not all(form.get(f, "").strip() for f in ("company_name", "contact_name", "email")):
                flash("Company, contact name and email are required.", "error")
                return render_template("agency/lead_new.html", form=form)
            lead_id = execute(
                """INSERT INTO leads (company_name, contact_name, email, phone, company_size,
                                      monthly_trips, message, source, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (form["company_name"].strip(), form["contact_name"].strip(), form["email"].strip().lower(),
                 form.get("phone", ""), form.get("company_size", ""), form.get("monthly_trips", ""),
                 form.get("message", ""), form.get("source", "manual"), form.get("notes", "")),
            )
            flash("Lead added.", "success")
            return redirect(url_for("agency_lead_detail", lead_id=lead_id))
        return render_template("agency/lead_new.html", form={})

    @app.route("/agency/leads/<int:lead_id>", methods=["GET", "POST"])
    @agency_only
    def agency_lead_detail(lead_id):
        lead = query("SELECT * FROM leads WHERE id = ?", (lead_id,), one=True) or abort(404)
        if request.method == "POST":
            status = request.form.get("status")
            if status not in LEAD_STATUSES:
                abort(400, "Unknown lead status.")
            execute("UPDATE leads SET status = ?, notes = ? WHERE id = ?",
                    (status, request.form.get("notes", ""), lead_id))
            flash("Lead updated.", "success")
            return redirect(url_for("agency_lead_detail", lead_id=lead_id))
        return render_template("agency/lead_detail.html", lead=lead)

    @app.route("/agency/leads/<int:lead_id>/convert", methods=["POST"])
    @agency_only
    def agency_lead_convert(lead_id):
        lead = query("SELECT * FROM leads WHERE id = ?", (lead_id,), one=True) or abort(404)
        if lead["company_id"]:
            flash("This lead is already a client.", "error")
            return redirect(url_for("agency_client_detail", company_id=lead["company_id"]))
        if query("SELECT 1 FROM users WHERE email = ?", (lead["email"],), one=True):
            flash(f"A user with email {lead['email']} already exists.", "error")
            return redirect(url_for("agency_lead_detail", lead_id=lead_id))

        company_id = execute("INSERT INTO companies (name) VALUES (?)", (lead["company_name"],))
        password = temp_password()
        execute(
            """INSERT INTO users (name, email, password_hash, role, company_id)
               VALUES (?, ?, ?, 'company_admin', ?)""",
            (lead["contact_name"], lead["email"], generate_password_hash(password), company_id),
        )
        execute("UPDATE leads SET status = 'won', company_id = ? WHERE id = ?", (company_id, lead_id))
        flash(f"{lead['company_name']} is now a client. Share these portal login details with "
              f"{lead['contact_name']}: email {lead['email']} / temporary password {password}", "success")
        return redirect(url_for("agency_client_detail", company_id=company_id))

    # ---- clients
    @app.route("/agency/clients")
    @agency_only
    def agency_clients():
        clients = query(
            """SELECT c.*,
                 (SELECT COUNT(*) FROM users u WHERE u.company_id = c.id) AS users,
                 (SELECT COUNT(*) FROM travel_requests r WHERE r.company_id = c.id) AS requests,
                 (SELECT COALESCE(SUM(quote_amount), 0) FROM travel_requests r
                    WHERE r.company_id = c.id AND r.status = 'booked') AS spend
               FROM companies c ORDER BY c.name""")
        return render_template("agency/clients.html", clients=clients)

    @app.route("/agency/clients/<int:company_id>")
    @agency_only
    def agency_client_detail(company_id):
        company = query("SELECT * FROM companies WHERE id = ?", (company_id,), one=True) or abort(404)
        users = query("SELECT * FROM users WHERE company_id = ? ORDER BY role, name", (company_id,))
        requests_ = query(
            """SELECT r.*, u.name AS requester, c.name AS company_name FROM travel_requests r
               JOIN users u ON u.id = r.requested_by JOIN companies c ON c.id = r.company_id
               WHERE r.company_id = ? ORDER BY r.created_at DESC""", (company_id,))
        return render_template("agency/client_detail.html", company=company, users=users, requests=requests_)

    # ---- travel requests
    @app.route("/agency/requests")
    @agency_only
    def agency_requests():
        status = request.args.get("status", "")
        sql = """SELECT r.*, u.name AS requester, c.name AS company_name FROM travel_requests r
                 JOIN users u ON u.id = r.requested_by JOIN companies c ON c.id = r.company_id"""
        if status in REQUEST_STATUSES:
            rows = query(sql + " WHERE r.status = ? ORDER BY r.depart_date", (status,))
        else:
            status = ""
            rows = query(sql + " ORDER BY r.created_at DESC")
        return render_template("agency/requests.html", requests=rows, status=status)

    @app.route("/agency/requests/<int:request_id>/quote", methods=["POST"])
    @agency_only
    def agency_quote(request_id):
        req = get_request_or_404(request_id)
        if req["status"] not in ("approved", "quoted"):
            abort(400, "Only approved requests can be quoted.")
        amount = to_float(request.form.get("quote_amount"), default=-1)
        if amount <= 0:
            flash("Enter a valid quote amount.", "error")
        else:
            details = request.form.get("quote_details", "").strip()
            set_request_status(request_id, "quoted", f"Quote {amount:,.0f}. {details}",
                               quote_amount=amount, quote_details=details)
            flash("Quote sent to client.", "success")
        return redirect(url_for("request_detail", request_id=request_id))

    @app.route("/agency/requests/<int:request_id>/book", methods=["POST"])
    @agency_only
    def agency_book(request_id):
        req = get_request_or_404(request_id)
        if req["status"] != "quote_accepted":
            abort(400, "Only requests with an accepted quote can be booked.")
        reference = request.form.get("booking_reference", "").strip()
        if not reference:
            flash("Booking reference / PNR is required.", "error")
        else:
            details = request.form.get("booking_details", "").strip()
            set_request_status(request_id, "booked", f"PNR/Ref {reference}. {details}",
                               booking_reference=reference, booking_details=details)
            flash("Marked as booked.", "success")
        return redirect(url_for("request_detail", request_id=request_id))


# --------------------------------------------------------------------------- client portal

def get_request_or_404(request_id):
    req = query(
        """SELECT r.*, u.name AS requester, u.email AS requester_email, u.department,
                  c.name AS company_name, c.max_trip_budget, c.allowed_flight_class
           FROM travel_requests r JOIN users u ON u.id = r.requested_by
           JOIN companies c ON c.id = r.company_id WHERE r.id = ?""", (request_id,), one=True)
    if req is None:
        abort(404)
    return req


def can_view_request(user, req):
    if user["role"] == "agency_admin":
        return True
    if user["company_id"] != req["company_id"]:
        return False
    return user["role"] == "company_admin" or user["id"] == req["requested_by"]


def policy_violations(company, budget, travel_class):
    issues = []
    if company["max_trip_budget"] and budget > company["max_trip_budget"]:
        issues.append(f"budget exceeds policy limit of ₹{company['max_trip_budget']:,.0f}")
    allowed = company["allowed_flight_class"] or "economy"
    if travel_class in TRAVEL_CLASSES and TRAVEL_CLASSES.index(travel_class) > TRAVEL_CLASSES.index(allowed):
        issues.append(f"{travel_class.replace('_', ' ')} class is above the allowed {allowed.replace('_', ' ')}")
    return issues


def register_portal_routes(app):
    company_user = login_required("company_admin", "employee")
    company_admin = login_required("company_admin")

    @app.route("/portal")
    @company_user
    def portal_dashboard():
        company = query("SELECT * FROM companies WHERE id = ?", (g.user["company_id"],), one=True)
        base = """SELECT r.*, u.name AS requester FROM travel_requests r
                  JOIN users u ON u.id = r.requested_by WHERE r.company_id = ?"""
        if g.user["role"] == "company_admin":
            requests_ = query(base + " ORDER BY r.created_at DESC", (company["id"],))
        else:
            requests_ = query(base + " AND r.requested_by = ? ORDER BY r.created_at DESC",
                              (company["id"], g.user["id"]))
        needs_action = [r for r in requests_ if r["status"] in ("pending_approval", "quoted")] \
            if g.user["role"] == "company_admin" else []
        spend = sum(r["quote_amount"] or 0 for r in requests_ if r["status"] == "booked")
        upcoming = [r for r in requests_ if r["status"] == "booked"]
        return render_template("portal/dashboard.html", company=company, requests=requests_,
                               needs_action=needs_action, spend=spend, upcoming=upcoming)

    @app.route("/portal/requests/new", methods=["GET", "POST"])
    @company_user
    def request_new():
        company = query("SELECT * FROM companies WHERE id = ?", (g.user["company_id"],), one=True)
        if request.method == "POST":
            form = request.form
            errors = []
            if form.get("trip_type") not in TRIP_TYPES:
                errors.append("Choose a trip type.")
            if not form.get("destination", "").strip():
                errors.append("Destination is required.")
            if not form.get("depart_date"):
                errors.append("Departure / check-in date is required.")
            if form.get("return_date") and form["return_date"] < form.get("depart_date", ""):
                errors.append("Return date can't be before the departure date.")
            travelers = int(to_float(form.get("travelers"), 1))
            if travelers < 1:
                errors.append("At least one traveler is required.")
            travel_class = form.get("travel_class") if form.get("travel_class") in TRAVEL_CLASSES else "economy"
            budget = to_float(form.get("budget"))
            if errors:
                for e in errors:
                    flash(e, "error")
                return render_template("portal/request_form.html", form=form, company=company)

            request_id = execute(
                """INSERT INTO travel_requests (company_id, requested_by, trip_type, origin, destination,
                       depart_date, return_date, travelers, travel_class, purpose, budget)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (company["id"], g.user["id"], form["trip_type"], form.get("origin", "").strip(),
                 form["destination"].strip(), form["depart_date"], form.get("return_date") or None,
                 travelers, travel_class, form.get("purpose", "").strip(), budget),
            )
            issues = policy_violations(company, budget, travel_class)
            log_event(request_id, "Submitted", "Out of policy: " + "; ".join(issues) if issues else "")
            # Travel managers' own trips, and in-policy trips when the company skips approvals,
            # go straight to the agency for a quote.
            if g.user["role"] == "company_admin" or (not company["approval_required"] and not issues):
                set_request_status(request_id, "approved", "Auto-approved")
                flash("Request sent to the agency for a quote.", "success")
            else:
                flash("Request submitted for approval.", "success")
            return redirect(url_for("request_detail", request_id=request_id))
        return render_template("portal/request_form.html", form={}, company=company)

    @app.route("/requests/<int:request_id>")
    @login_required()
    def request_detail(request_id):
        req = get_request_or_404(request_id)
        if not can_view_request(g.user, req):
            abort(403)
        events = query(
            """SELECT e.*, u.name AS user_name FROM request_events e LEFT JOIN users u ON u.id = e.user_id
               WHERE e.request_id = ? ORDER BY e.id""", (request_id,))
        company = {"max_trip_budget": req["max_trip_budget"], "allowed_flight_class": req["allowed_flight_class"]}
        issues = policy_violations(company, req["budget"] or 0, req["travel_class"])
        if req["quote_amount"] and req["max_trip_budget"] and req["quote_amount"] > req["max_trip_budget"]:
            issues.append(f"quote exceeds policy limit of ₹{req['max_trip_budget']:,.0f}")
        return render_template("request_detail.html", req=req, events=events, issues=issues)

    @app.route("/portal/requests/<int:request_id>/decision", methods=["POST"])
    @company_admin
    def request_decision(request_id):
        req = get_request_or_404(request_id)
        if req["company_id"] != g.user["company_id"]:
            abort(403)
        action = request.form.get("action")
        comment = request.form.get("comment", "").strip()
        transitions = {
            ("pending_approval", "approve"): ("approved", "Request approved and sent to the agency."),
            ("pending_approval", "reject"): ("rejected", "Request rejected."),
            ("quoted", "accept_quote"): ("quote_accepted", "Quote accepted. The agency will book it."),
            ("quoted", "reject_quote"): ("rejected", "Quote rejected."),
        }
        if (req["status"], action) not in transitions:
            abort(400, "That action isn't available for this request.")
        new_status, message = transitions[(req["status"], action)]
        set_request_status(request_id, new_status, comment)
        flash(message, "success")
        return redirect(url_for("request_detail", request_id=request_id))

    @app.route("/requests/<int:request_id>/cancel", methods=["POST"])
    @login_required()
    def request_cancel(request_id):
        req = get_request_or_404(request_id)
        if not can_view_request(g.user, req):
            abort(403)
        if req["status"] not in OPEN_STATUSES:
            abort(400, "Only open requests can be cancelled.")
        set_request_status(request_id, "cancelled", request.form.get("comment", "").strip())
        flash("Request cancelled.", "success")
        return redirect(url_for("request_detail", request_id=request_id))

    @app.route("/portal/team", methods=["GET", "POST"])
    @company_admin
    def portal_team():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            role = "company_admin" if request.form.get("role") == "company_admin" else "employee"
            if not name or "@" not in email:
                flash("Name and a valid email are required.", "error")
            elif query("SELECT 1 FROM users WHERE email = ?", (email,), one=True):
                flash("A user with that email already exists.", "error")
            else:
                password = temp_password()
                execute(
                    """INSERT INTO users (name, email, password_hash, role, company_id, department)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (name, email, generate_password_hash(password), role, g.user["company_id"],
                     request.form.get("department", "").strip()),
                )
                flash(f"Added {name}. Share their login: {email} / temporary password {password}", "success")
            return redirect(url_for("portal_team"))
        users = query("SELECT * FROM users WHERE company_id = ? ORDER BY role, name", (g.user["company_id"],))
        return render_template("portal/team.html", users=users)

    @app.route("/portal/team/<int:user_id>/toggle", methods=["POST"])
    @company_admin
    def portal_team_toggle(user_id):
        user = query("SELECT * FROM users WHERE id = ? AND company_id = ?",
                     (user_id, g.user["company_id"]), one=True) or abort(404)
        if user["id"] == g.user["id"]:
            abort(400, "You can't deactivate yourself.")
        execute("UPDATE users SET active = ? WHERE id = ?", (0 if user["active"] else 1, user_id))
        return redirect(url_for("portal_team"))

    @app.route("/portal/policy", methods=["GET", "POST"])
    @company_admin
    def portal_policy():
        company = query("SELECT * FROM companies WHERE id = ?", (g.user["company_id"],), one=True)
        if request.method == "POST":
            travel_class = request.form.get("allowed_flight_class")
            if travel_class not in TRAVEL_CLASSES:
                travel_class = "economy"
            execute(
                """UPDATE companies SET name = ?, gst_number = ?, billing_address = ?,
                       max_trip_budget = ?, approval_required = ?, allowed_flight_class = ?
                   WHERE id = ?""",
                (request.form.get("name", company["name"]).strip() or company["name"],
                 request.form.get("gst_number", "").strip(), request.form.get("billing_address", "").strip(),
                 max(0.0, to_float(request.form.get("max_trip_budget"))),
                 1 if request.form.get("approval_required") else 0, travel_class, company["id"]),
            )
            flash("Company profile and travel policy saved.", "success")
            return redirect(url_for("portal_policy"))
        return render_template("portal/policy.html", company=company)


if __name__ == "__main__":
    create_app().run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
