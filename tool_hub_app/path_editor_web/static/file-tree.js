export function renderFileTree(container, browserState, handlers) {
  container.innerHTML = "";

  const toolbar = document.createElement("div");
  toolbar.className = "sidebar-toolbar";

  const upButton = document.createElement("button");
  upButton.type = "button";
  upButton.className = "mini-button";
  upButton.textContent = "上级";
  upButton.disabled = !browserState.parent || browserState.cwd === browserState.parent;
  upButton.addEventListener("click", () => handlers.onBrowse(browserState.parent));
  toolbar.appendChild(upButton);

  const refreshButton = document.createElement("button");
  refreshButton.type = "button";
  refreshButton.className = "mini-button";
  refreshButton.textContent = "刷新";
  refreshButton.addEventListener("click", () => handlers.onBrowse(browserState.cwd));
  toolbar.appendChild(refreshButton);

  container.appendChild(toolbar);

  const cwd = document.createElement("div");
  cwd.className = "cwd-label";
  cwd.textContent = browserState.cwd || "";
  container.appendChild(cwd);

  const list = document.createElement("div");
  list.className = "tree-list";
  const fileFlag = browserState.fileFlag ?? "is_json";

  for (const entry of browserState.entries || []) {
    if (!entry.is_dir && !entry[fileFlag]) {
      continue;
    }

    const button = document.createElement("button");
    button.type = "button";
    const isSelected = !entry.is_dir && entry.path === browserState.selectedPath;
    button.className = `tree-entry ${entry.is_dir ? "dir" : "file"}${isSelected ? " selected" : ""}`;
    button.textContent = entry.is_dir ? `📁 ${entry.name}` : `📄 ${entry.name}`;
    button.addEventListener("click", () => {
      if (entry.is_dir) {
        handlers.onBrowse(entry.path);
      } else {
        handlers.onOpen(entry.path);
      }
    });
    list.appendChild(button);
  }

  container.appendChild(list);
}
