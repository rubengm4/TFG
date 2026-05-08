function resultsHasPendingTasks(table) {
  const rows = table.querySelectorAll("tbody tr");
  for (const row of rows) {
    const statusText = row.children[2]?.textContent?.trim()?.toUpperCase();
    if (statusText === "PENDIENTE" || statusText === "PENDING") return true;
  }
  return false;
}

document.addEventListener("DOMContentLoaded", () => {
  const table = document.querySelector("table[data-results-table='true']");
  if (!table) return;

  const intervalMs = Number.parseInt(table.dataset.pollIntervalMs || "15000", 10);
  if (intervalMs > 0) {
    window.setInterval(() => {
      if (resultsHasPendingTasks(table)) window.location.reload();
    }, intervalMs);
  }
});

