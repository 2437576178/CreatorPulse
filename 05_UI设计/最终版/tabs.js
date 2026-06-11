document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".dashboard-content").forEach((page) => {
    const tabs = Array.from(page.querySelectorAll("[data-tab-target]"));
    const panels = Array.from(page.querySelectorAll("[data-tab-panel]"));

    if (!tabs.length || !panels.length) return;

    const activateTab = (target) => {
      tabs.forEach((item) => {
        const active = item.dataset.tabTarget === target;
        item.classList.toggle("active", active);
        item.setAttribute("aria-selected", active ? "true" : "false");
      });

      panels.forEach((panel) => {
        panel.classList.toggle("active", panel.dataset.tabPanel === target);
      });
    };

    const urlParams = new URLSearchParams(window.location.search);
    const initialTarget = urlParams.get("tab") || window.location.hash.replace("#", "");
    if (initialTarget && panels.some((panel) => panel.dataset.tabPanel === initialTarget)) {
      activateTab(initialTarget);
    }

    tabs.forEach((tab) => {
      tab.addEventListener("click", (event) => {
        event.preventDefault();
        const target = tab.dataset.tabTarget;

        activateTab(target);
        history.replaceState(null, "", `#${target}`);
      });
    });
  });
});
