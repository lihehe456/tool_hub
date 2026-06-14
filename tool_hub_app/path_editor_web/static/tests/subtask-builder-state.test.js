import assert from "node:assert/strict";
import test from "node:test";

import {
  canCreateTaskWorkspace,
  canWriteSubtaskPairToWorkspace,
} from "../subtask-builder-state.js";

test("workspace creation only requires a workspace path", () => {
  assert.equal(
    canCreateTaskWorkspace({
      workspacePath: "/tmp/new-workspace.json",
      generatedSubtaskPair: null,
    }),
    true,
  );
});

test("writing subtasks still requires a generated subtask pair", () => {
  assert.equal(
    canWriteSubtaskPairToWorkspace({
      workspacePath: "/tmp/new-workspace.json",
      generatedSubtaskPair: null,
    }),
    false,
  );
  assert.equal(
    canWriteSubtaskPairToWorkspace({
      workspacePath: "/tmp/new-workspace.json",
      generatedSubtaskPair: { forwardSubtask: {}, returnSubtask: {} },
    }),
    true,
  );
});
