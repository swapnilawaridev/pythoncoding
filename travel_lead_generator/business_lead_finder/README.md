# Business Lead Finder – Sawari Travel

Find businesses that buy **group travel** in any city, then track every call and WhatsApp message until the deal is won.

| Type of business | What you sell them |
|---|---|
| Companies | Corporate offsites, team outings, business travel |
| Colleges | Industrial visits, educational tours |
| Schools | School excursions and study tours |
| Wedding planners | Referral partnership for honeymoons and destination weddings |
| Housing societies | Group tours and pilgrimages for residents and senior citizens |
| Banks & insurance | Incentive trips for top sales teams |
| Gyms & clubs | Adventure group trips (treks, rafting, Ladakh bike tours) |
| Custom | Anything you type, e.g. "pharma companies", "CA firms", "dental clinics" |

For each business you get its phone number, website, Google rating and map link. You also get one-tap **Call** and **WhatsApp** buttons;
WhatsApp opens with a ready-made pitch for that type of business, which you can edit before sending.
Mark each business New → Contacted → Interested → Quoted → Won / Not interested, add notes, and download everything to Excel (CSV).

## Run it
Python 3.9 or newer, nothing to install:
```bash
cd business_lead_finder
GOOGLE_MAPS_API_KEY=your-key python finder.py
```
On Windows (PowerShell):
```powershell
$env:GOOGLE_MAPS_API_KEY="your-key"; python finder.py
```
Open http://localhost:8001. The app only runs on your own computer, so your prospect list stays private.

## Get a Google Maps API key (one time, about 10 minutes)
1. Go to https://console.cloud.google.com, sign in, and create a project (e.g. "Sawari leads").
2. Turn on billing for the project. Google requires a billing account, but gives a free monthly allowance.
   Set a **budget alert** under *Billing → Budgets & alerts* (e.g. ₹500) so you are never surprised.
3. Go to *APIs & Services → Library*, search for **Places API (New)** and click **Enable**.
4. Go to *APIs & Services → Credentials → Create credentials → API key*.
   Click **Restrict key** and allow only **Places API (New)**.
5. Copy the key and use it as `GOOGLE_MAPS_API_KEY`.

Each search uses up to 3 requests and returns up to 60 businesses. Check current prices at
https://developers.google.com/maps/billing-and-pricing/pricing.

## Settings
| Variable | Default | Meaning |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | – | Required for searching |
| `AGENT_NAME` | Sawari Travel team | Your name in the WhatsApp pitch ("Hi, this is Swapnil from Sawari Travel...") |
| `SITE_URL` | https://sawaritravel.com | Your website, used in the pitch |
| `PORT` | 8001 | Port to open in the browser |
| `PROSPECTS_DB` | prospects.db | Where your list is saved |

To change the pitches or add new business types, edit `SEGMENTS` at the top of `finder.py`.

## Use it the right way
- **Message one business at a time, personally.** Don't paste the same message to hundreds of numbers:
  WhatsApp bans numbers that get reported or blocked, and unwanted bulk messages break India's TRAI/DPDP rules.
  Calling during office hours usually works better than WhatsApp for B2B.
- **Google data is kept for 30 days.** Google's terms limit how long you may store Places data.
  The app keeps each business's place ID with your status and notes. It clears Google's details after 30 days,
  and you can re-download them with **Refresh details**. Businesses you never touched are removed.
  Read the Google Maps Platform Terms of Service before using the data in other tools.

## A simple daily routine
1. Search one area and one business type (e.g. *Colleges in Nashik*).
2. Call or WhatsApp 15–20 of them. Start with the most-reviewed ones, which are shown first.
3. Write a note and set the status after every conversation.
4. Each morning, open **Interested** and **Quoted** and follow up.
