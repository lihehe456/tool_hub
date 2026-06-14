export function canCreateTaskWorkspace(state) {
  return !!state.workspacePath;
}

export function canWriteSubtaskPairToWorkspace(state) {
  return !!state.workspacePath && !!state.generatedSubtaskPair;
}
