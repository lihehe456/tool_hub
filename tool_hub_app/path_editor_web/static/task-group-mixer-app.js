import {
  browseUserFiles,
  exportTaskGroup,
  importSidecarWorkspaceIntoMixer,
  loadRuntimeConfig,
  loadOrCreateMixerWorkspace,
  saveTaskWorkspace,
} from "./api.js";
import {
  createTaskGroupMixerInitialState,
  reduceTaskGroupMixerState,
} from "./task-group-mixer-state.js";
import { renderTaskGroupMixerView } from "./task-group-mixer-view.js";

const WORKSPACE_HISTORY_KEY = "taskGroupMixer.workspaceHistory";
const SOURCE_HISTORY_KEY = "taskGroupMixer.sourceHistory";

let state = createTaskGroupMixerInitialState();
let browserTarget = "workspace";
let runtimeUserRoot = "/home";

const elements = {
  workspacePath: document.querySelector("#workspace-path"),
  workspaceHistory: document.querySelector("#workspace-history-list"),
  browseWorkspaceButton: document.querySelector("#browse-workspace-button"),
  loadWorkspaceButton: document.querySelector("#load-workspace-button"),
  sourcePath: document.querySelector("#source-path"),
  sourceHistory: document.querySelector("#source-history-list"),
  browseSourceButton: document.querySelector("#browse-source-button"),
  importSourceButton: document.querySelector("#import-source-button"),
  taskGroupName: document.querySelector("#task-group-name"),
  outputTaskPath: document.querySelector("#output-task-path"),
  exportTaskGroupButton: document.querySelector("#export-task-group-button"),
  status: document.querySelector("#task-group-status"),
  workspaceMeta: document.querySelector("#workspace-meta"),
  sourceList: document.querySelector("#source-list"),
  availableSubtasks: document.querySelector("#available-subtasks"),
  selectedSubtasks: document.querySelector("#selected-subtasks"),
  pickerOverlay: document.querySelector("#picker-overlay"),
  pickerTitle: document.querySelector("#picker-title"),
  pickerCwd: document.querySelector("#picker-cwd"),
  pickerList: document.querySelector("#picker-list"),
};

function readHistory(key) {
  try {
    return JSON.parse(window.localStorage.getItem(key) || "[]");
  } catch {
    return [];
  }
}

function writeHistory(key, items) {
  window.localStorage.setItem(key, JSON.stringify(items));
}

function dispatch(action) {
  state = reduceTaskGroupMixerState(state, action);
  renderTaskGroupMixerView(elements, state);
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

function recordWorkspaceHistory(workspacePath) {
  dispatch({ type: "RECORD_WORKSPACE_HISTORY", workspacePath });
  writeHistory(WORKSPACE_HISTORY_KEY, state.workspaceHistory);
}

function recordSourceHistory(sourcePath) {
  dispatch({ type: "RECORD_SOURCE_HISTORY", sourcePath });
  writeHistory(SOURCE_HISTORY_KEY, state.sourceHistory);
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
    message: `混编工作区自动保存成功：${state.workspacePath}`,
    error: false,
  });
}

async function loadWorkspace() {
  try {
    const workspacePath = elements.workspacePath.value.trim();
    dispatch({ type: "SET_WORKSPACE_PATH", workspacePath });
    const payload = await loadOrCreateMixerWorkspace(workspacePath);
    dispatch({
      type: "SET_WORKSPACE",
      workspacePath,
      workspace: payload.workspace,
    });
    recordWorkspaceHistory(workspacePath);
    dispatch({
      type: "SET_STATUS",
      message: payload.created ? "已创建新的混编工作区" : "混编工作区加载成功",
      error: false,
    });
  } catch (error) {
    dispatch({ type: "SET_STATUS", message: error.message, error: true });
  }
}

async function importSource(sourcePathOverride = "") {
  try {
    if (!state.workspacePath || !state.workspace) {
      throw new Error("请先加载或创建混编工作区");
    }
    const sourcePath = sourcePathOverride || elements.sourcePath.value.trim();
    dispatch({ type: "SET_SOURCE_PATH", sourcePath });
    const payload = await importSidecarWorkspaceIntoMixer(state.workspacePath, sourcePath);
    dispatch({
      type: "SET_WORKSPACE",
      workspacePath: state.workspacePath,
      workspace: payload.workspace,
    });
    dispatch({ type: "SET_ACTIVE_SOURCE", sourcePath });
    recordSourceHistory(sourcePath);
    dispatch({
      type: "SET_STATUS",
      message: `来源已导入或替换：${sourcePath}`,
      error: false,
    });
  } catch (error) {
    dispatch({ type: "SET_STATUS", message: error.message, error: true });
  }
}

async function exportCurrentTaskGroup() {
  try {
    if (!state.workspacePath) {
      throw new Error("请先加载混编工作区");
    }
    await runButtonFeedback(
      elements.exportTaskGroupButton,
      { pending: "导出中...", success: "已导出", failure: "导出失败" },
      async () => {
        dispatch({ type: "SET_STATUS", message: "正在导出混编任务组...", error: false });
        const exportDirectory = elements.outputTaskPath.value.trim();
        const payload = await exportTaskGroup(state.workspacePath, exportDirectory);
        dispatch({
          type: "SET_STATUS",
          message: `混编任务组导出成功：${payload.path}`,
          error: false,
        });
      },
    );
  } catch (error) {
    dispatch({ type: "SET_STATUS", message: error.message, error: true });
  }
}

async function mutateWorkspace(action) {
  dispatch(action);
  try {
    await persistWorkspace();
  } catch (error) {
    dispatch({ type: "SET_STATUS", message: error.message, error: true });
  }
}

function closePicker() {
  elements.pickerOverlay.classList.remove("visible");
}

async function browseTo(path) {
  const fileType = browserTarget === "source" ? "workspace_json" : "json";
  const payload = await browseUserFiles(path, fileType);
  elements.pickerCwd.textContent = payload.cwd;
  elements.pickerList.innerHTML = "";

  const up = document.createElement("div");
  up.className = "picker-entry dir";
  up.textContent = "..";
  up.onclick = () => browseTo(payload.parent);
  elements.pickerList.appendChild(up);

  for (const entry of payload.entries) {
    const item = document.createElement("div");
    if (entry.is_dir) {
      item.className = "picker-entry dir";
      item.textContent = entry.name;
      item.onclick = () => browseTo(entry.path);
    } else {
      const selectable =
        browserTarget === "source" ? entry.is_workspace_json : entry.is_json;
      item.className = `picker-entry ${selectable ? "json" : "other"}`;
      item.textContent = entry.name;
      if (selectable) {
        item.onclick = () => {
          if (browserTarget === "source") {
            elements.sourcePath.value = entry.path;
            dispatch({ type: "SET_SOURCE_PATH", sourcePath: entry.path });
          } else {
            elements.workspacePath.value = entry.path;
            dispatch({ type: "SET_WORKSPACE_PATH", workspacePath: entry.path });
          }
          closePicker();
        };
      }
    }
    elements.pickerList.appendChild(item);
  }
}

function openPicker(target) {
  browserTarget = target;
  elements.pickerTitle.textContent = target === "source" ? "选择旁路文件" : "选择混编工作区";
  elements.pickerOverlay.classList.add("visible");
  const currentPath =
    target === "source"
      ? elements.sourcePath.value.trim() || state.sourceHistory[0] || runtimeUserRoot
      : elements.workspacePath.value.trim() || state.workspaceHistory[0] || runtimeUserRoot;
  browseTo(currentPath).catch((error) => {
    dispatch({ type: "SET_STATUS", message: error.message, error: true });
    closePicker();
  });
}

elements.browseWorkspaceButton?.addEventListener("click", () => openPicker("workspace"));
elements.browseSourceButton?.addEventListener("click", () => openPicker("source"));
elements.loadWorkspaceButton?.addEventListener("click", loadWorkspace);
elements.importSourceButton?.addEventListener("click", () => importSource());
elements.exportTaskGroupButton?.addEventListener("click", exportCurrentTaskGroup);

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

elements.sourceList?.addEventListener("click", (event) => {
  const actionTarget = event.target.closest("[data-action]");
  if (!actionTarget) {
    return;
  }
  const sourcePath = actionTarget.dataset.sourcePath;
  if (!sourcePath) {
    return;
  }
  if (actionTarget.dataset.action === "activate-source") {
    dispatch({ type: "SET_ACTIVE_SOURCE", sourcePath });
  } else if (actionTarget.dataset.action === "reimport-source") {
    elements.sourcePath.value = sourcePath;
    dispatch({ type: "SET_SOURCE_PATH", sourcePath });
    importSource(sourcePath);
  }
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

elements.pickerOverlay?.addEventListener("click", (event) => {
  if (event.target === elements.pickerOverlay || event.target.dataset.action === "close-picker") {
    closePicker();
  }
});

state = {
  ...state,
  workspaceHistory: readHistory(WORKSPACE_HISTORY_KEY),
  sourceHistory: readHistory(SOURCE_HISTORY_KEY),
};
renderTaskGroupMixerView(elements, state);

loadRuntimeConfig()
  .then((config) => {
    if (config?.user_root) {
      runtimeUserRoot = config.user_root;
    }
  })
  .catch(() => {
    runtimeUserRoot = "/home";
  });
