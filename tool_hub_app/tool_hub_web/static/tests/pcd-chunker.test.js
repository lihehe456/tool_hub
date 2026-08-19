import assert from "node:assert/strict";
import test from "node:test";

import {
  buildChunkerPayload,
  buildLocConfigName,
  normalizeOptionalNumber,
  normalizeLocConfigSegment,
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
    workers: "4",
    cacheMb: "4096",
    mapCategory: "market",
    community: " 中铁阅山湖D区 ",
    building: "2_1",
    unit: "1",
    autoLocConfigName: true,
    locConfigName: " market_loc.yaml ",
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
    workers: 4,
    cache_mb: 4096,
    map_category: "market",
    community: "中铁阅山湖D区",
    building: "2_1",
    unit: "1",
    auto_loc_config_name: true,
    loc_config_name: "market_loc.yaml",
    force: true,
  });
});

test("buildLocConfigName mirrors the backend naming contract", () => {
  assert.equal(normalizeLocConfigSegment(" 2 / 1 "), "2___1");
  assert.equal(buildLocConfigName("中铁阅山湖D区", "2_1", "1", "elevator_hall"), "rycx_loc_中铁阅山湖D区_2_1_1_elevator_hall.yaml");
  assert.equal(buildLocConfigName("中铁阅山湖D区", "2_1", "", "floor"), "");
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
