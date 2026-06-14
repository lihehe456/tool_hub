import assert from "node:assert/strict";
import test from "node:test";

import { shouldAutoBrowseOnStartup } from "../startup-policy.js";

test("shouldAutoBrowseOnStartup defaults to false", () => {
  assert.equal(shouldAutoBrowseOnStartup({}), false);
});

test("shouldAutoBrowseOnStartup can be enabled explicitly", () => {
  assert.equal(shouldAutoBrowseOnStartup({ auto_browse_on_startup: true }), true);
});
