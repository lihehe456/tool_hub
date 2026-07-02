# PCD Chunker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone Tool Hub page that splits a full `.pcd` into chunked `index.txt + {id}.pcd` output for the 3D localization pipeline.

**Architecture:** Introduce a new `pcd_chunker.py` backend module based on the reference script, mount a dedicated page and JSON APIs in `server.py`, and add a focused front-end page/controller for browse-preview-export. Keep the feature isolated from `PCD to 2D Map` except for shared visual patterns and browse API conventions.

**Tech Stack:** Python Flask, Open3D, vanilla HTML/CSS/JS, pytest, Node test runner.

---

### Task 1: Add chunking core module

**Files:**
- Create: `pcd_chunker.py`
- Test: `tests/test_pcd_chunker.py`

- [ ] **Step 1: Write the failing test**

Add tests for grid assignment, bucket ordering, preview chunk stats, and export `index.txt` generation using a tiny synthetic point set.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/home/lmy/LMY/0_Code/git_tool_hub/tool_hub/tool_hub_app python3 -m pytest -q tests/test_pcd_chunker.py`
Expected: FAIL because `pcd_chunker.py` and its APIs do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `pcd_chunker.py` with option/result dataclasses, `pos_to_grid`, `bucket_points`, preview building, output directory preparation, optional voxel downsample, and export helpers modeled after `/mnt/data/convert_map(1).py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/home/lmy/LMY/0_Code/git_tool_hub/tool_hub/tool_hub_app python3 -m pytest -q tests/test_pcd_chunker.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pcd_chunker.py tests/test_pcd_chunker.py
git commit -m "feat: add pcd chunking core module"
```

### Task 2: Mount the new tool page and APIs

**Files:**
- Modify: `server.py`
- Modify: `static/index.html`
- Modify: `README.md`
- Modify: `USER_GUIDE.md`
- Modify: `tests/test_tool_hub_server.py`

- [ ] **Step 1: Write the failing test**

Extend server tests to assert the new hub card/page exists and that runtime config plus preview/export endpoints are mounted.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/home/lmy/LMY/0_Code/git_tool_hub/tool_hub/tool_hub_app python3 -m pytest -q tests/test_tool_hub_server.py`
Expected: FAIL because the route and APIs are not registered yet.

- [ ] **Step 3: Write minimal implementation**

Add the new page route, runtime config endpoint, browse endpoint reuse, and preview/export handlers that call `pcd_chunker.py`. Update hub navigation and docs so the tool appears alongside the others.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/home/lmy/LMY/0_Code/git_tool_hub/tool_hub/tool_hub_app python3 -m pytest -q tests/test_tool_hub_server.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server.py static/index.html README.md USER_GUIDE.md tests/test_tool_hub_server.py
git commit -m "feat: mount pcd chunker tool"
```

### Task 3: Build the PCD Chunker UI

**Files:**
- Create: `static/pcd-chunker.html`
- Create: `static/pcd-chunker.js`
- Create: `static/tests/pcd-chunker.test.js`

- [ ] **Step 1: Write the failing test**

Add a browser-free JS test for payload normalization and summary rendering inputs, including blank `voxel_size` handling.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test static/tests/pcd-chunker.test.js`
Expected: FAIL because the new front-end module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create the page and controller with browse, preview, export, status updates, and chunk/index rendering. Reuse the existing hub stylesheet and page composition patterns.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test static/tests/pcd-chunker.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add static/pcd-chunker.html static/pcd-chunker.js static/tests/pcd-chunker.test.js
git commit -m "feat: add pcd chunker UI"
```

### Task 4: Run focused end-to-end verification

**Files:**
- Modify: `ERROR_CODES.md` if a new user-visible error code is needed

- [ ] **Step 1: Run the focused Python suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/home/lmy/LMY/0_Code/git_tool_hub/tool_hub/tool_hub_app python3 -m pytest -q tests/test_pcd_chunker.py tests/test_tool_hub_server.py`
Expected: PASS

- [ ] **Step 2: Run the focused JS suite**

Run: `node --test static/tests/*.test.js`
Expected: PASS

- [ ] **Step 3: Manual smoke-check the page**

Start the local server if needed, open `/pcd-chunker`, verify browse-preview-export flow, and confirm the generated output contains `index.txt` plus numeric chunk filenames.

- [ ] **Step 4: Commit**

```bash
git add ERROR_CODES.md
git commit -m "test: verify pcd chunker flow"
```
