import assert from "node:assert/strict";
import test from "node:test";

import {
  buildLineSegments,
  createSubtaskComposerInitialState,
  documentFromSubtask,
  subtaskDocumentsFromPayload,
  reduceSubtaskComposerState,
  taskPayloadFromState,
  subtaskFromDocument,
  yawToQuaternion,
} from "../subtask-composer-state.js";


function demoSubtask() {
  return {
    change_loc: false,
    map_url: "/maps/indoor.yaml",
    pcd_url: "",
    subtask_name: "indoor",
    waypoints: [
      {
        waypoint_id: "indoor_0",
        pose: {
          position: { x: 1, y: 2, z: 0 },
          orientation: yawToQuaternion(Math.PI / 2),
        },
        speed_mode: "task_point",
        waypoint_task_id: "open_door_go",
        is_task_point: true,
        is_single_point: true,
        is_backward: false,
      },
    ],
  };
}


test("documentFromSubtask converts waypoints into editable anchors with task attrs", () => {
  const document = documentFromSubtask(demoSubtask());

  assert.equal(document.meta.subtask_name, "indoor");
  assert.equal(document.meta.map_url, "/maps/indoor.yaml");
  assert.equal(document.anchors.length, 1);
  assert.equal(document.anchors[0].waypoint_id, "indoor_0");
  assert.equal(document.anchors[0].task.waypoint_task_id, "open_door_go");
  assert.ok(Math.abs(document.anchors[0].yaw - Math.PI / 2) < 1e-9);
});


test("subtaskDocumentsFromPayload converts task group subtasks into switchable documents", () => {
  const payload = {
    document_type: "task_group",
    task_group: { task_group_name: "delivery" },
    subtasks: [
      { ...demoSubtask(), subtask_name: "go" },
      { ...demoSubtask(), subtask_name: "back", waypoints: [] },
    ],
    active_subtask_index: 1,
  };

  const documents = subtaskDocumentsFromPayload(payload);

  assert.equal(documents.documentType, "task_group");
  assert.equal(documents.activeSubtaskIndex, 1);
  assert.deepEqual(documents.subtaskNames, ["go", "back"]);
  assert.equal(documents.subtaskDocuments[1].meta.subtask_name, "back");
});


test("SELECT_SUBTASK stores current edits before switching documents", () => {
  const docs = subtaskDocumentsFromPayload({
    document_type: "task_group",
    task_group: { task_group_name: "delivery" },
    subtasks: [
      { ...demoSubtask(), subtask_name: "go", waypoints: [] },
      { ...demoSubtask(), subtask_name: "back", waypoints: [] },
    ],
    active_subtask_index: 0,
  });
  const state = reduceSubtaskComposerState(createSubtaskComposerInitialState(), {
    type: "SET_TASK_DOCUMENT",
    taskPath: "/tmp/group.json",
    ...docs,
  });
  const edited = reduceSubtaskComposerState(state, {
    type: "ADD_ANCHOR",
    point: { x: 7, y: 8, z: 0 },
  });

  const switched = reduceSubtaskComposerState(edited, {
    type: "SELECT_SUBTASK",
    index: 1,
  });

  assert.equal(switched.activeSubtaskIndex, 1);
  assert.equal(switched.document.meta.subtask_name, "back");
  assert.equal(switched.subtaskDocuments[0].anchors[0].x, 7);
});


test("taskPayloadFromState exports task group with current subtask edits", () => {
  const docs = subtaskDocumentsFromPayload({
    document_type: "task_group",
    task_group: { task_group_name: "delivery" },
    subtasks: [
      { ...demoSubtask(), subtask_name: "go", waypoints: [] },
      { ...demoSubtask(), subtask_name: "back", waypoints: [] },
    ],
    active_subtask_index: 0,
  });
  const state = reduceSubtaskComposerState(createSubtaskComposerInitialState(), {
    type: "SET_TASK_DOCUMENT",
    ...docs,
  });
  const edited = reduceSubtaskComposerState(state, {
    type: "ADD_ANCHOR",
    point: { x: 4, y: 5, z: 0 },
  });

  const payload = taskPayloadFromState(edited);

  assert.equal(payload.document_type, "task_group");
  assert.equal(payload.subtasks[0].waypoints[0].pose.position.x, 4);
  assert.equal(payload.subtasks[1].subtask_name, "back");
});


test("subtaskFromDocument exports the single subtask runtime shape", () => {
  const document = documentFromSubtask(demoSubtask());
  document.anchors.push({
    x: 3,
    y: 4,
    z: 0,
    yaw: 0,
    waypoint_id: "indoor_1",
    task: {
      speed_mode: "elevator_in",
      waypoint_task_id: "",
      is_task_point: false,
      is_single_point: true,
      is_backward: false,
    },
  });
  document.segments = buildLineSegments(document.anchors);

  const subtask = subtaskFromDocument(document);

  assert.deepEqual(Object.keys(subtask), ["change_loc", "map_url", "pcd_url", "subtask_name", "waypoints"]);
  assert.equal(subtask.waypoints[1].waypoint_id, "indoor_1");
  assert.equal(subtask.waypoints[1].speed_mode, "elevator_in");
  assert.deepEqual(subtask.waypoints[1].pose.position, { x: 3, y: 4, z: 0 });
});


test("ADD_ANCHOR creates a waypoint id and default task attributes", () => {
  const state = {
    ...createSubtaskComposerInitialState(),
    document: documentFromSubtask({ ...demoSubtask(), waypoints: [] }),
  };

  const next = reduceSubtaskComposerState(state, {
    type: "ADD_ANCHOR",
    point: { x: 1, y: 2, z: 0 },
  });

  assert.equal(next.document.anchors[0].waypoint_id, "indoor_0");
  assert.equal(next.document.anchors[0].task.speed_mode, "task_point");
  assert.equal(next.selectedIndex, 0);
  assert.equal(next.dirty, true);
});


test("UNDO restores the previous document edit", () => {
  const state = {
    ...createSubtaskComposerInitialState(),
    document: documentFromSubtask({ ...demoSubtask(), waypoints: [] }),
  };
  const edited = reduceSubtaskComposerState(state, {
    type: "ADD_ANCHOR",
    point: { x: 1, y: 2, z: 0 },
  });

  const undone = reduceSubtaskComposerState(edited, { type: "UNDO" });

  assert.equal(edited.document.anchors.length, 1);
  assert.equal(undone.document.anchors.length, 0);
  assert.equal(undone.selectedIndex, -1);
  assert.equal(undone.dirty, true);
});


test("UNDO ignores selection and panel visibility changes", () => {
  const state = {
    ...createSubtaskComposerInitialState(),
    document: documentFromSubtask(demoSubtask()),
    selectedIndex: 0,
  };
  const selected = reduceSubtaskComposerState(state, {
    type: "SELECT_ANCHOR",
    index: -1,
  });
  const toggled = reduceSubtaskComposerState(selected, { type: "TOGGLE_FILE_PANEL" });

  const undone = reduceSubtaskComposerState(toggled, { type: "UNDO" });

  assert.equal(undone.selectedIndex, -1);
  assert.equal(undone.filePanel.collapsed, true);
  assert.equal(undone.document.anchors.length, 1);
});


test("UPDATE_SELECTED_TASK_ATTR changes only task metadata", () => {
  const state = {
    ...createSubtaskComposerInitialState(),
    document: documentFromSubtask(demoSubtask()),
    selectedIndex: 0,
  };

  const next = reduceSubtaskComposerState(state, {
    type: "UPDATE_SELECTED_TASK_ATTR",
    patch: {
      speed_mode: "backward",
      waypoint_task_id: "close_door_back",
      is_task_point: true,
    },
  });

  assert.equal(next.document.anchors[0].x, 1);
  assert.equal(next.document.anchors[0].task.speed_mode, "backward");
  assert.equal(next.document.anchors[0].task.waypoint_task_id, "close_door_back");
});


test("TOGGLE_EDITOR_PANEL hides panel while preserving width", () => {
  const state = {
    ...createSubtaskComposerInitialState(),
    editorPanel: { collapsed: false, width: 380 },
  };

  const next = reduceSubtaskComposerState(state, { type: "TOGGLE_EDITOR_PANEL" });

  assert.equal(next.editorPanel.collapsed, true);
  assert.equal(next.editorPanel.width, 380);
});


test("TOGGLE_FILE_PANEL hides file controls without changing editor panel", () => {
  const state = {
    ...createSubtaskComposerInitialState(),
    filePanel: { collapsed: false },
    editorPanel: { collapsed: false, width: 380 },
  };

  const next = reduceSubtaskComposerState(state, { type: "TOGGLE_FILE_PANEL" });

  assert.deepEqual(next.filePanel, { collapsed: true });
  assert.deepEqual(next.editorPanel, { collapsed: false, width: 380 });
});


test("SET_EDITOR_PANEL_WIDTH clamps panel width", () => {
  const state = createSubtaskComposerInitialState();

  const tooSmall = reduceSubtaskComposerState(state, {
    type: "SET_EDITOR_PANEL_WIDTH",
    width: 100,
  });
  const tooLarge = reduceSubtaskComposerState(state, {
    type: "SET_EDITOR_PANEL_WIDTH",
    width: 900,
  });

  assert.equal(tooSmall.editorPanel.width, 260);
  assert.equal(tooLarge.editorPanel.width, 640);
});


test("OFFSET_ANCHORS moves every waypoint without changing selection", () => {
  const document = documentFromSubtask(demoSubtask());
  document.anchors.push({
    x: -1,
    y: 5,
    z: 0.2,
    yaw: 1,
    waypoint_id: "indoor_1",
    task: {
      speed_mode: "task_point",
      waypoint_task_id: "",
      is_task_point: false,
      is_single_point: true,
      is_backward: false,
    },
  });
  document.segments = buildLineSegments(document.anchors);
  const state = {
    ...createSubtaskComposerInitialState(),
    document,
    selectedIndex: 1,
  };

  const next = reduceSubtaskComposerState(state, {
    type: "OFFSET_ANCHORS",
    dx: 0.5,
    dy: -2,
  });

  assert.equal(next.selectedIndex, 1);
  assert.equal(next.dirty, true);
  assert.deepEqual(
    next.document.anchors.map((anchor) => [anchor.x, anchor.y, anchor.z]),
    [[1.5, 0, 0], [-0.5, 3, 0.2]],
  );
  assert.deepEqual(next.document.segments, [
    { startIndex: 0, endIndex: 1, type: "line", control: null },
  ]);
});
