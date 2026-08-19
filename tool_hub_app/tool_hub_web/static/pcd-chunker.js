export function normalizeOptionalNumber(rawValue) {
  const text = String(rawValue ?? "").trim();
  if (!text) {
    return "";
  }
  return Number(text);
}

export function buildChunkerPayload(formValues) {
  return {
    pcd_path: String(formValues.pcdPath ?? "").trim(),
    output_dir: String(formValues.outputDir ?? "").trim(),
    chunk_size: Number(formValues.chunkSize),
    voxel_size: normalizeOptionalNumber(formValues.voxelSize),
    start_x: Number(formValues.startX),
    start_y: Number(formValues.startY),
    start_z: Number(formValues.startZ),
    workers: Number(formValues.workers),
    cache_mb: Number(formValues.cacheMb),
    map_category: String(formValues.mapCategory ?? "outdoor").trim() || "outdoor",
    loc_config_name: String(formValues.locConfigName ?? "").trim(),
    force: Boolean(formValues.force),
  };
}

export function renderChunkCardsMarkup(chunks) {
  if (!chunks.length) {
    return '<p class="panel-empty">当前参数下没有可导出的 chunk</p>';
  }
  return chunks.map((chunk) => `
    <article class="chunker-card">
      <strong>Chunk ${chunk.chunk_id}</strong>
      <div class="chunker-card-meta">grid=(${chunk.grid_x}, ${chunk.grid_y})</div>
      <div class="chunker-card-meta">points=${chunk.point_count}</div>
      <div class="chunker-card-meta">${chunk.file_name || chunk.file_path || ""}</div>
    </article>
  `).join("");
}

const state = {
  defaultRoot: "/",
  browseCwd: "/",
  pickerMode: "pcd",
};

const el = typeof document === "undefined" ? {} : {
  pcdPath: document.querySelector("#pcd-path"),
  outputDir: document.querySelector("#output-dir"),
  chunkSize: document.querySelector("#chunk-size"),
  voxelSize: document.querySelector("#voxel-size"),
  startX: document.querySelector("#start-x"),
  startY: document.querySelector("#start-y"),
  startZ: document.querySelector("#start-z"),
  workers: document.querySelector("#workers"),
  cacheMb: document.querySelector("#cache-mb"),
  mapCategory: document.querySelector("#map-category"),
  locConfigName: document.querySelector("#loc-config-name"),
  forceOverwrite: document.querySelector("#force-overwrite"),
  previewButton: document.querySelector("#preview-button"),
  exportButton: document.querySelector("#export-button"),
  browsePcd: document.querySelector("#browse-pcd"),
  browseOutput: document.querySelector("#browse-output"),
  status: document.querySelector("#chunker-status"),
  totalInputPoints: document.querySelector("#total-input-points"),
  totalOutputPoints: document.querySelector("#total-output-points"),
  chunkCount: document.querySelector("#chunk-count"),
  chunkSizeSummary: document.querySelector("#chunk-size-summary"),
  outputDirSummary: document.querySelector("#output-dir-summary"),
  locConfigSummary: document.querySelector("#loc-config-summary"),
  indexPreview: document.querySelector("#index-preview"),
  chunkList: document.querySelector("#chunk-list"),
  pickerOverlay: document.querySelector("#picker-overlay"),
  pickerTitle: document.querySelector("#picker-title"),
  pickerCwd: document.querySelector("#picker-cwd"),
  pickerList: document.querySelector("#picker-list"),
  pickerSelectDir: document.querySelector("#picker-select-dir"),
  pickerClose: document.querySelector("#picker-close"),
};

function setStatus(message, error = false) {
  el.status.textContent = message;
  el.status.dataset.error = error ? "true" : "false";
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function currentPayload() {
  return buildChunkerPayload({
    pcdPath: el.pcdPath.value,
    outputDir: el.outputDir.value,
    chunkSize: el.chunkSize.value,
    voxelSize: el.voxelSize.value,
    startX: el.startX.value,
    startY: el.startY.value,
    startZ: el.startZ.value,
    workers: el.workers.value,
    cacheMb: el.cacheMb.value,
    mapCategory: el.mapCategory.value,
    locConfigName: el.locConfigName.value,
    force: el.forceOverwrite.checked,
  });
}

function renderPreview(preview) {
  el.totalInputPoints.textContent = String(preview.total_input_points ?? "-");
  el.totalOutputPoints.textContent = String(preview.total_output_points ?? "-");
  el.chunkCount.textContent = String(preview.chunk_count ?? "-");
  el.chunkSizeSummary.textContent = preview.chunk_size ? `${preview.chunk_size} m` : "-";
  el.outputDirSummary.textContent = preview.output_dir || "-";
  el.indexPreview.textContent = preview.index_preview || "无 index 预览";
  el.chunkList.innerHTML = renderChunkCardsMarkup(preview.chunks || []);
}

function renderResult(result) {
  renderPreview(result.preview);
  el.locConfigSummary.textContent = result.loc_config?.path || "导出时生成";
}

async function fetchRuntimeConfig() {
  const response = await fetch("/pcd-chunker/api/runtime_config");
  const payload = await response.json();
  state.defaultRoot = payload.default_root || "/";
  state.browseCwd = state.defaultRoot;
}

async function browse(path = state.browseCwd) {
  const payload = await postJson("/pcd-chunker/api/browse", {path});
  state.browseCwd = payload.cwd;
  el.pickerCwd.textContent = payload.cwd;
  el.pickerList.innerHTML = "";

  if (payload.parent && payload.parent !== payload.cwd) {
    const up = document.createElement("button");
    up.type = "button";
    up.className = "picker-entry dir";
    up.textContent = "..";
    up.addEventListener("click", () => browse(payload.parent));
    el.pickerList.appendChild(up);
  }

  payload.entries.forEach((entry) => {
    if (!entry.is_dir && state.pickerMode === "pcd" && !entry.is_pcd) {
      return;
    }
    if (!entry.is_dir && state.pickerMode === "output") {
      return;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = `picker-entry ${entry.is_dir ? "dir" : "file"}`;
    button.textContent = entry.is_dir ? `[DIR] ${entry.name}` : entry.name;
    button.addEventListener("click", () => {
      if (entry.is_dir) {
        browse(entry.path);
        return;
      }
      el.pcdPath.value = entry.path;
      closePicker();
      setStatus(`已选择 ${entry.path}`);
    });
    el.pickerList.appendChild(button);
  });
}

function openPicker(mode) {
  state.pickerMode = mode;
  el.pickerTitle.textContent = mode === "pcd" ? "选择 PCD 文件" : "选择输出目录";
  el.pickerSelectDir.disabled = mode === "pcd";
  el.pickerOverlay.classList.add("visible");
  const startPath = mode === "pcd"
    ? (el.pcdPath.value.trim() || state.browseCwd)
    : (el.outputDir.value.trim() || state.browseCwd);
  browse(startPath).catch((error) => setStatus(error.message, true));
}

function closePicker() {
  el.pickerOverlay.classList.remove("visible");
}

async function runAction(url, successMessage) {
  const start = await postJson(url, currentPayload());
  if (!start.job_id) {
    throw new Error("job_id is missing");
  }
  const statusUrl = url.replace(/\/$/, "");
  while (true) {
    const response = await fetch(`${statusUrl}/${start.job_id}`);
    const job = await response.json();
    if (!response.ok) {
      throw new Error(job.error || `HTTP ${response.status}`);
    }
    setStatus(`${job.message || "处理中"} (${job.progress || 0}%)`);
    if (job.status === "completed") {
      renderResult(job.result);
      setStatus(successMessage);
      return;
    }
    if (job.status === "failed") {
      throw new Error(job.error || job.message || "处理失败");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 500));
  }
}

function initPage() {
  fetchRuntimeConfig().catch((error) => setStatus(error.message, true));
  el.browsePcd.addEventListener("click", () => openPicker("pcd"));
  el.browseOutput.addEventListener("click", () => openPicker("output"));
  el.pickerClose.addEventListener("click", closePicker);
  el.pickerOverlay.addEventListener("click", (event) => {
    if (event.target === el.pickerOverlay) {
      closePicker();
    }
  });
  el.pickerSelectDir.addEventListener("click", () => {
    if (state.pickerMode !== "output") {
      return;
    }
    el.outputDir.value = state.browseCwd;
    closePicker();
    setStatus(`已选择 ${state.browseCwd}`);
  });
  el.previewButton.addEventListener("click", async () => {
    try {
      el.locConfigSummary.textContent = "导出时生成";
      setStatus("正在生成分块预览...");
      await runAction("/pcd-chunker/api/preview_job", "分块预览已更新");
    } catch (error) {
      setStatus(error.message, true);
    }
  });
  el.exportButton.addEventListener("click", async () => {
    try {
      if (!el.locConfigName.value.trim()) {
        throw new Error("请填写定位配置文件名");
      }
      setStatus("正在导出分块结果...");
      await runAction("/pcd-chunker/api/export_job", "分块结果已导出");
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

if (typeof document !== "undefined") {
  initPage();
}
