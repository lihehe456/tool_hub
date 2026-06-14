import assert from "node:assert/strict";
import test from "node:test";

import {
  addAnchor,
  createEmptyDocument,
  deleteAnchor,
  deleteAnchors,
  exportCompatiblePath,
  importCompatiblePath,
  insertAnchor,
  moveAnchor,
  moveControlPoint,
  offsetDocument,
  pushHistory,
  quaternionToYaw,
  redo,
  sampleQuadraticBezier,
  setSegmentControl,
  setAnchorYaw,
  undo,
  yawToQuaternion,
} from "../path-model.js";

test("compatible JSON imports into anchors and meta", () => {
  const doc = importCompatiblePath({
    path_name: "A",
    community: "demo",
    point_interval: 0.5,
    poses: [
      {
        waypoint_id: "A_0",
        position: { x: 1, y: 2, z: 0 },
        orientation: yawToQuaternion(Math.PI / 2),
      },
    ],
  });

  assert.equal(doc.meta.path_name, "A");
  assert.equal(doc.meta.community, "demo");
  assert.equal(doc.meta.point_interval, 0.5);
  assert.equal(doc.anchors.length, 1);
  assert.equal(
    Math.round(doc.anchors[0].yaw * 1000),
    Math.round((Math.PI / 2) * 1000),
  );
});

test("yaw and quaternion conversion round-trips", () => {
  const yaw = Math.PI / 3;
  const quaternion = yawToQuaternion(yaw);

  assert.ok(Math.abs(quaternionToYaw(quaternion) - yaw) < 1e-9);
});

test("quadratic bezier sampling returns requested point count", () => {
  const points = sampleQuadraticBezier(
    { x: 0, y: 0, z: 0 },
    { x: 1, y: 1, z: 0 },
    { x: 2, y: 0, z: 0 },
    20,
  );

  assert.equal(points.length, 21);
  assert.deepEqual(points[0], { x: 0, y: 0, z: 0 });
  assert.deepEqual(points.at(-1), { x: 2, y: 0, z: 0 });
});

test("line-mode export preserves anchors and numbering", () => {
  const exported = exportCompatiblePath({
    ...createEmptyDocument(),
    meta: {
      path_name: "route",
      community: "demo",
      point_interval: 0.5,
      map_url: "/maps/demo.yaml",
      pcd_url: "/pcd/demo",
      building: 1,
      unit: 2,
      floor: 3,
      door: 4,
    },
    anchors: [
      { x: 1, y: 2, z: 0, yaw: 0 },
      { x: 2, y: 3, z: 0, yaw: Math.PI / 2 },
    ],
  });

  assert.equal(exported.num, 2);
  assert.equal(exported.path_name, "route");
  assert.equal(exported.community, "demo");
  assert.equal(exported.poses[0].waypoint_id, "route_0");
  assert.equal(exported.poses[1].waypoint_id, "route_1");
  assert.equal(exported.poses[1].position.x, 2);
});

test("line-mode export preserves edited anchor yaw instead of path tangent", () => {
  const editedYaw = Math.PI / 2;
  const exported = exportCompatiblePath({
    ...createEmptyDocument(),
    meta: {
      path_name: "route",
      community: "demo",
      point_interval: 0.5,
      map_url: "",
      pcd_url: "",
      building: 0,
      unit: 0,
      floor: 0,
      door: 0,
    },
    anchors: [
      { x: 0, y: 0, z: 0, yaw: editedYaw },
      { x: 2, y: 0, z: 0, yaw: 0 },
    ],
  });

  const firstYaw = quaternionToYaw(exported.poses[0].orientation);
  assert.ok(Math.abs(firstYaw - editedYaw) < 1e-9);
});

test("bezier-mode export resamples using point interval", () => {
  const exported = exportCompatiblePath({
    ...createEmptyDocument(),
    drawMode: "bezier",
    meta: {
      path_name: "curve",
      community: "demo",
      point_interval: 0.5,
      map_url: "",
      pcd_url: "",
      building: 0,
      unit: 0,
      floor: 0,
      door: 0,
    },
    anchors: [
      { x: 0, y: 0, z: 0, yaw: 0 },
      { x: 2, y: 0, z: 0, yaw: 0 },
    ],
    segments: [
      {
        startIndex: 0,
        endIndex: 1,
        type: "bezier",
        control: { x: 1, y: 1, z: 0 },
      },
    ],
  });

  assert.ok(exported.num >= 4);
  assert.equal(exported.poses[0].waypoint_id, "curve_0");
  assert.equal(exported.poses.at(-1).position.x, 2);
});

test("history push undo and redo restores prior document snapshots", () => {
  const empty = createEmptyDocument();
  const withFirstHistory = pushHistory(empty, {
    ...empty,
    anchors: [{ x: 1, y: 2, z: 0, yaw: 0 }],
  });
  const undone = undo(withFirstHistory);
  const redone = redo(undone);

  assert.equal(withFirstHistory.history.past.length, 1);
  assert.equal(undone.anchors.length, 0);
  assert.equal(redone.anchors.length, 1);
});

test("history snapshots do not recursively retain nested history", () => {
  let doc = createEmptyDocument();
  doc = addAnchor(doc, { x: 0, y: 0, z: 0, yaw: 0 });
  doc = pushHistory(createEmptyDocument(), doc);

  const next = deleteAnchor(doc, 0);
  const withDeleteHistory = pushHistory(doc, next);

  assert.equal(withDeleteHistory.history.past.length, 2);
  assert.deepEqual(withDeleteHistory.history.past[0].history, { past: [], future: [] });
  assert.deepEqual(withDeleteHistory.history.past[1].history, { past: [], future: [] });
});

test("editing helpers update anchors and rebuild line segments", () => {
  let doc = createEmptyDocument();
  doc = addAnchor(doc, { x: 0, y: 0, z: 0, yaw: 0 });
  doc = addAnchor(doc, { x: 1, y: 0, z: 0, yaw: 0 });
  doc = addAnchor(doc, { x: 2, y: 0, z: 0, yaw: 0 });
  doc = moveAnchor(doc, 1, { x: 1, y: 2, z: 0 });
  doc = setAnchorYaw(doc, 1, Math.PI / 4);
  doc = deleteAnchor(doc, 1);

  assert.equal(doc.anchors.length, 2);
  assert.equal(doc.segments.length, 1);
  assert.equal(doc.anchors[1].x, 2);
});

test("offsetDocument translates every anchor and bezier control", () => {
  const doc = {
    ...createEmptyDocument(),
    anchors: [
      { x: 1, y: 2, z: 0, yaw: 0 },
      { x: 3, y: 4, z: 0, yaw: 0 },
    ],
    segments: [
      {
        startIndex: 0,
        endIndex: 1,
        type: "bezier",
        control: { x: 2, y: 3, z: 0 },
      },
    ],
  };

  const shifted = offsetDocument(doc, { x: 10, y: -2, z: 0 });

  assert.deepEqual(shifted.anchors.map((anchor) => [anchor.x, anchor.y]), [
    [11, 0],
    [13, 2],
  ]);
  assert.deepEqual(shifted.segments[0].control, { x: 12, y: 1, z: 0 });
});

test("deleteAnchors removes multiple points and rebuilds sequential segments", () => {
  let doc = createEmptyDocument();
  doc = addAnchor(doc, { x: 0, y: 0, z: 0, yaw: 0 });
  doc = addAnchor(doc, { x: 1, y: 0, z: 0, yaw: 0 });
  doc = addAnchor(doc, { x: 2, y: 0, z: 0, yaw: 0 });
  doc = addAnchor(doc, { x: 3, y: 0, z: 0, yaw: 0 });

  const next = deleteAnchors(doc, [1, 3]);

  assert.deepEqual(next.anchors.map((anchor) => anchor.x), [0, 2]);
  assert.deepEqual(
    next.segments.map((segment) => [segment.startIndex, segment.endIndex]),
    [[0, 1]],
  );
});

test("insertAnchor inserts a point between neighboring anchors and keeps numbering sequential on export", () => {
  let doc = createEmptyDocument();
  doc.meta.path_name = "route";
  doc = addAnchor(doc, { x: 0, y: 0, z: 0, yaw: 0 });
  doc = addAnchor(doc, { x: 4, y: 0, z: 0, yaw: 0 });
  doc = insertAnchor(doc, 1, { x: 2, y: 0, z: 0, yaw: 0 });

  assert.equal(doc.anchors.length, 3);
  assert.deepEqual(doc.anchors.map((anchor) => anchor.x), [0, 2, 4]);
  assert.equal(doc.segments.length, 2);
  assert.deepEqual(
    doc.segments.map((segment) => [segment.startIndex, segment.endIndex]),
    [[0, 1], [1, 2]],
  );

  const exported = exportCompatiblePath(doc);
  assert.deepEqual(
    exported.poses.map((pose) => pose.waypoint_id),
    ["route_0", "route_1", "route_2"],
  );
});

test("segment control helpers attach and move bezier controls", () => {
  let doc = createEmptyDocument();
  doc = addAnchor(doc, { x: 0, y: 0, z: 0, yaw: 0 });
  doc = addAnchor(doc, { x: 2, y: 0, z: 0, yaw: 0 });
  doc = setSegmentControl(doc, 0, { x: 1, y: 1, z: 0 });
  doc = moveControlPoint(doc, 0, { x: 1, y: 2, z: 0 });

  assert.equal(doc.segments[0].type, "bezier");
  assert.deepEqual(doc.segments[0].control, { x: 1, y: 2, z: 0 });
});
