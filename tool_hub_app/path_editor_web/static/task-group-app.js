import { exportTaskGroup, loadTaskWorkspace, saveTaskWorkspace } from "./api.js";
import { createTaskGroupInitialState, reduceTaskGroupState } from "./task-group-state.js";
import { renderTaskGroupView } from "./task-group-view.js";

let state = createTaskGroupInitialState();

const elements = {
  workspacePath: document.querySelector("#workspace-path"),
  loadWorkspaceButton: document.querySelector("#load-workspace-button"),
  taskGroupName: document.querySelector("#task-group-name"),
  outputTaskPath: document.querySelector("#output-task-path"),
  exportTaskGroupButton: document.querySelector("#export-task-group-button"),
  clearSubtasksButton: document.querySelector("#clear-subtasks-button"),
  status: document.querySelector("#task-group-status"),
  workspaceMeta: document.querySelector("#workspace-meta"),
  availableSubtasks: document.querySelector("#available-subtasks"),
  selectedSubtasks: document.querySelector("#selected-subtasks"),
};

function dispatch(action) {
  state = reduceTaskGroupState(state, action);
  renderTaskGroupView(elements, state);
}

async function runButtonFeedback(button, labels, operation) {
  if (!button) {
    return operation();
  }
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = labels.pending;
  try {
    const result = await operation();
    button.textContent = labels.success;
    window.setTimeout(() => {
      button.textContent = originalText;
      button.disabled = false;
    }, 1400);
    return result;
  } catch (error) {
    button.textContent = labels.failure ?? originalText;
    window.setTimeout(() => {
      button.textContent = originalText;
      button.disabled = false;
    }, 1800);
    throw error;
  }
}

async function persistWorkspace() {
  if (!state.workspacePath || !state.workspace) {
    return;
  }

  const payload = await saveTaskWorkspace(state.workspacePath, state.workspace);
  dispatch({
    type: "SET_WORKSPACE",
    workspacePath: state.workspacePath,
    workspace: payload.workspace,
  });
  dispatch({
    type: "SET_STATUS",
    message: `工作区自动保存成功：${state.workspacePath}`,
    error: false,
  });
}

async function loadWorkspace() {
  try {
    const workspacePath = elements.workspacePath.value.trim();
    const payload = await loadTaskWorkspace(workspacePath);
    dispatch({
      type: "SET_WORKSPACE",
      workspacePath,
      workspace: payload.workspace,
    });
    dispatch({
      type: "SET_STATUS",
      message: "工作区加载成功",
      error: false,
    });
  } catch (error) {
    dispatch({
      type: "SET_STATUS",
      message: error.message,
      error: true,
    });
  }
}

async function exportCurrentTaskGroup() {
  try {
    if (!state.workspacePath) {
      throw new Error("请先加载工作区");
    }
    await runButtonFeedback(
      elements.exportTaskGroupButton,
      { pending: "导出中...", success: "已导出", failure: "导出失败" },
      async () => {
        dispatch({ type: "SET_STATUS", message: "正在导出任务组...", error: false });
        const exportPath = elements.outputTaskPath.value.trim();
        const payload = await exportTaskGroup(state.workspacePath, exportPath);
        dispatch({
          type: "SET_STATUS",
          message: `任务组导出成功：${payload.path}`,
          error: false,
        });
      },
    );
  } catch (error) {
    dispatch({
      type: "SET_STATUS",
      message: error.message,
      error: true,
    });
  }
}

async function mutateWorkspace(action) {
  dispatch(action);
  try {
    await persistWorkspace();
  } catch (error) {
    dispatch({
      type: "SET_STATUS",
      message: error.message,
      error: true,
    });
  }
}

elements.loadWorkspaceButton?.addEventListener("click", loadWorkspace);
elements.exportTaskGroupButton?.addEventListener("click", exportCurrentTaskGroup);
elements.clearSubtasksButton?.addEventListener("click", () => {
  if (!state.workspace) {
    dispatch({
      type: "SET_STATUS",
      message: "请先加载工作区",
      error: true,
    });
    return;
  }

  const confirmed = window.confirm("确认清空工作区中的全部子任务吗？此操作会立即保存。");
  if (!confirmed) {
    return;
  }

  mutateWorkspace({ type: "CLEAR_SUBTASKS" });
});

elements.taskGroupName?.addEventListener("change", () => {
  mutateWorkspace({
    type: "RENAME_TASK_GROUP",
    taskGroupName: elements.taskGroupName.value.trim(),
  });
});

elements.outputTaskPath?.addEventListener("change", () => {
  mutateWorkspace({
    type: "SET_OUTPUT_TASK_PATH",
    outputTaskPath: elements.outputTaskPath.value.trim(),
  });
});

elements.availableSubtasks?.addEventListener("click", (event) => {
  const actionTarget = event.target.closest("[data-action]");
  if (!actionTarget) {
    return;
  }

  const subtaskId = actionTarget.dataset.subtaskId;
  if (!subtaskId) {
    return;
  }

  if (actionTarget.dataset.action === "add") {
    mutateWorkspace({ type: "ADD_SELECTED_SUBTASK", subtaskId });
  } else if (actionTarget.dataset.action === "remove") {
    mutateWorkspace({ type: "REMOVE_SELECTED_SUBTASK", subtaskId });
  }
});

elements.selectedSubtasks?.addEventListener("click", (event) => {
  const actionTarget = event.target.closest("[data-action]");
  if (!actionTarget) {
    return;
  }

  const subtaskId = actionTarget.dataset.subtaskId;
  if (!subtaskId) {
    return;
  }

  if (actionTarget.dataset.action === "remove") {
    mutateWorkspace({ type: "REMOVE_SELECTED_SUBTASK", subtaskId });
  } else if (actionTarget.dataset.action === "move-up") {
    mutateWorkspace({ type: "MOVE_SELECTED_SUBTASK", subtaskId, direction: "up" });
  } else if (actionTarget.dataset.action === "move-down") {
    mutateWorkspace({ type: "MOVE_SELECTED_SUBTASK", subtaskId, direction: "down" });
  }
});

elements.availableSubtasks?.addEventListener("change", (event) => {
  const input = event.target.closest(".subtask-name-input");
  if (!input) {
    return;
  }

  mutateWorkspace({
    type: "RENAME_SUBTASK",
    subtaskId: input.dataset.subtaskId,
    subtaskName: input.value.trim(),
  });
});

const initialWorkspacePath = new URLSearchParams(window.location.search).get("workspace_path");
if (initialWorkspacePath) {
  elements.workspacePath.value = initialWorkspacePath;
  loadWorkspace();
} else {
  renderTaskGroupView(elements, state);
}
