import assert from "node:assert/strict";
import test from "node:test";

import {
  consumeCanvasClickSuppression,
  deleteWallPoint,
  findNearestWallPoint,
  findNearestWallSegment,
  finishPointDrag,
  finishWallDrag,
  insertWallPoint,
  moveWallPolylines,
  moveWallPolyline,
  moveWallPoint,
  projectPointToSegment,
  resolveWallCanvasClick,
  toggleWallSelection,
} from "../virtual-wall-editor-state.js";

function worldToCanvas(point) {
  return { x: point.x * 10, y: point.y * 10 };
}

test("findNearestWallPoint returns the closest endpoint", () => {
  const polylines = [
    { points: [{ x: 1, y: 1, z: 0 }, { x: 4, y: 1, z: 0 }] },
    { points: [{ x: 9, y: 9, z: 0 }, { x: 11, y: 9, z: 0 }] },
  ];

  const hit = findNearestWallPoint(polylines, { x: 42, y: 11 }, worldToCanvas, 5);

  assert.deepEqual(hit, { polylineIndex: 0, pointIndex: 1, distanceSquared: 5 });
});

test("findNearestWallSegment returns insertion location for a segment", () => {
  const polylines = [{ points: [{ x: 1, y: 1, z: 0 }, { x: 4, y: 1, z: 0 }, { x: 6, y: 3, z: 0 }] }];

  const hit = findNearestWallSegment(polylines, { x: 48, y: 18 }, worldToCanvas, 8);

  assert.equal(hit.polylineIndex, 0);
  assert.equal(hit.insertAfterPointIndex, 1);
});

test("projectPointToSegment returns the closest point on a wall segment", () => {
  const projected = projectPointToSegment(
    { x: 2.4, y: 4, z: 0 },
    { x: 1, y: 1, z: 0 },
    { x: 4, y: 1, z: 0 },
  );

  assert.deepEqual(projected, { x: 2.4, y: 1, z: 0 });
});

test("insertWallPoint inserts a point after the hit segment", () => {
  const polylines = [{ points: [{ x: 1, y: 1, z: 0 }, { x: 4, y: 1, z: 0 }] }];

  const next = insertWallPoint(polylines, { polylineIndex: 0, insertAfterPointIndex: 0 }, {
    x: 2.5,
    y: 1,
    z: 0,
  });

  assert.deepEqual(next[0].points.map((point) => [point.x, point.y]), [
    [1, 1],
    [2.5, 1],
    [4, 1],
  ]);
});

test("moveWallPoint updates the selected point in place", () => {
  const polylines = [{ points: [{ x: 1, y: 1, z: 0 }, { x: 4, y: 1, z: 0 }] }];

  const next = moveWallPoint(polylines, { polylineIndex: 0, pointIndex: 1 }, {
    x: 5,
    y: 2,
    z: 0,
  });

  assert.deepEqual(next[0].points.map((point) => [point.x, point.y]), [
    [1, 1],
    [5, 2],
  ]);
});

test("moveWallPolyline translates every point in the selected wall", () => {
  const polylines = [
    { points: [{ x: 1, y: 1, z: 0 }, { x: 4, y: 1, z: 0 }] },
    { points: [{ x: 8, y: 8, z: 0 }, { x: 9, y: 9, z: 0 }] },
  ];

  const next = moveWallPolyline(polylines, 0, { x: 2, y: -3, z: 0 });

  assert.deepEqual(next[0].points.map((point) => [point.x, point.y]), [
    [3, -2],
    [6, -2],
  ]);
  assert.deepEqual(next[1].points.map((point) => [point.x, point.y]), [
    [8, 8],
    [9, 9],
  ]);
});

test("moveWallPolylines translates every point in multiple selected walls", () => {
  const polylines = [
    { points: [{ x: 1, y: 1, z: 0 }, { x: 4, y: 1, z: 0 }] },
    { points: [{ x: 8, y: 8, z: 0 }, { x: 9, y: 9, z: 0 }] },
    { points: [{ x: -1, y: -1, z: 0 }, { x: -2, y: -2, z: 0 }] },
  ];

  const next = moveWallPolylines(polylines, [0, 2], { x: 2, y: -3, z: 0 });

  assert.deepEqual(next[0].points.map((point) => [point.x, point.y]), [
    [3, -2],
    [6, -2],
  ]);
  assert.deepEqual(next[1].points.map((point) => [point.x, point.y]), [
    [8, 8],
    [9, 9],
  ]);
  assert.deepEqual(next[2].points.map((point) => [point.x, point.y]), [
    [1, -4],
    [0, -5],
  ]);
});

test("toggleWallSelection adds and removes wall indexes while keeping them sorted", () => {
  assert.deepEqual(toggleWallSelection([2], 0), [0, 2]);
  assert.deepEqual(toggleWallSelection([0, 2], 2), [0]);
});

test("finishing a moved drag suppresses the next canvas click only ერთხელ", () => {
  const gesture = {
    draggingPoint: { polylineIndex: 0, pointIndex: 1 },
    dragMoved: true,
    suppressNextClick: false,
  };

  finishPointDrag(gesture);

  assert.equal(gesture.draggingPoint, null);
  assert.equal(gesture.dragMoved, false);
  assert.equal(gesture.suppressNextClick, true);
  assert.equal(consumeCanvasClickSuppression(gesture), true);
  assert.equal(consumeCanvasClickSuppression(gesture), false);
});

test("finishing a moved wall drag suppresses the next canvas click only once", () => {
  const gesture = {
    draggingWall: { polylineIndex: 0, lastWorldPoint: { x: 1, y: 1, z: 0 } },
    wallDragMoved: true,
    suppressNextClick: false,
  };

  finishWallDrag(gesture);

  assert.equal(gesture.draggingWall, null);
  assert.equal(gesture.wallDragMoved, false);
  assert.equal(gesture.suppressNextClick, true);
  assert.equal(consumeCanvasClickSuppression(gesture), true);
  assert.equal(consumeCanvasClickSuppression(gesture), false);
});

test("selection mode never creates a new draft point from canvas clicks", () => {
  const result = resolveWallCanvasClick({
    mode: "select",
    draft: [],
    polylines: [{ points: [{ x: 1, y: 1, z: 0 }, { x: 4, y: 1, z: 0 }] }],
    canvasPoint: { x: 40, y: 10 },
    worldToCanvas,
    canvasToWorld: (point) => point,
  });

  assert.equal(result.action, "select");
  assert.equal(result.draft.length, 0);
});

test("deleteWallPoint removes a selected point from a completed wall", () => {
  const polylines = [
    { points: [{ x: 1, y: 1, z: 0 }, { x: 2, y: 1, z: 0 }, { x: 3, y: 1, z: 0 }] },
  ];

  const result = deleteWallPoint(polylines, { polylineIndex: 0, pointIndex: 1 });

  assert.deepEqual(result.polylines[0].points.map((point) => [point.x, point.y]), [
    [1, 1],
    [3, 1],
  ]);
  assert.equal(result.selectedIndex, 0);
  assert.equal(result.selectedPointIndex, -1);
});

test("deleteWallPoint removes the wall if fewer than two points remain", () => {
  const polylines = [
    { points: [{ x: 1, y: 1, z: 0 }, { x: 2, y: 1, z: 0 }] },
    { points: [{ x: 4, y: 4, z: 0 }, { x: 5, y: 4, z: 0 }] },
  ];

  const result = deleteWallPoint(polylines, { polylineIndex: 0, pointIndex: 1 });

  assert.equal(result.polylines.length, 1);
  assert.deepEqual(result.polylines[0].points.map((point) => [point.x, point.y]), [
    [4, 4],
    [5, 4],
  ]);
  assert.equal(result.selectedIndex, -1);
  assert.equal(result.selectedPointIndex, -1);
});
