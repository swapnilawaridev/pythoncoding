# Sawari Travel – automatic lead alerts on Netlify

sawaritravel.com is hosted on Netlify and already has a Netlify Form called **`enquiry`**
(fields: name, phone, email, service, destination, travel_date, message).
This folder adds a **Netlify Function** that runs automatically every time someone submits that form.
You don't need any other server.

For every verified (non-spam) enquiry it:

1. **Scores the lead** out of 100 and rates it **HOT / WARM / COLD**:

   | Signal | Points |
   |---|---|
   | Base for enquiring | 10 |
   | Valid Indian mobile number | 10 |
   | Valid email | 5 |
   | Destination given | 5 |
   | Travelling within 30 days | 35 |
   | Travelling within 31–90 days | 20 |
   | Travelling later than 90 days | 10 |
   | Service is a package, tour, honeymoon, group or corporate trip | 15 |
   | Service is a flight, hotel, visa, cab, train or bus booking | 10 |
   | Any other service | 5 |
   | Message over 80 characters | 20 |
   | Message over 20 characters | 10 |

   70 or more is HOT, 40–69 is WARM, below 40 is COLD.
2. **Sends you a WhatsApp alert**, with a "Chat now" link that opens a WhatsApp chat with the customer:
   ```
   New HOT lead (score 100/100) from sawaritravel.com
   Name: Asha Patil
   Phone: +91 9876543210
   Service: Tour Package
   Trip: Kerala, 2026-11-11
   Message: Honeymoon trip for 2, need houseboat ...
   Source: instagram
   Chat now: https://wa.me/919876543210?text=Hi%20Asha...
   ```
3. **Emails the customer an instant thank-you** from your own address (e.g. hello@sawaritravel.com).

Netlify still stores every submission (Forms tab, CSV download) and still sends its own email notifications,
just as it does today.

## Folder layout
```
netlify-site/
├── netlify.toml                      ← tells Netlify where things are
├── netlify/functions/lead-alert.mts  ← the lead alert function
└── site/                             ← put your website files here (index.html, images, css ...)
```

## One-time setup

### 1. Switch from drag-and-drop to a CLI or Git deploy
Your site is currently deployed by dragging a folder onto Netlify. **Drag-and-drop cannot deploy functions**,
so use one of these instead:

**Option A – Netlify CLI (closest to what you do now)**
```bash
npm install -g netlify-cli
netlify login
cd netlify-site
# copy your current website files into the "site" folder first
netlify link        # choose the "sawaritravel" project
netlify deploy --prod
```
Run `netlify deploy --prod` again every time you change the website.

**Option B – GitHub (automatic deploys)**
Push this folder to a GitHub repository. Then in Netlify go to *Project configuration → Build & deploy → Link repository*.
Every push now deploys automatically.

⚠️ Keep the form's `name="enquiry"` and its field names exactly as they are. The function reads them by name.

### 2. WhatsApp alerts
1. At https://developers.facebook.com create an app, add **WhatsApp**, and register a business phone number. Copy its **Phone number ID**.
2. Create a permanent access token: *Business Settings → System users → Generate token*, with the `whatsapp_business_messaging` permission.
3. **24-hour rule:** WhatsApp only delivers free-text messages to people who messaged your business number in the last 24 hours.
   For alerts that always arrive, create a **Utility** template in WhatsApp Manager:
   - Name: `new_lead_alert`
   - Body: `New travel enquiry: {{1}}`

   Once it is approved, set `WHATSAPP_TEMPLATE=new_lead_alert`.

### 3. Thank-you emails (Resend, free up to 3,000 emails/month)
1. Sign up at https://resend.com and add the domain **sawaritravel.com**.
2. Add the DNS records Resend shows you. If your domain's DNS is on Netlify, add them under *Domains → sawaritravel.com → DNS settings*.
3. Create an API key.

### 4. Add environment variables
In Netlify: *Project configuration → Environment variables → Add a variable*. Make sure each variable's scope includes **Functions**,
then redeploy so the function picks them up.

| Variable | Example | Needed for |
|---|---|---|
| `WHATSAPP_TOKEN` | `EAAG...` | WhatsApp |
| `WHATSAPP_PHONE_NUMBER_ID` | `1234567890` | WhatsApp |
| `WHATSAPP_ALERT_TO` | `919876543210,918765432109` | Who gets alerts: country code, no `+`, comma separated |
| `WHATSAPP_TEMPLATE` | `new_lead_alert` | Recommended (see the 24-hour rule) |
| `WHATSAPP_TEMPLATE_LANG` | `en` | Optional, defaults to `en` |
| `WHATSAPP_MIN_RATING` | `WARM` | Optional: only alert for `HOT` or `WARM` leads. The default is every lead |
| `RESEND_API_KEY` | `re_...` | Thank-you email |
| `FROM_EMAIL` | `Sawari Travel <hello@sawaritravel.com>` | Thank-you email |
| `REPLY_TO_EMAIL` | `sales@sawaritravel.com` | Optional: where customers' replies go |
| `LEAD_FORMS` | `enquiry` | Optional: names of the forms to process, comma separated |

Anything you haven't set yet is simply skipped, and the function writes to the log what it would have sent.

## Test it
1. Submit a real-looking enquiry on sawaritravel.com. Use a real email and full sentences:
   Netlify's spam filter flags obvious test messages, and the function only runs for verified submissions.
2. In Netlify, open *Logs → Functions → lead-alert*. You should see a line like `[lead] HOT (100) Asha Patil -> Kerala`,
   and any WhatsApp or email error.
3. If an enquiry seems to be missing, check *Forms → enquiry → Spam submissions* and mark it as verified.

## Track your campaigns
Add `utm_source` to the links you share:
```
https://sawaritravel.com/?utm_source=instagram
```
If the visitor submits the form on that page, the alert shows `Source: instagram`. Otherwise it shows the page they submitted from.
