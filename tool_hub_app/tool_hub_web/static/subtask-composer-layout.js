const RESIZE_ACTIONS = new Set([
  "SET_TASK_DOCUMENT",
  "SELECT_SUBTASK",
  "SET_EDITOR_PANEL_WIDTH",
  "TOGGLE_EDITOR_PANEL",
  "TOGGLE_FILE_PANEL",
]);

export function shouldResizeCanvasForAction(action) {
  return RESIZE_ACTIONS.has(action?.type);
}
