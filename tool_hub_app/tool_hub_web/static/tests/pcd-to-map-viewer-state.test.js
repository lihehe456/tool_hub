import assert from "node:assert/strict";
import test from "node:test";

import {
  createViewerState,
  fitViewerToFrame,
  panViewer,
  resetViewer,
  zoomViewerAtPoint,
} from "../pcd-to-map-viewer-state.js";

test("zoomViewerAtPoint keeps the pointed image coordinate stable", () => {
  const state = createViewerState();
  const next = zoomViewerAtPoint(state, 2, { x: 120, y: 80 });

  assert.equal(next.scale, 2);
  assert.equal(next.offsetX, -120);
  assert.equal(next.offsetY, -80);
});

test("panViewer moves the current image offset", () => {
  const state = { ...createViewerState(), offsetX: 10, offsetY: -20 };
  const next = panViewer(state, { dx: 15, dy: 5 });

  assert.equal(next.offsetX, 25);
  assert.equal(next.offsetY, -15);
});

test("zoomViewerAtPoint clamps scale and resetViewer restores the default view", () => {
  const zoomed = zoomViewerAtPoint(createViewerState(), 100, { x: 0, y: 0 });
  const reset = resetViewer(zoomed);

  assert.equal(zoomed.scale, 8);
  assert.deepEqual(reset, createViewerState());
});

test("fitViewerToFrame centers the image inside the viewer frame", () => {
  const next = fitViewerToFrame(createViewerState(), 800, 600, 2000, 1000);

  assert.equal(next.scale, 0.4);
  assert.equal(next.offsetX, 0);
  assert.equal(next.offsetY, 100);
});
