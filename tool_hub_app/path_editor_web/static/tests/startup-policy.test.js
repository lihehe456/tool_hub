import assert from "node:assert/strict";
import test from "node:test";

import { shouldAutoBrowseOnStartup, startupBrowseRoot } from "../startup-policy.js";

test("shouldAutoBrowseOnStartup defaults to false", () => {
  assert.equal(shouldAutoBrowseOnStartup({}), false);
});

test("shouldAutoBrowseOnStartup can be enabled explicitly", () => {
  assert.equal(shouldAutoBrowseOnStartup({ auto_browse_on_startup: true }), true);
});

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
