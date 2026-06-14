import assert from "node:assert/strict";
import test from "node:test";

import { PathCanvas } from "../canvas.js";

function createFakeContext() {
  const operations = [];
  const context = {
    operations,
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
    font: "",
    lineCap: "",
    lineJoin: "",
    shadowColor: "",
    shadowBlur: 0,
    beginPath() {
      operations.push(["beginPath"]);
    },
    moveTo(x, y) {
      operations.push(["moveTo", x, y]);
    },
    lineTo(x, y) {
      operations.push(["lineTo", x, y]);
    },
    stroke() {
      operations.push(["stroke"]);
    },
    fill() {
      operations.push(["fill"]);
    },
    arc(x, y, radius) {
      operations.push(["arc", x, y, radius]);
    },
    fillRect(x, y, width, height) {
      operations.push(["fillRect", x, y, width, height]);
    },
    fillText(text, x, y) {
      operations.push(["fillText", text, x, y]);
    },
    drawImage(...args) {
      operations.push(["drawImage", ...args]);
    },
    save() {
      operations.push(["save"]);
    },
    restore() {
      operations.push(["restore"]);
    },
    setLineDash(values) {
      operations.push(["setLineDash", ...values]);
    },
  };
  return context;
}

function createFakeCanvas() {
  const listeners = new Map();
  const context = createFakeContext();
  return {
    width: 400,
    height: 400,
    _listeners: listeners,
    _context: context,
    getContext() {
      return context;
    },
    addEventListener(type, handler) {
      listeners.set(type, handler);
    },
    getBoundingClientRect() {
      return { left: 0, top: 0, width: 400, height: 400 };
    },
  };
}

test("PathCanvas adds anchors at the actual cursor position without forcing grid snap", () => {
  const canvas = createFakeCanvas();
  let addedPoint = null;
  let rotatedAnchor = null;
  const pathCanvas = new PathCanvas(canvas, {
    onAddAnchor(worldPoint) {
      addedPoint = worldPoint;
      pathCanvas.setDocument({
        anchors: [{ x: worldPoint.x, y: worldPoint.y, z: 0, yaw: 0 }],
        segments: [],
      });
    },
    onRotateAnchor(index, yaw) {
      rotatedAnchor = { index, yaw };
    },
  });
  pathCanvas.setMapData({
    width: 200,
    height: 200,
    resolution: 0.05,
    origin: [0, 0, 0],
    imageElement: {},
  });
  pathCanvas.view = { scale: 4, offsetX: 0, offsetY: 0 };
  pathCanvas.setTool("add");

  canvas._listeners.get("pointerdown")({
    button: 0,
    clientX: 100,
    clientY: 125,
  });
  canvas._listeners.get("pointermove")({
    clientX: 120,
    clientY: 125,
  });

  assert.deepEqual(addedPoint, { x: 1.25, y: 8.4375 });
  assert.equal(rotatedAnchor.index, 0);
  assert.ok(Math.abs(rotatedAnchor.yaw) < 1e-9);
});

test("PathCanvas exposes the map frame origin in canvas coordinates for drawing", () => {
  const canvas = createFakeCanvas();
  const pathCanvas = new PathCanvas(canvas, {});
  pathCanvas.view = { scale: 2, offsetX: 20, offsetY: 30 };
  pathCanvas.setMapData({
    width: 100,
    height: 100,
    resolution: 0.5,
    origin: [1, 2, 0],
    imageElement: {},
  });
  pathCanvas.view = { scale: 2, offsetX: 20, offsetY: 30 };

  assert.deepEqual(pathCanvas.originCanvasPoint(), { x: 16, y: 238 });
});

test("PathCanvas computes alignment guides against the nearest anchor while moving", () => {
  const canvas = createFakeCanvas();
  const pathCanvas = new PathCanvas(canvas, {});
  pathCanvas.setMapData({
    width: 200,
    height: 200,
    resolution: 0.05,
    origin: [0, 0, 0],
    imageElement: {},
  });
  pathCanvas.view = { scale: 4, offsetX: 0, offsetY: 0 };
  pathCanvas.setDocument({
    anchors: [
      { x: 1.25, y: 8.0, z: 0, yaw: 0 },
      { x: 3.0, y: 6.5, z: 0, yaw: 0 },
    ],
    segments: [],
  });

  const guides = pathCanvas.alignmentGuidesForWorldPoint({ x: 1.28, y: 6.52, z: 0 });

  assert.deepEqual(guides, {
    vertical: { anchorIndex: 0, x: 1.25 },
    horizontal: { anchorIndex: 1, y: 6.5 },
  });
});

test("PathCanvas draws dashed alignment guides when guides are active", () => {
  const canvas = createFakeCanvas();
  const pathCanvas = new PathCanvas(canvas, {});
  pathCanvas.setMapData({
    width: 200,
    height: 200,
    resolution: 0.05,
    origin: [0, 0, 0],
    imageElement: {},
  });
  pathCanvas.view = { scale: 4, offsetX: 0, offsetY: 0 };
  pathCanvas.alignmentGuides = {
    vertical: { anchorIndex: 0, x: 1.0 },
    horizontal: { anchorIndex: 1, y: 2.0 },
  };

  pathCanvas.draw();

  assert.ok(canvas._context.operations.some((entry) => entry[0] === "setLineDash" && entry[1] === 8));
});

test("PathCanvas insert tool inserts a point on the nearest segment", () => {
  const canvas = createFakeCanvas();
  const inserted = [];
  const pathCanvas = new PathCanvas(canvas, {
    onInsertAnchor(segmentIndex, worldPoint) {
      inserted.push({ segmentIndex, worldPoint });
    },
  });
  pathCanvas.setMapData({
    width: 200,
    height: 200,
    resolution: 0.05,
    origin: [0, 0, 0],
    imageElement: {},
  });
  pathCanvas.view = { scale: 4, offsetX: 0, offsetY: 0 };
  pathCanvas.setDocument({
    anchors: [
      { x: 1, y: 8, z: 0, yaw: 0 },
      { x: 3, y: 8, z: 0, yaw: 0 },
    ],
    segments: [{ startIndex: 0, endIndex: 1, type: "line", control: null }],
  });
  pathCanvas.setTool("insert");

  canvas._listeners.get("pointerdown")({
    button: 0,
    clientX: 160,
    clientY: 160,
  });

  assert.equal(inserted.length, 1);
  assert.equal(inserted[0].segmentIndex, 0);
  assert.deepEqual(inserted[0].worldPoint, { x: 2, y: 8 });
});

test("PathCanvas toggles anchor multi-selection with modifier clicks", () => {
  const canvas = createFakeCanvas();
  const toggled = [];
  const pathCanvas = new PathCanvas(canvas, {
    onToggleAnchorSelection(index) {
      toggled.push(index);
    },
  });
  pathCanvas.setMapData({
    width: 200,
    height: 200,
    resolution: 0.05,
    origin: [0, 0, 0],
    imageElement: {},
  });
  pathCanvas.view = { scale: 4, offsetX: 0, offsetY: 0 };
  pathCanvas.setDocument({
    anchors: [
      { x: 1, y: 8, z: 0, yaw: 0 },
      { x: 3, y: 8, z: 0, yaw: 0 },
    ],
    segments: [{ startIndex: 0, endIndex: 1, type: "line", control: null }],
  });
  pathCanvas.setTool("select");

  canvas._listeners.get("pointerdown")({
    button: 0,
    clientX: 240,
    clientY: 160,
    ctrlKey: true,
  });

  assert.deepEqual(toggled, [1]);
});


test("PathCanvas draws virtual walls with the same map transform as anchors", () => {
  const canvas = createFakeCanvas();
  const pathCanvas = new PathCanvas(canvas, {});
  pathCanvas.setMapData({
    width: 100,
    height: 100,
    resolution: 0.5,
    origin: [10, 20, 0],
    imageElement: {},
  });
  pathCanvas.view = { scale: 2, offsetX: 5, offsetY: 7 };

  pathCanvas.setVirtualWalls([
    {
      points: [
        { x: 11, y: 21, z: 0 },
        { x: 12, y: 21, z: 0 },
      ],
      thickness: 0.2,
    },
  ]);

  assert.ok(
    canvas._context.operations.some(
      (entry) => entry[0] === "moveTo" && entry[1] === 9 && entry[2] === 203,
    ),
  );
  assert.ok(
    canvas._context.operations.some(
      (entry) => entry[0] === "lineTo" && entry[1] === 13 && entry[2] === 203,
    ),
  );
});
