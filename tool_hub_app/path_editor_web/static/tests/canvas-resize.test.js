import assert from "node:assert/strict";
import test from "node:test";

import { installCanvasResizeSync } from "../canvas-resize.js";

test("installCanvasResizeSync resizes when the canvas container changes size", () => {
  const observedTargets = [];
  let resizeObserverCallback = null;
  class FakeResizeObserver {
    constructor(callback) {
      resizeObserverCallback = callback;
    }

    observe(target) {
      observedTargets.push(target);
    }

    disconnect() {}
  }

  const target = { id: "canvas-wrap" };
  let resizeCount = 0;
  const cleanup = installCanvasResizeSync({
    target,
    pathCanvas: {
      resize() {
        resizeCount += 1;
      },
    },
    ResizeObserverCtor: FakeResizeObserver,
    windowObj: {
      addEventListener() {},
      removeEventListener() {},
      requestAnimationFrame(callback) {
        callback();
      },
    },
  });

  resizeObserverCallback();

  assert.deepEqual(observedTargets, [target]);
  assert.equal(resizeCount, 1);
  cleanup();
});

