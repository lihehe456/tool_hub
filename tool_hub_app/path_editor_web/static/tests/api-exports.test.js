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

test("createTaskWorkspace posts to the workspace creation endpoint", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      async json() {
        return { ok: true, created: true, workspace: {} };
      },
    };
  };

  try {
    await api.createTaskWorkspace("/tmp/new-workspace.json");
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/create_task_workspace");
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    workspace_path: "/tmp/new-workspace.json",
  });
});
