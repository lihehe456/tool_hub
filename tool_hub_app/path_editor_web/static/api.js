async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

export async function loadRuntimeConfig() {
  const response = await fetch("/api/runtime_config");
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

export function browsePaths(path) {
  return postJson("/api/browse_paths", { path });
}

export function browseMaps(path) {
  return postJson("/api/browse_maps", { path });
}

export function browseUserFiles(path, fileType) {
  return postJson("/api/browse_user_files", { path, file_type: fileType });
}

export function loadPath(path) {
  return postJson("/api/load_path", { path });
}

export function loadMap(yamlPath) {
  return postJson("/api/load_map", { yaml_path: yamlPath });
}

export function savePath(path, document) {
  return postJson("/api/save_path", { path, document });
}

export function savePathAs(path, document) {
  return postJson("/api/save_path_as", { path, document });
}

export function renamePath(srcPath, dstPath) {
  return postJson("/api/rename_path", { src_path: srcPath, dst_path: dstPath });
}

export function deletePath(path) {
  return postJson("/api/delete_path", { path });
}

export function buildSubtasksFromPath(path, generatedSubtaskName) {
  return postJson("/api/build_subtasks_from_path", {
    path,
    generated_subtask_name: generatedSubtaskName,
  });
}

export function loadTaskWorkspace(workspacePath) {
  return postJson("/api/load_task_workspace", { workspace_path: workspacePath });
}

export function createTaskWorkspace(workspacePath) {
  return postJson("/api/create_task_workspace", { workspace_path: workspacePath });
}

export function saveTaskWorkspace(workspacePath, workspace) {
  return postJson("/api/save_task_workspace", { workspace_path: workspacePath, workspace });
}

export function loadOrCreateMixerWorkspace(workspacePath) {
  return postJson("/api/load_or_create_mixer_workspace", { workspace_path: workspacePath });
}

export function importSidecarWorkspaceIntoMixer(workspacePath, sourceWorkspacePath) {
  return postJson("/api/import_sidecar_workspace_into_mixer", {
    workspace_path: workspacePath,
    source_workspace_path: sourceWorkspacePath,
  });
}

export function addSubtaskPairToWorkspace(workspacePath, forwardSubtask, returnSubtask) {
  return postJson("/api/add_subtask_pair_to_workspace", {
    workspace_path: workspacePath,
    forward_subtask: forwardSubtask,
    return_subtask: returnSubtask,
  });
}

export function replaceSubtaskPairInWorkspace(
  workspacePath,
  oldPairId,
  forwardSubtask,
  returnSubtask,
) {
  return postJson("/api/replace_subtask_pair_in_workspace", {
    workspace_path: workspacePath,
    old_pair_id: oldPairId,
    forward_subtask: forwardSubtask,
    return_subtask: returnSubtask,
  });
}

export function exportTaskGroup(workspacePath, exportDirectory) {
  return postJson("/api/export_task_group", {
    workspace_path: workspacePath,
    export_directory: exportDirectory,
  });
}
