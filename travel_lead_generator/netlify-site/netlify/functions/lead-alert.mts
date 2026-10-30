// Runs automatically on every verified (non-spam) Netlify Forms submission on
// sawaritravel.com. For the "enquiry", "trip-plan" and "trip-quiz" forms it:
//   1. Scores the lead 0-100 and rates it HOT / WARM / COLD
//   2. Sends the sales team a WhatsApp alert (WhatsApp Business Cloud API)
//   3. Emails the customer an instant thank-you reply (Resend)
// The submission itself is still stored in Netlify (Forms tab, CSV export),
// and Netlify's own email notification keeps working as before.
import type { FormSubmittedEvent } from "@netlify/functions"

const env = (key: string, fallback = "") => Netlify.env.get(key) ?? fallback

const SITE_NAME = () => env("SITE_NAME", "Sawari Travel")
const SITE_URL = () => env("SITE_URL", "https://sawaritravel.com")
const LEAD_FORMS = () => env("LEAD_FORMS", "enquiry,trip-plan,trip-quiz").split(",").map((f) => f.trim())
const RATING_RANK: Record<string, number> = { COLD: 0, WARM: 1, HOT: 2 }

type Lead = {
  name: string
  phone: string // 10-digit Indian mobile when valid, else as typed
  email: string
  service: string
  destination: string
  travelDate: string
  message: string
  source: string
}

function toLead(data: Record<string, string>): Lead {
  const get = (key: string) => String(data[key] ?? "").trim()
  const phone = get("phone").replace(/[\s()-]/g, "").replace(/^(\+?91|0)(?=[6-9]\d{9}$)/, "")
  const referrer = get("referrer")
  let source = ""
  try {
    const url = new URL(referrer)
    source = url.searchParams.get("utm_source") ?? url.pathname
  } catch {}
  return {
    name: get("name"),
    phone,
    email: get("email"),
    service: get("service"),
    destination: get("destination"),
    travelDate: get("travel_date"),
    message: get("message"),
    source,
  }
}

function scoreLead(lead: Lead, today = new Date()): { score: number; rating: string } {
  let score = 10 // they made an enquiry
  if (/^[6-9]\d{9}$/.test(lead.phone)) score += 10
  if (/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(lead.email)) score += 5
  if (lead.destination) score += 5

  const travel = Date.parse(lead.travelDate)
  if (!Number.isNaN(travel)) {
    const daysAway = (travel - today.setHours(0, 0, 0, 0)) / 86_400_000
    if (daysAway >= 0 && daysAway <= 30) score += 35
    else if (daysAway > 30 && daysAway <= 90) score += 20
    else if (daysAway > 90) score += 10
  }

  // Full holidays are worth more than a single flight or hotel booking.
  const service = lead.service.toLowerCase()
  if (/package|tour|honeymoon|holiday|group|corporate/.test(service)) score += 15
  else if (/flight|hotel|visa|cab|taxi|train|bus/.test(service)) score += 10
  else if (service) score += 5

  if (lead.message.length > 80) score += 20
  else if (lead.message.length > 20) score += 10

  score = Math.min(score, 100)
  return { score, rating: score >= 70 ? "HOT" : score >= 40 ? "WARM" : "COLD" }
}

function whatsappLink(phone: string, text = "") {
  const number = /^[6-9]\d{9}$/.test(phone) ? `91${phone}` : phone.replace(/\D/g, "")
  return `https://wa.me/${number}` + (text ? `?text=${encodeURIComponent(text)}` : "")
}

function alertText(lead: Lead, score: number, rating: string) {
  const greeting = `Hi ${lead.name}, thanks for your ${lead.destination || "travel"} enquiry with ${SITE_NAME()}!`
  return [
    `New ${rating} lead (score ${score}/100) from ${SITE_URL().replace(/^https?:\/\//, "")}`,
    `Name: ${lead.name}`,
    `Phone: ${/^[6-9]\d{9}$/.test(lead.phone) ? `+91 ${lead.phone}` : lead.phone}`,
    `Email: ${lead.email || "-"}`,
    `Service: ${lead.service || "-"}`,
    `Trip: ${lead.destination || "-"}, ${lead.travelDate || "flexible date"}`,
    lead.message ? `Message: ${lead.message.slice(0, 300)}` : "",
    lead.source ? `Source: ${lead.source}` : "",
    `Chat now: ${whatsappLink(lead.phone, greeting)}`,
  ].filter(Boolean).join("\n")
}

async function sendWhatsApp(to: string, text: string) {
  const token = env("WHATSAPP_TOKEN")
  const phoneNumberId = env("WHATSAPP_PHONE_NUMBER_ID")
  if (!token || !phoneNumberId) {
    console.log(`[whatsapp] not configured, would send to ${to}:\n${text}`)
    return
  }
  const template = env("WHATSAPP_TEMPLATE")
  const message = template
    ? {
        type: "template",
        template: {
          name: template,
          language: { code: env("WHATSAPP_TEMPLATE_LANG", "en") },
          // Template variables cannot contain new lines, tabs or 4+ spaces.
          components: [{ type: "body", parameters: [{ type: "text", text: text.replace(/\s+/g, " ").slice(0, 1000) }] }],
        },
      }
    : { type: "text", text: { body: text, preview_url: false } }
  const res = await fetch(`https://graph.facebook.com/v21.0/${phoneNumberId}/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ messaging_product: "whatsapp", to, ...message }),
  })
  if (!res.ok) throw new Error(`WhatsApp to ${to} failed: ${res.status} ${(await res.text()).slice(0, 300)}`)
}

async function sendAutoReply(lead: Lead) {
  const apiKey = env("RESEND_API_KEY")
  const from = env("FROM_EMAIL") // e.g. "Sawari Travel <hello@sawaritravel.com>"
  if (!lead.email) return
  if (!apiKey || !from) {
    console.log(`[email] not configured, skipping auto-reply to ${lead.email}`)
    return
  }
  const trip = lead.destination ? ` to ${lead.destination}` : ""
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from,
      to: [lead.email],
      reply_to: env("REPLY_TO_EMAIL") || undefined,
      subject: `Your trip enquiry${trip} - ${SITE_NAME()}`,
      text:
        `Hi ${lead.name},\n\n` +
        `Thank you for your interest in travelling${trip}! ` +
        `Our travel expert will call you on ${lead.phone} within 24 hours ` +
        `with a personalised itinerary and the best price.\n\n` +
        `Happy travels,\nTeam ${SITE_NAME()}\n${SITE_URL()}\n`,
    }),
  })
  if (!res.ok) throw new Error(`Email to ${lead.email} failed: ${res.status} ${(await res.text()).slice(0, 300)}`)
}

export default {
  async formSubmitted(event: FormSubmittedEvent) {
    const formName = event.data["form-name"] ?? event.data["form_name"]
    if (formName && !LEAD_FORMS().includes(formName)) return

    const lead = toLead(event.data)
    const { score, rating } = scoreLead(lead)
    console.log(`[lead] ${rating} (${score}) ${lead.name} -> ${lead.destination || lead.service}`)

    const tasks: Promise<void>[] = [sendAutoReply(lead)]
    const minRating = env("WHATSAPP_MIN_RATING", "COLD").toUpperCase()
    if (RATING_RANK[rating] >= (RATING_RANK[minRating] ?? 0)) {
      const text = alertText(lead, score, rating)
      const recipients = env("WHATSAPP_ALERT_TO").split(",").map((n) => n.trim().replace(/^\+/, "")).filter(Boolean)
      for (const to of recipients.length ? recipients : ["(set WHATSAPP_ALERT_TO)"]) tasks.push(sendWhatsApp(to, text))
    }
    // One failure (e.g. WhatsApp token expired) must not stop the others.
    for (const result of await Promise.allSettled(tasks)) {
      if (result.status === "rejected") console.error(String(result.reason))
    }
  },
}
