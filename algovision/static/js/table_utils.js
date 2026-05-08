function parseDmyHmToDate(value) {
  const trimmed = (value || "").trim();
  const [datePart, timePart] = trimmed.split(" ");
  if (!datePart || !timePart) return null;
  const [day, month, year] = datePart.split("/");
  if (!day || !month || !year) return null;
  return new Date(`${year}-${month}-${day}T${timePart}`);
}

function getComparable(text, type) {
  const t = (text || "").trim();
  switch (type) {
    case "date-dmy-hm": {
      const d = parseDmyHmToDate(t);
      return d ? d.getTime() : 0;
    }
    case "date-iso": {
      const d = new Date(t);
      return Number.isNaN(d.getTime()) ? 0 : d.getTime();
    }
    case "number": {
      const n = Number(t.replace(",", "."));
      return Number.isNaN(n) ? 0 : n;
    }
    case "text":
    default:
      return t.toLowerCase();
  }
}

function updateSortArrows(table, column, ascending) {
  table.querySelectorAll(".sort-arrow").forEach((arrow) => {
    const index = Number.parseInt(arrow.dataset.index || "", 10);
    arrow.textContent = index === column ? (ascending ? "↑" : "↓") : "";
  });
}

function sortTable(table, column, ascending) {
  const tbody = table.querySelector("tbody");
  if (!tbody) return;

  const type =
    table.querySelector(`th[data-sort-col="${column}"]`)?.dataset.sortType ||
    "text";

  const allRows = Array.from(tbody.querySelectorAll("tr"));
  const rows = allRows.filter((r) => !r.querySelector("td[colspan]"));
  const placeholders = allRows.filter((r) => r.querySelector("td[colspan]"));

  rows.sort((a, b) => {
    const aText = a.children[column]?.textContent || "";
    const bText = b.children[column]?.textContent || "";
    const aVal = getComparable(aText, type);
    const bVal = getComparable(bText, type);

    if (typeof aVal === "number" && typeof bVal === "number") {
      return ascending ? aVal - bVal : bVal - aVal;
    }

    const cmp = String(aVal).localeCompare(String(bVal), undefined, {
      numeric: true,
      sensitivity: "base",
    });
    return ascending ? cmp : -cmp;
  });

  rows.forEach((row) => tbody.appendChild(row));
  placeholders.forEach((row) => tbody.appendChild(row));
  updateSortArrows(table, column, ascending);

  table.dataset.sortColumn = String(column);
  table.dataset.sortAscending = ascending ? "true" : "false";
}

function initSortableTables() {
  document.querySelectorAll("table[data-sortable='true']").forEach((table) => {
    table.querySelectorAll("th[data-sort-col]").forEach((th) => {
      th.addEventListener("click", () => {
        const col = Number.parseInt(th.dataset.sortCol || "", 10);
        if (Number.isNaN(col)) return;

        const currentCol = Number.parseInt(table.dataset.sortColumn || "", 10);
        const currentAsc = table.dataset.sortAscending !== "false";
        const sameCol = currentCol === col;
        const nextAsc = sameCol ? !currentAsc : true;
        sortTable(table, col, nextAsc);
      });
    });

    const initialCol = Number.parseInt(table.dataset.sortInitialCol || "", 10);
    if (!Number.isNaN(initialCol)) {
      const dir = (table.dataset.sortInitialDir || "asc").toLowerCase();
      sortTable(table, initialCol, dir !== "desc");
    }
  });
}

function initConfirmForms() {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      const msg = form.dataset.confirm || "¿Estás seguro?";
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initSortableTables();
  initConfirmForms();
});

