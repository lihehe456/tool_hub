import { PathCanvas } from "/static/canvas.js";
import {
  createSubtaskComposerInitialState,
  reduceSubtaskComposerState,
  subtaskDocumentsFromPayload,
  subtaskFromDocument,
  taskPayloadFromState,
} from "/hub-static/subtask-composer-state.js";

let state = {
  defaultRoot: "/",
  browseCwd: "/",
  pickerMode: "subtask",
  defaultWaypointTasksPath: "",
  defaultSpeedModesPath: "",
  waypointTasks: [],
  speedModes: [],
  speedModesSingle: [],
  ...createSubtaskComposerInitialState(),
};

const el = {
  subtaskPath: document.querySelector("#subtask-path"),
  mapPath: document.querySelector("#map-path"),
  subtaskName: document.querySelector("#subtask-name"),
  pcdUrl: document.querySelector("#pcd-url"),
  status: document.querySelector("#composer-status"),
  filePanel: document.querySelector("#file-panel"),
  filePanelSummary: document.querySelector("#file-panel-summary"),
  toggleFilePanel: document.querySelector("#toggle-file-panel"),
  subtaskTabs: document.querySelector("#subtask-tabs"),
  canvas: document.querySelector("#composer-canvas"),
  waypointList: document.querySelector("#waypoint-list"),
  toolButtons: Array.from(document.querySelectorAll("[data-tool]")),
  browseSubtask: document.querySelector("#browse-subtask"),
  browseMap: document.querySelector("#browse-map"),
  loadSubtask: document.querySelector("#load-subtask"),
  newSubtask: document.querySelector("#new-subtask"),
  loadMap: document.querySelector("#load-map"),
  saveSubtask: document.querySelector("#save-subtask"),
  saveSubtaskAs: document.querySelector("#save-subtask-as"),
  buildReturn: document.querySelector("#build-return"),
  offsetX: document.querySelector("#offset-x"),
  offsetY: document.querySelector("#offset-y"),
  applyOffset: document.querySelector("#apply-offset"),
  editor: document.querySelector("#composer-editor"),
  toggleEditor: document.querySelector("#toggle-editor"),
  editorResizer: document.querySelector("#editor-resizer"),
  editorTitle: document.querySelector("#editor-title"),
  waypointId: document.querySelector("#field-waypoint-id"),
  speedMode: document.querySelector("#field-speed-mode"),
  waypointTaskId: document.querySelector("#field-waypoint-task-id"),
  fieldX: document.querySelector("#field-x"),
  fieldY: document.querySelector("#field-y"),
  fieldZ: document.querySelector("#field-z"),
  fieldYaw: document.querySelector("#field-yaw"),
  isTaskPoint: document.querySelector("#field-is-task-point"),
  isSinglePoint: document.querySelector("#field-is-single-point"),
  isBackward: document.querySelector("#field-is-backward"),
  changeLoc: document.querySelector("#field-change-loc"),
  applyPoint: document.querySelector("#apply-point"),
  flipYaw: document.querySelector("#flip-yaw"),
  pickerOverlay: document.querySelector("#picker-overlay"),
  pickerTitle: document.querySelector("#picker-title"),
  pickerCwd: document.querySelector("#picker-cwd"),
  pickerList: document.querySelector("#picker-list"),
  pickerSelectDir: document.querySelector("#picker-select-dir"),
  pickerUp: document.querySelector("#picker-up"),
  pickerClose: document.querySelector("#picker-close"),
};

const pathCanvas = new PathCanvas(el.canvas, {
  onAddAnchor(worldPoint) {
    dispatch({ type: "ADD_ANCHOR", point: { ...worldPoint, z: 0 } });
  },
  onInsertAnchor(segmentIndex, worldPoint) {
    const segment = state.document?.segments?.[segmentIndex];
    if (!segment) {
      return;
    }
    dispatch({ type: "INSERT_ANCHOR", index: segment.endIndex, point: { ...worldPoint, z: 0 } });
  },
  onMoveAnchor(index, worldPoint) {
    dispatch({ type: "MOVE_ANCHOR", index, point: { ...worldPoint, z: 0 } });
  },
  onRotateAnchor(index, yaw) {
    dispatch({ type: "SET_ANCHOR_YAW", index, yaw });
  },
  onDeleteAnchor(index) {
    dispatch({ type: "DELETE_ANCHOR", index });
  },
  onSelect(selection) {
    dispatch({ type: "SELECT_ANCHOR", index: selection.kind === "anchor" ? selection.index : -1 });
  },
  onToggleAnchorSelection(index) {
    dispatch({ type: "SELECT_ANCHOR", index });
  },
});

function dispatch(action) {
  state = reduceSubtaskComposerState(state, action);
  render();
}

function setStatus(message, error = false) {
  dispatch({ type: "SET_STATUS", message, error });
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

async function runButton(button, labels, action) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = labels.pending;
  try {
    const result = await action();
    button.textContent = labels.success;
    window.setTimeout(() => {
      button.textContent = originalText;
      button.disabled = false;
    }, 1100);
    return result;
  } catch (error) {
    button.textContent = labels.failure;
    setStatus(error.message, true);
    window.setTimeout(() => {
      button.textContent = originalText;
      button.disabled = false;
    }, 1600);
    throw error;
  }
}

function selectedAnchor() {
  return state.document?.anchors?.[state.selectedIndex] || null;
}

function formatNumber(value) {
  return Number(value || 0).toFixed(3);
}

function setSelectOptions(select, values, selectedValue, includeBlank = false) {
  const options = includeBlank ? ["", ...values] : values;
  const normalizedSelected = String(selectedValue || "");
  if (normalizedSelected && !options.includes(normalizedSelected)) {
    options.push(normalizedSelected);
  }
  select.innerHTML = "";
  options.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value || " ";
    option.selected = value === normalizedSelected;
    select.appendChild(option);
  });
}

function renderAttributeSelects(anchor = selectedAnchor()) {
  const speedValues = anchor?.task?.is_single_point
    ? state.speedModesSingle
    : state.speedModes;
  setSelectOptions(el.speedMode, speedValues, anchor?.task?.speed_mode || "task_point");
  setSelectOptions(el.waypointTaskId, state.waypointTasks, anchor?.task?.waypoint_task_id || "", true);
  el.waypointTaskId.disabled = !anchor || !anchor.task?.is_task_point;
}

function syncMetaInputs() {
  const meta = state.document?.meta || {};
  el.subtaskPath.value = state.taskPath || el.subtaskPath.value || "";
  el.mapPath.value = meta.map_url || el.mapPath.value || "";
  el.subtaskName.value = meta.subtask_name || el.subtaskName.value || "new_subtask";
  el.pcdUrl.value = meta.pcd_url || "";
  el.changeLoc.checked = Boolean(meta.change_loc);
  const filePanelCollapsed = Boolean(state.filePanel?.collapsed);
  el.filePanel.dataset.collapsed = filePanelCollapsed ? "true" : "false";
  el.toggleFilePanel.textContent = filePanelCollapsed ? "展开文件栏" : "收起文件栏";
  const taskText = state.taskPath || el.subtaskPath.value || "未打开子任务";
  const mapText = meta.map_url || el.mapPath.value || "未选择地图";
  el.filePanelSummary.textContent = `${taskText} | ${mapText}`;
}

function renderWaypointList() {
  const anchors = state.document?.anchors || [];
  if (!anchors.length) {
    el.waypointList.innerHTML = '<p class="composer-muted">暂无路点。选择“加点”后在地图上点击。</p>';
    return;
  }
  el.waypointList.innerHTML = "";
  anchors.forEach((anchor, index) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "waypoint-item";
    item.dataset.selected = index === state.selectedIndex ? "true" : "false";
    item.dataset.taskPoint = anchor.task?.is_task_point ? "true" : "false";
    item.innerHTML = `
      <span class="wp-index">#${index}</span>
      <span class="wp-id">${anchor.waypoint_id || `wp_${index}`}</span>
      <span class="wp-speed">${anchor.task?.speed_mode || ""}</span>
      ${anchor.task?.waypoint_task_id ? `<span class="wp-task">${anchor.task.waypoint_task_id}</span>` : ""}
    `;
    item.addEventListener("click", () => dispatch({ type: "SELECT_ANCHOR", index }));
    el.waypointList.appendChild(item);
  });
}

function renderSubtaskTabs() {
  const isTaskGroup = state.documentType === "task_group" && state.subtaskDocuments.length > 1;
  el.subtaskTabs.dataset.visible = isTaskGroup ? "true" : "false";
  el.subtaskTabs.innerHTML = "";
  if (!isTaskGroup) {
    return;
  }
  state.subtaskNames.forEach((name, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "subtask-tab";
    button.dataset.active = index === state.activeSubtaskIndex ? "true" : "false";
    button.textContent = name;
    button.addEventListener("click", async () => {
      dispatch({ type: "SELECT_SUBTASK", index });
      const mapUrl = state.document?.meta?.map_url;
      if (mapUrl) {
        try {
          await loadMap(mapUrl);
        } catch (error) {
          setStatus(error.message, true);
        }
      }
    });
    el.subtaskTabs.appendChild(button);
  });
}

function renderEditor() {
  el.editor.style.setProperty("--editor-width", `${state.editorPanel.width}px`);
  el.editor.dataset.collapsed = state.editorPanel.collapsed ? "true" : "false";
  el.toggleEditor.textContent = state.editorPanel.collapsed ? "展开" : "收起";
  const anchor = selectedAnchor();
  const disabled = !anchor;
  [
    el.waypointId,
    el.speedMode,
    el.waypointTaskId,
    el.fieldX,
    el.fieldY,
    el.fieldZ,
    el.fieldYaw,
    el.isTaskPoint,
    el.isSinglePoint,
    el.isBackward,
    el.applyPoint,
    el.flipYaw,
  ].forEach((input) => {
    input.disabled = disabled;
  });

  if (!anchor) {
    el.editorTitle.textContent = "未选择路点";
    el.waypointId.value = "";
    renderAttributeSelects(null);
    el.fieldX.value = "";
    el.fieldY.value = "";
    el.fieldZ.value = "";
    el.fieldYaw.value = "";
    el.isTaskPoint.checked = false;
    el.isSinglePoint.checked = false;
    el.isBackward.checked = false;
    return;
  }

  el.editorTitle.textContent = `编辑: ${anchor.waypoint_id}`;
  el.waypointId.value = anchor.waypoint_id || "";
  renderAttributeSelects(anchor);
  el.fieldX.value = Number(anchor.x || 0);
  el.fieldY.value = Number(anchor.y || 0);
  el.fieldZ.value = Number(anchor.z || 0);
  el.fieldYaw.value = Number(anchor.yaw || 0);
  el.isTaskPoint.checked = Boolean(anchor.task?.is_task_point);
  el.isSinglePoint.checked = Boolean(anchor.task?.is_single_point);
  el.isBackward.checked = Boolean(anchor.task?.is_backward);
  el.waypointTaskId.disabled = !el.isTaskPoint.checked;
}

function renderTools() {
  el.toolButtons.forEach((button) => {
    button.dataset.active = button.dataset.tool === state.activeTool ? "true" : "false";
  });
}

function render() {
  el.status.textContent = state.status.message || "准备就绪";
  el.status.dataset.error = state.status.error ? "true" : "false";
  syncMetaInputs();
  renderTools();
  renderSubtaskTabs();
  renderWaypointList();
  renderEditor();
  pathCanvas.setTool(state.activeTool);
  pathCanvas.setSelection(
    state.selectedIndex >= 0 ? { kind: "anchor", index: state.selectedIndex } : { kind: "none" },
  );
  pathCanvas.setDocument(state.document);
}

async function loadMap(yamlPath) {
  if (!yamlPath) {
    throw new Error("请先选择地图 YAML");
  }
  const data = await postJson("/api/load_map", { yaml_path: yamlPath });
  const image = new Image();
  await new Promise((resolve, reject) => {
    image.onload = resolve;
    image.onerror = reject;
    image.src = `data:image/png;base64,${data.image_b64}`;
  });
  const mapData = {
    imageElement: image,
    width: data.width,
    height: data.height,
    resolution: data.resolution,
    origin: data.origin,
  };
  pathCanvas.setMapData(mapData);
  pathCanvas.setVirtualWalls(data.virtual_walls || []);
  state.map = mapData;
  setStatus(`已加载地图：${yamlPath}${data.virtual_wall_path ? `，虚拟墙：${data.virtual_wall_path}` : ""}`);
}

async function loadSubtask() {
  const taskPath = el.subtaskPath.value.trim();
  if (!taskPath) {
    throw new Error("请填写子任务 JSON 路径");
  }
  const payload = await postJson("/subtask-composer/api/load", { path: taskPath });
  const documents = subtaskDocumentsFromPayload(payload);
  dispatch({
    type: "SET_TASK_DOCUMENT",
    taskPath: payload.path,
    ...documents,
  });
  setStatus(
    payload.document_type === "task_group"
      ? `已打开任务组：${payload.path}`
      : `已打开子任务：${payload.path}`,
  );
  if (payload.subtask.map_url) {
    await loadMap(payload.subtask.map_url);
  }
}

async function newSubtask() {
  const payload = await postJson("/subtask-composer/api/new", {
    subtask_name: el.subtaskName.value.trim() || "new_subtask",
    map_url: el.mapPath.value.trim(),
    pcd_url: el.pcdUrl.value.trim(),
    change_loc: el.changeLoc.checked,
  });
  dispatch({
    type: "SET_TASK_DOCUMENT",
    taskPath: "",
    ...subtaskDocumentsFromPayload({
      document_type: "subtask",
      subtask: payload.subtask,
      subtasks: [payload.subtask],
      active_subtask_index: 0,
    }),
    dirty: true,
  });
  setStatus("已创建新子任务");
  if (payload.subtask.map_url) {
    await loadMap(payload.subtask.map_url);
  }
}

function readMetaInputs(fallbackMeta = {}) {
  return {
    subtask_name: el.subtaskName.value.trim() || fallbackMeta.subtask_name || "new_subtask",
    map_url: el.mapPath.value.trim(),
    pcd_url: el.pcdUrl.value.trim(),
    change_loc: el.changeLoc.checked,
  };
}

function documentWithCurrentMeta() {
  if (!state.document) {
    return null;
  }
  return {
    ...state.document,
    meta: {
      ...state.document.meta,
      ...readMetaInputs(state.document.meta),
    },
  };
}

async function saveSubtask(pathOverride = null) {
  if (!state.document) {
    throw new Error("当前没有子任务");
  }
  const document = documentWithCurrentMeta();
  dispatch({ type: "UPDATE_META", patch: document.meta });
  const path = pathOverride || el.subtaskPath.value.trim() || state.taskPath;
  if (!path) {
    throw new Error("请填写保存路径");
  }
  const subtask = subtaskFromDocument(document);
  const taskPayload = taskPayloadFromState(state, document);
  const payload = await postJson("/subtask-composer/api/save", {
    path,
    subtask,
    ...taskPayload,
  });
  const documents = subtaskDocumentsFromPayload(payload);
  dispatch({
    type: "SET_TASK_DOCUMENT",
    taskPath: payload.path,
    ...documents,
  });
  setStatus(`保存成功：${payload.path}`);
}

async function saveSubtaskAs() {
  const path = window.prompt("保存为 JSON 绝对路径", el.subtaskPath.value || state.taskPath || "");
  if (!path) {
    return;
  }
  await saveSubtask(path);
}

async function buildReturnSubtask() {
  if (!state.document) {
    throw new Error("当前没有子任务");
  }
  const document = documentWithCurrentMeta();
  dispatch({ type: "UPDATE_META", patch: document.meta });
  const currentPath = el.subtaskPath.value.trim() || state.taskPath;
  const defaultPath = currentPath.replace(/\.json$/i, "_r.json") || "";
  const outputPath = window.prompt("返程子任务保存路径", defaultPath);
  if (!outputPath) {
    return;
  }
  const subtaskName = window.prompt(
    "返程子任务名称",
    `${el.subtaskName.value.trim() || state.document.meta.subtask_name || "subtask"}_r`,
  );
  if (!subtaskName) {
    return;
  }
  const waypointPrefix = window.prompt("返程 waypoint_id 前缀", `${subtaskName.replace(/_r$/, "")}_back`);
  const payload = await postJson("/subtask-composer/api/build_return", {
    subtask: subtaskFromDocument(document),
    subtask_name: subtaskName,
    waypoint_prefix: waypointPrefix,
    output_path: outputPath,
  });
  setStatus(`返程子任务已生成：${payload.path || outputPath}`);
}

function applyPointEdit() {
  const index = state.selectedIndex;
  if (index < 0) {
    return;
  }
  dispatch({
    type: "MOVE_ANCHOR",
    index,
    point: {
      x: Number(el.fieldX.value),
      y: Number(el.fieldY.value),
      z: Number(el.fieldZ.value),
    },
  });
  dispatch({
    type: "SET_ANCHOR_YAW",
    index,
    yaw: Number(el.fieldYaw.value),
  });
  dispatch({
    type: "UPDATE_SELECTED_TASK_ATTR",
    patch: {
      waypoint_id: el.waypointId.value.trim(),
      speed_mode: el.speedMode.value.trim() || "task_point",
      waypoint_task_id: el.isTaskPoint.checked ? el.waypointTaskId.value.trim() : "",
      is_task_point: el.isTaskPoint.checked,
      is_single_point: el.isSinglePoint.checked,
      is_backward: el.isBackward.checked,
    },
  });
  setStatus("点属性已更新");
}

async function loadAttributes() {
  const params = new URLSearchParams();
  if (state.defaultWaypointTasksPath) {
    params.set("waypoint_tasks_path", state.defaultWaypointTasksPath);
  }
  if (state.defaultSpeedModesPath) {
    params.set("speed_modes_path", state.defaultSpeedModesPath);
  }
  const query = params.toString();
  const response = await fetch(`/subtask-composer/api/attributes${query ? `?${query}` : ""}`);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  state.waypointTasks = payload.waypoint_tasks || [];
  state.speedModes = payload.speed_modes || [];
  state.speedModesSingle = payload.speed_modes_single || [];
  renderEditor();
}

function flipSelectedYaw() {
  const anchor = selectedAnchor();
  if (!anchor) {
    return;
  }
  dispatch({
    type: "SET_ANCHOR_YAW",
    index: state.selectedIndex,
    yaw: Number(anchor.yaw || 0) + Math.PI,
  });
}

function applyOffset() {
  if (!state.document) {
    return;
  }
  const dx = Number(el.offsetX.value || 0);
  const dy = Number(el.offsetY.value || 0);
  dispatch({ type: "OFFSET_ANCHORS", dx, dy });
}

async function browse(path = state.browseCwd) {
  const payload = await postJson("/subtask-composer/api/browse", { path });
  state.browseCwd = payload.cwd;
  el.pickerCwd.textContent = payload.cwd;
  el.pickerList.innerHTML = "";
  payload.entries.forEach((entry) => {
    const item = document.createElement("div");
    item.className = "picker-entry";
    const isJson = entry.is_json;
    const isYaml = entry.is_yaml;
    const selectable =
      entry.is_dir
      || (state.pickerMode === "subtask" && isJson)
      || (state.pickerMode === "map" && isYaml);
    item.dataset.clickable = selectable ? "true" : "false";
    item.textContent = `${entry.is_dir ? "[目录]" : "[文件]"} ${entry.name}`;
    item.addEventListener("click", () => {
      if (entry.is_dir) {
        browse(entry.path).catch((error) => setStatus(error.message, true));
        return;
      }
      if (state.pickerMode === "subtask" && isJson) {
        el.subtaskPath.value = entry.path;
        closePicker();
      } else if (state.pickerMode === "map" && isYaml) {
        el.mapPath.value = entry.path;
        closePicker();
      }
    });
    el.pickerList.appendChild(item);
  });
}

function openPicker(mode) {
  state.pickerMode = mode;
  el.pickerTitle.textContent = mode === "map" ? "选择地图 YAML" : "选择子任务 JSON";
  el.pickerSelectDir.style.display = mode === "save-dir" ? "" : "none";
  el.pickerOverlay.classList.add("visible");
  const startPath = mode === "map"
    ? el.mapPath.value.trim() || state.defaultRoot
    : el.subtaskPath.value.trim() || state.defaultRoot;
  browse(startPath).catch((error) => setStatus(error.message, true));
}

function closePicker() {
  el.pickerOverlay.classList.remove("visible");
}

function installResizer() {
  let dragging = false;
  el.editorResizer.addEventListener("pointerdown", (event) => {
    dragging = true;
    el.editorResizer.setPointerCapture(event.pointerId);
  });
  el.editorResizer.addEventListener("pointermove", (event) => {
    if (!dragging) {
      return;
    }
    const rect = el.editor.getBoundingClientRect();
    dispatch({ type: "SET_EDITOR_PANEL_WIDTH", width: rect.right - event.clientX });
  });
  el.editorResizer.addEventListener("pointerup", (event) => {
    dragging = false;
    if (el.editorResizer.hasPointerCapture(event.pointerId)) {
      el.editorResizer.releasePointerCapture(event.pointerId);
    }
  });
}

async function init() {
  const config = await fetch("/subtask-composer/api/runtime_config").then((response) => response.json());
  state.defaultRoot = config.default_root || "/";
  state.browseCwd = state.defaultRoot;
  state.defaultWaypointTasksPath = config.default_waypoint_tasks_path || "";
  state.defaultSpeedModesPath = config.default_speed_modes_path || "";
  el.subtaskPath.value = `${state.defaultRoot}/data/tasks/multi_tasks`;
  installResizer();
  pathCanvas.resize();
  await loadAttributes();
  render();
}

el.toolButtons.forEach((button) => {
  button.addEventListener("click", () => dispatch({ type: "SET_TOOL", tool: button.dataset.tool }));
});
el.browseSubtask.addEventListener("click", () => openPicker("subtask"));
el.browseMap.addEventListener("click", () => openPicker("map"));
el.loadSubtask.addEventListener("click", () => runButton(el.loadSubtask, { pending: "打开中...", success: "已打开", failure: "打开失败" }, loadSubtask));
el.newSubtask.addEventListener("click", () => runButton(el.newSubtask, { pending: "新建中...", success: "已新建", failure: "新建失败" }, newSubtask));
el.loadMap.addEventListener("click", () => runButton(el.loadMap, { pending: "加载中...", success: "已加载", failure: "加载失败" }, () => loadMap(el.mapPath.value.trim())));
el.saveSubtask.addEventListener("click", () => runButton(el.saveSubtask, { pending: "保存中...", success: "已保存", failure: "保存失败" }, () => saveSubtask()));
el.saveSubtaskAs.addEventListener("click", () => runButton(el.saveSubtaskAs, { pending: "另存中...", success: "已保存", failure: "另存失败" }, saveSubtaskAs));
el.buildReturn.addEventListener("click", () => runButton(el.buildReturn, { pending: "生成中...", success: "已生成", failure: "生成失败" }, buildReturnSubtask));
el.applyPoint.addEventListener("click", applyPointEdit);
el.flipYaw.addEventListener("click", flipSelectedYaw);
el.isSinglePoint.addEventListener("change", () => {
  renderAttributeSelects({
    ...(selectedAnchor() || {}),
    task: {
      ...(selectedAnchor()?.task || {}),
      is_single_point: el.isSinglePoint.checked,
      speed_mode: el.speedMode.value,
    },
  });
});
el.isTaskPoint.addEventListener("change", () => {
  el.waypointTaskId.disabled = !el.isTaskPoint.checked;
  if (!el.isTaskPoint.checked) {
    el.waypointTaskId.value = "";
  }
});
el.applyOffset.addEventListener("click", applyOffset);
el.toggleEditor.addEventListener("click", () => dispatch({ type: "TOGGLE_EDITOR_PANEL" }));
el.toggleFilePanel.addEventListener("click", () => dispatch({ type: "TOGGLE_FILE_PANEL" }));
el.pickerClose.addEventListener("click", closePicker);
el.pickerUp.addEventListener("click", () => {
  const parent = state.browseCwd === "/" ? "/" : state.browseCwd.split("/").slice(0, -1).join("/") || "/";
  browse(parent).catch((error) => setStatus(error.message, true));
});
el.pickerSelectDir.addEventListener("click", () => closePicker());
window.addEventListener("resize", () => pathCanvas.resize());
window.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && !event.shiftKey) {
    event.preventDefault();
    dispatch({ type: "UNDO" });
  }
});

init().catch((error) => setStatus(error.message, true));
