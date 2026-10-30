import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app  # noqa: E402


@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db"),
                      "ADMIN_EMAIL": "admin@agency.local", "ADMIN_PASSWORD": "admin123"})
    with app.test_client() as c:
        c.get("/")  # issues the CSRF token
        yield c


def post(client, url, data=None, **kw):
    with client.session_transaction() as s:
        token = s["csrf_token"]
    return client.post(url, data={**(data or {}), "csrf_token": token}, **kw)


def login(client, email, password):
    return post(client, "/login", {"email": email, "password": password}, follow_redirects=True)


def logout(client):
    post(client, "/logout")
    client.get("/")


def make_client_company(client):
    post(client, "/enquiry", {"company_name": "Acme Pvt Ltd", "contact_name": "Asha Rao",
                              "email": "asha@acme.example", "phone": "999"})
    login(client, "admin@agency.local", "admin123")
    resp = post(client, "/agency/leads/1/convert", follow_redirects=True)
    password = re.search(r"temporary password ([\w-]+)", resp.get_data(as_text=True)).group(1)
    logout(client)
    return password


def test_post_without_csrf_token_is_rejected(client):
    resp = client.post("/enquiry", data={"company_name": "X", "contact_name": "Y", "email": "a@b.c"})
    assert resp.status_code == 400


def test_enquiry_creates_lead_visible_to_agency(client):
    resp = post(client, "/enquiry", {"company_name": "Acme", "contact_name": "Asha", "email": "a@acme.example"})
    assert b"Thank you, Asha" in resp.data
    login(client, "admin@agency.local", "admin123")
    assert b"Acme" in client.get("/agency/leads").data


def test_enquiry_requires_fields(client):
    resp = post(client, "/enquiry", {"company_name": "", "contact_name": "Asha", "email": "bad"})
    assert resp.status_code == 400


def test_portal_requires_login_and_role(client):
    assert client.get("/agency").status_code == 302
    password = make_client_company(client)
    login(client, "asha@acme.example", password)
    assert client.get("/agency").status_code == 403
    assert client.get("/portal").status_code == 200


def test_full_trip_lifecycle(client):
    password = make_client_company(client)

    # Travel manager adds an employee
    login(client, "asha@acme.example", password)
    resp = post(client, "/portal/team", {"name": "Ravi", "email": "ravi@acme.example", "role": "employee"},
                follow_redirects=True)
    emp_password = re.search(r"temporary password ([\w-]+)", resp.get_data(as_text=True)).group(1)
    post(client, "/portal/policy", {"name": "Acme Pvt Ltd", "max_trip_budget": "20000",
                                    "allowed_flight_class": "economy", "approval_required": "1"})
    logout(client)

    # Employee raises an out-of-policy request
    login(client, "ravi@acme.example", emp_password)
    resp = post(client, "/portal/requests/new", {
        "trip_type": "flight", "origin": "Pune", "destination": "Delhi", "depart_date": "2026-12-01",
        "return_date": "2026-12-03", "travelers": "1", "travel_class": "business", "budget": "30000"},
        follow_redirects=True)
    body = resp.get_data(as_text=True)
    assert "Pending approval" in body and "Out of policy" in body
    # Employees can't approve
    assert post(client, "/portal/requests/1/decision", {"action": "approve"}).status_code == 403
    logout(client)

    # Manager approves
    login(client, "asha@acme.example", password)
    resp = post(client, "/portal/requests/1/decision", {"action": "approve"}, follow_redirects=True)
    assert b"Approved - awaiting quote" in resp.data
    logout(client)

    # Agency quotes
    login(client, "admin@agency.local", "admin123")
    assert b"Trips to quote" in client.get("/agency").data
    resp = post(client, "/agency/requests/1/quote", {"quote_amount": "18500", "quote_details": "6E-203"},
                follow_redirects=True)
    assert b"Quote received" in resp.data
    # Can't book before client accepts
    assert post(client, "/agency/requests/1/book", {"booking_reference": "X"}).status_code == 400
    logout(client)

    # Manager accepts quote
    login(client, "asha@acme.example", password)
    post(client, "/portal/requests/1/decision", {"action": "accept_quote"})
    logout(client)

    # Agency books
    login(client, "admin@agency.local", "admin123")
    resp = post(client, "/agency/requests/1/book", {"booking_reference": "PNR123"}, follow_redirects=True)
    assert b"PNR123" in resp.data and b"Booked" in resp.data
    assert "₹18,500" in client.get("/agency").get_data(as_text=True)


def test_manager_requests_are_auto_approved(client):
    password = make_client_company(client)
    login(client, "asha@acme.example", password)
    resp = post(client, "/portal/requests/new", {"trip_type": "hotel", "destination": "Mumbai",
                                                 "depart_date": "2026-11-10"}, follow_redirects=True)
    assert b"Approved - awaiting quote" in resp.data


def test_other_company_cannot_see_request(client):
    password = make_client_company(client)
    login(client, "asha@acme.example", password)
    post(client, "/portal/requests/new", {"trip_type": "hotel", "destination": "Goa", "depart_date": "2026-11-10"})
    logout(client)

    post(client, "/enquiry", {"company_name": "Globex", "contact_name": "Bo", "email": "bo@globex.example"})
    login(client, "admin@agency.local", "admin123")
    resp = post(client, "/agency/leads/2/convert", follow_redirects=True)
    other_password = re.search(r"temporary password ([\w-]+)", resp.get_data(as_text=True)).group(1)
    logout(client)

    login(client, "bo@globex.example", other_password)
    assert client.get("/requests/1").status_code == 403
    assert post(client, "/requests/1/cancel").status_code == 403
