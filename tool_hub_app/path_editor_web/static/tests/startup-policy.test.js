import assert from "node:assert/strict";
import test from "node:test";

import { startupBrowseRoot } from "../startup-policy.js";

test("startupBrowseRoot uses user home instead of configured data roots", () => {
  assert.equal(
    startupBrowseRoot({
      user_root: "/home/lmy",
      paths_root: "/huge/paths",
      maps_root: "/huge/maps",
    }),
    "/home/lmy",
  );
});

test("startupBrowseRoot falls back when user root is missing", () => {
  assert.equal(startupBrowseRoot({}, "/fallback"), "/fallback");
});
