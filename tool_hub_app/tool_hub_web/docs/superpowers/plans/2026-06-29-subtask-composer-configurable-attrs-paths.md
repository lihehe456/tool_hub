# Subtask Composer Configurable Attribute Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Subtask Composer's waypoint-task and speed-mode attribute directories user-configurable from the UI and supplied through runtime config.

**Architecture:** Extend the existing runtime config endpoint to expose the current attribute roots and add a small editable settings area in the Subtask Composer file panel. The UI should keep the current paths in the page state, let the user edit them, and reload the attribute lists on demand without changing the rest of the editor flow.

**Tech Stack:** Python Flask backend, vanilla ES modules, existing static HTML/CSS, Node test runner, pytest.

---

### Task 1: Add runtime-config support for editable attribute roots

**Files:**
- Modify: `launcher.py`
- Modify: `server.py:419-426`
- Test: `tests/test_tool_hub_server.py`

- [ ] **Step 1: Write the failing test**

```python
def test_subtask_composer_runtime_config_can_be_overridden(client, tmp_path):
    app = client.application
    app.config["SUBTASK_COMPOSER_WAYPOINT_TASKS_PATH"] = str(tmp_path / "waypoint_tasks")
    app.config["SUBTASK_COMPOSER_SPEED_MODES_PATH"] = str(tmp_path / "speed_modes")
    response = client.get("/subtask-composer/api/runtime_config")
    payload = response.get_json()
    assert payload["waypoint_tasks_path"] == str(tmp_path / "waypoint_tasks")
    assert payload["speed_modes_path"] == str(tmp_path / "speed_modes")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.. python3 -m pytest tests/test_tool_hub_server.py::test_subtask_composer_runtime_config_can_be_overridden -v`
Expected: FAIL because the runtime config fields do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add optional launcher args for the two paths, store them in `app.config`, and return them from the Subtask Composer runtime config as `waypoint_tasks_path` and `speed_modes_path`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.. python3 -m pytest tests/test_tool_hub_server.py::test_subtask_composer_runtime_config_can_be_overridden -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add launcher.py server.py tests/test_tool_hub_server.py
git commit -m "feat: make subtask composer attribute roots configurable"
```

### Task 2: Add editable path fields to the Subtask Composer UI

**Files:**
- Modify: `static/subtask-composer.html`
- Modify: `static/subtask-composer.js`
- Test: `static/tests/subtask-composer-state.test.js` or a new browser-free unit test if needed

- [ ] **Step 1: Write the failing test**

Add a small JS test that loads runtime config data into state and asserts the new path values are used for the attribute selector fetch URL.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test static/tests/subtask-composer-state.test.js`
Expected: FAIL until the UI state carries the new configurable paths.

- [ ] **Step 3: Write minimal implementation**

Add two inputs in the file panel for waypoint-task and speed-mode attribute roots, a refresh button, and state wiring so `loadAttributes()` uses the edited values. Keep the existing editor behavior unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test static/tests/*.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add static/subtask-composer.html static/subtask-composer.js static/tests/subtask-composer-state.test.js
git commit -m "feat: make subtask composer attribute paths editable"
```

### Task 3: Verify server and client behavior together

**Files:**
- Modify: `tests/test_tool_hub_server.py`

- [ ] **Step 1: Add a combined regression test**

Check that the UI receives the configured roots, and that the attributes endpoint resolves them correctly.

- [ ] **Step 2: Run the full targeted test set**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.. python3 -m pytest tests/test_subtask_composer.py tests/test_tool_hub_server.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_tool_hub_server.py
git commit -m "test: cover configurable subtask composer attribute roots"
```
