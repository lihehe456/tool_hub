import {
  chooseGridSpacingMeters,
  canvasDeltaToWorldYaw,
  canvasToWorld,
  findNearestAnchor,
  findNearestSegment,
  worldYawToCanvasDelta,
  worldToCanvas,
} from "./geometry.js";

const TOOL_SELECT = "select";
const TOOL_ADD = "add";
const TOOL_INSERT = "insert";
const TOOL_MOVE = "move";
const TOOL_ROTATE = "rotate";
const TOOL_DELETE = "delete";
const ALIGNMENT_THRESHOLD_METERS = 0.2;
const SEGMENT_HIT_THRESHOLD_PX = 12;

export class PathCanvas {
  constructor(canvas, callbacks = {}) {
    this.canvas = canvas;
    this.context = canvas.getContext("2d");
    this.callbacks = callbacks;
    this.view = { scale: 1, offsetX: 0, offsetY: 0 };
    this.document = null;
    this.mapData = null;
    this.virtualWalls = [];
    this.activeTool = TOOL_SELECT;
    this.selection = { kind: "none" };
    this.draggingAnchorIndex = null;
    this.rotatingAnchorIndex = null;
    this.addingAnchorIndex = null;
    this.panning = false;
    this.lastPointer = null;
    this.alignmentGuides = null;

    this.canvas.addEventListener("pointerdown", this.onPointerDown.bind(this));
    this.canvas.addEventListener("pointermove", this.onPointerMove.bind(this));
    this.canvas.addEventListener("pointerup", this.onPointerUp.bind(this));
    this.canvas.addEventListener("pointerleave", this.onPointerUp.bind(this));
    this.canvas.addEventListener("wheel", this.onWheel.bind(this), { passive: false });
    this.canvas.addEventListener("contextmenu", (event) => event.preventDefault());
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = Math.max(1, Math.floor(rect.width));
    this.canvas.height = Math.max(1, Math.floor(rect.height));
    this.draw();
  }

  setDocument(document) {
    this.document = document;
    this.draw();
  }

  setMapData(mapData) {
    this.mapData = mapData;
    this.fitMap();
    this.draw();
  }

  setVirtualWalls(virtualWalls) {
    this.virtualWalls = Array.isArray(virtualWalls) ? virtualWalls : [];
    this.draw();
  }

  setTool(tool) {
    this.activeTool = tool;
  }

  setSelection(selection) {
    this.selection = selection;
    this.draw();
  }

  fitMap() {
    if (!this.mapData) {
      return;
    }

    const scale = Math.min(
      this.canvas.width / this.mapData.width,
      this.canvas.height / this.mapData.height,
    ) * 0.92;
    this.view.scale = scale;
    this.view.offsetX = (this.canvas.width - this.mapData.width * scale) / 2;
    this.view.offsetY = (this.canvas.height - this.mapData.height * scale) / 2;
  }

  mapInfo() {
    return {
      resolution: this.mapData?.resolution ?? 0.05,
      origin: this.mapData?.origin ?? [0, 0, 0],
      imageHeight: this.mapData?.height ?? 1000,
    };
  }

  gridSpacingMeters() {
    return chooseGridSpacingMeters(this.mapInfo(), this.view);
  }

  canvasPointFromEvent(event) {
    const rect = this.canvas.getBoundingClientRect();
    return {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
  }

  worldPointFromEvent(event) {
    return canvasToWorld(this.canvasPointFromEvent(event), this.mapInfo(), this.view);
  }

  editableWorldPointFromEvent(event) {
    return this.worldPointFromEvent(event);
  }

  originCanvasPoint() {
    return worldToCanvas({ x: 0, y: 0 }, this.mapInfo(), this.view);
  }

  clearAlignmentGuides() {
    this.alignmentGuides = null;
  }

  alignmentGuidesForWorldPoint(point, options = {}) {
    if (!this.document?.anchors?.length) {
      return null;
    }

    const excludedAnchorIndex = options.excludedAnchorIndex;
    let vertical = null;
    let horizontal = null;

    this.document.anchors.forEach((anchor, index) => {
      if (index === excludedAnchorIndex) {
        return;
      }
      const dx = Math.abs(anchor.x - point.x);
      const dy = Math.abs(anchor.y - point.y);

      if (dx <= ALIGNMENT_THRESHOLD_METERS && (!vertical || dx < vertical.distance)) {
        vertical = { anchorIndex: index, x: anchor.x, distance: dx };
      }
      if (dy <= ALIGNMENT_THRESHOLD_METERS && (!horizontal || dy < horizontal.distance)) {
        horizontal = { anchorIndex: index, y: anchor.y, distance: dy };
      }
    });

    if (!vertical && !horizontal) {
      return null;
    }

    return {
      vertical: vertical ? { anchorIndex: vertical.anchorIndex, x: vertical.x } : null,
      horizontal: horizontal ? { anchorIndex: horizontal.anchorIndex, y: horizontal.y } : null,
    };
  }

  anchorCanvasPoints() {
    if (!this.document) {
      return [];
    }
    return this.document.anchors.map((anchor, index) => ({
      index,
      ...worldToCanvas(anchor, this.mapInfo(), this.view),
    }));
  }

  segmentCanvasLines() {
    if (!this.document) {
      return [];
    }
    return this.document.segments.map((segment, index) => ({
      index,
      start: worldToCanvas(this.document.anchors[segment.startIndex], this.mapInfo(), this.view),
      end: worldToCanvas(this.document.anchors[segment.endIndex], this.mapInfo(), this.view),
    }));
  }

  onPointerDown(event) {
    const point = this.canvasPointFromEvent(event);

    if (event.button === 1 || event.button === 2) {
      this.panning = true;
      this.lastPointer = point;
      return;
    }

    const hit = findNearestAnchor(point, this.anchorCanvasPoints(), 10);
    if (this.activeTool === TOOL_ADD) {
      this.callbacks.onAddAnchor?.(this.editableWorldPointFromEvent(event));
      if (this.document?.anchors?.length) {
        this.addingAnchorIndex = this.document.anchors.length - 1;
        this.rotatingAnchorIndex = this.addingAnchorIndex;
        this.callbacks.onSelect?.({ kind: "anchor", index: this.addingAnchorIndex });
      }
      this.clearAlignmentGuides();
      this.draw();
      return;
    }

    if (this.activeTool === TOOL_INSERT) {
      const segmentHit = findNearestSegment(point, this.segmentCanvasLines(), SEGMENT_HIT_THRESHOLD_PX);
      if (segmentHit) {
        this.callbacks.onInsertAnchor?.(segmentHit.index, this.editableWorldPointFromEvent(event));
        this.clearAlignmentGuides();
        this.draw();
      }
      return;
    }

    if (this.activeTool === TOOL_DELETE && hit) {
      this.callbacks.onDeleteAnchor?.(hit.index);
      return;
    }

    if (hit) {
      if (event.ctrlKey || event.metaKey || event.shiftKey) {
        this.callbacks.onToggleAnchorSelection?.(hit.index);
        return;
      }
      this.callbacks.onSelect?.({ kind: "anchor", index: hit.index });
      if (this.activeTool === TOOL_MOVE) {
        this.draggingAnchorIndex = hit.index;
      } else if (this.activeTool === TOOL_ROTATE) {
        this.rotatingAnchorIndex = hit.index;
      }
    } else {
      this.callbacks.onSelect?.({ kind: "none" });
    }
  }

  onPointerMove(event) {
    const point = this.canvasPointFromEvent(event);
    const worldPoint = this.worldPointFromEvent(event);

    if (this.panning && this.lastPointer) {
      this.view.offsetX += point.x - this.lastPointer.x;
      this.view.offsetY += point.y - this.lastPointer.y;
      this.lastPointer = point;
      this.draw();
      return;
    }

    if (this.activeTool === TOOL_ADD && this.addingAnchorIndex == null) {
      this.alignmentGuides = this.alignmentGuidesForWorldPoint(worldPoint);
      this.draw();
      return;
    }

    if (this.draggingAnchorIndex != null) {
      this.alignmentGuides = this.alignmentGuidesForWorldPoint(worldPoint, {
        excludedAnchorIndex: this.draggingAnchorIndex,
      });
      this.callbacks.onMoveAnchor?.(this.draggingAnchorIndex, worldPoint);
      this.draw();
      return;
    }

    if (this.rotatingAnchorIndex != null && this.document?.anchors[this.rotatingAnchorIndex]) {
      const anchorPoint = worldToCanvas(
        this.document.anchors[this.rotatingAnchorIndex],
        this.mapInfo(),
        this.view,
      );
      const yaw = canvasDeltaToWorldYaw({
        x: point.x - anchorPoint.x,
        y: point.y - anchorPoint.y,
      });
      this.callbacks.onRotateAnchor?.(this.rotatingAnchorIndex, yaw);
    }
  }

  onPointerUp() {
    this.draggingAnchorIndex = null;
    this.rotatingAnchorIndex = null;
    this.addingAnchorIndex = null;
    this.panning = false;
    this.lastPointer = null;
    this.clearAlignmentGuides();
    this.draw();
  }

  onWheel(event) {
    event.preventDefault();
    const multiplier = event.deltaY < 0 ? 1.08 : 0.92;
    const cursor = this.canvasPointFromEvent(event);
    const before = canvasToWorld(cursor, this.mapInfo(), this.view);
    this.view.scale = Math.max(0.1, Math.min(20, this.view.scale * multiplier));
    const after = worldToCanvas(before, this.mapInfo(), this.view);
    this.view.offsetX += cursor.x - after.x;
    this.view.offsetY += cursor.y - after.y;
    this.draw();
  }

  drawMap() {
    if (!this.mapData?.imageElement) {
      return;
    }

    this.context.drawImage(
      this.mapData.imageElement,
      this.view.offsetX,
      this.view.offsetY,
      this.mapData.width * this.view.scale,
      this.mapData.height * this.view.scale,
    );
  }

  drawGrid() {
    if (!this.mapData) {
      return;
    }

    const spacing = this.gridSpacingMeters();
    const [originX, originY] = this.mapInfo().origin;
    const worldWidth = this.mapData.width * this.mapData.resolution;
    const worldHeight = this.mapData.height * this.mapData.resolution;
    const minX = originX;
    const maxX = originX + worldWidth;
    const minY = originY;
    const maxY = originY + worldHeight;

    this.context.save();
    this.context.strokeStyle = "rgba(125, 149, 168, 0.22)";
    this.context.lineWidth = 1;
    this.context.setLineDash([4, 4]);

    const startX = originX + Math.ceil((minX - originX) / spacing) * spacing;
    for (let x = startX; x <= maxX + 1e-9; x += spacing) {
      const top = worldToCanvas({ x, y: maxY }, this.mapInfo(), this.view);
      const bottom = worldToCanvas({ x, y: minY }, this.mapInfo(), this.view);
      this.context.beginPath();
      this.context.moveTo(top.x, top.y);
      this.context.lineTo(bottom.x, bottom.y);
      this.context.stroke();
    }

    const startY = originY + Math.ceil((minY - originY) / spacing) * spacing;
    for (let y = startY; y <= maxY + 1e-9; y += spacing) {
      const left = worldToCanvas({ x: minX, y }, this.mapInfo(), this.view);
      const right = worldToCanvas({ x: maxX, y }, this.mapInfo(), this.view);
      this.context.beginPath();
      this.context.moveTo(left.x, left.y);
      this.context.lineTo(right.x, right.y);
      this.context.stroke();
    }

    this.context.restore();
  }

  drawOriginMarker() {
    if (!this.mapData) {
      return;
    }

    const origin = this.originCanvasPoint();
    const size = 10;
    this.context.save();
    this.context.strokeStyle = "#ff6b6b";
    this.context.lineWidth = 2;
    this.context.beginPath();
    this.context.moveTo(origin.x - size, origin.y);
    this.context.lineTo(origin.x + size, origin.y);
    this.context.moveTo(origin.x, origin.y - size);
    this.context.lineTo(origin.x, origin.y + size);
    this.context.stroke();
    this.context.fillStyle = "#ffd166";
    this.context.font = "12px monospace";
    this.context.fillText("O", origin.x + 8, origin.y - 8);
    this.context.restore();
  }

  drawAlignmentGuides() {
    if (!this.alignmentGuides || !this.mapData) {
      return;
    }

    const [originX, originY] = this.mapInfo().origin;
    const worldWidth = this.mapData.width * this.mapData.resolution;
    const worldHeight = this.mapData.height * this.mapData.resolution;
    const minX = originX;
    const maxX = originX + worldWidth;
    const minY = originY;
    const maxY = originY + worldHeight;

    this.context.save();
    this.context.strokeStyle = "rgba(255, 209, 102, 0.95)";
    this.context.lineWidth = 1.5;
    this.context.setLineDash([8, 6]);

    if (this.alignmentGuides.vertical) {
      const x = this.alignmentGuides.vertical.x;
      const top = worldToCanvas({ x, y: maxY }, this.mapInfo(), this.view);
      const bottom = worldToCanvas({ x, y: minY }, this.mapInfo(), this.view);
      this.context.beginPath();
      this.context.moveTo(top.x, top.y);
      this.context.lineTo(bottom.x, bottom.y);
      this.context.stroke();
    }

    if (this.alignmentGuides.horizontal) {
      const y = this.alignmentGuides.horizontal.y;
      const left = worldToCanvas({ x: minX, y }, this.mapInfo(), this.view);
      const right = worldToCanvas({ x: maxX, y }, this.mapInfo(), this.view);
      this.context.beginPath();
      this.context.moveTo(left.x, left.y);
      this.context.lineTo(right.x, right.y);
      this.context.stroke();
    }

    this.context.restore();
  }

  drawVirtualWalls() {
    if (!this.virtualWalls.length) {
      return;
    }

    this.context.save();
    this.context.lineCap = "round";
    this.context.lineJoin = "round";
    this.context.strokeStyle = "rgba(255, 77, 77, 0.92)";
    this.context.shadowColor = "rgba(255, 77, 77, 0.32)";
    this.context.shadowBlur = 8;

    this.virtualWalls.forEach((wall) => {
      const points = Array.isArray(wall.points) ? wall.points : [];
      if (points.length < 2) {
        return;
      }
      const thickness = Number(wall.thickness || 0.1);
      this.context.lineWidth = Math.max(3, (thickness / this.mapInfo().resolution) * this.view.scale);
      this.context.beginPath();
      points.forEach((point, index) => {
        const canvasPoint = worldToCanvas(point, this.mapInfo(), this.view);
        if (index === 0) {
          this.context.moveTo(canvasPoint.x, canvasPoint.y);
        } else {
          this.context.lineTo(canvasPoint.x, canvasPoint.y);
        }
      });
      this.context.stroke();
    });

    this.context.shadowBlur = 0;
    this.context.strokeStyle = "rgba(255, 240, 240, 0.82)";
    this.context.lineWidth = 1;
    this.virtualWalls.forEach((wall) => {
      const points = Array.isArray(wall.points) ? wall.points : [];
      if (points.length < 2) {
        return;
      }
      this.context.beginPath();
      points.forEach((point, index) => {
        const canvasPoint = worldToCanvas(point, this.mapInfo(), this.view);
        if (index === 0) {
          this.context.moveTo(canvasPoint.x, canvasPoint.y);
        } else {
          this.context.lineTo(canvasPoint.x, canvasPoint.y);
        }
      });
      this.context.stroke();
    });

    this.context.restore();
  }

  drawAnchors() {
    if (!this.document) {
      return;
    }

    const anchors = this.anchorCanvasPoints();
    this.context.strokeStyle = "#50b8ff";
    this.context.lineWidth = 2;
    this.context.beginPath();
    anchors.forEach((anchor, index) => {
      if (index === 0) {
        this.context.moveTo(anchor.x, anchor.y);
      } else {
        this.context.lineTo(anchor.x, anchor.y);
      }
    });
    this.context.stroke();

    anchors.forEach((anchor) => {
      const selected =
        (this.selection.kind === "anchor" && this.selection.index === anchor.index)
        || (this.selection.kind === "anchors" && this.selection.indexes?.includes(anchor.index));
      this.context.fillStyle = selected ? "#ff7f50" : "#ffd166";
      this.context.beginPath();
      this.context.arc(anchor.x, anchor.y, selected ? 8 : 6, 0, Math.PI * 2);
      this.context.fill();

      const source = this.document.anchors[anchor.index];
      const arrowLength = 18;
      const arrowDelta = worldYawToCanvasDelta(source.yaw, arrowLength);
      const endX = anchor.x + arrowDelta.x;
      const endY = anchor.y + arrowDelta.y;
      this.context.strokeStyle = "#8ce99a";
      this.context.beginPath();
      this.context.moveTo(anchor.x, anchor.y);
      this.context.lineTo(endX, endY);
      this.context.stroke();
    });

  }

  draw() {
    this.context.fillStyle = "#0f1418";
    this.context.fillRect(0, 0, this.canvas.width, this.canvas.height);
    this.drawMap();
    this.drawGrid();
    this.drawOriginMarker();
    this.drawVirtualWalls();
    this.drawAlignmentGuides();
    this.drawAnchors();

    if (!this.document) {
      this.context.fillStyle = "#9bb0c3";
      this.context.font = "16px monospace";
      this.context.fillText("请选择或新建一条路径", 24, 36);
    }
  }
}
