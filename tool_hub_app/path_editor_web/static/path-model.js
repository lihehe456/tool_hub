function cloneDocument(document) {
  return JSON.parse(JSON.stringify(document));
}

function snapshotDocument(document) {
  const cloned = cloneDocument(document);
  cloned.history = { past: [], future: [] };
  return cloned;
}

export function createEmptyDocument() {
  return {
    meta: {
      path_name: "",
      type: "community",
      mode: "online",
      community: "",
      building: 0,
      unit: 0,
      floor: 0,
      door: 0,
      point_interval: 1.0,
      map_url: "",
      pcd_url: "",
    },
    drawMode: "line",
    anchors: [],
    segments: [],
    history: {
      past: [],
      future: [],
    },
  };
}

export function yawToQuaternion(yaw) {
  return {
    x: 0,
    y: 0,
    z: Math.sin(yaw / 2),
    w: Math.cos(yaw / 2),
  };
}

export function quaternionToYaw(quaternion) {
  return Math.atan2(
    2 * (quaternion.w * quaternion.z + quaternion.x * quaternion.y),
    1 - 2 * (quaternion.y * quaternion.y + quaternion.z * quaternion.z),
  );
}

export function importCompatiblePath(raw) {
  const document = createEmptyDocument();
  document.meta = {
    ...document.meta,
    path_name: raw.path_name ?? "",
    type: raw.type ?? "community",
    mode: raw.mode ?? "online",
    community: raw.community ?? "",
    building: raw.building ?? 0,
    unit: raw.unit ?? 0,
    floor: raw.floor ?? 0,
    door: raw.door ?? 0,
    point_interval: raw.point_interval ?? 1.0,
    map_url: raw.map_url ?? "",
    pcd_url: raw.pcd_url ?? "",
  };
  document.anchors = (raw.poses ?? []).map((pose) => ({
    x: pose.position.x,
    y: pose.position.y,
    z: pose.position.z,
    yaw: quaternionToYaw(pose.orientation),
  }));
  document.segments = buildLineSegments(document.anchors);
  return document;
}

export function sampleQuadraticBezier(start, control, end, numSegments = 20) {
  const points = [];
  for (let index = 0; index <= numSegments; index += 1) {
    const t = index / numSegments;
    const u = 1 - t;
    points.push({
      x: u * u * start.x + 2 * u * t * control.x + t * t * end.x,
      y: u * u * start.y + 2 * u * t * control.y + t * t * end.y,
      z: u * u * start.z + 2 * u * t * control.z + t * t * end.z,
    });
  }
  return points;
}

export function buildLineSegments(anchors) {
  const segments = [];
  for (let index = 1; index < anchors.length; index += 1) {
    segments.push({
      startIndex: index - 1,
      endIndex: index,
      type: "line",
      control: null,
    });
  }
  return segments;
}

export function addAnchor(document, anchor) {
  const nextDocument = cloneDocument(document);
  nextDocument.anchors.push(anchor);
  nextDocument.segments = buildLineSegments(nextDocument.anchors);
  return nextDocument;
}

export function insertAnchor(document, index, anchor) {
  const nextDocument = cloneDocument(document);
  const insertIndex = Math.max(0, Math.min(index, nextDocument.anchors.length));
  nextDocument.anchors.splice(insertIndex, 0, anchor);
  nextDocument.segments = buildLineSegments(nextDocument.anchors);
  return nextDocument;
}

export function moveAnchor(document, index, position) {
  const nextDocument = cloneDocument(document);
  const current = nextDocument.anchors[index];
  if (!current) {
    return nextDocument;
  }
  nextDocument.anchors[index] = { ...current, ...position };
  nextDocument.segments = buildLineSegments(nextDocument.anchors);
  return nextDocument;
}

export function setAnchorYaw(document, index, yaw) {
  const nextDocument = cloneDocument(document);
  if (!nextDocument.anchors[index]) {
    return nextDocument;
  }
  nextDocument.anchors[index].yaw = yaw;
  return nextDocument;
}

export function deleteAnchor(document, index) {
  const nextDocument = cloneDocument(document);
  nextDocument.anchors.splice(index, 1);
  nextDocument.segments = buildLineSegments(nextDocument.anchors);
  return nextDocument;
}

export function deleteAnchors(document, indexes) {
  const nextDocument = cloneDocument(document);
  const indexesToDelete = new Set(indexes);
  nextDocument.anchors = nextDocument.anchors.filter((_, index) => !indexesToDelete.has(index));
  nextDocument.segments = buildLineSegments(nextDocument.anchors);
  return nextDocument;
}

export function offsetDocument(document, delta) {
  const nextDocument = cloneDocument(document);
  const dx = Number(delta.x || 0);
  const dy = Number(delta.y || 0);
  const dz = Number(delta.z || 0);
  nextDocument.anchors = nextDocument.anchors.map((anchor) => ({
    ...anchor,
    x: anchor.x + dx,
    y: anchor.y + dy,
    z: anchor.z + dz,
  }));
  nextDocument.segments = nextDocument.segments.map((segment) => ({
    ...segment,
    control: segment.control
      ? {
          ...segment.control,
          x: segment.control.x + dx,
          y: segment.control.y + dy,
          z: segment.control.z + dz,
        }
      : segment.control,
  }));
  return nextDocument;
}

export function setSegmentControl(document, segmentIndex, control) {
  const nextDocument = cloneDocument(document);
  if (!nextDocument.segments[segmentIndex]) {
    return nextDocument;
  }
  nextDocument.segments[segmentIndex] = {
    ...nextDocument.segments[segmentIndex],
    type: "bezier",
    control,
  };
  return nextDocument;
}

export function moveControlPoint(document, segmentIndex, control) {
  const nextDocument = cloneDocument(document);
  if (!nextDocument.segments[segmentIndex]) {
    return nextDocument;
  }
  nextDocument.segments[segmentIndex].control = control;
  nextDocument.segments[segmentIndex].type = "bezier";
  return nextDocument;
}

function segmentPoints(document) {
  if (document.drawMode !== "bezier") {
    return document.anchors.map(({ x, y, z }) => ({ x, y, z }));
  }

  const points = [];
  const segments = document.segments.length > 0 ? document.segments : buildLineSegments(document.anchors);
  segments.forEach((segment, index) => {
    const start = document.anchors[segment.startIndex];
    const end = document.anchors[segment.endIndex];
    if (!start || !end) {
      return;
    }

    let sampled = [
      { x: start.x, y: start.y, z: start.z },
      { x: end.x, y: end.y, z: end.z },
    ];
    if (segment.type === "bezier" && segment.control) {
      sampled = sampleQuadraticBezier(start, segment.control, end, 20);
    }

    if (index > 0) {
      sampled = sampled.slice(1);
    }
    points.push(...sampled);
  });
  return points;
}

function resamplePoints(points, interval) {
  if (points.length < 2 || interval <= 0) {
    return points;
  }

  const resampled = [points[0]];
  let carried = 0;

  for (let index = 1; index < points.length; index += 1) {
    const prev = points[index - 1];
    const curr = points[index];
    const dx = curr.x - prev.x;
    const dy = curr.y - prev.y;
    const dz = curr.z - prev.z;
    const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);

    if (distance < 1e-9) {
      continue;
    }

    let segmentOffset = 0;
    let remaining = distance;
    while (carried + remaining >= interval) {
      const needed = interval - carried;
      const t = (segmentOffset + needed) / distance;
      resampled.push({
        x: prev.x + dx * t,
        y: prev.y + dy * t,
        z: prev.z + dz * t,
      });
      segmentOffset += needed;
      remaining -= needed;
      carried = 0;
    }

    carried += remaining;
  }

  const last = points.at(-1);
  const tail = resampled.at(-1);
  const dx = last.x - tail.x;
  const dy = last.y - tail.y;
  const dz = last.z - tail.z;
  if (Math.sqrt(dx * dx + dy * dy + dz * dz) > 1e-6) {
    resampled.push(last);
  }

  return resampled;
}

function poseFromPoint(point, nextPoint, fallbackYaw) {
  const yaw = nextPoint
    ? Math.atan2(nextPoint.y - point.y, nextPoint.x - point.x)
    : fallbackYaw;
  return {
    position: {
      x: point.x,
      y: point.y,
      z: point.z,
    },
    orientation: yawToQuaternion(yaw),
  };
}

export function exportCompatiblePath(document) {
  if (document.drawMode !== "bezier") {
    const poses = document.anchors.map((anchor, index) => ({
      waypoint_id: `${document.meta.path_name}_${index}`,
      position: {
        x: anchor.x,
        y: anchor.y,
        z: anchor.z,
      },
      orientation: yawToQuaternion(anchor.yaw),
    }));

    return {
      num: poses.length,
      path_name: document.meta.path_name,
      type: document.meta.type ?? "community",
      mode: document.meta.mode ?? "online",
      community: document.meta.community,
      building: document.meta.building,
      unit: document.meta.unit,
      floor: document.meta.floor,
      door: document.meta.door,
      point_interval: document.meta.point_interval,
      map_url: document.meta.map_url,
      pcd_url: document.meta.pcd_url,
      poses,
    };
  }

  const basePoints = segmentPoints(document);
  const points = resamplePoints(basePoints, document.meta.point_interval);

  const poses = points.map((point, index) => {
    const nextPoint = points[index + 1];
    const fallbackYaw = document.anchors.at(-1)?.yaw ?? 0;
    const pose = poseFromPoint(point, nextPoint, fallbackYaw);
    return {
      waypoint_id: `${document.meta.path_name}_${index}`,
      ...pose,
    };
  });

  return {
    num: poses.length,
    path_name: document.meta.path_name,
    type: document.meta.type ?? "community",
    mode: document.meta.mode ?? "online",
    community: document.meta.community,
    building: document.meta.building,
    unit: document.meta.unit,
    floor: document.meta.floor,
    door: document.meta.door,
    point_interval: document.meta.point_interval,
    map_url: document.meta.map_url,
    pcd_url: document.meta.pcd_url,
    poses,
  };
}

export function pushHistory(previousDocument, nextDocument) {
  const history = previousDocument.history ?? { past: [], future: [] };
  return {
    ...cloneDocument(nextDocument),
    history: {
      past: [...history.past, snapshotDocument(previousDocument)],
      future: [],
    },
  };
}

export function undo(document) {
  if (!document.history?.past?.length) {
    return document;
  }

  const previous = cloneDocument(document.history.past.at(-1));
  const currentClone = snapshotDocument(document);
  return {
    ...previous,
    history: {
      past: document.history.past.slice(0, -1),
      future: [currentClone, ...(document.history.future ?? [])],
    },
  };
}

export function redo(document) {
  if (!document.history?.future?.length) {
    return document;
  }

  const next = cloneDocument(document.history.future[0]);
  const currentClone = snapshotDocument(document);
  return {
    ...next,
    history: {
      past: [...(document.history.past ?? []), currentClone],
      future: document.history.future.slice(1),
    },
  };
}
