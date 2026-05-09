// ---------------------------
// Admin JS — Yeslek Pro
// ---------------------------

(function () {
  "use strict";

  const root = document.documentElement;
  const sidebarToggle = document.querySelector("[data-admin-sidebar-toggle]");
  const themeToggle = document.querySelector("[data-admin-theme-toggle]");

  function getTheme() {
    return localStorage.getItem("yeslek_admin_theme") || "light";
  }

  function setTheme(theme) {
    root.setAttribute("data-theme", theme);
    localStorage.setItem("yeslek_admin_theme", theme);
  }

  setTheme(getTheme());

  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      const next = getTheme() === "dark" ? "light" : "dark";
      setTheme(next);
    });
  }

  if (sidebarToggle) {
    sidebarToggle.addEventListener("click", function () {
      document.body.classList.toggle("is-admin-sidebar-collapsed");
    });
  }

  document.querySelectorAll("[data-admin-filter-reset]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const form = btn.closest("form");
      if (!form) return;

      form.querySelectorAll("input, select").forEach(function (field) {
        field.value = "";
      });

      form.submit();
    });
  });

  document.querySelectorAll("[data-admin-auto-submit]").forEach(function (field) {
    field.addEventListener("change", function () {
      const form = field.closest("form");
      if (form) form.submit();
    });
  });
})();