const STORAGE_KEY = "ry_robot_tool_hub.recentTool";

document.querySelectorAll(".tool-card").forEach((card) => {
  if (card.dataset.tool === window.localStorage.getItem(STORAGE_KEY)) {
    card.dataset.recent = "true";
  }
});

document.querySelectorAll(".tool-link").forEach((link) => {
  link.addEventListener("click", () => {
    const card = link.closest(".tool-card");
    if (card?.dataset.tool) {
      window.localStorage.setItem(STORAGE_KEY, card.dataset.tool);
    }
  });
});
