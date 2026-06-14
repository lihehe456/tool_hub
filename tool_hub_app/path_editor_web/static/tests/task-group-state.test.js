import assert from "node:assert/strict";
import test from "node:test";

import {
  createTaskGroupInitialState,
  reduceTaskGroupState,
} from "../task-group-state.js";

test("SET_WORKSPACE loads workspace and clears status errors", () => {
  const initial = createTaskGroupInitialState();
  const next = reduceTaskGroupState(initial, {
    type: "SET_WORKSPACE",
    workspacePath: "/tmp/demo-workspace.json",
    workspace: {
      workspace_name: "demo",
      task_group_name: "delivery_demo",
      subtasks: [],
      selected_subtask_ids: [],
    },
  });

  assert.equal(next.workspacePath, "/tmp/demo-workspace.json");
  assert.equal(next.workspace.task_group_name, "delivery_demo");
  assert.equal(next.status.error, false);
});

test("MOVE_SELECTED_SUBTASK reorders selected_subtask_ids", () => {
  const state = {
    ...createTaskGroupInitialState(),
    workspace: {
      subtasks: [],
      selected_subtask_ids: ["a", "b", "c"],
    },
  };

  const next = reduceTaskGroupState(state, {
    type: "MOVE_SELECTED_SUBTASK",
    subtaskId: "b",
    direction: "up",
  });

  assert.deepEqual(next.workspace.selected_subtask_ids, ["b", "a", "c"]);
});

test("RENAME_TASK_GROUP updates workspace task_group_name", () => {
  const state = {
    ...createTaskGroupInitialState(),
    workspace: {
      subtasks: [],
      selected_subtask_ids: [],
      task_group_name: "old_name",
    },
  };

  const next = reduceTaskGroupState(state, {
    type: "RENAME_TASK_GROUP",
    taskGroupName: "new_name",
  });

  assert.equal(next.workspace.task_group_name, "new_name");
});

test("SET_OUTPUT_TASK_PATH updates workspace export target", () => {
  const state = {
    ...createTaskGroupInitialState(),
    workspace: {
      subtasks: [],
      selected_subtask_ids: [],
      output_task_path: "",
    },
  };

  const next = reduceTaskGroupState(state, {
    type: "SET_OUTPUT_TASK_PATH",
    outputTaskPath: "/tmp/export.json",
  });

  assert.equal(next.workspace.output_task_path, "/tmp/export.json");
});

test("CLEAR_SUBTASKS empties subtasks and selected ids but keeps workspace metadata", () => {
  const state = {
    ...createTaskGroupInitialState(),
    workspace: {
      workspace_name: "demo",
      task_group_name: "delivery_demo",
      output_task_path: "/tmp/export.json",
      subtasks: [{ id: "a" }, { id: "b" }],
      selected_subtask_ids: ["a"],
    },
  };

  const next = reduceTaskGroupState(state, {
    type: "CLEAR_SUBTASKS",
  });

  assert.deepEqual(next.workspace.subtasks, []);
  assert.deepEqual(next.workspace.selected_subtask_ids, []);
  assert.equal(next.workspace.task_group_name, "delivery_demo");
  assert.equal(next.workspace.output_task_path, "/tmp/export.json");
});
