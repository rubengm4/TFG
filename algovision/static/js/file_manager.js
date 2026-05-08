function showAlert(text, type = "error") {
  const container = document.getElementById("alerts-container");
  if (!container) return;
  const id = `alert-${Date.now()}`;
  const alert = document.createElement("div");
  alert.id = id;
  alert.className =
    type === "success"
      ? "bg-green-600 text-white px-4 py-2 rounded shadow-lg mb-2"
      : "bg-red-600 text-white px-4 py-2 rounded shadow-lg mb-2";
  alert.textContent = text;
  container.appendChild(alert);
  setTimeout(() => {
    document.getElementById(id)?.remove();
  }, 5000);
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    document.cookie.split(";").forEach((c) => {
      let cookie = c.trim();
      if (cookie.startsWith(`${name}=`)) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
      }
    });
  }
  return cookieValue;
}

function getAllActionButtons() {
  const rows = Array.from(document.querySelectorAll("table tbody tr"));
  const buttons = [];
  rows.forEach((row) => {
    const tds = row.querySelectorAll("td");
    const lastTd = tds[tds.length - 1];
    if (!lastTd) return;
    lastTd
      .querySelectorAll('button, input[type="submit"], input[type="button"], a')
      .forEach((btn) => buttons.push(btn));
  });
  return buttons;
}

function hideAllActionButtons() {
  getAllActionButtons().forEach((btn) => {
    if (btn.dataset._origDisplay === undefined)
      btn.dataset._origDisplay = btn.style.display || "";
    btn.style.display = "none";
  });
}

function restoreAllActionButtons() {
  getAllActionButtons().forEach((btn) => {
    btn.style.display = btn.dataset._origDisplay || "";
    delete btn.dataset._origDisplay;
  });
}

function cancelEdit(td) {
  if (!td) return;
  if (td.dataset._origHtml !== undefined) {
    td.innerHTML = td.dataset._origHtml;
    delete td.dataset._origHtml;
  }
  const row = td.closest("tr");
  if (row) {
    const tds = row.querySelectorAll("td");
    const actionsCell = tds[tds.length - 1];
    if (actionsCell)
      actionsCell
        .querySelectorAll(".confirm-edit-btn, .cancel-edit-btn")
        .forEach((btn) => btn.remove());
  }
  restoreAllActionButtons();
}

async function saveNewName(fileId, baseName, extension, td) {
  if (!td || !baseName) {
    showAlert("El nombre no puede estar vacío.");
    return;
  }
  const newName = baseName + extension;

  try {
    const res = await fetch(`/files/rename/${fileId}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ new_name: newName }),
    });
    if (!res.ok) {
      let msg = "Error al renombrar el archivo.";
      try {
        const data = await res.json();
        msg = data.error || msg;
      } catch {
        // ignore
      }
      throw new Error(msg);
    }
    showAlert("Nombre actualizado correctamente.", "success");
    window.location.reload();
  } catch (err) {
    showAlert(err?.message || "Error desconocido.");
    cancelEdit(td);
  }
}

function makeEditable(td, fileId) {
  if (!td) return;

  document.querySelectorAll("table tbody tr").forEach((row) => {
    if (row !== td.closest("tr")) {
      const tds = row.querySelectorAll("td");
      const actionsCell = tds[tds.length - 1];
      if (actionsCell) {
        actionsCell
          .querySelectorAll(".confirm-edit-btn, .cancel-edit-btn")
          .forEach((btn) => btn.remove());
        actionsCell.querySelectorAll("button, a").forEach((btn) => {
          btn.style.display = "";
        });
      }
    }
  });

  td.dataset._origHtml = td.innerHTML;

  const fullName = td.textContent.trim();
  const lastDotIndex = fullName.lastIndexOf(".");
  const baseName =
    lastDotIndex > 0 ? fullName.substring(0, lastDotIndex) : fullName;
  const extension = lastDotIndex > 0 ? fullName.substring(lastDotIndex) : "";

  const input = document.createElement("input");
  input.type = "text";
  input.value = baseName;
  input.className =
    "border rounded px-2 py-1 text-sm w-full focus:ring-2 focus:ring-lime-500 outline-none";

  const extSpan = document.createElement("span");
  extSpan.textContent = extension;
  extSpan.className = "ml-2 text-gray-700 font-semibold select-none";

  const wrapper = document.createElement("div");
  wrapper.className = "flex items-center gap-1";
  wrapper.appendChild(input);
  wrapper.appendChild(extSpan);

  td.innerHTML = "";
  td.appendChild(wrapper);
  input.focus();
  input.select();

  hideAllActionButtons();
  const row = td.closest("tr");
  const rowTds = row?.querySelectorAll("td") || [];
  const actionsCell = rowTds[rowTds.length - 1];
  if (!actionsCell) return;

  const confirmBtn = document.createElement("button");
  confirmBtn.type = "button";
  confirmBtn.className =
    "confirm-edit-btn text-lime-600 hover:text-lime-800 font-semibold px-2 py-1 rounded text-sm flex items-center gap-1 transition";
  confirmBtn.innerHTML = '<i class="fas fa-check"></i> Confirmar';

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className =
    "cancel-edit-btn text-lime-600 hover:text-lime-800 font-semibold px-2 py-1 rounded text-sm flex items-center gap-1 transition";
  cancelBtn.innerHTML = '<i class="fas fa-times"></i> Cancelar';

  actionsCell.appendChild(confirmBtn);
  actionsCell.appendChild(cancelBtn);

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      confirmBtn.click();
    }
    if (e.key === "Escape") {
      e.preventDefault();
      cancelEdit(td);
    }
  });

  confirmBtn.addEventListener("click", () =>
    saveNewName(fileId, input.value.trim(), extension, td),
  );
  cancelBtn.addEventListener("click", () => cancelEdit(td));
}

function initFileInputLabel() {
  const fileInput = document.getElementById("fileInput");
  const fileInputLabel = document
    .getElementById("fileInputLabel")
    ?.querySelector("span");
  if (!fileInput) return;
  fileInput.addEventListener("change", () => {
    const files = Array.from(fileInput.files || [])
      .map((f) => f.name)
      .join(", ");
    if (fileInputLabel)
      fileInputLabel.textContent =
        files || "Selecciona archivo/s (Límite: 10 MB por archivo)";
  });
}

function initRenameButtons() {
  document.querySelectorAll("[data-action='rename-file']").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      const fileId = Number.parseInt(el.dataset.fileId || "", 10);
      if (Number.isNaN(fileId)) return;

      const row = el.closest("tr");
      const nameCell = row?.querySelector("td.file-name-cell");
      if (!nameCell) return;
      makeEditable(nameCell, fileId);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initFileInputLabel();
  initRenameButtons();
});

