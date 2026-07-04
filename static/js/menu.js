// ---------------------------
// Side menu — Full screen swipe
// ---------------------------
(function () {

  const toggle = document.getElementById("menuToggle");
  const menu = document.getElementById("sideMenu");
  const overlay = document.getElementById("menuOverlay");

  if (!toggle || !menu || !overlay) return;

  // ---------------------------
  // Disable swipe only on Select Amount page
  // ---------------------------
  const disableSwipeMenu =
    window.location.pathname.includes("/recharge/select-amount") ||
    window.location.pathname.includes("/recharge/select_amount") ||
    window.location.pathname.includes("/select-amount") ||
    window.location.pathname.includes("/select_amount");

  let isOpen = false;

  // =========================
  // OPEN / CLOSE
  // =========================
  function openMenu() {
    menu.classList.add("open");
    overlay.classList.add("show");
    menu.style.transform = "";
    overlay.style.opacity = "";
    document.body.style.overflow = "hidden";
    isOpen = true;
  }

  function closeMenu() {
    menu.classList.remove("open");
    overlay.classList.remove("show");
    menu.style.transform = "";
    overlay.style.opacity = "";
    document.body.style.overflow = "";
    isOpen = false;
  }

  toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    isOpen ? closeMenu() : openMenu();
  });

  overlay.addEventListener("click", closeMenu);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen) closeMenu();
  });

  // =========================
  // FULL SCREEN SWIPE
  // =========================

  let startX = 0;
  let currentX = 0;
  let dragging = false;

  const menuWidth = () => menu.offsetWidth;
  const THRESHOLD_RATIO = 0.25; // 25% largeur pour valider

  document.addEventListener("touchstart", (e) => {
    if (disableSwipeMenu) return;
    startX = e.touches[0].clientX;
    currentX = startX;
    dragging = true;

    menu.style.transition = "none";
    overlay.style.transition = "none";
  });

  document.addEventListener("touchmove", (e) => {
    if (!dragging) return;

    currentX = e.touches[0].clientX;
    let delta = currentX - startX;

    // ================= OPEN =================
    if (!isOpen && delta < 0) { // swipe vers gauche
      const progress = Math.min(Math.abs(delta) / menuWidth(), 1);
      menu.style.transform = `translateX(${100 - progress * 100}%)`;
      overlay.style.opacity = progress * 0.4;
      overlay.classList.add("show");
    }

    // ================= CLOSE =================
    if (isOpen && delta > 0) { // swipe vers droite
      const progress = Math.min(delta / menuWidth(), 1);
      menu.style.transform = `translateX(${progress * 100}%)`;
      overlay.style.opacity = (1 - progress) * 0.4;
    }
  });

  document.addEventListener("touchend", () => {
    if (!dragging) return;

    menu.style.transition = "transform 0.3s ease";
    overlay.style.transition = "opacity 0.3s ease";

    const delta = currentX - startX;
    const threshold = menuWidth() * THRESHOLD_RATIO;

    if (!isOpen && delta < -threshold) {
      openMenu();
    } else if (isOpen && delta > threshold) {
      closeMenu();
    } else {
      isOpen ? openMenu() : closeMenu();
    }

    dragging = false;
  });

})();