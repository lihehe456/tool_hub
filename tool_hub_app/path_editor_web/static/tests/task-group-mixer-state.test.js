import assert from "node:assert/strict";
import test from "node:test";

import {
  createTaskGroupMixerInitialState,
  reduceTaskGroupMixerState,
} from "../task-group-mixer-state.js";

test("SET_WORKSPACE stores workspace and activates first source", () => {
  const next = reduceTaskGroupMixerState(createTaskGroupMixerInitialState(), {
    type: "SET_WORKSPACE",
    workspacePath: "/tmp/mixer.json",
    workspace: {
      workspace_name: "mixer",
      task_group_name: "mix_result",
      subtasks: [
        { id: "a", source_workspace_path: "/tmp/source-a.workspace.json" },
        { id: "b", source_workspace_path: "/tmp/source-b.workspace.json" },
      ],
      selected_subtask_ids: [],
    },
  });

  assert.equal(next.workspacePath, "/tmp/mixer.json");
  assert.equal(next.activeSourcePath, "/tmp/source-a.workspace.json");
});

test("SET_ACTIVE_SOURCE switches visible source inventory", () => {
  const state = {
    ...createTaskGroupMixerInitialState(),
    activeSourcePath: "/tmp/source-a.workspace.json",
  };

  const next = reduceTaskGroupMixerState(state, {
    type: "SET_ACTIVE_SOURCE",
    sourcePath: "/tmp/source-b.workspace.json",
  });

  assert.equal(next.activeSourcePath, "/tmp/source-b.workspace.json");
});

test("SET_WORKSPACE drops stale selections after source replace", () => {
  const state = {
    ...createTaskGroupMixerInitialState(),
    activeSourcePath: "/tmp/source-a.workspace.json",
    workspace: {
      subtasks: [
        { id: "old-a", source_workspace_path: "/tmp/source-a.workspace.json" },
        { id: "other", source_workspace_path: "/tmp/source-b.workspace.json" },
      ],
      selected_subtask_ids: ["old-a", "other"],
    },
  };

  const next = reduceTaskGroupMixerState(state, {
    type: "SET_WORKSPACE",
    workspacePath: "/tmp/mixer.json",
    workspace: {
      subtasks: [
        { id: "new-a", source_workspace_path: "/tmp/source-a.workspace.json" },
        { id: "other", source_workspace_path: "/tmp/source-b.workspace.json" },
      ],
      selected_subtask_ids: ["other"],
    },
  });

  assert.equal(next.activeSourcePath, "/tmp/source-a.workspace.json");
  assert.deepEqual(next.workspace.selected_subtask_ids, ["other"]);
});

test("RECORD_WORKSPACE_HISTORY keeps newest path first without duplicates", () => {
  let state = createTaskGroupMixerInitialState();
  state = reduceTaskGroupMixerState(state, {
    type: "RECORD_WORKSPACE_HISTORY",
    workspacePath: "/tmp/one.json",
  });
  state = reduceTaskGroupMixerState(state, {
    type: "RECORD_WORKSPACE_HISTORY",
    workspacePath: "/tmp/two.json",
  });
  state = reduceTaskGroupMixerState(state, {
    type: "RECORD_WORKSPACE_HISTORY",
    workspacePath: "/tmp/one.json",
  });

  assert.deepEqual(state.workspaceHistory, ["/tmp/one.json", "/tmp/two.json"]);
});

test("RECORD_SOURCE_HISTORY keeps newest sidecar path first without duplicates", () => {
  let state = createTaskGroupMixerInitialState();
  state = reduceTaskGroupMixerState(state, {
    type: "RECORD_SOURCE_HISTORY",
    sourcePath: "/tmp/a.workspace.json",
  });
  state = reduceTaskGroupMixerState(state, {
    type: "RECORD_SOURCE_HISTORY",
    sourcePath: "/tmp/b.workspace.json",
  });
  state = reduceTaskGroupMixerState(state, {
    type: "RECORD_SOURCE_HISTORY",
    sourcePath: "/tmp/a.workspace.json",
  });

  assert.deepEqual(state.sourceHistory, ["/tmp/a.workspace.json", "/tmp/b.workspace.json"]);
});
