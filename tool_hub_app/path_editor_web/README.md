# Path Editor Web

Run from repository root:

```bash
cd tool_hub_app/path_editor_web
python3 server.py
```

Open:

```text
http://127.0.0.1:7790/
```

## Workflow

This tool now has two related workspaces:

- `Path Editor`
  Used for map loading, path editing, and generating a forward/return subtask pair from the currently open path file.
- `Task Group Builder`
  Used for loading a workspace file, choosing subtasks, ordering them, renaming subtasks, renaming the task group, and exporting the final task-group JSON.
- `Task Group Mixer`
  Used for creating a dedicated mixer workspace, importing multiple sidecar `*.workspace.json` files, and freely recombining subtasks across task groups.

### Path Editor

In the right-side `Subtask Builder` panel:

1. Fill in a user-chosen workspace JSON path.
2. Open a path file from the left tree.
3. Click `生成子任务对`.
4. Review the generated forward and return subtasks.
5. Click `加入工作区` to append them to the workspace file.
6. If the source path changes later, regenerate and use `替换同源对子任务`.
7. Click `前往任务组工作区` to jump into the standalone builder page.
8. Click `前往任务组混编页` to jump into the standalone cross-task-group mixer page.

### Task Group Builder

Open:

```text
http://127.0.0.1:7790/task-groups
```

Or jump there from the Path Editor with a workspace path already attached in the query string.

In this page:

1. Load the workspace file.
2. Add or remove subtasks from the current task group.
3. Reorder the selected subtasks.
4. Edit the task group name.
5. Edit individual subtask names.
6. Set an export directory.
7. Click `导出任务组`. The backend will save the file as `<task_group_name>.json` inside that directory.

### Task Group Mixer

Open:

```text
http://127.0.0.1:7790/task-group-mixer
```

In this page:

1. Choose a dedicated mixer workspace JSON path and click `加载/创建`.
2. Choose a sidecar source `*.workspace.json`.
3. Click `导入/替换` to copy that source into the mixer workspace.
4. Select a source in the left column to inspect its local subtask pool.
5. Add or remove subtasks from the mixed task group.
6. Reorder the current mixed task group.
7. Edit the final task group name and export directory.
8. Click `导出任务组` to write the runtime task-group JSON.

## Workspace Files

Workspace files are user-chosen JSON files and are saved automatically after changes in the Task Group Builder page. They are intended to survive browser refreshes, page closes, and project moves.

Workspace files store:

- workspace name
- task group name
- generated subtask snapshots
- current selected subtask order
- output task path

Subtasks stored in a workspace are frozen snapshots. If a source path file changes, regenerate the pair from the Path Editor and explicitly replace the matching workspace pair.

Task Group Mixer workspaces are also user-chosen JSON files and are auto-saved after each mutation. When the same sidecar source is imported again, the mixer performs a source-level replace so old and new snapshots from that source do not coexist.

## Tests

Python tests:

```bash
PYTHONPATH=tool_hub_app python3 -m pytest tool_hub_app/path_editor_web/tests -q
```

Node tests:

```bash
node --test tool_hub_app/path_editor_web/static/tests/*.test.js
```
