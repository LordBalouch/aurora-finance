// Small page behaviours. Everything works without JS; this only adds polish.
(function () {
  "use strict";

  // Drop zone: highlight while dragging, show the chosen file name.
  function initDropzones(root) {
    root.querySelectorAll("[data-dropzone]").forEach((zone) => {
      const input = zone.querySelector("input[type=file]");
      const label = zone.querySelector("[data-filename]");
      if (!input || zone.dataset.ready) return;
      zone.dataset.ready = "1";
      const show = () => { if (input.files.length && label) label.textContent = input.files[0].name; };
      input.addEventListener("change", show);
      ["dragenter", "dragover"].forEach((t) => zone.addEventListener(t, () => zone.classList.add("is-over")));
      ["dragleave", "drop"].forEach((t) => zone.addEventListener(t, () => zone.classList.remove("is-over")));
    });
  }

  // New-account fields only when "New account…" is chosen.
  function initAccountChoice(root) {
    root.querySelectorAll("[data-account-select]").forEach((select) => {
      const extra = document.getElementById(select.dataset.accountSelect);
      if (!extra) return;
      const sync = () => { extra.hidden = select.value !== ""; };
      select.addEventListener("change", sync);
      sync();
    });
  }

  // Ask page: an example question fills the field and asks it.
  document.addEventListener("click", (e) => {
    const chip = e.target.closest("[data-question]");
    if (!chip) return;
    const form = document.querySelector(".ask-form");
    if (!form) return;
    form.querySelector("[name=question]").value = chip.dataset.question;
    form.requestSubmit();
  });

  // Forms that need a confirmation click.
  document.addEventListener("submit", (e) => {
    const msg = e.target.dataset && e.target.dataset.confirm;
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  // "/" focuses the search field.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.target.closest("input, textarea, select")) return;
    const search = document.querySelector("[data-search]");
    if (search) { e.preventDefault(); search.focus(); }
  });

  document.addEventListener("DOMContentLoaded", () => { initDropzones(document); initAccountChoice(document); });
})();

// Table rows with data-href open their drill-down link (the first cell also holds a real link).
document.addEventListener("click", (e) => {
  const row = e.target.closest("tr[data-href]");
  if (row && !e.target.closest("a, button, input, select")) window.location.href = row.dataset.href;
});
