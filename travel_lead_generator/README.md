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
| Follow up | Sends the visitor an instant thank-you email and sends you a new-lead alert by email **and WhatsApp** (with a one-tap "chat with this lead" link) |
| Manage | Password-protected dashboard sorted by score, with call / WhatsApp / email links, with status (New → Contacted → Quoted → Booked / Lost) and CSV export |

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

## WhatsApp alerts
Every new lead is sent to your phone on WhatsApp, for example:
```
New HOT lead #1 (score 100/100)
Name: Asha Patil
Phone: +91 9876543210
Trip: Kerala, 2026-11-19, 4 pax
Budget: 50,000 - 1,00,000 | Family
Source: instagram
Chat now: https://wa.me/919876543210?text=Hi%20Asha%20Patil...
```
Tapping **Chat now** opens a WhatsApp chat with the customer with a greeting already typed.

It uses the official **WhatsApp Business Cloud API** from Meta:
1. Create an app at https://developers.facebook.com, add the **WhatsApp** product, and register a business phone number. Copy its **Phone number ID**.
2. Create a **permanent access token** (Business Settings → System users → Generate token, with `whatsapp_business_messaging` permission).
3. Set the environment variables:

| Variable | Example | Meaning |
|----------|---------|---------|
| `WHATSAPP_TOKEN` | `EAAG...` | Access token |
| `WHATSAPP_PHONE_NUMBER_ID` | `1234567890` | The business number's Phone number ID |
| `WHATSAPP_ALERT_TO` | `919876543210,918765432109` | Who gets alerts (country code, no `+`), comma separated |
| `WHATSAPP_MIN_RATING` | `WARM` | Only alert for leads this good or better: `HOT`, `WARM` or `COLD` (default, all leads) |
| `WHATSAPP_TEMPLATE` | `new_lead_alert` | Approved message template (see below) |
| `WHATSAPP_TEMPLATE_LANG` | `en` | Template language code |

**Important: WhatsApp's 24-hour rule.** WhatsApp only delivers a free-text message if the person has messaged your business number in the last 24 hours. So either:
- message your business number from each alert phone once a day (fine for testing), **or**
- in WhatsApp Manager, create a **Utility** template named e.g. `new_lead_alert` whose body is `New travel enquiry: {{1}}`, wait for approval, and set `WHATSAPP_TEMPLATE=new_lead_alert`. The whole lead summary is sent as `{{1}}`, and it is delivered at any time.

If `WHATSAPP_TOKEN` is not set, alerts are written to `whatsapp_outbox.log` so you can test without an account. A WhatsApp failure is printed in the console and never stops the lead from being saved.

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
