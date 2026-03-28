(function () {
  "use strict";

  const STATUS = document.getElementById("cook-save-status");

  function getOrderedIds() {
    return [...document.querySelectorAll("#cook-tbody tr")]
      .map(tr => tr.dataset.recipeId);
  }

  function refreshRowNumbers() {
    const rows = [...document.querySelectorAll("#cook-tbody tr")];
    rows.forEach((tr, idx) => {
      tr.querySelector("td:first-child").textContent = idx + 1;
    });
  }

  async function saveOrder() {
    const ids = getOrderedIds();
    if (!STATUS) return;
    STATUS.textContent = "Saving…";
    try {
      const resp = await fetch("/api/v1/recipes/sort", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": document.cookie.replace(/(?:(?:^|.*;\s*)csrftoken\s*\=\s*([^;]*).*$)|^.*$/, "$1")
        },
        body: JSON.stringify({ recipe_ids: ids }),
      });
      if (resp.ok) {
        STATUS.textContent = "Saved.";
        setTimeout(() => STATUS && (STATUS.textContent = ""), 2000);
      } else {
        STATUS.textContent = "Save failed - refresh the page.";
      }
    } catch (_) {
      STATUS.textContent = "Network error.";
    }
  }

  function moveRow(recipeId, direction) {
    const tbody = document.getElementById("cook-tbody");
    const row = document.getElementById("cook-row-" + recipeId);
    if (!row || !tbody) return;
    if (direction === -1 && row.previousElementSibling) {
      tbody.insertBefore(row, row.previousElementSibling);
    } else if (direction === 1 && row.nextElementSibling) {
      tbody.insertBefore(row.nextElementSibling, row);
    }
    refreshRowNumbers();
    saveOrder();
  }

  // Event delegation for move buttons
  const table = document.getElementById("cook-table");
  if (table) {
    table.addEventListener("click", function (e) {
      const btn = e.target.closest("[data-direction]");
      if (!btn) return;
      const row = btn.closest("tr");
      if (!row) return;
      const recipeId = row.dataset.recipeId;
      const direction = parseInt(btn.dataset.direction, 10);
      moveRow(recipeId, direction);
    });
  }
})();
