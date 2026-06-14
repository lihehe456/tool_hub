function basename(path) {
  if (!path) {
    return "";
  }
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

function uniqueSources(workspace) {
  const byPath = new Map();
  for (const subtask of workspace?.subtasks ?? []) {
    const sourcePath = subtask.source_workspace_path || "";
    if (!sourcePath) {
      continue;
    }
    if (!byPath.has(sourcePath)) {
      byPath.set(sourcePath, {
        path: sourcePath,
        taskGroupName: subtask.source_task_group_name || "",
        count: 0,
      });
    }
    byPath.get(sourcePath).count += 1;
  }
  return [...byPath.values()];
}

function renderHistoryOptions(items) {
  return items.map((item) => `<option value="${item}"></option>`).join("");
}

function renderSourceList(sources, activeSourcePath) {
  if (!sources.length) {
    return "<p class=\"panel-empty\">还没有导入任何旁路来源。</p>";
  }

  return `
    <ul class="task-group-list task-group-list-plain">
      ${sources
        .map(
          (source) => `
            <li class="task-group-list-item" data-selected="${source.path === activeSourcePath}">
              <strong>${source.taskGroupName || basename(source.path)}</strong>
              <span>${basename(source.path)}</span>
              <span>${source.count} 个子任务</span>
              <div class="task-group-actions">
                <button type="button" data-action="activate-source" data-source-path="${source.path}">查看</button>
                <button type="button" data-action="reimport-source" data-source-path="${source.path}">整体替换</button>
              </div>
            </li>
          `,
        )
        .join("")}
    </ul>
  `;
}

function renderAvailableSubtasks(items, selectedIds) {
  if (!items.length) {
    return "<p class=\"panel-empty\">当前来源下没有子任务。</p>";
  }

  return `
    <ul class="task-group-list task-group-list-plain">
      ${items
        .map((item) => {
          const selected = selectedIds.includes(item.id);
          return `
            <li class="task-group-list-item" data-selected="${selected}">
              <label class="task-group-inline-label">
                <span>名称</span>
                <input
                  class="subtask-name-input"
                  data-subtask-id="${item.id}"
                  type="text"
                  value="${item.subtask_name ?? item.generated_subtask_name ?? item.id}"
                >
              </label>
              <span>${item.direction ?? "unknown"}</span>
              <button type="button" data-action="${selected ? "remove" : "add"}" data-subtask-id="${item.id}">
                ${selected ? "移出任务组" : "加入任务组"}
              </button>
            </li>
          `;
        })
        .join("")}
    </ul>
  `;
}

function renderSelectedSubtasks(items) {
  if (!items.length) {
    return "<p class=\"panel-empty\">当前没有混编结果。</p>";
  }

  return `
    <ol class="task-group-list">
      ${items
        .map(
          (item) => `
            <li class="task-group-list-item" data-selected="true">
              <strong>${item.subtask_name ?? item.generated_subtask_name ?? item.id}</strong>
              <span>${item.direction ?? "unknown"}</span>
              <span>${item.source_task_group_name ?? ""}</span>
              <div class="task-group-actions">
                <button type="button" data-action="move-up" data-subtask-id="${item.id}">上移</button>
                <button type="button" data-action="move-down" data-subtask-id="${item.id}">下移</button>
                <button type="button" data-action="remove" data-subtask-id="${item.id}">移除</button>
              </div>
            </li>
          `,
        )
        .join("")}
    </ol>
  `;
}

export function renderTaskGroupMixerView(elements, state) {
  elements.workspacePath.value = state.workspacePath ?? "";
  elements.sourcePath.value = state.sourcePath ?? "";
  elements.workspaceHistory.innerHTML = renderHistoryOptions(state.workspaceHistory ?? []);
  elements.sourceHistory.innerHTML = renderHistoryOptions(state.sourceHistory ?? []);
  elements.status.textContent = state.status.message || "等待载入混编工作区";
  elements.status.dataset.error = state.status.error ? "true" : "false";

  const workspace = state.workspace;
  if (!workspace) {
    elements.workspaceMeta.textContent = "未加载混编工作区";
    elements.taskGroupName.value = "";
    elements.outputTaskPath.value = "";
    elements.sourceList.innerHTML = "<p class=\"panel-empty\">先加载或创建混编工作区。</p>";
    elements.availableSubtasks.innerHTML = "<p class=\"panel-empty\">当前来源下没有子任务。</p>";
    elements.selectedSubtasks.innerHTML = "<p class=\"panel-empty\">当前没有混编结果。</p>";
    return;
  }

  const sources = uniqueSources(workspace);
  const activeSourcePath = state.activeSourcePath || sources[0]?.path || "";
  const availableSubtasks = (workspace.subtasks ?? []).filter(
    (subtask) => subtask.source_workspace_path === activeSourcePath,
  );
  const selectedSubtasks = (workspace.selected_subtask_ids ?? [])
    .map((subtaskId) => (workspace.subtasks ?? []).find((subtask) => subtask.id === subtaskId))
    .filter(Boolean);

  elements.workspaceMeta.textContent = `${workspace.workspace_name || "未命名混编工作区"} | ${
    workspace.task_group_name || "未命名任务组"
  }`;
  elements.taskGroupName.value = workspace.task_group_name || "";
  elements.outputTaskPath.value = workspace.output_task_path || "";
  elements.sourceList.innerHTML = renderSourceList(sources, activeSourcePath);
  elements.availableSubtasks.innerHTML = renderAvailableSubtasks(
    availableSubtasks,
    workspace.selected_subtask_ids ?? [],
  );
  elements.selectedSubtasks.innerHTML = renderSelectedSubtasks(selectedSubtasks);
}
