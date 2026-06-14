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

export function createTaskGroupInitialState() {
  return {
    workspacePath: "",
    workspace: null,
    status: {
      message: "",
      error: false,
    },
  };
}

export function reduceTaskGroupState(state, action) {
  switch (action.type) {
    case "SET_WORKSPACE":
      return {
        ...state,
        workspacePath: action.workspacePath,
        workspace: action.workspace,
        status: {
          message: "",
          error: false,
        },
      };
    case "SET_STATUS":
      return {
        ...state,
        status: {
          message: action.message,
          error: action.error ?? false,
        },
      };
    case "ADD_SELECTED_SUBTASK":
      if (!state.workspace) {
        return state;
      }
      if (state.workspace.selected_subtask_ids.includes(action.subtaskId)) {
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
      const fromIndex = state.workspace.selected_subtask_ids.indexOf(action.subtaskId);
      const toIndex = action.direction === "up" ? fromIndex - 1 : fromIndex + 1;
      return {
        ...state,
        workspace: {
          ...state.workspace,
          selected_subtask_ids: moveItem(state.workspace.selected_subtask_ids, fromIndex, toIndex),
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
    case "CLEAR_SUBTASKS":
      if (!state.workspace) {
        return state;
      }
      return {
        ...state,
        workspace: {
          ...state.workspace,
          subtasks: [],
          selected_subtask_ids: [],
        },
      };
    default:
      return state;
  }
}
