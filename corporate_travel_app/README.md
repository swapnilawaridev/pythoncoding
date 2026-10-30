# Corporate Travel Portal

A web app for a travel agency to **win corporate clients (lead generation)** and then
**manage those companies' business travel** end to end.

## What it does

| Who | What they get |
|-----|---------------|
| **Prospects** (public website) | Landing page explaining your corporate travel service + an enquiry form. Every submission becomes a **lead**. |
| **Your agency** (`/agency`) | Dashboard, lead pipeline (New → Contacted → Proposal → Won/Lost) with notes, add offline leads (referrals, calls, events), **one-click "Convert to client"** which creates the company and its portal login, client list with booked spend, and the trip queue to quote and book. |
| **Client travel manager** | Adds employees, sets travel policy (max budget per trip, highest allowed class, whether every trip needs approval), approves/rejects requests, accepts/rejects your quotes, sees company travel spend. |
| **Client employees** | Raise flight / hotel / train / cab / visa requests and track their status, PNR and booking details. |

### Trip workflow

```
Employee submits ──► Manager approves ──► Agency sends quote ──► Manager accepts ──► Agency books (PNR)
   (pending)           (approved)            (quoted)           (quote accepted)        (booked)
```

* Trips raised by a travel manager are auto-approved.
* If the company turns off "approval required", in-policy trips skip approval; out-of-policy ones
  (over budget or above allowed class) still need it and are flagged.
* Every step is recorded in the trip's history timeline.

## Run it

```bash
cd corporate_travel_app
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 and log in as the agency with `admin@agency.local` / `admin123`.

**Try the full flow:** submit the enquiry form on the home page → log in as admin → Leads → open
the lead → *Convert to corporate client* → use the login shown to sign in as the client → add an
employee, raise a trip, approve it → back as admin, quote and book it.

## Configuration (environment variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENCY_NAME` | SkyBridge Corporate Travel | Shown on the site |
| `AGENCY_PHONE`, `AGENCY_EMAIL` | sample values | Shown in footer / thank-you page |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | admin@agency.local / admin123 | First agency login (created on first start) |
| `SECRET_KEY` | change-me-in-production | **Set a long random value in production** |
| `DATABASE` | `travel.db` next to `app.py` | SQLite file location |
| `PORT` | 5000 | Port for `python app.py` |

## Tests

```bash
python -m pytest -q tests
```

## Going live checklist

* Set `SECRET_KEY` and a strong `ADMIN_PASSWORD`; change your password after first login.
* Run behind a production server, e.g. `pip install gunicorn && gunicorn "app:create_app()"`, with HTTPS.
* Possible next steps: email notifications (new lead, approval needed, quote ready), invoice PDFs,
  GST billing reports, and a flight/hotel API for live fares.
