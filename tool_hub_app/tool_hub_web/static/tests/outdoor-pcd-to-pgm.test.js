import assert from "node:assert/strict";
import test from "node:test";

import {bindOutdoorPreviewViewer, buildOutdoorPcdToPgmPayload, createOutdoorPreviewZoom} from "../outdoor-pcd-to-pgm.js";

test("buildOutdoorPcdToPgmPayload keeps the outdoor algorithm independent", () => {
  const payload = buildOutdoorPcdToPgmPayload({
    pcdPath: " /tmp/outdoor.pcd ",
    trajectoryPath: " /tmp/Trajectory-Opt.pcd ",
    outputDir: " /tmp/output ",
    mapName: "outdoor",
    zMin: "0",
    zMax: "0.4",
    resolution: "0.05",
    radius: "0.5",
    minNeighbors: "10",
    sensorHeight: "0.5",
    trajectorySearchRadius: "30",
    flagPassThrough: true,
  });

  assert.deepEqual(payload, {
    pcd_path: "/tmp/outdoor.pcd",
    trajectory_pcd_path: "/tmp/Trajectory-Opt.pcd",
    output_dir: "/tmp/output",
    map_name: "outdoor",
    z_min: 0,
    z_max: 0.4,
    resolution: 0.05,
    radius: 0.5,
    min_neighbors: 10,
    sensor_height: 0.5,
    trajectory_search_radius: 30,
    flag_pass_through: true,
  });
});

test("bindOutdoorPreviewViewer opens the generated preview in a large viewer", () => {
  const previewImage = fakeElement();
  const viewerOverlay = fakeElement();
  const viewerImage = fakeElement();
  const viewerClose = fakeElement();
  const viewerTitle = fakeElement();

  bindOutdoorPreviewViewer({previewImage, viewerOverlay, viewerImage, viewerClose, viewerTitle});
  previewImage.src = "data:image/png;base64,abc123";
  previewImage.dataset.ready = "true";

  previewImage.dispatch("click");

  assert.equal(viewerOverlay.classList.has("visible"), true);
  assert.equal(viewerImage.src, "data:image/png;base64,abc123");
  assert.equal(viewerTitle.textContent, "地图预览");

  viewerClose.dispatch("click");
  assert.equal(viewerOverlay.classList.has("visible"), false);
});

test("createOutdoorPreviewZoom scales both inline and large preview images", () => {
  const inlineImage = fakeElement();
  const viewerImage = fakeElement();
  const scaleLabel = fakeElement();
  const zoom = createOutdoorPreviewZoom({inlineImage, viewerImage, scaleLabel});

  zoom.zoomIn();
  assert.equal(inlineImage.style.width, "125%");
  assert.equal(viewerImage.style.width, "125%");
  assert.equal(scaleLabel.textContent, "125%");

  zoom.zoomOut();
  zoom.reset();
  assert.equal(inlineImage.style.width, "100%");
  assert.equal(viewerImage.style.width, "100%");
  assert.equal(scaleLabel.textContent, "100%");
});

function fakeElement() {
  const listeners = new Map();
  return {
    dataset: {},
    src: "",
    textContent: "",
    style: {},
    classList: {
      values: new Set(),
      add(value) { this.values.add(value); },
      remove(value) { this.values.delete(value); },
      has(value) { return this.values.has(value); },
    },
    addEventListener(event, handler) {
      listeners.set(event, handler);
    },
    dispatch(event) {
      const handler = listeners.get(event);
      if (handler) handler({preventDefault() {}});
    },
  };
}
