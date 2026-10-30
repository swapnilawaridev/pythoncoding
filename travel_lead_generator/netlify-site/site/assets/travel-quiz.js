// "Where should you travel next?" quiz for sawaritravel.com/travel-quiz.html
// Visitors answer 6 questions, get a matching destination, and leave their WhatsApp
// number to receive the plan and price (Netlify Form "trip-quiz"). After that they get
// a personal share link, so every lead can bring in friends (tracked as "referred_by").
// Loaded as a separate file because the site's Content-Security-Policy blocks inline scripts.

// Sawari Travel's WhatsApp number (country code, no "+").
var SAWARI_WHATSAPP = "919730749747";
// Optional reward shown on the share screen, e.g. "₹500 off for you and your friend".
// Leave "" until you decide on a reward you want to honour.
var REFERRAL_REWARD = "";
var SITE = "https://sawaritravel.com";

var QUESTIONS = [
  {key: "who", q: "Who's travelling?", options: [
    ["couple", "💑 Couple / honeymoon"], ["family", "👨‍👩‍👧 Family with kids"], ["friends", "🎉 Group of friends"],
    ["solo", "🎒 Just me"], ["parents", "🙏 Parents / seniors"]]},
  {key: "vibe", q: "What kind of holiday do you love?", options: [
    ["beach", "🏖️ Beaches & islands"], ["mountains", "🏔️ Mountains & snow"], ["culture", "🏰 Forts, temples & culture"],
    ["adventure", "🪂 Adventure & thrills"], ["luxury", "🛍️ Luxury & shopping"]]},
  {key: "budget", q: "Budget per person (including travel)?", options: [
    ["25000", "Under ₹25,000"], ["50000", "₹25,000 – ₹50,000"], ["100000", "₹50,000 – ₹1 lakh"], ["999999", "Above ₹1 lakh"]]},
  {key: "days", q: "How many days can you get away?", options: [
    ["4", "3 – 4 days"], ["6", "5 – 6 days"], ["8", "7 days or more"]]},
  {key: "when", q: "When do you want to go?", options: [
    ["1", "Next month"], ["3", "In 2 – 3 months"], ["6", "Later this year"], ["0", "Not sure yet"]]},
  {key: "where", q: "India or abroad?", options: [
    ["india", "🇮🇳 India"], ["abroad", "✈️ Abroad"], ["any", "🤷 Surprise me"]]}
];

// from = typical per-person price (budget stay, incl. return travel); typical = comfort stay.
// months = best months (1-12). Update prices to match your own packages.
var DESTINATIONS = [
  {name: "Goa", abroad: false, tags: ["beach", "friends", "couple", "solo"], from: 19500, typical: 29500, days: 5, months: [11, 12, 1, 2, 3],
   why: "Beaches, water sports, nightlife and Portuguese-era churches. Easy and great value."},
  {name: "Kerala", abroad: false, tags: ["beach", "couple", "family", "parents", "culture"], from: 26000, typical: 39000, days: 6, months: [9, 10, 11, 12, 1, 2, 3],
   why: "Houseboats on the backwaters, misty Munnar tea gardens and Ayurvedic spas."},
  {name: "Kashmir", abroad: false, tags: ["mountains", "couple", "family", "parents"], from: 28000, typical: 43000, days: 6, months: [3, 4, 5, 6, 7, 8, 9, 10],
   why: "Shikara rides on Dal Lake, Gulmarg's gondola and snow-capped valleys."},
  {name: "Manali & Shimla", abroad: false, tags: ["mountains", "friends", "adventure", "family", "couple"], from: 19000, typical: 30000, days: 6, months: [3, 4, 5, 6, 12, 1],
   why: "Snow at Solang and Atal Tunnel, river rafting, cosy cafes in Old Manali."},
  {name: "Rajasthan", abroad: false, tags: ["culture", "family", "parents", "luxury"], from: 24500, typical: 42000, days: 7, months: [10, 11, 12, 1, 2, 3],
   why: "Royal forts and palaces, a desert camp under the stars and Udaipur's lakes."},
  {name: "Ladakh", abroad: false, tags: ["adventure", "mountains", "friends", "solo"], from: 36500, typical: 54000, days: 7, months: [5, 6, 7, 8, 9],
   why: "Khardung La, Pangong Lake and Nubra's sand dunes. A once-in-a-lifetime road trip."},
  {name: "Andaman", abroad: false, tags: ["beach", "couple", "adventure", "family"], from: 36000, typical: 54000, days: 6, months: [10, 11, 12, 1, 2, 3, 4, 5],
   why: "Crystal-clear water, scuba diving at Havelock and India's best beaches."},
  {name: "Sikkim & Darjeeling", abroad: false, tags: ["mountains", "family", "parents", "culture"], from: 27500, typical: 41500, days: 7, months: [3, 4, 5, 10, 11, 12],
   why: "Kanchenjunga sunrise, the toy train, tea gardens and peaceful monasteries."},
  {name: "Dubai", abroad: true, tags: ["luxury", "family", "friends", "adventure"], from: 60000, typical: 80000, days: 5, months: [11, 12, 1, 2, 3],
   why: "Burj Khalifa, desert safari, theme parks and the world's best shopping."},
  {name: "Thailand", abroad: true, tags: ["beach", "friends", "solo", "couple", "adventure"], from: 43000, typical: 61000, days: 6, months: [11, 12, 1, 2, 3, 4],
   why: "Phi Phi islands, Bangkok's temples and street food. The best-value trip abroad."},
  {name: "Bali", abroad: true, tags: ["beach", "couple", "culture", "solo"], from: 59000, typical: 77000, days: 6, months: [4, 5, 6, 7, 8, 9, 10],
   why: "Rice terraces, cliff-top temples, private pool villas and the Bali swing."},
  {name: "Singapore", abroad: true, tags: ["family", "luxury", "parents"], from: 63000, typical: 83000, days: 5, months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
   why: "Universal Studios, Gardens by the Bay and Night Safari. Perfect with kids."},
  {name: "Maldives", abroad: true, tags: ["beach", "luxury", "couple"], from: 61000, typical: 97000, days: 4, months: [11, 12, 1, 2, 3, 4],
   why: "Overwater villas, turquoise lagoons and total privacy. The ultimate honeymoon."},
  {name: "Vietnam", abroad: true, tags: ["culture", "adventure", "solo", "friends"], from: 54500, typical: 72000, days: 7, months: [11, 12, 1, 2, 3, 4],
   why: "Ha Long Bay cruise, lantern-lit Hoi An and amazing food at great prices."}
];

var $ = function (id) { return document.getElementById(id); };
var inr = function (n) { return "₹" + (Math.round(n / 500) * 500).toLocaleString("en-IN"); };
var answers = {};
var step = 0;
var matches = [];

function param(name) { return new URLSearchParams(location.search).get(name) || ""; }
function storage(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch (e) {}
  return value;
}

// Each visitor gets a short code for their share link; friends who come through it are tagged with it.
var myCode = storage("sawari_ref") || storage("sawari_ref", Math.random().toString(36).slice(2, 8).toUpperCase());
var referredBy = param("ref").replace(/[^A-Za-z0-9]/g, "").slice(0, 12);
if (referredBy === myCode) referredBy = "";

function travelMonth() {
  var ahead = +answers.when;
  if (!ahead) return 0;
  var d = new Date();
  d.setMonth(d.getMonth() + ahead);
  return d;
}

function score(d) {
  var s = 0;
  if (d.tags.indexOf(answers.who) >= 0) s += 3;
  if (d.tags.indexOf(answers.vibe) >= 0) s += 5;
  var budget = +answers.budget;
  if (d.typical <= budget) s += 3;
  else if (d.from <= budget) s += 1;
  else s -= 5;
  // Prefer trips that use the budget they chose, not just fit under it.
  var budgets = QUESTIONS[2].options.map(function (o) { return +o[0]; });
  var lower = budgets[budgets.indexOf(budget) - 1] || 0;
  if (d.typical >= lower) s += 2;
  if (answers.where === "india" && d.abroad) s -= 6;
  if (answers.where === "abroad" && !d.abroad) s -= 6;
  var days = +answers.days;
  if (Math.abs(d.days - days) <= 1) s += 1;
  var month = travelMonth();
  if (month) s += d.months.indexOf(month.getMonth() + 1) >= 0 ? 2 : -2;
  return s;
}

function showQuestion() {
  var q = QUESTIONS[step];
  $("progress-bar").style.width = (step / QUESTIONS.length * 100) + "%";
  $("q-count").textContent = "Question " + (step + 1) + " of " + QUESTIONS.length;
  $("q-text").textContent = q.q;
  $("back").classList.toggle("hidden", step === 0);
  var box = $("q-options");
  box.innerHTML = "";
  q.options.forEach(function (o) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "opt";
    b.textContent = o[1];
    b.onclick = function () {
      answers[q.key] = o[0];
      step++;
      if (step < QUESTIONS.length) showQuestion(); else showResult();
    };
    box.appendChild(b);
  });
  box.firstChild.focus({preventScroll: true});
}

// [11, 12, 1, 2, 3] -> "Nov – Mar"; [3, 4, 5, 6, 12, 1] -> "Mar – Jun, Dec – Jan"
function seasons(months) {
  if (months.length === 12) return "All year";
  var name = function (m) { return new Date(2000, m - 1, 1).toLocaleString("en-IN", {month: "short"}); };
  var has = function (m) { return months.indexOf((m + 11) % 12 + 1) >= 0; };
  var ranges = [];
  months.forEach(function (m) {
    if (has(m - 1)) return;  // not the start of a run
    var end = m;
    while (has(end + 1)) end = (end % 12) + 1;
    ranges.push(end === m ? name(m) : name(m) + " – " + name(end));
  });
  return ranges.join(", ");
}

function showResult() {
  matches = DESTINATIONS.slice().sort(function (a, b) { return score(b) - score(a); }).slice(0, 3);
  var best = matches[0];
  $("quiz").classList.add("hidden");
  $("result").classList.remove("hidden");
  $("r-name").textContent = best.name;
  $("r-why").textContent = best.why;
  $("r-price").textContent = "from " + inr(best.from) + " per person";
  $("r-days").textContent = best.days + " days ideal";
  $("r-best").textContent = "Best: " + seasons(best.months);
  $("r-alt").textContent = matches.slice(1).map(function (d) { return d.name; }).join(" or ");
  $("result").scrollIntoView({behavior: "smooth", block: "start"});
}

function shareLink() {
  return SITE + "/travel-quiz.html?ref=" + myCode + "&utm_source=quiz_share";
}

function showShare(name) {
  var best = matches[0];
  $("lead").classList.add("hidden");
  $("thanks").classList.remove("hidden");
  $("thanks-title").textContent = "Done, " + name + "! Your " + best.name + " plan is on its way.";
  if (REFERRAL_REWARD) {
    $("reward").textContent = "🎁 " + REFERRAL_REWARD + " when a friend books through your link.";
    $("reward").classList.remove("hidden");
  }
  var text = "I took the Sawari Travel quiz and got " + best.name + "! 🌴 Find your perfect holiday in 30 seconds: " + shareLink();
  $("share-wa").href = "https://wa.me/?text=" + encodeURIComponent(text);
  $("share-link").value = shareLink();
  $("chat").href = "https://wa.me/" + SAWARI_WHATSAPP + "?text=" + encodeURIComponent(
    "Hi Sawari Travel, my quiz result was " + best.name + ". Please send me the plan and best price.");
  if (navigator.share) {
    $("share-native").classList.remove("hidden");
    $("share-native").onclick = function () {
      navigator.share({title: "Where should you travel next?", text: "I got " + best.name + "! Take the quiz:", url: shareLink()}).catch(function () {});
    };
  }
  $("thanks").scrollIntoView({behavior: "smooth", block: "start"});
}

$("start").onclick = function () {
  $("intro").classList.add("hidden");
  $("quiz").classList.remove("hidden");
  showQuestion();
};
$("back").onclick = function () { step--; showQuestion(); };
$("retake").onclick = function () {
  answers = {};
  step = 0;
  $("result").classList.add("hidden");
  $("quiz").classList.remove("hidden");
  showQuestion();
};
$("copy").onclick = function () {
  var input = $("share-link");
  input.select();
  (navigator.clipboard ? navigator.clipboard.writeText(input.value) : Promise.reject()).catch(function () {
    document.execCommand("copy");
  });
  $("copy").textContent = "Copied!";
};

$("lead-form").onsubmit = function (e) {
  e.preventDefault();
  var form = e.target;
  var err = $("err");
  var phone = form.phone.value.replace(/[\s()-]/g, "").replace(/^(\+?91|0)(?=[6-9]\d{9}$)/, "");
  if (!/^[6-9]\d{9}$/.test(phone)) {
    err.textContent = "Please enter a valid 10-digit WhatsApp number.";
    err.classList.remove("hidden");
    form.phone.focus();
    return;
  }
  err.classList.add("hidden");
  var best = matches[0];
  var month = travelMonth();
  var labels = {};
  QUESTIONS.forEach(function (q) {
    q.options.forEach(function (o) {
      if (answers[q.key] === o[0]) labels[q.key] = o[1].replace(/^[^A-Za-z₹0-9]+/, "");  // drop the emoji
    });
  });
  form.phone.value = phone;
  form.destination.value = best.name;
  form.travel_date.value = month ? month.toISOString().slice(0, 7) + "-01" : "";
  form.ref_code.value = myCode;
  form.referred_by.value = referredBy;
  form.message.value = "Travel quiz: " + labels.who + ", " + labels.vibe + ", budget " + labels.budget + ", " +
    labels.days + ", " + labels.when + ", " + labels.where + ". Also suggested: " +
    matches.slice(1).map(function (d) { return d.name; }).join(", ") + "." +
    (referredBy ? " Referred by friend code " + referredBy + "." : "") + " Own share code " + myCode + ".";
  $("submit").disabled = true;
  $("submit").textContent = "Sending...";
  fetch("/", {
    method: "POST",
    headers: {"Content-Type": "application/x-www-form-urlencoded"},
    body: new URLSearchParams(new FormData(form)).toString()
  }).then(function (r) {
    if (!r.ok) throw new Error(r.status);
    if (window.gtag) gtag("event", "generate_lead", {destination: best.name, method: "quiz"});
    if (window.fbq) fbq("track", "Lead");
    showShare(form.name.value);
  }).catch(function () {
    err.textContent = "Sorry, we couldn't send that. Please check your internet connection and try again.";
    err.classList.remove("hidden");
    $("submit").disabled = false;
    $("submit").textContent = "Send me the plan & price";
  });
};

if (referredBy) $("friend").classList.remove("hidden");
