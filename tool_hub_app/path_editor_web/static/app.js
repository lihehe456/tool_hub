import {
  addSubtaskPairToWorkspace,
  buildSubtasksFromPath,
  browseMaps,
  browsePaths,
  createTaskWorkspace,
  loadRuntimeConfig,
  loadTaskWorkspace,
  loadMap,
  loadPath,
  replaceSubtaskPairInWorkspace,
  savePath,
  savePathAs,
} from "./api.js";
import { installCanvasResizeSync } from "./canvas-resize.js";
import { PathCanvas } from "./canvas.js";
import { renderFileTree } from "./file-tree.js";
import { shouldAutoBrowseOnStartup } from "./startup-policy.js";
import { createInitialState, reduce } from "./state.js";
import {
  canCreateTaskWorkspace,
  canWriteSubtaskPairToWorkspace,
} from "./subtask-builder-state.js";
import {
  addAnchor,
  createEmptyDocument,
  deleteAnchor,
  deleteAnchors,
  exportCompatiblePath,
  importCompatiblePath,
  insertAnchor,
  moveAnchor,
  pushHistory,
  redo,
  setAnchorYaw,
  offsetDocument,
  undo,
  yawToQuaternion,
} from "./path-model.js";

const DEFAULT_PATHS_ROOT = "/";
const DEFAULT_MAPS_ROOT = "/";

const state = {
  app: createInitialState(),
  browser: {
    cwd: DEFAULT_PATHS_ROOT,
    parent: DEFAULT_PATHS_ROOT,
    entries: [],
  },
  maps: {
    cwd: DEFAULT_MAPS_ROOT,
    entries: [],
  },
  loadedMap: null,
};

const elements = {
  status: document.querySelector("#status"),
  topbar: document.querySelector("#topbar"),
  fileTree: document.querySelector("#file-tree"),
  mapTree: document.querySelector("#map-tree"),
  mapCanvas: document.querySelector("#map-canvas"),
  mapInfo: document.querySelector("#map-info"),
  pointInfo: document.querySelector("#point-info"),
  offsetX: document.querySelector("#offset-x"),
  offsetY: document.querySelector("#offset-y"),
  offsetButton: document.querySelector("#offset-path-button"),
  currentPath: document.querySelector("#current-path"),
  metaForm: document.querySelector("#meta-form"),
  drawMode: document.querySelector("#draw-mode"),
  toolButtons: Array.from(document.querySelectorAll("[data-tool]")),
  saveButton: document.querySelector("#save-button"),
  saveAsButton: document.querySelector("#save-as-button"),
  newButton: document.querySelector("#new-button"),
  openMapButton: document.querySelector("#open-map-button"),
  toggleTopbarButton: document.querySelector("#toggle-topbar-button"),
  workspacePath: document.querySelector("#workspace-path"),
  generateSubtasksButton: document.querySelector("#generate-subtasks-button"),
  createWorkspaceButton: document.querySelector("#create-workspace-button"),
  addSubtasksButton: document.querySelector("#add-subtasks-button"),
  replaceSubtasksButton: document.querySelector("#replace-subtasks-button"),
  subtaskBuilderStatus: document.querySelector("#subtask-builder-status"),
  subtaskPreview: document.querySelector("#subtask-preview"),
  taskGroupLink: document.querySelector("#task-group-link"),
};

const pathCanvas = new PathCanvas(elements.mapCanvas, {
  onAddAnchor(worldPoint) {
    if (!state.app.document) {
      return;
    }
    const nextAnchor = {
      x: worldPoint.x,
      y: worldPoint.y,
      z: 0,
      yaw: state.app.document.anchors.at(-1)?.yaw ?? 0,
    };
    const nextDocument = addAnchor(state.app.document, nextAnchor);
    dispatch({ type: "SET_DOCUMENT", document: pushHistory(state.app.document, nextDocument) });
  },
  onInsertAnchor(segmentIndex, worldPoint) {
    if (!state.app.document) {
      return;
    }
    const segment = state.app.document.segments?.[segmentIndex];
    const startAnchor = segment ? state.app.document.anchors?.[segment.startIndex] : null;
    const endAnchor = segment ? state.app.document.anchors?.[segment.endIndex] : null;
    if (!segment || !startAnchor || !endAnchor) {
      return;
    }
    const insertedAnchor = {
      x: worldPoint.x,
      y: worldPoint.y,
      z: 0,
      yaw: Math.atan2(endAnchor.y - startAnchor.y, endAnchor.x - startAnchor.x),
    };
    const insertIndex = segment.endIndex;
    const nextDocument = insertAnchor(state.app.document, insertIndex, insertedAnchor);
    dispatch({ type: "SET_DOCUMENT", document: pushHistory(state.app.document, nextDocument) });
    dispatch({ type: "SELECT_ELEMENT", selection: { kind: "anchor", index: insertIndex } });
  },
  onMoveAnchor(index, worldPoint) {
    if (!state.app.document) {
      return;
    }
    const nextDocument = moveAnchor(state.app.document, index, { x: worldPoint.x, y: worldPoint.y, z: 0 });
    dispatch({ type: "SET_DOCUMENT", document: nextDocument });
  },
  onRotateAnchor(index, yaw) {
    if (!state.app.document) {
      return;
    }
    const nextDocument = setAnchorYaw(state.app.document, index, yaw);
    dispatch({ type: "SET_DOCUMENT", document: nextDocument });
  },
  onDeleteAnchor(index) {
    if (!state.app.document) {
      return;
    }
    const nextDocument = deleteAnchor(state.app.document, index);
    dispatch({ type: "SET_DOCUMENT", document: pushHistory(state.app.document, nextDocument) });
  },
  onSelect(selection) {
    dispatch({ type: "SELECT_ELEMENT", selection });
  },
  onToggleAnchorSelection(index) {
    const selection = state.app.selection;
    const currentIndexes = selection.kind === "anchors"
      ? selection.indexes
      : selection.kind === "anchor"
        ? [selection.index]
        : [];
    const nextIndexes = currentIndexes.includes(index)
      ? currentIndexes.filter((item) => item !== index)
      : [...currentIndexes, index];
    dispatch({
      type: "SELECT_ELEMENT",
      selection: nextIndexes.length === 1
        ? { kind: "anchor", index: nextIndexes[0] }
        : { kind: "anchors", indexes: nextIndexes.sort((left, right) => left - right) },
    });
  },
});

function formatPointValue(value) {
  return Number(value ?? 0).toFixed(3);
}

function renderPointInfo() {
  if (!elements.pointInfo) {
    return;
  }
  const document = state.app.document;
  const selection = state.app.selection;
  if (!document || selection.kind !== "anchor") {
    if (document && selection.kind === "anchors" && selection.indexes?.length) {
      const ids = selection.indexes
        .filter((index) => document.anchors?.[index])
        .map((index) => `${document.meta.path_name}_${index}`);
      elements.pointInfo.textContent = `点信息：已选择 ${ids.length} 个点 | ${ids.join(", ")}`;
      return;
    }
    elements.pointInfo.textContent = "点信息：未选择路点";
    return;
  }

  const anchor = document.anchors?.[selection.index];
  if (!anchor) {
    elements.pointInfo.textContent = "点信息：未选择路点";
    return;
  }

  const waypointId = `${document.meta.path_name}_${selection.index}`;
  const quaternion = yawToQuaternion(anchor.yaw);
  elements.pointInfo.textContent = [
    `点id: ${waypointId}`,
    `位置: x=${formatPointValue(anchor.x)}, y=${formatPointValue(anchor.y)}, z=${formatPointValue(anchor.z)}`,
    `朝向: yaw=${formatPointValue(anchor.yaw)}, q=(${formatPointValue(quaternion.x)}, ${formatPointValue(quaternion.y)}, ${formatPointValue(quaternion.z)}, ${formatPointValue(quaternion.w)})`,
  ].join(" | ");
}

function setStatus(message, isError = false) {
  elements.status.textContent = message;
  elements.status.dataset.error = isError ? "true" : "false";
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

function dispatch(action) {
  state.app = reduce(state.app, action);
  render();
}

function drawPlaceholder() {
  const canvas = elements.mapCanvas;
  const context = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(rect.width));
  canvas.height = Math.max(1, Math.floor(rect.height));

  context.fillStyle = "#0f1418";
  context.fillRect(0, 0, canvas.width, canvas.height);

  context.strokeStyle = "#25323d";
  context.lineWidth = 1;
  for (let x = 0; x < canvas.width; x += 32) {
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, canvas.height);
    context.stroke();
  }
  for (let y = 0; y < canvas.height; y += 32) {
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(canvas.width, y);
    context.stroke();
  }

  context.fillStyle = "#9bb0c3";
  context.font = "16px monospace";
  context.fillText("地图画布（下一步接入交互绘制）", 24, 36);
}

function fillMetaForm() {
  const form = elements.metaForm;
  const meta = state.app.document?.meta ?? createEmptyDocument().meta;
  for (const input of form.querySelectorAll("[name]")) {
    input.value = meta[input.name] ?? "";
  }
}

function renderMapInfo() {
  if (state.loadedMap) {
    elements.mapInfo.textContent = `${state.app.mapPath || "未命名地图"} | ${state.loadedMap.width} x ${state.loadedMap.height}`;
  } else {
    elements.mapInfo.textContent = "未加载地图";
  }
}

function renderSubtaskPreview() {
  const pair = state.app.generatedSubtaskPair;
  if (!pair) {
    elements.subtaskPreview.innerHTML = "<p class=\"panel-empty\">尚未生成子任务对</p>";
    return;
  }

  const cards = [
    ["去程子任务", pair.forwardSubtask],
    ["返程子任务", pair.returnSubtask],
  ];

  elements.subtaskPreview.innerHTML = cards
    .map(
      ([title, subtask]) => `
        <article class="subtask-card">
          <h3>${title}</h3>
          <p>${subtask.subtask_name}</p>
          <p>方向：${subtask.direction}</p>
          <p>路点数：${subtask.waypoints?.length ?? 0}</p>
        </article>
      `,
    )
    .join("");
}

function defaultSubtaskNameForPath(path) {
  const filename = path.split("/").at(-1) ?? "subtask";
  return filename.replace(/\.json$/i, "") || "subtask";
}

function render() {
  state.browser.selectedPath = state.app.filePath;
  state.browser.fileFlag = "is_json";
  state.maps.selectedPath = state.app.mapPath;
  state.maps.fileFlag = "is_yaml";
  elements.topbar.classList.toggle("collapsed", state.app.topbarCollapsed);
  elements.toggleTopbarButton.textContent = state.app.topbarCollapsed ? "展开" : "收起";
  elements.toggleTopbarButton.setAttribute("aria-expanded", String(!state.app.topbarCollapsed));
  elements.toggleTopbarButton.setAttribute(
    "title",
    state.app.topbarCollapsed ? "展开顶部栏" : "折叠顶部栏",
  );
  elements.currentPath.textContent = state.app.filePath || "未打开路径";
  elements.drawMode.value = state.app.drawMode;
  elements.workspacePath.value = state.app.workspacePath;
  elements.taskGroupLink.href = state.app.taskGroupPageHref;
  elements.subtaskBuilderStatus.textContent =
    state.app.subtaskBuilderStatus.message || "等待生成子任务对";
  elements.subtaskBuilderStatus.dataset.error = state.app.subtaskBuilderStatus.error ? "true" : "false";
  fillMetaForm();
  renderMapInfo();
  renderPointInfo();
  renderSubtaskPreview();
  pathCanvas.setTool(state.app.activeTool);
  pathCanvas.setSelection(state.app.selection);
  pathCanvas.setDocument(state.app.document);

  const dirtySuffix = state.app.dirty ? " *" : "";
  document.title = `Path Editor Web${dirtySuffix}`;

  for (const button of elements.toolButtons) {
    button.dataset.active = button.dataset.tool === state.app.activeTool ? "true" : "false";
  }

  elements.generateSubtasksButton.disabled = !state.app.filePath;
  elements.createWorkspaceButton.disabled = !canCreateTaskWorkspace(state.app);
  elements.addSubtasksButton.disabled = !canWriteSubtaskPairToWorkspace(state.app);
  elements.replaceSubtasksButton.disabled = !canWriteSubtaskPairToWorkspace(state.app);
}

async function refreshFileTree(path = state.browser.cwd) {
  try {
    state.browser = await browsePaths(path);
    state.browser.selectedPath = state.app.filePath;
    state.browser.fileFlag = "is_json";
    renderFileTree(elements.fileTree, state.browser, {
      onBrowse: refreshFileTree,
      onOpen: openPath,
    });
    setStatus(`路径目录：${state.browser.cwd}`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function refreshMaps(path = state.maps.cwd) {
  try {
    state.maps = await browseMaps(path);
    state.maps.selectedPath = state.app.mapPath;
    state.maps.fileFlag = "is_yaml";
    renderFileTree(elements.mapTree, state.maps, {
      onBrowse: refreshMaps,
      onOpen: openMap,
    });
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function openPath(path) {
  try {
    const rawDocument = await loadPath(path);
    const document = importCompatiblePath(rawDocument);
    dispatch({ type: "OPEN_DOCUMENT", filePath: path, document });
    if (document.meta.map_url) {
      await openMap(document.meta.map_url);
    }
    setStatus(`已加载路径：${path}`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function openMap(path) {
  try {
    const mapPayload = await loadMap(path);
    const imageElement = new Image();
    imageElement.src = `data:image/png;base64,${mapPayload.image_b64}`;
    await imageElement.decode();
    state.loadedMap = {
      ...mapPayload,
      imageElement,
    };
    pathCanvas.setMapData(state.loadedMap);
    pathCanvas.setVirtualWalls(mapPayload.virtual_walls || []);
    dispatch({ type: "SET_MAP_PATH", mapPath: path });
    state.app.dirty = false;
    await refreshMaps(state.maps.cwd);
    const wallMessage = mapPayload.virtual_wall_path ? `，已叠加虚拟墙：${mapPayload.virtual_wall_path}` : "";
    setStatus(`已加载地图：${path}${wallMessage}`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function handleSave() {
  if (!state.app.document || !state.app.filePath) {
    setStatus("当前没有可保存的路径", true);
    return;
  }

  try {
    await runButtonFeedback(
      elements.saveButton,
      { pending: "保存中...", success: "已保存", failure: "保存失败" },
      async () => {
        setStatus("正在保存路径...");
        await savePath(state.app.filePath, exportCompatiblePath(state.app.document));
        dispatch({ type: "SAVE_SUCCESS" });
        setStatus(`保存成功：${state.app.filePath}`);
        await refreshFileTree(state.browser.cwd);
      },
    );
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function handleSaveAs() {
  if (!state.app.document) {
    setStatus("当前没有可保存的路径", true);
    return;
  }

  const target = window.prompt(
    "请输入另存为路径",
    state.app.filePath || `${state.browser.cwd || DEFAULT_PATHS_ROOT}/untitled/new-path.json`,
  );
  if (!target) {
    return;
  }

  try {
    await runButtonFeedback(
      elements.saveAsButton,
      { pending: "另存中...", success: "已另存", failure: "另存失败" },
      async () => {
        setStatus("正在另存为...");
        await savePathAs(target, exportCompatiblePath(state.app.document));
        dispatch({ type: "SAVE_AS_SUCCESS", filePath: target });
        setStatus(`另存为成功：${target}`);
        await refreshFileTree(state.browser.cwd);
      },
    );
  } catch (error) {
    setStatus(error.message, true);
  }
}

function handleNewDocument() {
  const emptyDocument = createEmptyDocument();
  dispatch({ type: "OPEN_DOCUMENT", filePath: "", document: emptyDocument });
  dispatch({ type: "CLEAR_GENERATED_SUBTASK_PAIR" });
  state.loadedMap = null;
  pathCanvas.setVirtualWalls([]);
  setStatus("已创建空白路径");
}

async function handleGenerateSubtasks() {
  if (!state.app.filePath) {
    dispatch({ type: "SET_SUBTASK_BUILDER_STATUS", message: "请先打开路径文件", error: true });
    return;
  }

  try {
    const generatedSubtaskName = defaultSubtaskNameForPath(state.app.filePath);
    const payload = await buildSubtasksFromPath(state.app.filePath, generatedSubtaskName);
    dispatch({
      type: "SET_GENERATED_SUBTASK_PAIR",
      pair: {
        forwardSubtask: payload.forward_subtask,
        returnSubtask: payload.return_subtask,
      },
    });
    dispatch({
      type: "SET_SUBTASK_BUILDER_STATUS",
      message: "子任务对生成成功",
      error: false,
    });
  } catch (error) {
    dispatch({
      type: "SET_SUBTASK_BUILDER_STATUS",
      message: error.message,
      error: true,
    });
  }
}

async function handleAddSubtasks() {
  if (!state.app.workspacePath || !state.app.generatedSubtaskPair) {
    dispatch({
      type: "SET_SUBTASK_BUILDER_STATUS",
      message: "请先填写工作区文件并生成子任务对",
      error: true,
    });
    return;
  }

  try {
    await addSubtaskPairToWorkspace(
      state.app.workspacePath,
      state.app.generatedSubtaskPair.forwardSubtask,
      state.app.generatedSubtaskPair.returnSubtask,
    );
    dispatch({
      type: "SET_SUBTASK_BUILDER_STATUS",
      message: "子任务对已加入工作区",
      error: false,
    });
  } catch (error) {
    dispatch({
      type: "SET_SUBTASK_BUILDER_STATUS",
      message: error.message,
      error: true,
    });
  }
}

async function handleCreateWorkspace() {
  if (!state.app.workspacePath) {
    dispatch({
      type: "SET_SUBTASK_BUILDER_STATUS",
      message: "请先填写工作区文件",
      error: true,
    });
    return;
  }

  try {
    const payload = await createTaskWorkspace(state.app.workspacePath);
    dispatch({
      type: "SET_SUBTASK_BUILDER_STATUS",
      message: payload.created ? "工作区文件已生成" : "工作区文件已就绪",
      error: false,
    });
  } catch (error) {
    dispatch({
      type: "SET_SUBTASK_BUILDER_STATUS",
      message: error.message,
      error: true,
    });
  }
}

function handleOffsetPath() {
  if (!state.app.document) {
    setStatus("当前没有可偏移的路径", true);
    return;
  }
  const dx = Number(elements.offsetX.value || 0);
  const dy = Number(elements.offsetY.value || 0);
  if (!Number.isFinite(dx) || !Number.isFinite(dy)) {
    setStatus("偏移量必须是数字", true);
    return;
  }
  if (Math.abs(dx) < 1e-12 && Math.abs(dy) < 1e-12) {
    setStatus("偏移量为 0，路径未变化");
    return;
  }
  const nextDocument = offsetDocument(state.app.document, { x: dx, y: dy, z: 0 });
  dispatch({ type: "SET_DOCUMENT", document: pushHistory(state.app.document, nextDocument) });
  setStatus(`路径已整体偏移：dx=${dx}, dy=${dy}`);
}

async function handleReplaceSubtasks() {
  if (!state.app.workspacePath || !state.app.generatedSubtaskPair || !state.app.filePath) {
    dispatch({
      type: "SET_SUBTASK_BUILDER_STATUS",
      message: "请先填写工作区文件并生成子任务对",
      error: true,
    });
    return;
  }

  try {
    const workspacePayload = await loadTaskWorkspace(state.app.workspacePath);
    const existingPair = (workspacePayload.workspace.subtasks ?? []).find(
      (subtask) => subtask.source_path === state.app.filePath && subtask.direction === "forward",
    );

    if (!existingPair?.pair_id) {
      throw new Error("工作区中未找到同源对子任务");
    }

    await replaceSubtaskPairInWorkspace(
      state.app.workspacePath,
      existingPair.pair_id,
      state.app.generatedSubtaskPair.forwardSubtask,
      state.app.generatedSubtaskPair.returnSubtask,
    );
    dispatch({
      type: "SET_SUBTASK_BUILDER_STATUS",
      message: "工作区中的同源对子任务已替换",
      error: false,
    });
  } catch (error) {
    dispatch({
      type: "SET_SUBTASK_BUILDER_STATUS",
      message: error.message,
      error: true,
    });
  }
}

function bindEvents() {
  elements.metaForm.addEventListener("input", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) {
      return;
    }
    const value = target.type === "number" ? Number(target.value) : target.value;
    dispatch({ type: "UPDATE_META", patch: { [target.name]: value } });
  });

  elements.drawMode.addEventListener("change", (event) => {
    dispatch({ type: "SET_DRAW_MODE", drawMode: event.target.value });
  });

  elements.toolButtons.forEach((button) => {
    button.addEventListener("click", () => {
      dispatch({ type: "SET_TOOL", tool: button.dataset.tool });
    });
  });

  elements.saveButton.addEventListener("click", handleSave);
  elements.saveAsButton.addEventListener("click", handleSaveAs);
  elements.newButton.addEventListener("click", handleNewDocument);
  elements.workspacePath.addEventListener("change", () => {
    dispatch({ type: "SET_WORKSPACE_PATH", workspacePath: elements.workspacePath.value.trim() });
  });
  elements.generateSubtasksButton.addEventListener("click", handleGenerateSubtasks);
  elements.createWorkspaceButton.addEventListener("click", handleCreateWorkspace);
  elements.addSubtasksButton.addEventListener("click", handleAddSubtasks);
  elements.replaceSubtasksButton.addEventListener("click", handleReplaceSubtasks);
  elements.offsetButton.addEventListener("click", handleOffsetPath);
  elements.toggleTopbarButton.addEventListener("click", () => {
    dispatch({ type: "TOGGLE_TOPBAR" });
  });
  elements.openMapButton.addEventListener("click", async () => {
    const mapPath = window.prompt(
      "请输入地图 YAML 路径",
      state.app.document?.meta?.map_url || `${state.maps.cwd || DEFAULT_MAPS_ROOT}/map.yaml`,
    );
    if (mapPath) {
      await openMap(mapPath);
    }
  });

  installCanvasResizeSync({
    target: elements.mapCanvas.parentElement,
    pathCanvas,
  });
  window.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
      event.preventDefault();
      if (!state.app.document) {
        return;
      }
      if (event.shiftKey) {
        dispatch({ type: "SET_DOCUMENT", document: redo(state.app.document), markDirty: true });
      } else {
        dispatch({ type: "SET_DOCUMENT", document: undo(state.app.document), markDirty: true });
      }
      return;
    }

    if (event.key === "Delete" && ["anchor", "anchors"].includes(state.app.selection.kind)) {
      if (!state.app.document) {
        return;
      }
      const indexes = state.app.selection.kind === "anchors"
        ? state.app.selection.indexes
        : [state.app.selection.index];
      const nextDocument = indexes.length > 1
        ? deleteAnchors(state.app.document, indexes)
        : deleteAnchor(state.app.document, indexes[0]);
      dispatch({ type: "SET_DOCUMENT", document: pushHistory(state.app.document, nextDocument) });
      dispatch({ type: "SELECT_ELEMENT", selection: { kind: "none" } });
      return;
    }

    if (event.code === "Space") {
      event.preventDefault();
      dispatch({
        type: "SET_TOOL",
        tool: state.app.activeTool === "add" ? "select" : "add",
      });
    }
  });
}

async function bootstrap() {
  bindEvents();
  const runtimeConfig = await loadRuntimeConfig();
  state.browser.cwd = runtimeConfig.paths_root || DEFAULT_PATHS_ROOT;
  state.browser.parent = runtimeConfig.paths_root || DEFAULT_PATHS_ROOT;
  state.maps.cwd = runtimeConfig.maps_root || DEFAULT_MAPS_ROOT;
  pathCanvas.resize();
  render();
  if (shouldAutoBrowseOnStartup(runtimeConfig)) {
    await Promise.all([refreshFileTree(), refreshMaps()]);
  }
}

bootstrap().catch((error) => {
  setStatus(error.message, true);
});
