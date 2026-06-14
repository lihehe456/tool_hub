import assert from "node:assert/strict";
import test from "node:test";

import { startupBrowseRoot } from "../startup-policy.js";

test("startupBrowseRoot uses runtime work root instead of configured data roots", () => {
  assert.equal(
    startupBrowseRoot({
      user_root: "/opt/ry",
      paths_root: "/huge/paths",
      maps_root: "/huge/maps",
    }),
    "/opt/ry",
  );
});

test("startupBrowseRoot falls back when user root is missing", () => {
  assert.equal(startupBrowseRoot({}, "/fallback"), "/fallback");
});
