// ---------------------------
// Feature: Select forfait (FINAL PRODUCTION CLEAN)
// ---------------------------

(async function () {

  const form = document.getElementById("selectForfaitForm");
  const optionsWrap = document.getElementById("forfaitOptionsWrap");

  if (!form || !optionsWrap) {
    initCloseButton();
    return;
  }

  // ---------------------------
  // Elements
  // ---------------------------

  const selectedDisplay = document.getElementById("selectedForfaitDisplay");
  const selectedPlanId = document.getElementById("selectedPlanId");
  const selectedPlanGb = document.getElementById("selectedPlanGb");
  const selectedPlanPrice = document.getElementById("selectedPlanPrice");

  const continueBtn = document.getElementById("continueForfaitBtn");

  const rowReceived = document.getElementById("rowForfaitReceived");
  const rowAmount = document.getElementById("rowForfaitAmount");
  const rowTax = document.getElementById("rowForfaitTax");

  const accordionBtn = document.getElementById("forfaitAccordionBtn");
  const panel = document.getElementById("forfaitPanel");
  const chevron = document.getElementById("forfaitChevron");

  const userCurrency = "€";

  let selectedButton = null;
  let hasUserSelected = false;
  let isSubmitting = false;
  let scrollTimeout = null;
  let isAutoSelecting = false;
  let forfaitsLoaded = false;
  let forfaitsReady = false;
  // ---------------------------
  // Helpers
  // ---------------------------

  function fmt2(value) {
    return (Math.round(Number(value || 0) * 100) / 100).toFixed(2);
  }

  function setMoneyOpen(open) {
    if (!panel || !accordionBtn) return;

    panel.style.display = open ? "block" : "none";
    accordionBtn.setAttribute("aria-expanded", String(open));

    if (chevron) {
      chevron.textContent = open ? "▴" : "▾";
    }
  }

  function scrollToDetails() {
    setTimeout(() => {
      panel?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    }, 120);
  }

  function setContinueState(enabled, totalPrice) {
    if (!continueBtn) return;

    continueBtn.disabled = !enabled;
    continueBtn.setAttribute("aria-disabled", String(!enabled));
    continueBtn.style.opacity = enabled ? "1" : "0.5";

    if (enabled) {
      const template = continueBtn.dataset.payText || "Payer {amount}";
      continueBtn.textContent =
        template.replace("{amount}", `${fmt2(totalPrice)} ${userCurrency}`);
    } else {
      continueBtn.textContent = continueBtn.dataset.payText || "Continuer";
    }
  }

  function setLoading(loading) {
    isSubmitting = loading;

    document.querySelectorAll(".tz-forfait-option").forEach(btn => {
      btn.disabled = loading;
      btn.style.opacity = loading && btn !== selectedButton ? "0.5" : "1";
    });

    if (continueBtn) {
      continueBtn.disabled = loading;
      continueBtn.classList.toggle("is-loading", loading);
    }
  }

  function animateSelectedDisplay(value) {
    if (!selectedDisplay) return;

    selectedDisplay.textContent = value || "—";
    selectedDisplay.style.transform = "scale(1.08)";
    selectedDisplay.style.opacity = "0.7";

    setTimeout(() => {
      selectedDisplay.style.transform = "scale(1)";
      selectedDisplay.style.opacity = "1";
    }, 140);
  }

  function centerSelectedButton(btn) {
    requestAnimationFrame(() => {
      btn.scrollIntoView({
        behavior: "smooth",
        inline: "center",
        block: "nearest"
      });
    });
  }

  // ---------------------------
  // Fees API (SYNC BACKEND)
  // ---------------------------

  async function updateFees(price) {

    try {

      const res = await fetch("/recharge/api/fees", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ amount: price })
      });

      const data = await res.json();
      if (!data.ok) return;

      const amount = Number(data.amount || price);
      const tax = Number(data.tax || 0);
      const total = Number(data.total || price);

      if (rowAmount)
        rowAmount.textContent = `${fmt2(amount)} ${userCurrency}`;

      if (rowTax)
        rowTax.textContent = `${fmt2(tax)} ${userCurrency}`;

      setContinueState(true, total);

    } catch (e) {
      console.error("fees error", e);
    }
  }

  // ---------------------------
  // Selection
  // ---------------------------

  function applySelection(btn, options = {}) {

    if (!btn || isSubmitting) return;
    hasUserSelected = true;
    const planId = btn.dataset.id || "";
    const gb = btn.dataset.gb || "";
    const price = Number(btn.dataset.price || 0);

    if (!planId || price <= 0) return;

    selectedButton = btn;

    document.querySelectorAll(".tz-forfait-option").forEach(el =>
      el.classList.remove("is-selected")
    );

    btn.classList.add("is-selected");

    if (!options.skipCenter) {
      centerSelectedButton(btn);
    }

    selectedPlanId.value = planId;
    selectedPlanGb.value = gb;
    selectedPlanPrice.value = fmt2(price);

    animateSelectedDisplay(gb);

    if (rowReceived)
      rowReceived.textContent = gb || "—";

    updateFees(price);

    setMoneyOpen(true);

    if (!options.skipDetailsScroll) {
      scrollToDetails();
    }
  }

// ---------------------------
// Submit
// ---------------------------

async function submitSelection() {

  // 🔒 attendre que les forfaits soient prêts
  if (!forfaitsReady) {
    if (typeof tzToast === "function") {
      tzToast("Chargement...");
    }
    return;
  }

  // 🔒 sécurité UX
  if (isSubmitting) return;

  // 🔥 UX: message si rien sélectionné
  if (!selectedButton) {
    if (typeof tzToast === "function") {
      tzToast("Sélectionnez un forfait");
    }
    return;
  }

  const planId = selectedPlanId.value;
  const price = Number(selectedPlanPrice.value);

  if (!planId || price <= 0) return;

  setLoading(true);

  try {

    const res = await fetch("/recharge/select-forfait", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: planId })
    });

    const data = await res.json();

    if (!data.ok) throw new Error("forfait_save_error");

    // 🔥 UX: mini feedback avant redirect
    continueBtn.textContent = "✔";
    continueBtn.style.opacity = "0.8";

    setTimeout(() => {
      window.location.href = "/payment/method";
    }, 120);

  } catch (e) {
    console.error(e);
    setLoading(false);

    if (typeof tzToast === "function") {
      tzToast("Erreur, réessayez");
    }
  }
}

  // ---------------------------
  // Events
  // ---------------------------

  optionsWrap.addEventListener("click", e => {
    const btn = e.target.closest(".tz-forfait-option");
    if (!btn) return;
    applySelection(btn);
  });

  optionsWrap.addEventListener("scroll", () => {

    if (isSubmitting || isAutoSelecting) return;

    clearTimeout(scrollTimeout);

    scrollTimeout = setTimeout(() => {

      const cards = [...optionsWrap.querySelectorAll(".tz-forfait-slide")];
      let closest = null;
      let min = Infinity;

      const center = optionsWrap.scrollLeft + optionsWrap.offsetWidth / 2;

      cards.forEach(card => {
        const offset = Math.abs(
          (card.offsetLeft + card.offsetWidth / 2) - center
        );

        if (offset < min) {
          min = offset;
          closest = card;
        }
      });

      if (closest && hasUserSelected && closest !== selectedButton) {
        isAutoSelecting = true;

        applySelection(closest, {
          skipCenter: true,
          skipDetailsScroll: true
        });

        setTimeout(() => {
          isAutoSelecting = false;
        }, 80);
      }

    }, 140);

  });

  accordionBtn?.addEventListener("click", () => {
    const open = panel.style.display !== "none";
    setMoneyOpen(!open);
  });

  continueBtn?.addEventListener("click", submitSelection);
// ---------------------------
// Load forfaits LIVE (SYNC ONLY - NO UI BREAK)
// ---------------------------

async function loadForfaits() {

  // 🔒 anti double call
  if (sessionStorage.getItem("forfaits_loaded") === "1") return;
  sessionStorage.setItem("forfaits_loaded", "1");

  try {

    const res = await fetch("/recharge/api/forfaits", {
      method: "POST"
    });

    const data = await res.json();

    if (!data.plans || !data.plans.length) return;
    forfaitsReady = true;

    // 👉 sync silencieux (prod clean)
    console.log("forfaits synced");

  } catch (e) {
    console.error("forfaits sync error", e);
  }
}

// ---------------------------
// Init
// ---------------------------

setMoneyOpen(true);
setContinueState(false, 0);
selectedButton = null;

// 👉 RESET UI (important)
if (rowAmount) rowAmount.textContent = "—";
if (rowTax) rowTax.textContent = "—";
if (rowReceived) rowReceived.textContent = "—";

// 👉 API en background (sans casser UI)
loadForfaits();

initCloseButton();

})();


// ---------------------------
// Close forfait
// ---------------------------

function initCloseButton() {
  const btn = document.getElementById("closeForfaitBtn");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    try {
      await fetch("/recharge/clear-forfait", { method: "POST" });
    } catch (_) {}

    window.location.href = "/recharge/enter-number";
  });
}