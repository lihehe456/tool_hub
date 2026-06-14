import assert from "node:assert/strict";
import test from "node:test";

import {
  chooseGridSpacingMeters,
  canvasDeltaToWorldYaw,
  canvasToWorld,
  distanceSquared,
  findNearestAnchor,
  findNearestControlPoint,
  findNearestSegment,
  worldYawToCanvasDelta,
  worldToCanvas,
} from "../geometry.js";

test("world/canvas conversion round-trips", () => {
  const view = { scale: 2, offsetX: 100, offsetY: 50 };
  const map = { resolution: 0.05, origin: [1, 2, 0], imageHeight: 400 };
  const canvasPoint = worldToCanvas({ x: 3, y: 4 }, map, view);
  const worldPoint = canvasToWorld(canvasPoint, map, view);

  assert.ok(Math.abs(worldPoint.x - 3) < 1e-6);
  assert.ok(Math.abs(worldPoint.y - 4) < 1e-6);
});

test("distanceSquared computes planar squared distance", () => {
  assert.equal(distanceSquared({ x: 1, y: 2 }, { x: 4, y: 6 }), 25);
});

test("findNearestAnchor returns the closest hit under threshold", () => {
  const anchors = [
    { x: 10, y: 10 },
    { x: 30, y: 30 },
  ];
  const hit = findNearestAnchor({ x: 12, y: 12 }, anchors, 5);
  const miss = findNearestAnchor({ x: 100, y: 100 }, anchors, 5);

  assert.equal(hit.index, 0);
  assert.equal(miss, null);
});

test("findNearestControlPoint and nearest segment behave predictably", () => {
  const controlHit = findNearestControlPoint(
    { x: 12, y: 11 },
    [{ control: { x: 10, y: 10 } }],
    5,
  );
  const segmentHit = findNearestSegment(
    { x: 10, y: 2 },
    [
      { start: { x: 0, y: 0 }, end: { x: 20, y: 0 } },
      { start: { x: 30, y: 30 }, end: { x: 40, y: 30 } },
    ],
  );

  assert.equal(controlHit.index, 0);
  assert.equal(segmentHit.index, 0);
});

test("world yaw converts to upward canvas direction for positive pi/2", () => {
  const delta = worldYawToCanvasDelta(Math.PI / 2, 10);

  assert.ok(Math.abs(delta.x) < 1e-9);
  assert.equal(delta.y, -10);
});

test("canvas delta converts back to world yaw with inverted y axis", () => {
  const yaw = canvasDeltaToWorldYaw({ x: 0, y: -10 });

  assert.ok(Math.abs(yaw - Math.PI / 2) < 1e-9);
});

test("world origin projects into canvas space using map origin", () => {
  const view = { scale: 4, offsetX: 20, offsetY: 30 };
  const map = { resolution: 0.5, origin: [1, 2, 0], imageHeight: 100 };

  const canvasPoint = worldToCanvas({ x: 1, y: 2 }, map, view);

  assert.equal(canvasPoint.x, 20);
  assert.equal(canvasPoint.y, 430);
});

test("chooseGridSpacingMeters adapts to zoom level", () => {
  const map = { resolution: 0.05 };

  assert.equal(chooseGridSpacingMeters(map, { scale: 4 }), 1);
  assert.equal(chooseGridSpacingMeters(map, { scale: 0.4 }), 5);
});
