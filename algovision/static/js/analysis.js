function initSecondFileToggle() {
  const algoSelect = document.getElementById("algorithm-select");
  const secondFileBlock = document.getElementById("second-file-block");
  if (!algoSelect || !secondFileBlock) return;

  function apply() {
    const selected = algoSelect.options[algoSelect.selectedIndex];
    const needsTwo = selected?.dataset?.requiresTwo === "true";
    secondFileBlock.classList.toggle("hidden", !needsTwo);
  }

  algoSelect.addEventListener("change", apply);
  apply();
}

document.addEventListener("DOMContentLoaded", () => {
  initSecondFileToggle();
});

