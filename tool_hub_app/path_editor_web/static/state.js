export function createInitialState() {
  return {
    filePath: "",
    mapPath: "",
    document: null,
    dirty: false,
    topbarCollapsed: false,
    activeTool: "select",
    drawMode: "line",
    selection: { kind: "none" },
    workspacePath: "",
    generatedSubtaskPair: null,
    subtaskBuilderStatus: {
      message: "",
      error: false,
    },
    taskGroupPageHref: "/task-groups",
  };
}

export function reduce(state, action) {
  switch (action.type) {
    case "OPEN_DOCUMENT":
      return {
        ...state,
        filePath: action.filePath,
        mapPath: action.document?.meta?.map_url ?? "",
        document: action.document,
        drawMode: action.document?.drawMode ?? "line",
        dirty: false,
        selection: { kind: "none" },
        generatedSubtaskPair: null,
      };
    case "MARK_DIRTY":
      return { ...state, dirty: true };
    case "UPDATE_META":
      return {
        ...state,
        dirty: true,
        mapPath: action.patch.map_url ?? state.mapPath,
        document: {
          ...state.document,
          meta: {
            ...state.document.meta,
            ...action.patch,
          },
        },
      };
    case "SET_DOCUMENT":
      return {
        ...state,
        dirty: action.markDirty ?? true,
        document: action.document,
      };
    case "SAVE_SUCCESS":
      return { ...state, dirty: false };
    case "SAVE_AS_SUCCESS":
      return { ...state, filePath: action.filePath, dirty: false };
    case "SET_TOOL":
      return { ...state, activeTool: action.tool };
    case "TOGGLE_TOPBAR":
      return { ...state, topbarCollapsed: !state.topbarCollapsed };
    case "SET_WORKSPACE_PATH":
      return {
        ...state,
        workspacePath: action.workspacePath,
        taskGroupPageHref: action.workspacePath
          ? `/task-groups?workspace_path=${encodeURIComponent(action.workspacePath)}`
          : "/task-groups",
      };
    case "SET_GENERATED_SUBTASK_PAIR":
      return { ...state, generatedSubtaskPair: action.pair };
    case "CLEAR_GENERATED_SUBTASK_PAIR":
      return { ...state, generatedSubtaskPair: null };
    case "SET_SUBTASK_BUILDER_STATUS":
      return {
        ...state,
        subtaskBuilderStatus: {
          message: action.message,
          error: action.error ?? false,
        },
      };
    case "SET_MAP_PATH":
      return {
        ...state,
        mapPath: action.mapPath,
        document: state.document
          ? {
              ...state.document,
              meta: {
                ...state.document.meta,
                map_url: action.mapPath,
              },
            }
          : state.document,
      };
    case "SET_DRAW_MODE":
      return {
        ...state,
        drawMode: action.drawMode,
        dirty: true,
        document: state.document
          ? { ...state.document, drawMode: action.drawMode }
          : state.document,
      };
    case "SELECT_ELEMENT":
      return { ...state, selection: action.selection };
    default:
      return state;
  }
}
