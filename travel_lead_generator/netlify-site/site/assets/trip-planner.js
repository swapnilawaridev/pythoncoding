// Trip cost calculator for sawaritravel.com/trip-planner.html
// Loaded as a separate file because the site's Content-Security-Policy blocks inline scripts.

// Sawari Travel's WhatsApp number (country code, no "+"). Leave "" to hide the button.
var SAWARI_WHATSAPP = "919730749747";

// Rough per-person costs in INR. day = stay + food + local transport + sightseeing per day,
// for Budget / Comfort / Luxury. travel = return flight or train from a major Indian city
// (plus visa where needed). Update these with your own package prices.
var DESTINATIONS = [
  {name: "Goa", day: [2500, 4500, 9000], travel: 7000, ideal: 5, best: "Nov - Feb", plan: [
    "Arrive, check in near Calangute / Baga, sunset at the beach",
    "North Goa: Fort Aguada, Anjuna, Vagator and Chapora Fort",
    "Water sports at Baga, evening at a beach shack",
    "South Goa: Old Goa churches, Colva and Palolem beaches",
    "Dudhsagar waterfall and spice plantation",
    "Cruise on the Mandovi river, shopping at Mapusa market"]},
  {name: "Kerala", day: [2800, 5000, 10000], travel: 9000, ideal: 6, best: "Sep - Mar", plan: [
    "Arrive in Kochi: Fort Kochi, Chinese fishing nets, Kathakali show",
    "Drive to Munnar, waterfalls on the way",
    "Munnar tea gardens, Eravikulam National Park, Mattupetty Dam",
    "Thekkady: spice plantation and Periyar boat ride",
    "Alleppey houseboat stay on the backwaters",
    "Kovalam / Varkala beach",
    "Ayurvedic massage and departure"]},
  {name: "Kashmir", day: [3000, 5500, 11000], travel: 10000, ideal: 6, best: "Mar - Oct", plan: [
    "Arrive in Srinagar, shikara ride on Dal Lake, houseboat stay",
    "Mughal Gardens: Nishat, Shalimar, Chashme Shahi",
    "Day trip to Gulmarg, Gondola cable car",
    "Pahalgam: Betaab Valley and Aru Valley",
    "Sonamarg and Thajiwas Glacier",
    "Local markets of Srinagar, departure"]},
  {name: "Manali & Shimla", day: [2200, 4000, 8000], travel: 6000, ideal: 6, best: "Mar - Jun, Dec - Jan", plan: [
    "Arrive in Shimla, the Mall Road and the Ridge",
    "Kufri and Chail day trip",
    "Drive to Manali via Kullu, river rafting",
    "Solang Valley adventure activities",
    "Atal Tunnel and Sissu / Rohtang Pass (when open)",
    "Hadimba Temple, Old Manali cafes, Vashisht hot springs"]},
  {name: "Rajasthan", day: [2500, 5000, 12000], travel: 7000, ideal: 7, best: "Oct - Mar", plan: [
    "Jaipur: Amber Fort, Hawa Mahal, City Palace",
    "Jaipur bazaars, drive to Pushkar",
    "Drive to Jodhpur, Mehrangarh Fort",
    "Jaisalmer Fort and havelis",
    "Sam sand dunes, camel safari, desert camp night",
    "Drive to Udaipur",
    "Udaipur: City Palace, Lake Pichola boat ride"]},
  {name: "Ladakh", day: [3500, 6000, 11000], travel: 12000, ideal: 7, best: "May - Sep", plan: [
    "Arrive in Leh and rest to get used to the altitude",
    "Leh Palace, Shanti Stupa, Leh market",
    "Sham Valley: Magnetic Hill, Gurudwara Pathar Sahib",
    "Drive over Khardung La to Nubra Valley, Bactrian camel ride",
    "Nubra to Pangong Lake via Shyok",
    "Pangong Lake sunrise, back to Leh",
    "Monasteries: Thiksey and Hemis"]},
  {name: "Andaman", day: [3500, 6500, 12000], travel: 15000, ideal: 6, best: "Oct - May", plan: [
    "Arrive in Port Blair, Cellular Jail light and sound show",
    "Ferry to Havelock, Radhanagar Beach sunset",
    "Scuba diving / snorkelling at Elephant Beach",
    "Neil Island: Bharatpur and Laxmanpur beaches",
    "Back to Port Blair, Ross Island and North Bay",
    "Shopping and departure"]},
  {name: "Sikkim & Darjeeling", day: [2500, 4500, 8500], travel: 10000, ideal: 7, best: "Mar - May, Oct - Dec", plan: [
    "Arrive in Bagdogra, drive to Gangtok",
    "Tsomgo Lake and Baba Mandir",
    "Gangtok sightseeing: Rumtek Monastery, MG Marg",
    "Drive to Darjeeling",
    "Tiger Hill sunrise over Kanchenjunga, toy train",
    "Tea gardens and Peace Pagoda",
    "Mirik Lake, departure"]},
  {name: "Dubai", day: [6000, 10000, 20000], travel: 30000, ideal: 5, best: "Nov - Mar", plan: [
    "Arrive, Dhow cruise dinner at Dubai Marina",
    "City tour, Burj Khalifa observation deck, Dubai Mall fountain show",
    "Desert safari with dune bashing and BBQ dinner",
    "Abu Dhabi day trip: Sheikh Zayed Mosque, Ferrari World",
    "Miracle Garden / Global Village, gold souk shopping"]},
  {name: "Thailand", day: [3500, 6500, 13000], travel: 22000, ideal: 6, best: "Nov - Apr", plan: [
    "Arrive in Bangkok, evening at a floating market or night market",
    "Bangkok temples: Grand Palace, Wat Arun, Wat Pho",
    "Fly to Phuket, Patong beach",
    "Phi Phi Islands speedboat tour",
    "James Bond Island / Phang Nga Bay",
    "Big Buddha, Old Phuket town, departure"]},
  {name: "Bali", day: [4000, 7000, 15000], travel: 35000, ideal: 6, best: "Apr - Oct", plan: [
    "Arrive, check in at Seminyak or Kuta, beach sunset",
    "Ubud: Tegallalang rice terraces, Monkey Forest, Bali swing",
    "Kintamani volcano view and coffee plantation",
    "Nusa Penida island day trip",
    "Tanah Lot and Uluwatu temples, Kecak fire dance",
    "Spa day and shopping"]},
  {name: "Singapore", day: [7000, 11000, 20000], travel: 28000, ideal: 5, best: "All year", plan: [
    "Arrive, Gardens by the Bay light show, Marina Bay Sands",
    "Sentosa Island: Universal Studios",
    "Sentosa: S.E.A. Aquarium, Wings of Time",
    "Night Safari, Chinatown and Little India",
    "Orchard Road shopping, departure"]},
  {name: "Maldives", day: [9000, 18000, 40000], travel: 25000, ideal: 4, best: "Nov - Apr", plan: [
    "Arrive in Male, speedboat or seaplane to your resort",
    "Snorkelling on the house reef, sunset cruise",
    "Island hopping and sandbank picnic",
    "Spa and water sports, departure"]},
  {name: "Vietnam", day: [3500, 6000, 12000], travel: 30000, ideal: 7, best: "Nov - Apr", plan: [
    "Arrive in Hanoi, Old Quarter and water puppet show",
    "Ha Long Bay overnight cruise",
    "Back to Hanoi, fly to Da Nang",
    "Ba Na Hills and the Golden Bridge",
    "Hoi An ancient town, lantern evening",
    "Fly to Ho Chi Minh City, Cu Chi Tunnels",
    "Mekong Delta day trip"]}
];
var STYLES = ["Budget", "Comfort", "Luxury"];
var CHILD_FACTOR = 0.6;

var $ = function (id) { return document.getElementById(id); };
var inr = function (n) { return "₹" + (Math.round(n / 500) * 500).toLocaleString("en-IN"); };
var style = 1;
var unlocked = false;

DESTINATIONS.forEach(function (d, i) {
  var o = document.createElement("option");
  o.value = i;
  o.textContent = d.name;
  $("dest").appendChild(o);
});
var next = new Date();
next.setMonth(next.getMonth() + 1);
$("month").value = next.toISOString().slice(0, 7);
$("month").min = new Date().toISOString().slice(0, 7);

// Pre-select from a link like /trip-planner?destination=Kerala (use it in your ads)
var wanted = new URLSearchParams(location.search).get("destination");
DESTINATIONS.forEach(function (d, i) {
  if (wanted && d.name.toLowerCase().indexOf(wanted.toLowerCase()) === 0) {
    $("dest").value = i;
    $("days").value = d.ideal;
  }
});

function clamp(v, lo, hi, def) {
  v = parseInt(v, 10);
  return isNaN(v) ? def : Math.min(hi, Math.max(lo, v));
}

function trip() {
  var d = DESTINATIONS[$("dest").value];
  var days = clamp($("days").value, 2, 21, d.ideal);
  var adults = clamp($("adults").value, 1, 50, 2);
  var kids = clamp($("kids").value, 0, 20, 0);
  var people = adults + kids * CHILD_FACTOR;
  var perAdult = d.day[style] * days + ($("travel").checked ? d.travel : 0);
  var total = perAdult * people;
  var plan = d.plan.slice(0, days - 1);
  while (plan.length < days - 1) plan.push("Free day: relax, shop or add an optional activity");
  plan.push("Check out and depart with great memories");
  return {d: d, days: days, adults: adults, kids: kids, perAdult: perAdult,
          low: total * 0.9, high: total * 1.15, plan: plan, month: $("month").value};
}

function render() {
  var t = trip();
  var who = t.adults + " adult" + (t.adults > 1 ? "s" : "") + (t.kids ? ", " + t.kids + " child" + (t.kids > 1 ? "ren" : "") : "");
  $("r-title").textContent = "Estimated cost: " + t.d.name + ", " + t.days + " days, " + who;
  $("r-total").textContent = inr(t.low) + " – " + inr(t.high);
  $("r-per").textContent = "About " + inr(t.perAdult) + " per adult, " + STYLES[style].toLowerCase() + " stay" +
    ($("travel").checked ? ", including return travel" : ", excluding travel to the destination");
  var facts = ["Best time: " + t.d.best, "Ideal length: " + t.d.ideal + " days", STYLES[style] + " hotels"];
  if (t.month) {
    var m = new Date(t.month + "-01");
    facts.unshift(m.toLocaleString("en-IN", {month: "long", year: "numeric"}));
  }
  $("r-facts").innerHTML = "";
  facts.forEach(function (f) {
    var s = document.createElement("span");
    s.textContent = f;
    $("r-facts").appendChild(s);
  });
  $("plan-title").textContent = "Your " + t.days + "-day " + t.d.name + " plan";
  $("days-list").innerHTML = "";
  t.plan.forEach(function (p) {
    var li = document.createElement("li");
    li.textContent = p;
    $("days-list").appendChild(li);
  });
  if (unlocked) updateWhatsApp();
}

function updateWhatsApp() {
  if (!SAWARI_WHATSAPP) { $("wa-btn").classList.add("hidden"); return; }
  var t = trip();
  var text = "Hi Sawari Travel, I'd like a quote for " + t.d.name + ", " + t.days + " days, " + t.adults +
    " adults" + (t.kids ? " + " + t.kids + " children" : "") + (t.month ? ", " + t.month : "") +
    " (" + STYLES[style] + "). My estimate was " + inr(t.low) + " – " + inr(t.high) + ".";
  $("wa-btn").href = "https://wa.me/" + SAWARI_WHATSAPP + "?text=" + encodeURIComponent(text);
}

document.querySelectorAll(".seg button").forEach(function (b) {
  b.onclick = function () {
    style = +b.dataset.style;
    document.querySelectorAll(".seg button").forEach(function (x) { x.setAttribute("aria-pressed", x === b); });
    render();
  };
});
$("dest").onchange = function () { $("days").value = DESTINATIONS[this.value].ideal; render(); };
["days", "adults", "kids", "month", "travel"].forEach(function (id) { $(id).oninput = render; });

$("lead-form").onsubmit = function (e) {
  e.preventDefault();
  var form = e.target;
  var err = $("err");
  var phone = form.phone.value.replace(/[\s()-]/g, "").replace(/^(\+?91|0)(?=[6-9]\d{9}$)/, "");
  if (!/^[6-9]\d{9}$/.test(phone)) {
    err.textContent = "Please enter a valid 10-digit mobile number.";
    err.classList.remove("hidden");
    form.phone.focus();
    return;
  }
  err.classList.add("hidden");
  var t = trip();
  form.phone.value = phone;
  form.destination.value = t.d.name;
  form.travel_date.value = t.month ? t.month + "-01" : "";
  form.message.value = "Trip planner: " + t.days + " days, " + t.adults + " adult" + (t.adults > 1 ? "s" : "") +
    (t.kids ? ", " + t.kids + " child" + (t.kids > 1 ? "ren" : "") : "") + ", " +
    STYLES[style] + ", " + ($("travel").checked ? "with" : "without") + " travel. Estimate " +
    inr(t.low) + " - " + inr(t.high) + "." + (location.search ? " Link: " + location.search : "");
  $("submit").disabled = true;
  $("submit").textContent = "Sending...";
  fetch("/", {
    method: "POST",
    headers: {"Content-Type": "application/x-www-form-urlencoded"},
    body: new URLSearchParams(new FormData(form)).toString()
  }).then(function (r) {
    if (!r.ok) throw new Error(r.status);
    unlocked = true;
    $("plan").classList.remove("locked");
    var name = form.name.value;
    $("unlock").innerHTML = "<h2></h2><p class='muted' style='margin:0'>Your full itinerary is above. " +
      "A Sawari Travel expert will call you within 24 hours with an exact quote.</p>";
    $("unlock").querySelector("h2").textContent = "Thank you, " + name + "!";
    $("after").classList.remove("hidden");
    updateWhatsApp();
    if (window.gtag) gtag("event", "generate_lead", {destination: t.d.name});
    if (window.fbq) fbq("track", "Lead");
    $("plan-title").scrollIntoView({behavior: "smooth"});
  }).catch(function () {
    err.textContent = "Sorry, we couldn't send that. Please check your internet connection and try again.";
    err.classList.remove("hidden");
    $("submit").disabled = false;
    $("submit").textContent = "Show my full itinerary";
  });
};

$("print-btn").onclick = function () { window.print(); };

render();
