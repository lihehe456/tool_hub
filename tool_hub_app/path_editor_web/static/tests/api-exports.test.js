import assert from "node:assert/strict";
import test from "node:test";

import * as api from "../api.js";

test("api exports all functions imported by the path editor app", () => {
  const expectedExports = [
    "addSubtaskPairToWorkspace",
    "buildSubtasksFromPath",
    "browseMaps",
    "browsePaths",
    "createTaskWorkspace",
    "loadRuntimeConfig",
    "loadTaskWorkspace",
    "loadMap",
    "loadPath",
    "replaceSubtaskPairInWorkspace",
    "savePath",
    "savePathAs",
  ];

  for (const exportName of expectedExports) {
    assert.equal(typeof api[exportName], "function", `${exportName} should be exported`);
  }
});
