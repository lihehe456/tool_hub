function renderAvailableSubtaskList(items, selectedIds = []) {
  if (!items.length) {
    return "<p class=\"panel-empty\">暂无子任务</p>";
  }

  return `
    <ul class="task-group-list">
      ${items
        .map((item) => {
          const selected = selectedIds.includes(item.id) ? "true" : "false";
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
              <button type="button" data-action="${selected === "true" ? "remove" : "add"}" data-subtask-id="${item.id}">
                ${selected === "true" ? "移出任务组" : "加入任务组"}
              </button>
            </li>
          `;
        })
        .join("")}
    </ul>
  `;
}

function renderSelectedSubtaskList(items) {
  if (!items.length) {
    return "<p class=\"panel-empty\">当前没有任务组组合。</p>";
  }

  return `
    <ol class="task-group-list">
      ${items
        .map(
          (item) => `
            <li class="task-group-list-item" data-selected="true">
              <strong>${item.subtask_name ?? item.generated_subtask_name ?? item.id}</strong>
              <span>${item.direction ?? "unknown"}</span>
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

export function renderTaskGroupView(elements, state) {
  elements.workspacePath.value = state.workspacePath ?? "";
  elements.status.textContent = state.status.message || "等待载入工作区";
  elements.status.dataset.error = state.status.error ? "true" : "false";

  const workspace = state.workspace;
  if (!workspace) {
    elements.workspaceMeta.textContent = "未加载工作区";
    elements.availableSubtasks.innerHTML = "<p class=\"panel-empty\">先输入工作区路径并加载。</p>";
    elements.selectedSubtasks.innerHTML = "<p class=\"panel-empty\">当前没有任务组组合。</p>";
    elements.taskGroupName.value = "";
    elements.outputTaskPath.value = "";
    return;
  }

  elements.workspaceMeta.textContent = `${workspace.workspace_name || "未命名工作区"} | ${
    workspace.task_group_name || "未命名任务组"
  }`;
  elements.taskGroupName.value = workspace.task_group_name || "";
  elements.outputTaskPath.value = workspace.output_task_path || "";
  elements.availableSubtasks.innerHTML = renderAvailableSubtaskList(
    workspace.subtasks ?? [],
    workspace.selected_subtask_ids ?? [],
  );

  const selectedSubtasks = (workspace.selected_subtask_ids ?? [])
    .map((subtaskId) => (workspace.subtasks ?? []).find((item) => item.id === subtaskId))
    .filter(Boolean);
  elements.selectedSubtasks.innerHTML = renderSelectedSubtaskList(selectedSubtasks);
}
