function moveItem(items, fromIndex, toIndex) {
  if (
    fromIndex < 0 ||
    fromIndex >= items.length ||
    toIndex < 0 ||
    toIndex >= items.length ||
    fromIndex === toIndex
  ) {
    return items;
  }

  const next = [...items];
  const [item] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, item);
  return next;
}

function dedupeHistory(items, value) {
  if (!value) {
    return items;
  }
  return [value, ...items.filter((item) => item !== value)].slice(0, 12);
}

function firstSourcePath(workspace) {
  const first = (workspace?.subtasks ?? []).find((subtask) => subtask.source_workspace_path);
  return first?.source_workspace_path ?? "";
}

export function createTaskGroupMixerInitialState() {
  return {
    workspacePath: "",
    sourcePath: "",
    activeSourcePath: "",
    workspace: null,
    workspaceHistory: [],
    sourceHistory: [],
    status: {
      message: "",
      error: false,
    },
  };
}

export function reduceTaskGroupMixerState(state, action) {
  switch (action.type) {
    case "SET_WORKSPACE_PATH":
      return {
        ...state,
        workspacePath: action.workspacePath,
      };
    case "SET_SOURCE_PATH":
      return {
        ...state,
        sourcePath: action.sourcePath,
      };
    case "SET_WORKSPACE": {
      const nextActiveSourcePath =
        state.activeSourcePath &&
        (action.workspace?.subtasks ?? []).some(
          (subtask) => subtask.source_workspace_path === state.activeSourcePath,
        )
          ? state.activeSourcePath
          : firstSourcePath(action.workspace);
      return {
        ...state,
        workspacePath: action.workspacePath,
        workspace: action.workspace,
        activeSourcePath: nextActiveSourcePath,
        status: {
          message: "",
          error: false,
        },
      };
    }
    case "SET_ACTIVE_SOURCE":
      return {
        ...state,
        activeSourcePath: action.sourcePath,
      };
    case "SET_STATUS":
      return {
        ...state,
        status: {
          message: action.message,
          error: action.error ?? false,
        },
      };
    case "RECORD_WORKSPACE_HISTORY":
      return {
        ...state,
        workspaceHistory: dedupeHistory(state.workspaceHistory, action.workspacePath),
      };
    case "RECORD_SOURCE_HISTORY":
      return {
        ...state,
        sourceHistory: dedupeHistory(state.sourceHistory, action.sourcePath),
      };
    case "ADD_SELECTED_SUBTASK":
      if (!state.workspace || state.workspace.selected_subtask_ids.includes(action.subtaskId)) {
        return state;
      }
      return {
        ...state,
        workspace: {
          ...state.workspace,
          selected_subtask_ids: [...state.workspace.selected_subtask_ids, action.subtaskId],
        },
      };
    case "REMOVE_SELECTED_SUBTASK":
      if (!state.workspace) {
        return state;
      }
      return {
        ...state,
        workspace: {
          ...state.workspace,
          selected_subtask_ids: state.workspace.selected_subtask_ids.filter(
            (subtaskId) => subtaskId !== action.subtaskId,
          ),
        },
      };
    case "MOVE_SELECTED_SUBTASK":
      if (!state.workspace) {
        return state;
      }
      return {
        ...state,
        workspace: {
          ...state.workspace,
          selected_subtask_ids: moveItem(
            state.workspace.selected_subtask_ids,
            state.workspace.selected_subtask_ids.indexOf(action.subtaskId),
            action.direction === "up"
              ? state.workspace.selected_subtask_ids.indexOf(action.subtaskId) - 1
              : state.workspace.selected_subtask_ids.indexOf(action.subtaskId) + 1,
          ),
        },
      };
    case "RENAME_SUBTASK":
      if (!state.workspace) {
        return state;
      }
      return {
        ...state,
        workspace: {
          ...state.workspace,
          subtasks: state.workspace.subtasks.map((subtask) =>
            subtask.id === action.subtaskId
              ? { ...subtask, subtask_name: action.subtaskName }
              : subtask,
          ),
        },
      };
    case "RENAME_TASK_GROUP":
      if (!state.workspace) {
        return state;
      }
      return {
        ...state,
        workspace: {
          ...state.workspace,
          task_group_name: action.taskGroupName,
        },
      };
    case "SET_OUTPUT_TASK_PATH":
      if (!state.workspace) {
        return state;
      }
      return {
        ...state,
        workspace: {
          ...state.workspace,
          output_task_path: action.outputTaskPath,
        },
      };
    default:
      return state;
  }
}
