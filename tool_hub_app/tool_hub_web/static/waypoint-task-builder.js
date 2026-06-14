import {
  createNodeFromSchema,
  createWaypointTaskBuilderInitialState,
  reduceWaypointTaskBuilderState,
} from "./waypoint-task-builder-state.js";
import { renderWaypointTaskBuilderView } from "./waypoint-task-builder-view.js";

let state = createWaypointTaskBuilderInitialState();
let browseTarget = "task";
let currentDragPayload = null;
let runtimeWaypointTasksRoot = "/";

const elements = {
  taskPath: document.querySelector("#task-path"),
  taskDirectory: document.querySelector("#task-directory"),
  taskName: document.querySelector("#task-name"),
  loadButton: document.querySelector("#load-task-button"),
  newButton: document.querySelector("#new-task-button"),
  saveButton: document.querySelector("#save-task-button"),
  clearButton: document.querySelector("#clear-tree-button"),
  parseXmlButton: document.querySelector("#parse-xml-button"),
  browseTaskButton: document.querySelector("#browse-task-button"),
  browseDirectoryButton: document.querySelector("#browse-directory-button"),
  status: document.querySelector("#builder-status"),
  palette: document.querySelector("#builder-palette"),
  tree: document.querySelector("#builder-tree"),
  fields: document.querySelector("#builder-fields"),
  xmlPreview: document.querySelector("#xml-preview"),
  pickerOverlay: document.querySelector("#picker-overlay"),
  pickerTitle: document.querySelector("#picker-title"),
  pickerCwd: document.querySelector("#picker-cwd"),
  pickerList: document.querySelector("#picker-list"),
};

function dispatch(action) {
  state = reduceWaypointTaskBuilderState(state, action);
  renderWaypointTaskBuilderView(elements, state);
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

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

async function loadRuntimeConfig() {
  const payload = await requestJson("/waypoint-task-builder/api/runtime_config");
  runtimeWaypointTasksRoot = payload.waypoint_tasks_root || "/";
}

async function loadSchema() {
  const payload = await requestJson("/waypoint-task-builder/api/schema");
  dispatch({ type: "SET_SCHEMA", nodes: payload.nodes });
}

async function loadTask() {
  try {
    const taskPath = elements.taskPath.value.trim();
    const payload = await requestJson("/waypoint-task-builder/api/load", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: taskPath }),
    });
    dispatch({
      type: "SET_DOCUMENT",
      taskPath,
      taskDirectory: taskPath.split("/").slice(0, -1).join("/"),
      document: payload.document,
      xmlText: payload.xml_text,
    });
    dispatch({ type: "SET_STATUS", message: "任务模板加载成功", error: false });
  } catch (error) {
    dispatch({ type: "SET_STATUS", message: error.message, error: true });
  }
}

function createNewTask() {
  const taskName = (elements.taskName.value.trim() || "new_waypoint_task").replace(/\.xml$/i, "");
  const rootSchema = state.nodes.Sequence;
  const rootNode = createNodeFromSchema("Sequence", rootSchema);
  rootNode.attrs.name = "MainSequence";
  dispatch({
    type: "SET_DOCUMENT",
    taskPath: "",
    taskDirectory: elements.taskDirectory.value.trim(),
      document: {
        task_name: taskName,
        tree: rootNode,
      },
    });
  dispatch({ type: "SET_STATUS", message: "已创建新的任务模板", error: false });
}

async function parseXmlText() {
  try {
    const payload = await requestJson("/waypoint-task-builder/api/parse_xml", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_name: elements.taskName.value.trim() || "parsed_task",
        xml_text: elements.xmlPreview.value,
      }),
    });
    dispatch({
      type: "SET_DOCUMENT",
      taskPath: state.taskPath,
      taskDirectory: elements.taskDirectory.value.trim(),
      document: payload.document,
      xmlText: payload.xml_text,
    });
    dispatch({ type: "SET_STATUS", message: "XML 已成功还原为树结构", error: false });
  } catch (error) {
    dispatch({ type: "SET_STATUS", message: error.message, error: true });
  }
}

async function documentForSave() {
  const taskName = elements.taskName.value.trim() || state.taskName || "saved_task";
  const currentXml = elements.xmlPreview.value;
  if (!state.document) {
    throw new Error("当前没有可保存的任务模板");
  }
  if (currentXml === (state.xmlText ?? "")) {
    return state.document;
  }

  const payload = await requestJson("/waypoint-task-builder/api/parse_xml", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task_name: taskName,
      xml_text: currentXml,
    }),
  });
  dispatch({
    type: "SET_DOCUMENT",
    taskPath: state.taskPath,
    taskDirectory: elements.taskDirectory.value.trim(),
    document: payload.document,
    xmlText: payload.xml_text,
  });
  return payload.document;
}

async function saveTask() {
  try {
    await runButtonFeedback(
      elements.saveButton,
      { pending: "保存中...", success: "已保存", failure: "保存失败" },
      async () => {
        dispatch({ type: "SET_STATUS", message: "正在保存 XML...", error: false });
        const document = await documentForSave();
        const payload = await requestJson("/waypoint-task-builder/api/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            directory: elements.taskDirectory.value.trim(),
            task_name: elements.taskName.value.trim(),
            document,
          }),
        });
        dispatch({ type: "SET_TASK_PATH", taskPath: payload.path });
        dispatch({ type: "SET_STATUS", message: `保存成功：${payload.path}`, error: false });
      },
    );
  } catch (error) {
    dispatch({ type: "SET_STATUS", message: error.message, error: true });
  }
}

function closePicker() {
  elements.pickerOverlay.classList.remove("visible");
}

async function browseTo(path) {
  const payload = await requestJson("/waypoint-task-builder/api/browse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
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
    } else if (entry.is_xml) {
      item.className = "picker-entry json";
      item.textContent = entry.name;
      item.onclick = () => {
        if (browseTarget === "task") {
          elements.taskPath.value = entry.path;
          dispatch({ type: "SET_TASK_PATH", taskPath: entry.path });
        } else {
          elements.taskDirectory.value = payload.cwd;
          elements.taskName.value = entry.name.replace(/\.xml$/i, "");
          dispatch({ type: "SET_TASK_DIRECTORY", taskDirectory: payload.cwd });
          dispatch({ type: "SET_TASK_NAME", taskName: entry.name.replace(/\.xml$/i, "") });
        }
        closePicker();
      };
    } else {
      item.className = "picker-entry other";
      item.textContent = entry.name;
    }
    elements.pickerList.appendChild(item);
  }
}

function openPicker(target) {
  browseTarget = target;
  elements.pickerTitle.textContent = target === "task" ? "选择任务模板" : "选择保存目录";
  elements.pickerOverlay.classList.add("visible");
  const startPath =
    target === "task"
      ? elements.taskPath.value.trim() || elements.taskDirectory.value.trim()
      : elements.taskDirectory.value.trim() || elements.taskPath.value.trim();
  browseTo(startPath || runtimeWaypointTasksRoot).catch(
    (error) => {
      dispatch({ type: "SET_STATUS", message: error.message, error: true });
      closePicker();
    },
  );
}

function handlePaletteDragStart(event) {
  const target = event.target.closest("[data-node-type]");
  if (!target) {
    return;
  }
  const nodeType = target.dataset.nodeType;
  event.dataTransfer.setData("text/node-type", nodeType);
  currentDragPayload = { kind: "palette", nodeType };
}

function handleTreeDragStart(event) {
  const target = event.target.closest("[data-node-id]");
  if (!target) {
    return;
  }
  const nodeId = target.dataset.nodeId;
  event.dataTransfer.setData("text/node-id", nodeId);
  currentDragPayload = { kind: "existing", nodeId };
}

function handleDropzoneDrop(event) {
  event.preventDefault();
  const isRootDropzone = Boolean(event.target.closest("[data-root-dropzone]"));
  if (isRootDropzone) {
    const payload = currentDragPayload;
    if (!payload) {
      return;
    }
    if (payload.kind === "palette") {
      const schema = state.nodes[payload.nodeType];
      if (!schema) {
        return;
      }
      const nodeTemplate = createNodeFromSchema(payload.nodeType, schema);
      dispatch({ type: "ADD_ROOT_NODE", nodeTemplate });
    }
    currentDragPayload = null;
    return;
  }
  const parentNodeId = event.target.closest("[data-drop-parent-id]")?.dataset.dropParentId;
  if (!parentNodeId) {
    return;
  }
  const payload = currentDragPayload;
  if (!payload) {
    return;
  }
  if (payload.kind === "palette") {
    const schema = state.nodes[payload.nodeType];
    if (!schema) {
      return;
    }
    const nodeTemplate = createNodeFromSchema(payload.nodeType, schema);
    dispatch({ type: "ADD_NODE_AS_CHILD", parentNodeId, nodeTemplate });
  } else if (payload.kind === "existing") {
    dispatch({ type: "MOVE_NODE_TO_CHILD_END", parentNodeId, nodeId: payload.nodeId });
  }
  currentDragPayload = null;
}

elements.loadButton?.addEventListener("click", loadTask);
elements.newButton?.addEventListener("click", createNewTask);
elements.saveButton?.addEventListener("click", saveTask);
elements.clearButton?.addEventListener("click", () => {
  dispatch({ type: "CLEAR_TREE" });
  dispatch({ type: "SET_STATUS", message: "树结构已清空", error: false });
});
elements.parseXmlButton?.addEventListener("click", parseXmlText);
elements.browseTaskButton?.addEventListener("click", () => openPicker("task"));
elements.browseDirectoryButton?.addEventListener("click", () => openPicker("directory"));

elements.taskName?.addEventListener("change", () => {
  dispatch({ type: "SET_TASK_NAME", taskName: elements.taskName.value.trim() });
});

elements.taskDirectory?.addEventListener("change", () => {
  dispatch({ type: "SET_TASK_DIRECTORY", taskDirectory: elements.taskDirectory.value.trim() });
});

elements.palette?.addEventListener("dragstart", handlePaletteDragStart);
elements.tree?.addEventListener("dragstart", handleTreeDragStart);
elements.tree?.addEventListener("dragover", (event) => {
  if (event.target.closest("[data-drop-parent-id]") || event.target.closest("[data-root-dropzone]")) {
    event.preventDefault();
  }
});
elements.tree?.addEventListener("drop", handleDropzoneDrop);
elements.tree?.addEventListener("dragend", () => {
  currentDragPayload = null;
});

elements.tree?.addEventListener("click", (event) => {
  const actionTarget = event.target.closest("[data-action]");
  if (!actionTarget) {
    return;
  }
  const nodeId = actionTarget.dataset.nodeId;
  if (actionTarget.dataset.action === "select-node") {
    dispatch({ type: "SELECT_NODE", nodeId });
  } else if (actionTarget.dataset.action === "move-node-up") {
    dispatch({ type: "MOVE_NODE", nodeId, direction: "up" });
  } else if (actionTarget.dataset.action === "move-node-down") {
    dispatch({ type: "MOVE_NODE", nodeId, direction: "down" });
  } else if (actionTarget.dataset.action === "remove-node") {
    dispatch({ type: "REMOVE_NODE", nodeId });
  }
});

elements.tree?.addEventListener("focusin", (event) => {
  const input = event.target.closest("[data-inline-field-name]");
  if (!input) {
    return;
  }
  dispatch({ type: "SELECT_NODE", nodeId: input.dataset.nodeId });
});

elements.tree?.addEventListener("change", (event) => {
  const input = event.target.closest("[data-inline-field-name]");
  if (!input) {
    return;
  }
  dispatch({
    type: "UPDATE_NODE_ATTR",
    nodeId: input.dataset.nodeId,
    fieldName: input.dataset.inlineFieldName,
    value: input.value,
  });
});

elements.fields?.addEventListener("change", (event) => {
  const input = event.target.closest("[data-field-name]");
  if (!input || !state.selectedNodeId) {
    return;
  }
  dispatch({
    type: "UPDATE_NODE_ATTR",
    nodeId: state.selectedNodeId,
    fieldName: input.dataset.fieldName,
    value: input.value,
  });
});

elements.xmlPreview?.addEventListener("input", () => {
  dispatch({ type: "SET_XML_TEXT", xmlText: elements.xmlPreview.value });
});

elements.pickerOverlay?.addEventListener("click", (event) => {
  if (event.target === elements.pickerOverlay || event.target.dataset.action === "close-picker") {
    closePicker();
  }
});

Promise.all([loadRuntimeConfig(), loadSchema()])
  .then(() => {
    renderWaypointTaskBuilderView(elements, state);
  })
  .catch((error) => {
    dispatch({ type: "SET_STATUS", message: error.message, error: true });
  });
