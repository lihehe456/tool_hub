const DEFAULT_SCALE = 1;
const MIN_SCALE = 0.25;
const MAX_SCALE = 8;

export function createViewerState() {
  return {
    scale: DEFAULT_SCALE,
    offsetX: 0,
    offsetY: 0,
    isDragging: false,
    dragStartX: 0,
    dragStartY: 0,
    dragOriginX: 0,
    dragOriginY: 0,
  };
}

function clampScale(scale) {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
}

export function zoomViewerAtPoint(state, nextScale, point) {
  const scale = clampScale(nextScale);
  const zoomRatio = scale / state.scale;
  return {
    ...state,
    scale,
    offsetX: point.x - (point.x - state.offsetX) * zoomRatio,
    offsetY: point.y - (point.y - state.offsetY) * zoomRatio,
  };
}

export function panViewer(state, delta) {
  return {
    ...state,
    offsetX: state.offsetX + delta.dx,
    offsetY: state.offsetY + delta.dy,
  };
}

export function resetViewer() {
  return createViewerState();
}

export function fitViewerToFrame(state, frameWidth, frameHeight, imageWidth, imageHeight) {
  if (!frameWidth || !frameHeight || !imageWidth || !imageHeight) {
    return resetViewer(state);
  }

  const scale = clampScale(Math.min(frameWidth / imageWidth, frameHeight / imageHeight));
  const scaledWidth = imageWidth * scale;
  const scaledHeight = imageHeight * scale;
  return {
    ...state,
    scale,
    offsetX: (frameWidth - scaledWidth) / 2,
    offsetY: (frameHeight - scaledHeight) / 2,
    isDragging: false,
    dragStartX: 0,
    dragStartY: 0,
    dragOriginX: 0,
    dragOriginY: 0,
  };
}
