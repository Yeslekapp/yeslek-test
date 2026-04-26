// ---------------------------
// Enter number UX
// ---------------------------
// Flutter parity + production safe
// ---------------------------
(function () {
  "use strict";

  const phoneInput = document.getElementById("phoneInput");
  const phoneE164 = document.getElementById("phoneE164");
  const countryIsoInput = document.getElementById("countryIso");
  const countryCodeInput = document.getElementById("countryCode");
  const continueBtn = document.getElementById("continueBtn");
  const help = document.getElementById("phoneHelp");
  const cityImage = document.getElementById("cityImage");

  const countryBtn = document.getElementById("countryBtn");
  const countryFlag = document.getElementById("countryFlag");
  const contactBtn = document.getElementById("contactBtn");

  const form = document.getElementById("enterNumberForm");

  let COUNTRIES = [];
  let DIAL_INDEX = new Map();
  let MAX_DIAL_LEN = 4;

  let _isProgrammaticUpdate = false;
  let lookupTimer = null;
  let lookupRequestId = 0;
  let lastLookupKey = "";
  let lastLookupValid = false;

  // ---------------------------
  // Countries shared loader
  // ---------------------------
  function getCountriesPromise() {
    if (!window.__tzCountriesPromise) {
      window.__tzCountriesPromise = fetch("/static/data/countries.json", {
        cache: "force-cache"
      }).then((res) => {
        if (!res.ok) {
          throw new Error("countries.json not found");
        }
        return res.json();
      });
    }

    return window.__tzCountriesPromise;
  }

  // ---------------------------
  // Helpers
  // ---------------------------
  function digitsOnly(value) {
    return String(value || "").replace(/[^\d]/g, "");
  }
function setPhoneValue(value) {
  _isProgrammaticUpdate = true;
  phoneInput.value = value;
  _isProgrammaticUpdate = false;
}
// ---------------------------
// Phone rules validation
// ---------------------------
function validateByCountry(iso, e164) {
  const rules = window.TZ_PHONE_RULES || {};
  const rule = rules[iso];

  if (!rule) return true;

  const digits = digitsOnly(e164);
  const country = getSelectedCountry();
  const dial = digitsOnly(country?.dial || "");

  const national = digits.slice(dial.length);

  return (
    national.length >= rule.min &&
    national.length <= rule.max
  );
}
  function sanitizeIso(value) {
    const iso = String(value || "").trim().toLowerCase();
    return /^[a-z]{2}$/.test(iso) ? iso : "fr";
  }

  function sanitizeToPhoneInput(value) {
    let v = String(value || "").replace(/[^\d+]/g, "");

    if (!v) {
      return "";
    }

    if (!v.startsWith("+")) {
      v = "+" + v.replace(/\+/g, "");
    } else {
      v = "+" + v.slice(1).replace(/\+/g, "");
    }

    const digits = digitsOnly(v);
    if (digits.length > 15) {
      v = "+" + digits.slice(0, 15);
    }

    return v;
  }

  function sanitizeToE164(value) {
    const cleaned = sanitizeToPhoneInput(value);

    if (!cleaned || !/^\+\d+$/.test(cleaned)) {
      return null;
    }

    const digits = digitsOnly(cleaned);
    if (digits.length > 15) {
      return null;
    }

    return cleaned;
  }

  function buildDialIndex() {
    DIAL_INDEX.clear();
    MAX_DIAL_LEN = 1;

    for (const c of COUNTRIES) {
      const dialDigits = digitsOnly(c.dial || "");

      if (!dialDigits) {
        continue;
      }

      if (!DIAL_INDEX.has(dialDigits)) {
        DIAL_INDEX.set(dialDigits, c);
      }

      MAX_DIAL_LEN = Math.max(MAX_DIAL_LEN, dialDigits.length);
    }

    MAX_DIAL_LEN = Math.min(MAX_DIAL_LEN, 6);
  }

  function findCountryByIso(iso) {
    const normalizedIso = sanitizeIso(iso);
    return COUNTRIES.find((c) => {
      return sanitizeIso(c.iso || c.iso2) === normalizedIso;
    }) || null;
  }

  function findCountryByDialPrefix(phoneValue) {
    const digits = digitsOnly(phoneValue);
    if (!digits) {
      return null;
    }

    const maxLen = Math.min(MAX_DIAL_LEN, digits.length);

    for (let len = maxLen; len >= 1; len--) {
      const candidate = digits.slice(0, len);
      const country = DIAL_INDEX.get(candidate);
      if (country) {
        return country;
      }
    }

    return null;
  }

  function getSelectedIso() {
    return sanitizeIso(
      countryBtn?.dataset?.countryIso ||
      countryIsoInput?.value ||
      "fr"
    );
  }

  function getSelectedCountry() {
    return findCountryByIso(getSelectedIso());
  }

  function syncHiddenE164(e164) {
    if (phoneE164) {
      phoneE164.value = e164 || "";
    }
  }

  function syncCountryCode(dial) {
    if (countryCodeInput) {
      countryCodeInput.value = dial || "";
    }
  }

  function syncCountryIso(iso) {
    const normalizedIso = sanitizeIso(iso);

    if (countryBtn) {
      countryBtn.dataset.countryIso = normalizedIso;
    }

    if (countryIsoInput) {
      countryIsoInput.value = normalizedIso;
    }
  }

  function formatForDisplay(e164) {
    return e164 ? e164.replace(/\s+/g, "") : "";
  }

function setCityByIso(iso) {
  if (!cityImage) return;

  const normalizedIso = sanitizeIso(iso);

  cityImage.src =
    "https://source.unsplash.com/1200x600/?city," +
    normalizedIso +
    "&sig=" +
    Date.now();
}

  function normalizeInternationalNumber(phone) {
    const cleaned = sanitizeToPhoneInput(phone);

    if (!cleaned.startsWith("+")) {
      return cleaned;
    }

    const digits = cleaned.slice(1);
    const maxLen = Math.min(MAX_DIAL_LEN, digits.length);

    for (let len = maxLen; len >= 1; len--) {
      const code = digits.slice(0, len);
      const country = DIAL_INDEX.get(code);

      if (!country) {
        continue;
      }

      const rest = digits.slice(len);
      if (rest.startsWith("0")) {
        return `+${code}${rest.slice(1)}`;
      }

      return cleaned;
    }

    return cleaned;
  }

  function normalizeInternationalNumberWithCountry(phone) {
    const cleaned = sanitizeToPhoneInput(phone);
    if (!cleaned.startsWith("+")) {
      return cleaned;
    }

    const country = getSelectedCountry();
    if (!country) {
      return cleaned;
    }

    const code = digitsOnly(country.dial || "");
    const digits = cleaned.slice(1);

    if (!digits.startsWith(code)) {
      return cleaned;
    }

    const rest = digits.slice(code.length);
    if (rest.startsWith("0")) {
      return `+${code}${rest.slice(1)}`;
    }

    return cleaned;
  }

// ---------------------------
// Country state
// ---------------------------
function applyCountry(country, options = {}) {
  if (!country) {
    return;
  }

  const iso = sanitizeIso(country.iso || country.iso2);
  const dial = country.dial || "";

  const shouldSetPrefix = !!options.setPrefixIfEmpty;
  const forceReplace = !!options.forceReplaceDial;

  syncCountryIso(iso);
  syncCountryCode(dial);

  if (countryFlag) {
    countryFlag.textContent = country.flag || "";
  }

  setCityByIso(iso);

  if (!phoneInput) return;

  const current = phoneInput.value || "";

  // ---------------------------
  // FORCE replace (user change country)
  // ---------------------------
  if (forceReplace) {
    const digits = digitsOnly(current);
    const newDial = digitsOnly(dial || "");

    // supprime ancien code (1 à 4 chiffres)
    const rest = digits.replace(/^\d{1,4}/, "");

    const next = "+" + newDial + rest;

    setPhoneValue(next);
    syncHiddenE164(next);
    return;
  }

  // ---------------------------
  // Initial prefix (empty input)
  // ---------------------------
  if (shouldSetPrefix && !current.trim()) {
    const nextValue = formatForDisplay(dial);
    setPhoneValue(nextValue);
    syncHiddenE164(dial);
  }
}

function syncCountryFromPhone(value) {
  const country = findCountryByDialPrefix(value);

  if (!country) {
    return;
  }

  const currentIso = getSelectedIso();
  const nextIso = sanitizeIso(country.iso || country.iso2);

  if (currentIso !== nextIso) {
    applyCountry(country, { setPrefixIfEmpty: false });
  }
}

  // ---------------------------
  // UI states
  // ---------------------------
  function setContinueDisabled(disabled) {
    if (!continueBtn) {
      return;
    }

    continueBtn.disabled = !!disabled;
    continueBtn.setAttribute("aria-disabled", disabled ? "true" : "false");
  }

  function showEmpty() {
    setContinueDisabled(true);

    if (help) {
      help.classList.remove("tz-help--ok", "tz-help--error");
      help.classList.add("tz-help--muted");
      help.textContent = help.dataset.empty || "";
    }

    phoneInput?.classList.remove("tz-input--error");
  }

  function showValid(operatorName) {
    setContinueDisabled(false);

    if (help) {
      help.classList.remove("tz-help--error", "tz-help--muted");
      help.classList.add("tz-help--ok");
      help.textContent = operatorName || help.dataset.valid || "";
    }

    phoneInput?.classList.remove("tz-input--error");
  }

  function showInvalid() {
    setContinueDisabled(true);

    if (help) {
      help.classList.remove("tz-help--ok", "tz-help--muted");
      help.classList.add("tz-help--error");
      help.textContent = help.dataset.invalid || "";
    }

    phoneInput?.classList.add("tz-input--error");
  }

  function showChecking() {
    setContinueDisabled(true);

    if (help) {
      help.classList.remove("tz-help--ok", "tz-help--error");
      help.classList.add("tz-help--muted");
      help.textContent = help.dataset.valid || "";
    }

    phoneInput?.classList.remove("tz-input--error");
  }

  // ---------------------------
  // Lookup
  // ---------------------------
  async function tzLookupNumber() {
    if (!phoneInput) {
      return;
    }

    const phone = phoneE164?.value || "";
    const country = getSelectedIso();

    if (!phone || !country) {
      lastLookupValid = false;
      setContinueDisabled(true);
      return;
    }

    const digits = digitsOnly(phone);

    if (digits.length < 9 || digits.length > 15) {
      lastLookupValid = false;
      setContinueDisabled(true);
      return;
    }

    const lookupKey = `${phone}|${country}`;

    if (lookupKey === lastLookupKey && lastLookupValid) {
      showValid();
      return;
    }

    const requestId = ++lookupRequestId;
    showChecking();

    try {
      const res = await fetch("/recharge/api/lookup-number", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          phone: phone,
          country: country.toUpperCase()
        })
      });

      let data = {};
      try {
        data = await res.json();
      } catch (e) {
        data = {};
      }

      if (requestId !== lookupRequestId) {
        return;
      }

      if (res.ok && data.valid) {
        lastLookupKey = lookupKey;
        lastLookupValid = true;
        showValid(data.operatorName || "");
      } else {
        lastLookupKey = lookupKey;
        lastLookupValid = false;
        showInvalid();
      }
    } catch (e) {
      if (requestId !== lookupRequestId) {
        return;
      }

      lastLookupKey = lookupKey;
      lastLookupValid = false;
      showInvalid();
    }
  }

  function scheduleLookup() {
    clearTimeout(lookupTimer);
    lookupTimer = setTimeout(() => {
      tzLookupNumber();
    }, 350);
  }

  // ---------------------------
  // Validation / Flutter parity
  // ---------------------------
  function validateAndSync() {
    if (!phoneInput) {
      return;
    }

    let text = phoneInput.value || "";

    if (!text.trim()) {
      syncHiddenE164("");
      lastLookupValid = false;
      showEmpty();
      return;
    }

text = sanitizeToPhoneInput(text);

// force affichage du "+" immédiatement (UX mobile clean)
if (phoneInput.value !== text) {
  setPhoneValue(text);
}

    const digitsBeforeNormalize = digitsOnly(text);
    if (digitsBeforeNormalize.length > 15) {
      text = "+" + digitsBeforeNormalize.slice(0, 15);
    }

    syncCountryFromPhone(text);

    text = normalizeInternationalNumberWithCountry(text);
    text = normalizeInternationalNumber(text);

    const e164 = sanitizeToE164(text);

    if (!e164) {
      syncHiddenE164("");
      lastLookupValid = false;
      showInvalid();
      return;
    }

    syncCountryFromPhone(e164);
    syncHiddenE164(e164);

    const display = formatForDisplay(e164);
    if (phoneInput.value !== display) {
      setPhoneValue(display);
    }

    const iso = getSelectedIso();
    const validLength = validateByCountry(iso, e164);

    if (!validLength) {
      lastLookupValid = false;
      showInvalid();
      return;
    }

    scheduleLookup();
  }

  // ---------------------------
  // Contact picker
  // ---------------------------
  async function pickContact() {
    if (!("contacts" in navigator) || !("select" in navigator.contacts)) {
      const message = contactBtn?.dataset?.unavailableMessage || "";
      if (message) {
        alert(message);
      }
      return;
    }

    try {
      const contacts = await navigator.contacts.select(["tel"], { multiple: false });

      if (!contacts.length || !contacts[0].tel?.length) {
        return;
      }

      let raw = String(contacts[0].tel[0] || "").replace(/[^\d+]/g, "");

      if (raw.startsWith("+")) {
        raw = normalizeInternationalNumber(raw);
      } else {
        if (raw.startsWith("0")) {
          raw = raw.slice(1);
        }

        const country = getSelectedCountry();
        const dialDigits = digitsOnly(country?.dial || "");

        raw = dialDigits ? `+${dialDigits}${raw}` : `+${raw}`;
      }

      setPhoneValue(formatForDisplay(raw));
      lastLookupKey = "";
      lastLookupValid = false;
      validateAndSync();
      phoneInput?.focus();
    } catch (e) {
      // cancelled
    }
  }

// ---------------------------
// Events (FINAL SAFE)
// ---------------------------
function bindEvents() {

  // ---------------------------
  // Input typing
  // ---------------------------
  phoneInput?.addEventListener("input", () => {
    if (_isProgrammaticUpdate) return;

    lastLookupKey = "";
    lastLookupValid = false;

    validateAndSync();
    updateButtonPosition(); // bouton dynamique
  });
  // ---------------------------
// Prevent removing +
// ---------------------------
phoneInput?.addEventListener("keydown", (e) => {
  if (!phoneInput.value.startsWith("+")) return;

  if (
    (e.key === "Backspace" && phoneInput.selectionStart === 1) ||
    (e.key === "Delete" && phoneInput.selectionStart === 0)
  ) {
    e.preventDefault();
  }

  if (
    phoneInput.selectionStart === 0 &&
    (e.key === "ArrowLeft" || e.key === "Home")
  ) {
    e.preventDefault();
  }
});

phoneInput?.addEventListener("paste", (e) => {
  e.preventDefault();

  const paste = (e.clipboardData || window.clipboardData).getData("text");

  let cleaned = sanitizeToPhoneInput(paste);

  setPhoneValue(cleaned);
  validateAndSync();
});

  // ---------------------------
  // Blur → force validation API
  // ---------------------------
  phoneInput?.addEventListener("blur", () => {
    tzLookupNumber();

    // clavier fermé
    document.body.classList.remove("tz-keyboard-open");
  });

  // ---------------------------
  // Focus → clavier ouvert
  // ---------------------------
  phoneInput?.addEventListener("focus", () => {
    document.body.classList.add("tz-keyboard-open");
  });

  // ---------------------------
  // Contact picker
  // ---------------------------
  contactBtn?.addEventListener("click", pickContact);

  // ---------------------------
  // Country selected
  // ---------------------------
  document.addEventListener("tz:country-selected", (event) => {
    const country = event.detail?.country;
    if (!country) return;

    applyCountry(country, { forceReplaceDial: true });

    lastLookupKey = "";
    lastLookupValid = false;

    validateAndSync();
    updateButtonPosition();

    phoneInput?.focus();
  });

  // ---------------------------
  // Submit
  // ---------------------------
  form?.addEventListener("submit", async (e) => {
    validateAndSync();

    if (!phoneE164?.value) {
      e.preventDefault();
      return;
    }

    if (lastLookupValid) {
      return;
    }

    e.preventDefault();

    await tzLookupNumber();

    if (lastLookupValid) {
      form.submit();
    }
  });

}


// ---------------------------
// Keyboard follow (REAL mobile behavior)
// ---------------------------

function bindKeyboardFollow() {
  if (!continueBtn) return;

  let initialHeight = window.innerHeight;

  window.addEventListener("resize", () => {
    const currentHeight = window.innerHeight;

    // clavier ouvert (écran plus petit)
    if (currentHeight < initialHeight - 100) {
      continueBtn.classList.add("is-active");
      document.body.classList.add("tz-keyboard-open");
    } else {
      continueBtn.classList.remove("is-active");
      document.body.classList.remove("tz-keyboard-open");
    }
  });
}
  // ---------------------------
  // Init
  // ---------------------------
  async function init() {
    if (!phoneInput || !countryBtn) {
      return;
    }

    try {
      COUNTRIES = await getCountriesPromise();
      if (!Array.isArray(COUNTRIES)) {
        COUNTRIES = [];
      }
    } catch (e) {
      COUNTRIES = [];
    }

    buildDialIndex();

    const initialIso = getSelectedIso();
    const initialCountry = findCountryByIso(initialIso) || COUNTRIES[0] || null;

    if (initialCountry) {
      applyCountry(initialCountry, {
        setPrefixIfEmpty: !String(phoneInput.value || "").trim()
      });
    } else {
      setCityByIso(initialIso);
    }

    const initialValue = String(phoneInput.value || "").trim();
    if (!initialValue && initialCountry?.dial) {
      setPhoneValue(formatForDisplay(initialCountry.dial));
      syncHiddenE164(initialCountry.dial);
    }

    validateAndSync();
    bindEvents();
    bindKeyboardFollow();
    requestAnimationFrame(() => {
      phoneInput.focus();
      try {
        phoneInput.setSelectionRange(phoneInput.value.length, phoneInput.value.length);
      } catch (e) {
        // no-op
      }
    });
  }
  init();
  // ---------------------------
// Dynamic button position (FINAL FIX)
// ---------------------------

function updateButtonPosition() {
  if (!phoneInput || !continueBtn) return;

  const value = phoneInput.value.trim();

  if (value.length > 3) {
    continueBtn.classList.add("is-active"); // monte
  } else {
    continueBtn.classList.remove("is-active"); // reste en bas
  }
}
})();