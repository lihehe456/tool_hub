export function buildOutdoorPcdToPgmPayload(values) {
  return {
    pcd_path: String(values.pcdPath ?? "").trim(),
    trajectory_pcd_path: String(values.trajectoryPath ?? "").trim(),
    output_dir: String(values.outputDir ?? "").trim(),
    map_name: String(values.mapName ?? "").trim(),
    z_min: Number(values.zMin),
    z_max: Number(values.zMax),
    resolution: Number(values.resolution),
    radius: Number(values.radius),
    min_neighbors: Number(values.minNeighbors),
    sensor_height: Number(values.sensorHeight),
    trajectory_search_radius: Number(values.trajectorySearchRadius),
    flag_pass_through: Boolean(values.flagPassThrough),
  };
}

const state = { defaultRoot: "/", browseCwd: "/", pickerMode: "pcd" };
const el = typeof document === "undefined" ? {} : {
  pcdPath: document.querySelector("#pcd-path"),
  trajectoryPath: document.querySelector("#trajectory-path"),
  outputDir: document.querySelector("#output-dir"),
  mapName: document.querySelector("#map-name"),
  zMin: document.querySelector("#z-min"),
  zMax: document.querySelector("#z-max"),
  resolution: document.querySelector("#resolution"),
  radius: document.querySelector("#radius"),
  minNeighbors: document.querySelector("#min-neighbors"),
  sensorHeight: document.querySelector("#sensor-height"),
  trajectorySearchRadius: document.querySelector("#trajectory-search-radius"),
  flagPassThrough: document.querySelector("#flag-pass-through"),
  status: document.querySelector("#outdoor-status"),
  previewImage: document.querySelector("#preview-image"),
  rawPointCount: document.querySelector("#raw-point-count"),
  filteredPointCount: document.querySelector("#filtered-point-count"),
  mapSize: document.querySelector("#map-size"),
  mapOrigin: document.querySelector("#map-origin"),
  trajectoryUsed: document.querySelector("#trajectory-used"),
  warnings: document.querySelector("#warnings"),
  exportedFiles: document.querySelector("#exported-files"),
  browsePcd: document.querySelector("#browse-pcd"),
  browseTrajectory: document.querySelector("#browse-trajectory"),
  browseOutput: document.querySelector("#browse-output"),
  previewButton: document.querySelector("#preview-button"),
  exportButton: document.querySelector("#export-button"),
  previewZoomOut: document.querySelector("#preview-zoom-out"),
  previewZoomIn: document.querySelector("#preview-zoom-in"),
  previewReset: document.querySelector("#preview-reset"),
  previewScale: document.querySelector("#preview-scale"),
  previewViewerOverlay: document.querySelector("#preview-viewer-overlay"),
  previewViewerImage: document.querySelector("#preview-viewer-image"),
  previewViewerTitle: document.querySelector("#preview-viewer-title"),
  previewViewerClose: document.querySelector("#preview-viewer-close"),
  previewViewerFrame: document.querySelector("#preview-viewer-frame"),
  previewViewerZoomOut: document.querySelector("#preview-viewer-zoom-out"),
  previewViewerZoomIn: document.querySelector("#preview-viewer-zoom-in"),
  previewViewerReset: document.querySelector("#preview-viewer-reset"),
  previewViewerScale: document.querySelector("#preview-viewer-scale"),
  pickerOverlay: document.querySelector("#picker-overlay"),
  pickerTitle: document.querySelector("#picker-title"),
  pickerCwd: document.querySelector("#picker-cwd"),
  pickerList: document.querySelector("#picker-list"),
  pickerSelectDir: document.querySelector("#picker-select-dir"),
  pickerClose: document.querySelector("#picker-close"),
};

export function createOutdoorPreviewZoom({inlineImage, viewerImage, scaleLabel, viewerScaleLabel}) {
  let scale = 1;
  const clamp = (value) => Math.max(0.25, Math.min(8, value));

  const apply = () => {
    const percent = `${Math.round(scale * 100)}%`;
    if (inlineImage) {
      inlineImage.style.width = percent;
      inlineImage.style.maxWidth = "none";
    }
    if (viewerImage) {
      viewerImage.style.width = percent;
      viewerImage.style.maxWidth = "none";
    }
    if (scaleLabel) scaleLabel.textContent = percent;
    if (viewerScaleLabel) viewerScaleLabel.textContent = percent;
  };

  apply();
  return {
    zoomIn() {
      scale = clamp(scale * 1.25);
      apply();
    },
    zoomOut() {
      scale = clamp(scale / 1.25);
      apply();
    },
    reset() {
      scale = 1;
      apply();
    },
  };
}

export function bindOutdoorPreviewViewer(elements) {
  const {previewImage, viewerOverlay, viewerImage, viewerClose, viewerTitle, viewerFrame} = elements;
  if (!previewImage || !viewerOverlay || !viewerImage || !viewerClose) return;

  const closeViewer = () => {
    viewerOverlay.classList.remove("visible");
  };

  previewImage.addEventListener("click", () => {
    if (previewImage.dataset.ready !== "true" || !previewImage.src) return;
    viewerImage.src = previewImage.src;
    if (viewerTitle) viewerTitle.textContent = "地图预览";
    viewerOverlay.classList.add("visible");
    if (viewerFrame) {
      viewerFrame.scrollLeft = Math.max(0, (viewerImage.naturalWidth || viewerImage.width || 0) / 2 - viewerFrame.clientWidth / 2);
      viewerFrame.scrollTop = Math.max(0, (viewerImage.naturalHeight || viewerImage.height || 0) / 2 - viewerFrame.clientHeight / 2);
    }
  });

  viewerClose.addEventListener("click", closeViewer);
  viewerOverlay.addEventListener("click", (event) => {
    if (event.target === viewerOverlay) closeViewer();
  });
}

function setStatus(message, error = false) {
  el.status.textContent = message;
  el.status.dataset.error = error ? "true" : "false";
}

async function postJson(url, payload) {
  const response = await fetch(url, { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function payload() {
  return buildOutdoorPcdToPgmPayload({
    pcdPath: el.pcdPath.value,
    trajectoryPath: el.trajectoryPath.value,
    outputDir: el.outputDir.value,
    mapName: el.mapName.value,
    zMin: el.zMin.value,
    zMax: el.zMax.value,
    resolution: el.resolution.value,
    radius: el.radius.value,
    minNeighbors: el.minNeighbors.value,
    sensorHeight: el.sensorHeight.value,
    trajectorySearchRadius: el.trajectorySearchRadius.value,
    flagPassThrough: el.flagPassThrough.checked,
  });
}

function renderResult(result) {
  el.previewImage.src = `data:image/png;base64,${result.preview_png_base64}`;
  el.previewImage.dataset.ready = "true";
  el.rawPointCount.textContent = String(result.raw_point_count);
  el.filteredPointCount.textContent = String(result.filtered_point_count);
  el.mapSize.textContent = `${result.width} x ${result.height}, resolution=${result.resolution}`;
  el.mapOrigin.textContent = `[${result.origin.join(", ")}]`;
  el.trajectoryUsed.textContent = result.trajectory_used ? "是" : "否";
  el.warnings.innerHTML = (result.warnings || []).map((warning) => `<div>提示：${warning}</div>`).join("");
}

async function browse(path = state.browseCwd) {
  const data = await postJson("/outdoor-pcd-to-pgm/api/browse", {path});
  state.browseCwd = data.cwd;
  el.pickerCwd.textContent = data.cwd;
  el.pickerList.innerHTML = "";
  if (data.parent && data.parent !== data.cwd) {
    const up = document.createElement("button");
    up.type = "button"; up.className = "picker-entry"; up.textContent = "..";
    up.addEventListener("click", () => browse(data.parent));
    el.pickerList.appendChild(up);
  }
  data.entries.forEach((entry) => {
    if (!entry.is_dir && state.pickerMode !== "output" && !entry.is_pcd) return;
    if (!entry.is_dir && state.pickerMode === "output") return;
    const button = document.createElement("button");
    button.type = "button"; button.className = "picker-entry";
    button.textContent = entry.is_dir ? `[DIR] ${entry.name}` : entry.name;
    button.addEventListener("click", () => {
      if (entry.is_dir) { browse(entry.path); return; }
      if (state.pickerMode === "pcd") el.pcdPath.value = entry.path;
      if (state.pickerMode === "trajectory") el.trajectoryPath.value = entry.path;
      closePicker();
    });
    el.pickerList.appendChild(button);
  });
}

function openPicker(mode) {
  state.pickerMode = mode;
  el.pickerTitle.textContent = mode === "output" ? "选择输出目录" : "选择 PCD 文件";
  el.pickerSelectDir.disabled = mode !== "output";
  el.pickerOverlay.classList.add("visible");
  const current = mode === "output" ? el.outputDir.value : (mode === "trajectory" ? el.trajectoryPath.value : el.pcdPath.value);
  browse(current.trim() || state.browseCwd).catch((error) => setStatus(error.message, true));
}

function closePicker() { el.pickerOverlay.classList.remove("visible"); }

async function runAction(url, successMessage) {
  const start = await postJson(url, payload());
  if (!start.job_id) throw new Error("job_id is missing");
  const statusUrl = url.replace(/\/$/, "");
  while (true) {
    const response = await fetch(`${statusUrl}/${start.job_id}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.error || `HTTP ${response.status}`);
    setStatus(`${job.message || "处理中"} (${job.progress || 0}%)`);
    if (job.status === "completed") {
      renderResult(job.result.result);
  if (job.result.exported) {
        const exportedLines = [
          `PGM：${job.result.exported.pgm_path}`,
          `YAML：${job.result.exported.yaml_path}`,
        ];
        if (job.result.exported.trajectory_overlay_ppm_path) {
          exportedLines.push(`轨迹叠加图：${job.result.exported.trajectory_overlay_ppm_path}`);
        }
        el.exportedFiles.innerHTML = exportedLines.join("<br>");
      }
      setStatus(successMessage);
      return;
    }
    if (job.status === "failed") throw new Error(job.error || job.message || "处理失败");
    await new Promise((resolve) => window.setTimeout(resolve, 250));
  }
}

function bindActions() {
  const zoom = createOutdoorPreviewZoom({
    inlineImage: el.previewImage,
    viewerImage: el.previewViewerImage,
    scaleLabel: el.previewScale,
    viewerScaleLabel: el.previewViewerScale,
  });
  el.browsePcd.addEventListener("click", () => openPicker("pcd"));
  el.browseTrajectory.addEventListener("click", () => openPicker("trajectory"));
  el.browseOutput.addEventListener("click", () => openPicker("output"));
  el.pickerClose.addEventListener("click", closePicker);
  el.pickerSelectDir.addEventListener("click", () => { el.outputDir.value = state.browseCwd; closePicker(); });
  el.previewButton.addEventListener("click", () => runAction("/outdoor-pcd-to-pgm/api/preview_job", "预览已生成").catch((error) => setStatus(error.message, true)));
  el.exportButton.addEventListener("click", () => runAction("/outdoor-pcd-to-pgm/api/export_job", "PGM/YAML 已导出").catch((error) => setStatus(error.message, true)));
  el.previewZoomOut.addEventListener("click", zoom.zoomOut);
  el.previewZoomIn.addEventListener("click", zoom.zoomIn);
  el.previewReset.addEventListener("click", zoom.reset);
  el.previewViewerZoomOut.addEventListener("click", zoom.zoomOut);
  el.previewViewerZoomIn.addEventListener("click", zoom.zoomIn);
  el.previewViewerReset.addEventListener("click", zoom.reset);
  bindOutdoorPreviewViewer({
    previewImage: el.previewImage,
    viewerOverlay: el.previewViewerOverlay,
    viewerImage: el.previewViewerImage,
    viewerClose: el.previewViewerClose,
    viewerTitle: el.previewViewerTitle,
    viewerFrame: el.previewViewerFrame,
  });
}

async function init() {
  bindActions();
  try {
    const response = await fetch("/outdoor-pcd-to-pgm/api/runtime_config");
    if (!response.ok) throw new Error(`runtime config HTTP ${response.status}`);
    const config = await response.json();
    state.defaultRoot = config.default_root || "/";
    state.browseCwd = state.defaultRoot;
  } catch (error) {
    setStatus(`运行配置加载失败：${error.message}`, true);
  }
}

if (typeof document !== "undefined") {
  init();
}
