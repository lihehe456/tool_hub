import assert from "node:assert/strict";
import test from "node:test";

import { createInitialState, reduce } from "../state.js";

test("opening a new path clears selection and dirty state", () => {
  let state = createInitialState();
  state = reduce(state, { type: "MARK_DIRTY" });
  state = reduce(state, {
    type: "OPEN_DOCUMENT",
    filePath: "/tmp/demo.json",
    document: { meta: { path_name: "demo" }, anchors: [] },
  });

  assert.equal(state.filePath, "/tmp/demo.json");
  assert.equal(state.dirty, false);
  assert.deepEqual(state.selection, { kind: "none" });
});

test("updating metadata marks document dirty and preserves file path", () => {
  let state = createInitialState();
  state = reduce(state, {
    type: "OPEN_DOCUMENT",
    filePath: "/tmp/demo.json",
    document: { meta: { path_name: "demo", community: "A" }, anchors: [] },
  });
  state = reduce(state, {
    type: "UPDATE_META",
    patch: { community: "B" },
  });

  assert.equal(state.filePath, "/tmp/demo.json");
  assert.equal(state.document.meta.community, "B");
  assert.equal(state.dirty, true);
});

test("save as path change preserves current document and clears dirty flag", () => {
  let state = createInitialState();
  const document = { meta: { path_name: "demo" }, anchors: [{ x: 1 }] };
  state = reduce(state, {
    type: "OPEN_DOCUMENT",
    filePath: "/tmp/demo.json",
    document,
  });
  state = reduce(state, { type: "MARK_DIRTY" });
  state = reduce(state, { type: "SAVE_AS_SUCCESS", filePath: "/tmp/demo-copy.json" });

  assert.equal(state.filePath, "/tmp/demo-copy.json");
  assert.deepEqual(state.document, document);
  assert.equal(state.dirty, false);
});

test("switching tools and selecting points updates state predictably", () => {
  let state = createInitialState();
  state = reduce(state, { type: "SET_TOOL", tool: "rotate" });
  state = reduce(state, { type: "SELECT_ELEMENT", selection: { kind: "anchor", index: 2 } });

  assert.equal(state.activeTool, "rotate");
  assert.deepEqual(state.selection, { kind: "anchor", index: 2 });
});

test("opening a map updates map path without forcing dirty state", () => {
  let state = createInitialState();
  state = reduce(state, {
    type: "OPEN_DOCUMENT",
    filePath: "/tmp/demo.json",
    document: { meta: { path_name: "demo", map_url: "" }, anchors: [] },
  });
  state = reduce(state, {
    type: "SET_MAP_PATH",
    mapPath: "/tmp/map.yaml",
  });

  assert.equal(state.mapPath, "/tmp/map.yaml");
  assert.equal(state.document.meta.map_url, "/tmp/map.yaml");
  assert.equal(state.dirty, false);
});

test("toggling the topbar collapse flips collapsed state", () => {
  let state = createInitialState();

  state = reduce(state, { type: "TOGGLE_TOPBAR" });
  assert.equal(state.topbarCollapsed, true);

  state = reduce(state, { type: "TOGGLE_TOPBAR" });
  assert.equal(state.topbarCollapsed, false);
});

test("SET_WORKSPACE_PATH stores the chosen task workspace path", () => {
  const next = reduce(createInitialState(), {
    type: "SET_WORKSPACE_PATH",
    workspacePath: "/tmp/demo-workspace.json",
  });

  assert.equal(next.workspacePath, "/tmp/demo-workspace.json");
});

test("SET_GENERATED_SUBTASK_PAIR stores forward and return subtasks", () => {
  const next = reduce(createInitialState(), {
    type: "SET_GENERATED_SUBTASK_PAIR",
    pair: { forwardSubtask: { id: "a" }, returnSubtask: { id: "b" } },
  });

  assert.equal(next.generatedSubtaskPair.forwardSubtask.id, "a");
  assert.equal(next.generatedSubtaskPair.returnSubtask.id, "b");
});
