/* ---------------------------
# Auth UX helpers (Tikzok)
--------------------------- */
(function () {
  function setButtonLoading(btn, loading) {
    if (!btn) return;
    if (loading) {
      btn.classList.add("is-loading");
      btn.setAttribute("disabled", "disabled");
      const label = btn.getAttribute("data-label") || btn.textContent.trim();
      btn.setAttribute("data-label", label);
      btn.innerHTML =
        '<span class="tz-btn-loader" aria-hidden="true"></span><span>' +
        label +
        "</span>";
    } else {
      btn.classList.remove("is-loading");
      btn.removeAttribute("disabled");
      const label = btn.getAttribute("data-label");
      if (label) btn.textContent = label;
    }
  }

  // Anti double submit + loading button
document.querySelectorAll("form[data-tz-form]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    const btn =
      event.submitter instanceof HTMLButtonElement
        ? event.submitter
        : form.querySelector("button[type=submit]");

    setButtonLoading(btn, true);
    form.setAttribute("aria-busy", "true");
  });
});

  // OTP: digits only + paste + autofocus
  document.querySelectorAll("input[data-tz-otp]").forEach((otp) => {
    otp.addEventListener("input", (e) => {
      const v = (e.target.value || "").replace(/\D+/g, "");
      e.target.value = v;
    });

    otp.addEventListener("paste", (e) => {
      const text = (e.clipboardData || window.clipboardData).getData("text") || "";
      const v = text.replace(/\D+/g, "");
      if (!v) return;
      e.preventDefault();
      otp.value = v;
    });

    if (!otp.value) setTimeout(() => otp.focus(), 50);
  });


// expose global (HTML onclick)
window.selectCountry = function(code){
window.openCountryModal = function(){
  const el = document.getElementById("countryCode")
   alert("country selector ici (on fera modal après)")
  if(!el) return
  el.value = code
 }
}
  // Resend timer UI (front only, backend enforce aussi)
  document.querySelectorAll("[data-tz-resend]").forEach((wrap) => {
    const btn = wrap.querySelector("[data-tz-resend-btn]");
    const badge = wrap.querySelector("[data-tz-resend-badge]");
    const seconds = parseInt(wrap.getAttribute("data-tz-resend"), 10);
    if (!btn || !badge || !seconds || seconds <= 0) return;

    let left = seconds;
    btn.setAttribute("disabled", "disabled");
    badge.textContent = left + "s";

    const tick = () => {
      left -= 1;
      if (left <= 0) {
        btn.removeAttribute("disabled");
        badge.textContent = "";
        return;
      }
      badge.textContent = left + "s";
      setTimeout(tick, 1000);
    };
    setTimeout(tick, 1000);
  });
})();
//---------------------------
//Country picker logic
//---------------------------
const COUNTRIES = [
  {name:"France", code:"+33", flag:"🇫🇷"},
  {name:"United States", code:"+1", flag:"🇺🇸"},
  {name:"United Kingdom", code:"+44", flag:"🇬🇧"},
  {name:"Germany", code:"+49", flag:"🇩🇪"},
  {name:"Italy", code:"+39", flag:"🇮🇹"},
  {name:"Spain", code:"+34", flag:"🇪🇸"},
]

window.openCountryModal = function(){
  document.getElementById("countryModal").classList.add("tz-modal--open")
  renderCountries(COUNTRIES)
}

window.closeCountryModal = function(){
  document.getElementById("countryModal").classList.remove("tz-modal--open")
}

function renderCountries(list){
  const el = document.getElementById("countryList")
  if(!el) return

  el.innerHTML = list.map(c=>`
    <button class="tz-country-row" onclick="selectCountryItem('${c.code}','${c.flag}','${c.name}')">
      <span>${c.flag}</span>
      <span>${c.name}</span>
      <span style="margin-left:auto">${c.code}</span>
    </button>
  `).join("")
}

window.selectCountryItem = function(code,flag,name){
  const codeEl = document.getElementById("countryCode")
  if(codeEl) codeEl.value = code

  document.getElementById("countryFlag").textContent = flag
  document.getElementById("countryLabel").textContent = `${name} (${code})`

  closeCountryModal()
}

window.filterCountries = function(){
  const q = document.getElementById("countrySearch").value.toLowerCase()

  const filtered = COUNTRIES.filter(c =>
    c.name.toLowerCase().includes(q) ||
    c.code.includes(q)
  )

  renderCountries(filtered)
}
// =========================
// iOS Style Menu Animation
// =========================

const menu = document.getElementById("sideMenu");
const overlay = document.getElementById("menuOverlay");

function openMenu() {
  menu.classList.add("open");
  overlay.classList.add("show");
}

function closeMenu() {
  menu.classList.remove("open");
  overlay.classList.remove("show");
}

// bouton navbar (ajuste l'ID si nécessaire)
const menuBtn = document.getElementById("menuToggle");

if (menuBtn) {
  menuBtn.addEventListener("click", openMenu);
}

overlay.addEventListener("click", closeMenu);