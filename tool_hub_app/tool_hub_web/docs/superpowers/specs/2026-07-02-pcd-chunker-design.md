# PCD Chunker Design

**Date:** 2026-07-02

**Purpose**

Add a new standalone Tool Hub page for splitting a full-map `.pcd` file into chunked `index.txt + {id}.pcd` output for the 3D localization pipeline. This tool is separate from `PCD to 2D Map` and must not share user-facing workflow with 2D map generation.

**User Workflow**

The user opens a dedicated `PCD Chunker` page from the hub, selects an input `.pcd`, sets an output directory, tunes chunking parameters, previews the chunk layout/statistics, and then exports the chunk set to disk. The resulting directory should be directly usable by the downstream 3D localization system that expects Lightning-LM style chunked map files.

**Scope**

This feature includes:

- A new hub card and route for `PCD Chunker`
- A backend module that encapsulates chunking logic from `/mnt/data/convert_map(1).py`
- A preview API that computes chunk metadata without writing files
- An export API that writes `index.txt` and chunked compressed `.pcd` files
- Focused tests for algorithm behavior, route mounting, and front-end request wiring

This feature does not include:

- Any 2D map generation UI or logic
- RViz-style map rendering
- Task queues, job polling, or background workers
- Additional localization metadata beyond the current reference script output

**Architecture**

The implementation will follow the existing `tool_hub_web` pattern used by `PCD to 2D Map`, but as an independent tool. A new `pcd_chunker.py` module will hold pure chunking logic and file output helpers. `server.py` will register the page route plus small JSON APIs. The front-end will be a dedicated HTML page with a small vanilla JS controller for browse, preview, and export flows.

**Backend Design**

`pcd_chunker.py` will expose:

- argument/result dataclasses for chunk options and preview/export output
- `load_cloud_xyz()` using `open3d`
- `pos_to_grid()` with the same grid formula as the reference script
- `bucket_points()` preserving first-seen grid order
- optional `voxel_downsample()`
- `build_chunk_preview()` returning counts, bounds, and index preview data
- `export_chunked_map()` writing `index.txt` and compressed chunk `.pcd` files

The server APIs will be:

- `POST /pcd-chunker/api/browse`
- `GET /pcd-chunker/api/runtime_config`
- `POST /pcd-chunker/api/preview`
- `POST /pcd-chunker/api/export`

Preview will validate inputs and return chunk statistics without touching the filesystem beyond reading the source `.pcd`. Export will reuse the same validated options and then write output files.

**Frontend Design**

The page will reuse the existing hub visual language:

- file inputs for source `.pcd` and output directory
- numeric controls for `chunk_size`, optional `voxel_size`, and `start_x/y/z`
- a checkbox for overwrite
- toolbar buttons for browse, preview, and export
- a status banner
- a summary panel for total points, total chunks, chunk size, and output path
- a chunk list panel showing per-chunk id, grid coordinate, point count, and file name
- an `index.txt` preview panel

The UI will stay deliberately operational and dense, matching the rest of the hub rather than introducing a new design language.

**Error Handling**

Validation should return clear JSON errors for:

- missing or non-`.pcd` input file
- non-positive `chunk_size`
- non-positive `voxel_size` when provided
- dangerous or invalid output directory
- empty point clouds
- write failures from `open3d`

The front-end should surface backend errors in the status banner and keep the current form state intact.

**Testing**

Python tests will cover:

- grid assignment and bucket ordering
- preview statistics for a small synthetic point cloud
- export output structure and `index.txt` content
- overwrite behavior
- new route/runtime config visibility

JS tests will cover:

- payload building for preview/export
- optional `voxel_size` handling
- response rendering for chunk summary/index preview

**Open Implementation Choice**

The implementation will default to synchronous request handling for now. If very large point clouds later make the UI feel blocked, this can be upgraded to the existing preview/export job pattern used elsewhere without changing the chunking core module.
