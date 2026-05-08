function initSidebarToggle() {
  const toggleBtn = document.getElementById("sidebarToggle");
  const sidebar = document.getElementById("sidebar");
  const mainContent = document.getElementById("mainContent");

  if (!toggleBtn || !sidebar || !mainContent) return;

  const sidebarWidth = 16; // Tailwind rem units for 64 width (16rem)
  const extraGap = 1; // 1rem gap for separation
  const collapsedLeft = 1; // left position when collapsed (rem)

  const isCollapsed = localStorage.getItem("sidebarCollapsed") === "true";

  function applySidebarState(collapsed) {
    if (collapsed) {
      sidebar.classList.add("-translate-x-full");
      mainContent.classList.remove("ml-64");
      mainContent.classList.add("ml-0");
      toggleBtn.style.left = `${collapsedLeft}rem`;
    } else {
      sidebar.classList.remove("-translate-x-full");
      mainContent.classList.add("ml-64");
      mainContent.classList.remove("ml-0");
      toggleBtn.style.left = `${sidebarWidth + extraGap}rem`;
    }
  }

  applySidebarState(isCollapsed);

  toggleBtn.addEventListener("click", () => {
    const collapsed = sidebar.classList.toggle("-translate-x-full");
    localStorage.setItem("sidebarCollapsed", String(collapsed));
    applySidebarState(collapsed);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initSidebarToggle();
});

