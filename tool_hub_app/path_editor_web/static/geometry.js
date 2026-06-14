export function worldToCanvas(point, map, view) {
  const [originX, originY] = map.origin;
  const pixelX = (point.x - originX) / map.resolution;
  const pixelY = map.imageHeight - (point.y - originY) / map.resolution;

  return {
    x: view.offsetX + pixelX * view.scale,
    y: view.offsetY + pixelY * view.scale,
  };
}

export function canvasToWorld(point, map, view) {
  const pixelX = (point.x - view.offsetX) / view.scale;
  const pixelY = (point.y - view.offsetY) / view.scale;

  return {
    x: map.origin[0] + pixelX * map.resolution,
    y: map.origin[1] + (map.imageHeight - pixelY) * map.resolution,
  };
}

export function worldYawToCanvasDelta(yaw, length) {
  return {
    x: Math.cos(yaw) * length,
    y: -Math.sin(yaw) * length,
  };
}

export function canvasDeltaToWorldYaw(delta) {
  return Math.atan2(-delta.y, delta.x);
}

export function chooseGridSpacingMeters(map, view) {
  const pixelsPerMeter = view.scale / map.resolution;
  const preferredPixels = 36;
  const candidates = [1, 2, 5, 10, 20];
  for (const spacing of candidates) {
    if (pixelsPerMeter * spacing >= preferredPixels) {
      return spacing;
    }
  }
  return candidates.at(-1);
}

export function distanceSquared(a, b) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return dx * dx + dy * dy;
}

export function findNearestAnchor(point, anchors, threshold) {
  const thresholdSquared = threshold * threshold;
  let best = null;

  anchors.forEach((anchor, index) => {
    const distance = distanceSquared(point, anchor);
    if (distance <= thresholdSquared && (!best || distance < best.distanceSquared)) {
      best = { index, distanceSquared: distance };
    }
  });

  return best;
}

export function findNearestControlPoint(point, segments, threshold) {
  const thresholdSquared = threshold * threshold;
  let best = null;

  segments.forEach((segment, index) => {
    if (!segment.control) {
      return;
    }
    const distance = distanceSquared(point, segment.control);
    if (distance <= thresholdSquared && (!best || distance < best.distanceSquared)) {
      best = { index, distanceSquared: distance };
    }
  });

  return best;
}

function pointToSegmentDistanceSquared(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  if (dx === 0 && dy === 0) {
    return distanceSquared(point, start);
  }

  const t = Math.max(
    0,
    Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)),
  );
  const projection = {
    x: start.x + t * dx,
    y: start.y + t * dy,
  };
  return distanceSquared(point, projection);
}

export function findNearestSegment(point, segments, threshold = Infinity) {
  const thresholdSquared = Number.isFinite(threshold) ? threshold * threshold : Infinity;
  let best = null;

  segments.forEach((segment, index) => {
    const distance = pointToSegmentDistanceSquared(point, segment.start, segment.end);
    if (distance <= thresholdSquared && (!best || distance < best.distanceSquared)) {
      best = { index, distanceSquared: distance };
    }
  });

  return best;
}
