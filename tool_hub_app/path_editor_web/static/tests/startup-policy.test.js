import assert from "node:assert/strict";
import test from "node:test";

import { shouldAutoBrowseOnStartup } from "../startup-policy.js";

test("shouldAutoBrowseOnStartup defaults to true", () => {
  assert.equal(shouldAutoBrowseOnStartup({}), true);
});

test("shouldAutoBrowseOnStartup can be disabled explicitly", () => {
  assert.equal(shouldAutoBrowseOnStartup({ auto_browse_on_startup: false }), false);
});
