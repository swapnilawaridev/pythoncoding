/* Sawari Travel "Plan my trip" lead widget.
 * Add to every page of sawaritravel.com (e.g. before </body>):
 *   <script src="https://leads.sawaritravel.com/widget.js" defer></script>
 * Any link or button with class "sawari-enquire" also opens the form, and
 * data-destination="Kerala" on it pre-fills the destination.
 */
(function () {
  var CONFIG = __CONFIG__;
  var API = new URL(document.currentScript.src).origin + "/api/leads";

  // Remember the campaign the visitor arrived from, even after they browse other pages.
  var params = new URLSearchParams(location.search);
  var source = params.get("utm_source") || params.get("ref");
  try {
    if (source) sessionStorage.setItem("sawari_source", source);
    else source = sessionStorage.getItem("sawari_source");
    if (!source && document.referrer && new URL(document.referrer).host !== location.host) {
      source = new URL(document.referrer).host;
      sessionStorage.setItem("sawari_source", source);
    }
  } catch (e) {}

  var css = "" +
    ".sw-btn{position:fixed;right:20px;bottom:20px;z-index:99998;background:#f28c28;color:#fff;border:0;border-radius:30px;padding:14px 22px;font:600 16px system-ui,sans-serif;box-shadow:0 6px 20px #0003;cursor:pointer}" +
    ".sw-bg{position:fixed;inset:0;z-index:99999;background:#0008;display:none;align-items:center;justify-content:center;padding:16px}" +
    ".sw-box{background:#fff;color:#1d2b36;border-radius:14px;max-width:520px;width:100%;max-height:92vh;overflow:auto;padding:22px;font:15px system-ui,sans-serif;box-sizing:border-box}" +
    ".sw-box h3{margin:0 0 4px;font-size:21px}.sw-box p{margin:0 0 14px;color:#5d6d7e}" +
    ".sw-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.sw-full{grid-column:1/-1}" +
    ".sw-box input,.sw-box select,.sw-box textarea{width:100%;box-sizing:border-box;padding:10px;border:1px solid #c7d3dc;border-radius:8px;font:inherit}" +
    ".sw-send{background:#f28c28;color:#fff;border:0;border-radius:8px;padding:13px;font:700 16px system-ui,sans-serif;cursor:pointer}" +
    ".sw-x{float:right;background:none;border:0;font-size:26px;line-height:1;cursor:pointer;color:#5d6d7e}" +
    ".sw-err{background:#fde8e8;color:#9b1c1c;padding:10px;border-radius:8px;margin-bottom:10px;display:none}" +
    ".sw-box label{font-size:13px;color:#5d6d7e}.sw-hp{display:none}@media(max-width:520px){.sw-grid{grid-template-columns:1fr}}";

  function opts(label, list) {
    return '<option value="">' + label + "</option>" + list.map(function (v) {
      return "<option>" + v + "</option>";
    }).join("");
  }

  var today = new Date().toISOString().slice(0, 10);
  var style = document.createElement("style");
  style.textContent = css;
  var button = document.createElement("button");
  button.className = "sw-btn";
  button.textContent = "✈ Plan my trip";
  var bg = document.createElement("div");
  bg.className = "sw-bg";
  bg.innerHTML =
    '<div class="sw-box" role="dialog" aria-modal="true" aria-label="Plan my trip">' +
    '<button class="sw-x" aria-label="Close">&times;</button>' +
    "<h3>Plan your dream holiday</h3><p>Get a free custom itinerary from " + CONFIG.siteName + " within 24 hours.</p>" +
    '<div class="sw-err"></div>' +
    '<form class="sw-grid">' +
    '<input name="name" placeholder="Full name" required>' +
    '<input name="phone" placeholder="10-digit mobile" inputmode="tel" required>' +
    '<input class="sw-full" name="email" type="email" placeholder="Email" required>' +
    '<input class="sw-full" name="destination" placeholder="Destination (e.g. Goa, Kerala, Dubai)" required>' +
    '<label>Travel date<input name="travel_date" type="date" min="' + today + '"></label>' +
    '<label>Travellers<input name="travelers" type="number" min="1" max="100" value="2"></label>' +
    '<select name="budget" aria-label="Budget per person">' + opts("Budget per person (INR)", CONFIG.budgets) + "</select>" +
    '<select name="trip_type" aria-label="Trip type">' + opts("Trip type", CONFIG.tripTypes) + "</select>" +
    '<textarea class="sw-full" name="message" rows="2" placeholder="Anything else we should know?"></textarea>' +
    '<input class="sw-hp" name="website" tabindex="-1" autocomplete="off">' +
    '<button class="sw-send sw-full" type="submit">Get my free itinerary</button>' +
    "</form></div>";

  function open(destination) {
    if (destination) bg.querySelector('[name="destination"]').value = destination;
    bg.style.display = "flex";
    bg.querySelector('[name="name"]').focus();
  }
  function close() { bg.style.display = "none"; }

  button.onclick = function () { open(); };
  bg.querySelector(".sw-x").onclick = close;
  bg.onclick = function (e) { if (e.target === bg) close(); };
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
  document.addEventListener("click", function (e) {
    var el = e.target.closest && e.target.closest(".sawari-enquire");
    if (el) { e.preventDefault(); open(el.getAttribute("data-destination")); }
  });

  var form = bg.querySelector("form");
  var err = bg.querySelector(".sw-err");
  var send = bg.querySelector(".sw-send");
  form.onsubmit = function (e) {
    e.preventDefault();
    var data = Object.fromEntries(new FormData(form));
    data.source = [source, location.pathname].filter(Boolean).join(" ").slice(0, 100);
    send.disabled = true;
    send.textContent = "Sending...";
    fetch(API, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.errors.join("\n"));
        bg.querySelector(".sw-box").innerHTML =
          '<button class="sw-x" aria-label="Close">&times;</button><h3>Thank you!</h3>' +
          "<p>Your enquiry reference is #" + res.id + ". Our travel expert will call you within 24 hours.</p>";
        bg.querySelector(".sw-x").onclick = close;
        if (window.gtag) window.gtag("event", "generate_lead", { destination: data.destination });
        if (window.fbq) window.fbq("track", "Lead");
      })
      .catch(function (ex) {
        err.textContent = ex instanceof TypeError || !ex.message
          ? "Could not send your enquiry. Please check your internet and try again."
          : ex.message;
        err.style.whiteSpace = "pre-line";
        err.style.display = "block";
        send.disabled = false;
        send.textContent = "Get my free itinerary";
      });
  };

  function mount() {
    document.head.appendChild(style);
    document.body.appendChild(button);
    document.body.appendChild(bg);
  }
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
})();
