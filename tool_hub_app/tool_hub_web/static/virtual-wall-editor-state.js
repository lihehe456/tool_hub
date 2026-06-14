export function distanceSquared(a, b) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return dx * dx + dy * dy;
}

export function distanceToSegment(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  if (dx === 0 && dy === 0) {
    return Math.hypot(point.x - start.x, point.y - start.y);
  }
  const t = Math.max(
    0,
    Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)),
  );
  return Math.hypot(point.x - (start.x + t * dx), point.y - (start.y + t * dy));
}

export function projectPointToSegment(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  if (dx === 0 && dy === 0) {
    return { x: start.x, y: start.y, z: point.z ?? start.z ?? 0 };
  }
  const t = Math.max(
    0,
    Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)),
  );
  return {
    x: roundCoordinate(start.x + t * dx),
    y: roundCoordinate(start.y + t * dy),
    z: point.z ?? start.z ?? 0,
  };
}

function roundCoordinate(value) {
  return Math.round(value * 1e9) / 1e9;
}

export function findNearestWallPoint(polylines, canvasPoint, worldToCanvas, threshold = 12) {
  const thresholdSquared = threshold * threshold;
  let best = null;
  polylines.forEach((polyline, polylineIndex) => {
    (polyline.points ?? []).forEach((point, pointIndex) => {
      const distance = distanceSquared(canvasPoint, worldToCanvas(point));
      if (distance <= thresholdSquared && (!best || distance < best.distanceSquared)) {
        best = { polylineIndex, pointIndex, distanceSquared: distance };
      }
    });
  });
  return best;
}

export function findNearestWallSegment(polylines, canvasPoint, worldToCanvas, threshold = 10) {
  let best = null;
  polylines.forEach((polyline, polylineIndex) => {
    const points = polyline.points ?? [];
    for (let pointIndex = 0; pointIndex < points.length - 1; pointIndex += 1) {
      const distance = distanceToSegment(
        canvasPoint,
        worldToCanvas(points[pointIndex]),
        worldToCanvas(points[pointIndex + 1]),
      );
      if (distance <= threshold && (!best || distance < best.distance)) {
        best = { polylineIndex, insertAfterPointIndex: pointIndex, distance };
      }
    }
  });
  return best;
}

export function insertWallPoint(polylines, hit, worldPoint) {
  if (!hit) {
    return polylines;
  }
  return polylines.map((polyline, polylineIndex) => {
    if (polylineIndex !== hit.polylineIndex) {
      return polyline;
    }
    const points = [...(polyline.points ?? [])];
    points.splice(hit.insertAfterPointIndex + 1, 0, { ...worldPoint, z: worldPoint.z ?? 0 });
    return { ...polyline, points };
  });
}

export function moveWallPoint(polylines, hit, worldPoint) {
  if (!hit) {
    return polylines;
  }
  return polylines.map((polyline, polylineIndex) => {
    if (polylineIndex !== hit.polylineIndex) {
      return polyline;
    }
    return {
      ...polyline,
      points: (polyline.points ?? []).map((point, pointIndex) =>
        pointIndex === hit.pointIndex ? { ...worldPoint, z: worldPoint.z ?? point.z ?? 0 } : point,
      ),
    };
  });
}

export function moveWallPolyline(polylines, polylineIndexToMove, delta) {
  return polylines.map((polyline, polylineIndex) => {
    if (polylineIndex !== polylineIndexToMove) {
      return polyline;
    }
    return {
      ...polyline,
      points: (polyline.points ?? []).map((point) => ({
        x: roundCoordinate(point.x + delta.x),
        y: roundCoordinate(point.y + delta.y),
        z: roundCoordinate((point.z ?? 0) + (delta.z ?? 0)),
      })),
    };
  });
}

export function moveWallPolylines(polylines, polylineIndexesToMove, delta) {
  const selectedIndexes = new Set(polylineIndexesToMove);
  return polylines.map((polyline, polylineIndex) => {
    if (!selectedIndexes.has(polylineIndex)) {
      return polyline;
    }
    return {
      ...polyline,
      points: (polyline.points ?? []).map((point) => ({
        x: roundCoordinate(point.x + delta.x),
        y: roundCoordinate(point.y + delta.y),
        z: roundCoordinate((point.z ?? 0) + (delta.z ?? 0)),
      })),
    };
  });
}

export function toggleWallSelection(selectedIndexes, polylineIndex) {
  const selected = new Set(selectedIndexes);
  if (selected.has(polylineIndex)) {
    selected.delete(polylineIndex);
  } else {
    selected.add(polylineIndex);
  }
  return Array.from(selected).sort((left, right) => left - right);
}

export function finishPointDrag(gestureState) {
  if (gestureState.draggingPoint && gestureState.dragMoved) {
    gestureState.suppressNextClick = true;
  }
  gestureState.draggingPoint = null;
  gestureState.dragMoved = false;
}

export function finishWallDrag(gestureState) {
  if (gestureState.draggingWall && gestureState.wallDragMoved) {
    gestureState.suppressNextClick = true;
  }
  gestureState.draggingWall = null;
  gestureState.wallDragMoved = false;
}

export function consumeCanvasClickSuppression(gestureState) {
  if (!gestureState.suppressNextClick) {
    return false;
  }
  gestureState.suppressNextClick = false;
  return true;
}

export function resolveWallCanvasClick({
  mode,
  draft,
  polylines,
  canvasPoint,
  worldToCanvas,
  canvasToWorld,
}) {
  const pointHit = findNearestWallPoint(polylines, canvasPoint, worldToCanvas, 12);
  if (pointHit) {
    return {
      action: "select",
      selectedIndex: pointHit.polylineIndex,
      selectedPointIndex: pointHit.pointIndex,
      draft,
      polylines,
    };
  }

  const segmentHit = findNearestWallSegment(polylines, canvasPoint, worldToCanvas, 10);
  if (mode !== "draw") {
    return {
      action: segmentHit ? "select" : "none",
      selectedIndex: segmentHit?.polylineIndex ?? -1,
      selectedPointIndex: -1,
      draft,
      polylines,
    };
  }

  if (draft.length === 0 && segmentHit) {
    const worldPoint = canvasToWorld(canvasPoint);
    const polyline = polylines[segmentHit.polylineIndex];
    const projectedPoint = projectPointToSegment(
      worldPoint,
      polyline.points[segmentHit.insertAfterPointIndex],
      polyline.points[segmentHit.insertAfterPointIndex + 1],
    );
    return {
      action: "insert",
      selectedIndex: segmentHit.polylineIndex,
      selectedPointIndex: segmentHit.insertAfterPointIndex + 1,
      draft,
      polylines: insertWallPoint(polylines, segmentHit, projectedPoint),
    };
  }

  return {
    action: "draw",
    selectedIndex: -1,
    selectedPointIndex: -1,
    draft: [...draft, canvasToWorld(canvasPoint)],
    polylines,
  };
}

export function deleteWallPoint(polylines, hit) {
  if (!hit || hit.polylineIndex < 0 || hit.pointIndex < 0) {
    return {
      polylines,
      selectedIndex: -1,
      selectedPointIndex: -1,
    };
  }

  const nextPolylines = [];
  let removedWholeWall = false;
  polylines.forEach((polyline, polylineIndex) => {
    if (polylineIndex !== hit.polylineIndex) {
      nextPolylines.push(polyline);
      return;
    }
    const points = (polyline.points ?? []).filter((_, pointIndex) => pointIndex !== hit.pointIndex);
    if (points.length >= 2) {
      nextPolylines.push({ ...polyline, points });
      return;
    }
    removedWholeWall = true;
  });

  return {
    polylines: nextPolylines,
    selectedIndex: removedWholeWall ? -1 : hit.polylineIndex,
    selectedPointIndex: -1,
  };
}
