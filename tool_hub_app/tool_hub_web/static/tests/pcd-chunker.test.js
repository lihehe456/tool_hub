import assert from "node:assert/strict";
import test from "node:test";

import {
  buildChunkerPayload,
  normalizeOptionalNumber,
  renderChunkCardsMarkup,
} from "../pcd-chunker.js";

test("normalizeOptionalNumber keeps empty values blank for optional voxel size", () => {
  assert.equal(normalizeOptionalNumber(""), "");
  assert.equal(normalizeOptionalNumber("  "), "");
  assert.equal(normalizeOptionalNumber("0.25"), 0.25);
});

test("buildChunkerPayload normalizes numeric fields and trims paths", () => {
  const payload = buildChunkerPayload({
    pcdPath: " /tmp/map.pcd ",
    outputDir: " /tmp/output ",
    chunkSize: "50",
    voxelSize: "",
    startX: "1.5",
    startY: "-2",
    startZ: "0",
    force: true,
  });

  assert.deepEqual(payload, {
    pcd_path: "/tmp/map.pcd",
    output_dir: "/tmp/output",
    chunk_size: 50,
    voxel_size: "",
    start_x: 1.5,
    start_y: -2,
    start_z: 0,
    force: true,
  });
});

test("renderChunkCardsMarkup renders chunk details for the results panel", () => {
  const markup = renderChunkCardsMarkup([
    {chunk_id: 0, grid_x: 1, grid_y: -1, point_count: 123, file_name: "0.pcd"},
  ]);

  assert.match(markup, /Chunk 0/);
  assert.match(markup, /grid=\(1, -1\)/);
  assert.match(markup, /points=123/);
  assert.match(markup, /0\.pcd/);
});
