const state = {
  defaultRoot: "/",
  browseCwd: "/",
  pickerMode: "pcd",
  slices: [],
  previews: [],
  selectedSliceId: "",
};

const el = {
  pcdPath: document.querySelector("#pcd-path"),
  outputDir: document.querySelector("#output-dir"),
  mapName: document.querySelector("#map-name"),
  resolution: document.querySelector("#resolution"),
  radius: document.querySelector("#radius"),
  minNeighbors: document.querySelector("#min-neighbors"),
  flagPassThrough: document.querySelector("#flag-pass-through"),
  transform: document.querySelector("#transform"),
  status: document.querySelector("#pcd-status"),
  sliceList: document.querySelector("#slice-list"),
  previewList: document.querySelector("#preview-list"),
  browsePcd: document.querySelector("#browse-pcd"),
  browseOutput: document.querySelector("#browse-output"),
  addSlice: document.querySelector("#add-slice"),
  previewSlices: document.querySelector("#preview-slices"),
  exportSelected: document.querySelector("#export-selected"),
  pickerOverlay: document.querySelector("#picker-overlay"),
  pickerTitle: document.querySelector("#picker-title"),
  pickerCwd: document.querySelector("#picker-cwd"),
  pickerList: document.querySelector("#picker-list"),
  pickerSelectDir: document.querySelector("#picker-select-dir"),
  pickerUp: document.querySelector("#picker-up"),
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

function parseTransform() {
  const values = el.transform.value.split(",").map((item) => Number(item.trim()));
  if (values.length !== 6 || values.some((value) => Number.isNaN(value))) {
    throw new Error("odom_to_lidar_odom 需要 6 个数字，用英文逗号分隔");
  }
  return values;
}

function basePayload() {
  return {
    pcd_path: el.pcdPath.value.trim(),
    resolution: Number(el.resolution.value),
    radius: Number(el.radius.value),
    min_neighbors: Number(el.minNeighbors.value),
    flag_pass_through: el.flagPassThrough.checked,
    odom_to_lidar_odom: parseTransform(),
  };
}

function addSlice(zMin = 0, zMax = 1) {
  state.slices.push({
    id: `slice-${Date.now()}-${state.slices.length}`,
    z_min: zMin,
    z_max: zMax,
  });
  renderSlices();
}

function renderSlices() {
  el.sliceList.innerHTML = "";
  state.slices.forEach((slice, index) => {
    const row = document.createElement("div");
    row.className = "slice-row";
    row.innerHTML = `
      <label>
        <span>Z min</span>
        <input type="number" step="0.01" value="${slice.z_min}" data-field="z_min">
      </label>
      <label>
        <span>Z max</span>
        <input type="number" step="0.01" value="${slice.z_max}" data-field="z_max">
      </label>
      <button type="button">删除</button>
    `;
    row.querySelectorAll("input").forEach((input) => {
      input.addEventListener("input", () => {
        slice[input.dataset.field] = Number(input.value);
      });
    });
    row.querySelector("button").addEventListener("click", () => {
      state.slices.splice(index, 1);
      renderSlices();
    });
    el.sliceList.appendChild(row);
  });
}

function renderPreviews() {
  el.previewList.innerHTML = "";
  if (!state.previews.length) {
    el.previewList.innerHTML = '<p class="pcd-muted">暂无预览。</p>';
    return;
  }
  state.previews.forEach((preview) => {
    const card = document.createElement("article");
    card.className = "preview-card";
    card.dataset.selected = preview.id === state.selectedSliceId ? "true" : "false";
    card.innerHTML = `
      <strong>${preview.id}: Z [${preview.z_min}, ${preview.z_max}]</strong>
      <img alt="slice preview" src="data:image/png;base64,${preview.preview_png_base64}">
      <div class="preview-meta">
        points=${preview.point_count}, size=${preview.width}x${preview.height},
        resolution=${preview.resolution}, origin=[${preview.origin.join(", ")}]
      </div>
    `;
    card.addEventListener("click", () => {
      state.selectedSliceId = preview.id;
      renderPreviews();
      setStatus(`已选择 ${preview.id}`);
    });
    el.previewList.appendChild(card);
  });
}

async function browse(path = state.browseCwd) {
  const payload = await postJson("/pcd-to-map/api/browse", {path});
  state.browseCwd = payload.cwd;
  el.pickerCwd.textContent = payload.cwd;
  el.pickerList.innerHTML = "";
  payload.entries.forEach((entry) => {
    const item = document.createElement("div");
    item.className = "picker-entry";
    const selectableFile = state.pickerMode === "pcd" && entry.is_pcd;
    item.dataset.clickable = entry.is_dir || selectableFile ? "true" : "false";
    item.textContent = `${entry.is_dir ? "[目录]" : "[文件]"} ${entry.name}`;
    item.addEventListener("click", () => {
      if (entry.is_dir) {
        browse(entry.path).catch((error) => setStatus(error.message, true));
      } else if (selectableFile) {
        el.pcdPath.value = entry.path;
        closePicker();
      }
    });
    el.pickerList.appendChild(item);
  });
}

function openPicker(mode) {
  state.pickerMode = mode;
  el.pickerTitle.textContent = mode === "pcd" ? "选择 PCD 文件" : "选择输出目录";
  el.pickerSelectDir.style.display = mode === "output" ? "" : "none";
  el.pickerOverlay.classList.add("visible");
  browse(state.browseCwd || state.defaultRoot).catch((error) => setStatus(error.message, true));
}

function closePicker() {
  el.pickerOverlay.classList.remove("visible");
}

async function previewSlices() {
  const payload = {
    ...basePayload(),
    slices: state.slices.map((slice, index) => ({
      id: `slice-${index + 1}`,
      z_min: Number(slice.z_min),
      z_max: Number(slice.z_max),
    })),
  };
  const data = await postJson("/pcd-to-map/api/preview", payload);
  state.previews = data.slices;
  state.selectedSliceId = state.previews[0]?.id || "";
  renderPreviews();
  setStatus(`已生成 ${state.previews.length} 个切片预览`);
}

async function exportSelected() {
  const selected = state.previews.find((preview) => preview.id === state.selectedSliceId);
  if (!selected) {
    throw new Error("请先选择一个预览切片");
  }
  const data = await postJson("/pcd-to-map/api/export", {
    ...basePayload(),
    output_dir: el.outputDir.value.trim(),
    map_name: el.mapName.value.trim(),
    slice: {z_min: selected.z_min, z_max: selected.z_max},
  });
  setStatus(`导出成功: ${data.yaml_path}`);
}

async function withButton(button, pendingText, action) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = pendingText;
  try {
    await action();
    button.textContent = "完成";
  } catch (error) {
    setStatus(error.message, true);
    button.textContent = "失败";
  } finally {
    window.setTimeout(() => {
      button.textContent = original;
      button.disabled = false;
    }, 1200);
  }
}

async function init() {
  const response = await fetch("/pcd-to-map/api/runtime_config");
  const config = await response.json();
  state.defaultRoot = config.default_root || "/";
  state.browseCwd = state.defaultRoot;
  el.pcdPath.value = state.defaultRoot;
  el.outputDir.value = state.defaultRoot;
  addSlice(-10, 10);
  addSlice(0.1, 0.8);
  addSlice(0.8, 2.0);
  setStatus("准备就绪");
}

el.browsePcd.addEventListener("click", () => openPicker("pcd"));
el.browseOutput.addEventListener("click", () => openPicker("output"));
el.addSlice.addEventListener("click", () => addSlice(0, 1));
el.previewSlices.addEventListener("click", () => withButton(el.previewSlices, "预览中...", previewSlices));
el.exportSelected.addEventListener("click", () => withButton(el.exportSelected, "导出中...", exportSelected));
el.pickerClose.addEventListener("click", closePicker);
el.pickerUp.addEventListener("click", () => {
  const parent = state.browseCwd === "/" ? "/" : state.browseCwd.split("/").slice(0, -1).join("/") || "/";
  browse(parent).catch((error) => setStatus(error.message, true));
});
el.pickerSelectDir.addEventListener("click", () => {
  el.outputDir.value = state.browseCwd;
  closePicker();
});

init().catch((error) => setStatus(error.message, true));
