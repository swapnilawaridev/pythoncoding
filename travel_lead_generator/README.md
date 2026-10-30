# Travel Website – Automatic Lead Generator

A single Python file (standard library only, nothing to install) that turns website visitors into sales leads.

## What it does
| Step | Automatic action |
|------|------------------|
| Capture | "Plan your dream holiday" enquiry form (name, email, mobile, destination, date, travellers, budget, trip type) |
| Validate | Checks email and 10-digit Indian mobile number, blocks past dates and spam bots (hidden honeypot field) |
| Track source | Records where the visitor came from (`?utm_source=instagram`, `?ref=...` or the referring site) |
| De-duplicate | The same email + destination within 24 hours is not saved twice |
| Score | Each lead gets a score out of 100 and a **HOT / WARM / COLD** rating (budget × travellers, how soon they travel, trip type, detail given) |
| Follow up | Sends the visitor an instant thank-you email and sends you a new-lead alert |
| Manage | Password-protected dashboard sorted by score, with status (New → Contacted → Quoted → Booked / Lost) and CSV export |

## Run it
```bash
cd travel_lead_generator
ADMIN_PASSWORD=mysecret python lead_generator.py
```
- Enquiry form: http://localhost:8000
- Dashboard: http://localhost:8000/admin (user `admin`, password from `ADMIN_PASSWORD`)

## Settings (environment variables)
| Variable | Default | Meaning |
|----------|---------|---------|
| `SITE_NAME` | My Travel Website | Name used on the page and in emails |
| `PORT` | 8000 | Web server port |
| `ADMIN_USER` / `ADMIN_PASSWORD` | admin / change-me | Dashboard login |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | empty, 587 | Email server. For Gmail use `smtp.gmail.com` and an App Password |
| `SALES_EMAIL` | `SMTP_USER` | Where new-lead alerts are sent |
| `LEADS_DB` | leads.db | SQLite database file |

If `SMTP_HOST` is not set, emails are written to `outbox.log` instead, so you can test without an email account.

## Connect it to your existing website
Link your "Enquire now" buttons to the form, adding the campaign source:
```
https://your-site.com/?utm_source=google_ads
```
Or post from your own form / chat widget with JavaScript:
```js
fetch("/api/leads", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({name, email, phone, destination, travelers: 2, source: "homepage_popup"})
});
```

For production, run it behind HTTPS (e.g. Nginx or a hosting platform) so the dashboard password is encrypted.
