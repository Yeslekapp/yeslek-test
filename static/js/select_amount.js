// ---------------------------
// Feature: Forfait behavior (FINAL PRODUCTION)
// ---------------------------

(function () {

  const form = document.getElementById("selectAmountForm");
  if (!form) return;

  const continueBtn = document.getElementById("continueBtn");
  const amountCard = document.getElementById("amountCard");
  const amountDisplay = document.getElementById("amountDisplay");
  const amountInput = document.getElementById("amountInput");

  const rowAmount = document.getElementById("rowAmount");
  const rowTax = document.getElementById("rowTax");
  const rowReceived = document.getElementById("rowReceived");
  const creditEarnedText = document.getElementById("creditEarnedText"); 

  const moneyBtn = document.getElementById("moneyAccordionBtn");
  const moneyPanel = document.getElementById("moneyPanel");
  const chevron = document.getElementById("moneyChevron");

  const fixedWrap = document.getElementById("fixedAmountWrap");
  const range = document.getElementById("amountRange");

  const forfaitCard = document.getElementById("forfaitCard");
  const forfaitTitle = document.getElementById("forfaitTitle");
  const removeForfaitBtn = document.getElementById("removeForfaitBtn");
  const forfaitGb = document.getElementById("forfaitGb");
  const forfaitPrice = document.getElementById("forfaitPrice");

  const taxRate = parseFloat(amountCard?.dataset?.taxRate || "0.10");
  const creditRate = parseFloat(
  amountCard?.dataset?.creditRate ||
  amountCard?.dataset?.pointsRate ||
  "0.025"
);

  const userCurrency = "€";

  let minAmount = 1.99;
  let maxAmount = 34.99;

  let debounceT = null;

  function fmt2(v) {
    return (Math.round(Number(v || 0) * 100) / 100).toFixed(2);
  }

  function clampAmount(v) {
    const n = Number(v || 0);
    return Math.min(Math.max(n, minAmount), maxAmount);
  }

  function setSelectedButton(v) {
    if (!fixedWrap) return;

    fixedWrap.querySelectorAll(".tz-amt-btn").forEach((b) => {
      b.classList.toggle("is-selected", parseFloat(b.dataset.amount) === v);
    });
  }

  function setMoneyOpen(open) {
    if (!moneyBtn || !moneyPanel) return;

    moneyPanel.style.display = open ? "block" : "none";

    if (chevron) chevron.textContent = open ? "▴" : "▾";

    moneyBtn.setAttribute("aria-expanded", String(open));
  }

  function scrollToDetails() {
    window.setTimeout(() => {
      moneyPanel?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    }, 200);
  }

function setAmountLocked(locked) {

  if (fixedWrap) {
    fixedWrap.style.display = locked ? "none" : "flex";
  }

  if (range) {
    range.style.display = locked ? "none" : "block";
  }
}
  // ---------------------------
  // UI update
  // ---------------------------

  function updateUI(amount) {

    const a = clampAmount(amount);

    if (amountInput) amountInput.value = fmt2(a);

    if (amountDisplay)
      amountDisplay.textContent = `${fmt2(a)} ${userCurrency}`;

    if (rowAmount)
      rowAmount.textContent = `${fmt2(a)} ${userCurrency}`;

    if (rowTax)
      rowTax.textContent = `${fmt2(a * taxRate)} ${userCurrency}`;

// ---------------------------
// Credit earned
// ---------------------------
if (creditEarnedText) {

  const credit = fmt2(a * creditRate);

  const template = creditEarnedText.dataset.template;

  if (template && template.includes("{amount}")) {
    creditEarnedText.textContent =
      template.replace("{amount}", credit);
  } else {
    creditEarnedText.textContent =
      `Vous gagnez ${credit} € de crédit`;
  }
}

    const total = a + (a * taxRate);

    if (continueBtn) {

      const payText = continueBtn?.dataset?.payText || "";
      const formatted = `${fmt2(total)} ${userCurrency}`;

      continueBtn.textContent = payText.includes("{amount}")
        ? payText.replace("{amount}", formatted)
        : `${payText} ${formatted}`.trim();

      // ✅ validation bouton (FIX)
      const isValid = a >= minAmount && a <= maxAmount;
      continueBtn.disabled = !isValid;
      continueBtn.style.opacity = isValid ? "1" : "0.5";
    }
  }

  // ---------------------------
  // API
  // ---------------------------

  async function fetchQuote(amount) {

    // ✅ protection API (FIX)
    if (!amount || amount < minAmount || amount > maxAmount) {
      return;
    }

    const gb = forfaitGb?.value;

    if (gb && rowReceived) {
      rowReceived.textContent = gb;
      return;
    }

    if (rowReceived) {
      rowReceived.style.opacity = "0.6";
    }

    try {

      const res = await fetch("/recharge/api/quote", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          amount: amount
        })
      });

      let data = null;

      try {
        data = await res.json();
      } catch (_) {
        data = null;
      }

      // ✅ update min/max dynamique
      if (data?.min) minAmount = Number(data.min);
      if (data?.max) maxAmount = Number(data.max);

      if (range) {
        range.min = minAmount;
        range.max = maxAmount;
      }

      if (!res.ok || !data || !data.ok) {

        if (rowReceived) {
          rowReceived.textContent = "—";
          rowReceived.style.opacity = "0.5";
        }

        return;
      }

      if (rowReceived) {

        const received = data.received;

        rowReceived.textContent =
          (received && received !== "—") ? received : "—";

        rowReceived.style.transition = "all .25s ease";
        rowReceived.style.transform = "scale(1.05)";
        rowReceived.style.opacity = "1";

        setTimeout(() => {
          rowReceived.style.transform = "scale(1)";
        }, 140);
      }

    } catch (e) {

      console.error("quote error", e);

      if (rowReceived) {
        rowReceived.textContent = "—";
        rowReceived.style.opacity = "0.5";
      }
    }
  }

  // ---------------------------
  // Debounce
  // ---------------------------

  function scheduleQuote(amount) {

    if (debounceT)
      window.clearTimeout(debounceT);

    debounceT =
      window.setTimeout(() => fetchQuote(amount), 250);
  }

  // ---------------------------
  // Forfait logic
  // ---------------------------

  function applyForfaitStateFromInputs() {

    const gb = (forfaitGb?.value || "").trim();
    const priceStr = (forfaitPrice?.value || "").trim();

    const hasForfait = !!gb && !!priceStr && !Number.isNaN(Number(priceStr));

    if (hasForfait) {

      const p = Number(priceStr);

      updateUI(p);
      setSelectedButton(p);
      setMoneyOpen(true);
      setAmountLocked(true);
      scheduleQuote(p);
      scrollToDetails();

    } else {

      setAmountLocked(false);
    }
  }

  // ---------------------------
  // Events
  // ---------------------------

  moneyBtn?.addEventListener("click", () => {
    const isOpen = moneyPanel.style.display !== "none";
    setMoneyOpen(!isOpen);
  });

  fixedWrap?.addEventListener("click", (e) => {

    const btn = e.target.closest(".tz-amt-btn");
    if (!btn) return;

    const v = parseFloat(btn.dataset.amount);

    setSelectedButton(v);
    updateUI(v);
    setMoneyOpen(true);
    scheduleQuote(v);
    scrollToDetails();
  });

  range?.addEventListener("input", () => {
    updateUI(parseFloat(range.value));
  });

  range?.addEventListener("change", () => {

    const v = parseFloat(range.value);

    setMoneyOpen(true);
    scheduleQuote(v);
    scrollToDetails();
  });

removeForfaitBtn?.addEventListener("click", async (e) => {

  e.preventDefault();
  e.stopPropagation();

  try {
    await fetch("/recharge/clear-forfait", { method: "POST" });
  } catch (_) {}

  window.location.href = "/recharge/select-forfait";
});

  forfaitCard?.addEventListener("click", (e) => {

    if (e.target.closest("#removeForfaitBtn")) return;

    const url = forfaitCard.dataset.forfaitUrl;

    if (url) {
      window.location.href = url;
    }
  });

  // ---------------------------
  // Init
  // ---------------------------

  if (rowReceived) {
    rowReceived.style.opacity = "0.8";
  }

  const initialAmount =
    parseFloat(amountInput?.value || "0");

  updateUI(initialAmount);
  setMoneyOpen(true);
  scheduleQuote(initialAmount);
  scrollToDetails();
  applyForfaitStateFromInputs();
// ---------------------------
// Auth check
// ---------------------------
form.addEventListener("submit", function (e) {

  const isLogged = document.querySelector(".tz-page")?.dataset.user === "true";

  if (!isLogged) {
    e.preventDefault();
    window.location.href = "/auth/login";
  }

});

})();