import assert from "node:assert/strict";
import test from "node:test";

import { shouldResizeCanvasForAction } from "../subtask-composer-layout.js";

test("shouldResizeCanvasForAction flags layout-changing actions", () => {
  assert.equal(shouldResizeCanvasForAction({ type: "TOGGLE_FILE_PANEL" }), true);
  assert.equal(shouldResizeCanvasForAction({ type: "TOGGLE_EDITOR_PANEL" }), true);
  assert.equal(shouldResizeCanvasForAction({ type: "SET_EDITOR_PANEL_WIDTH" }), true);
  assert.equal(shouldResizeCanvasForAction({ type: "SET_TASK_DOCUMENT" }), true);
  assert.equal(shouldResizeCanvasForAction({ type: "SELECT_SUBTASK" }), true);
});

test("shouldResizeCanvasForAction ignores content-only actions", () => {
  assert.equal(shouldResizeCanvasForAction({ type: "SELECT_ANCHOR" }), false);
  assert.equal(shouldResizeCanvasForAction({ type: "MOVE_ANCHOR" }), false);
  assert.equal(shouldResizeCanvasForAction({ type: "UNDO" }), false);
});
