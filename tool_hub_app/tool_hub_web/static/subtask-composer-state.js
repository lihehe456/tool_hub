function clone(value) {
  return structuredClone(value);
}

export function yawToQuaternion(yaw) {
  return {
    x: 0,
    y: 0,
    z: Math.sin(yaw / 2),
    w: Math.cos(yaw / 2),
  };
}

export function quaternionToYaw(quaternion) {
  const q = quaternion || {};
  const x = Number(q.x || 0);
  const y = Number(q.y || 0);
  const z = Number(q.z || 0);
  const w = Number(q.w ?? 1);
  return Math.atan2(
    2 * (w * z + x * y),
    1 - 2 * (y * y + z * z),
  );
}

export function buildLineSegments(anchors) {
  const segments = [];
  for (let index = 1; index < anchors.length; index += 1) {
    segments.push({
      startIndex: index - 1,
      endIndex: index,
      type: "line",
      control: null,
    });
  }
  return segments;
}

function defaultTaskAttrs() {
  return {
    speed_mode: "task_point",
    waypoint_task_id: "",
    is_task_point: false,
    is_single_point: true,
    is_backward: false,
  };
}

function waypointIdFor(document, index) {
  const prefix = document?.meta?.subtask_name || "wp";
  return `${prefix}_${index}`;
}

function anchorFromWaypoint(waypoint, index) {
  const pose = waypoint.pose || {};
  const position = pose.position || {};
  return {
    x: Number(position.x || 0),
    y: Number(position.y || 0),
    z: Number(position.z || 0),
    yaw: quaternionToYaw(pose.orientation),
    waypoint_id: String(waypoint.waypoint_id || `wp_${index}`),
    task: {
      ...defaultTaskAttrs(),
      speed_mode: String(waypoint.speed_mode || "task_point"),
      waypoint_task_id: String(waypoint.waypoint_task_id || ""),
      is_task_point: Boolean(waypoint.is_task_point),
      is_single_point: waypoint.is_single_point !== undefined ? Boolean(waypoint.is_single_point) : true,
      is_backward: Boolean(waypoint.is_backward),
    },
  };
}

export function documentFromSubtask(subtask = {}) {
  const anchors = (subtask.waypoints || []).map(anchorFromWaypoint);
  return {
    meta: {
      subtask_name: String(subtask.subtask_name || ""),
      map_url: String(subtask.map_url || ""),
      pcd_url: String(subtask.pcd_url || ""),
      change_loc: Boolean(subtask.change_loc),
    },
    drawMode: "line",
    anchors,
    segments: buildLineSegments(anchors),
    history: {
      past: [],
      future: [],
    },
  };
}

export function subtaskDocumentsFromPayload(payload = {}) {
  const subtasks = payload.subtasks || (payload.subtask ? [payload.subtask] : []);
  const activeSubtaskIndex = Math.max(
    subtasks.length ? 0 : -1,
    Math.min(Number(payload.active_subtask_index ?? 0), subtasks.length - 1),
  );
  return {
    documentType: payload.document_type || "subtask",
    taskGroup: payload.task_group || null,
    subtaskDocuments: subtasks.map(documentFromSubtask),
    subtaskNames: subtasks.map((subtask, index) => subtask.subtask_name || `subtask_${index}`),
    activeSubtaskIndex,
  };
}

function waypointFromAnchor(anchor, index, document) {
  const task = {
    ...defaultTaskAttrs(),
    ...(anchor.task || {}),
  };
  return {
    is_backward: Boolean(task.is_backward),
    is_single_point: Boolean(task.is_single_point),
    is_task_point: Boolean(task.is_task_point),
    pose: {
      position: {
        x: Number(anchor.x || 0),
        y: Number(anchor.y || 0),
        z: Number(anchor.z || 0),
      },
      orientation: yawToQuaternion(Number(anchor.yaw || 0)),
    },
    speed_mode: String(task.speed_mode || "task_point"),
    waypoint_id: String(anchor.waypoint_id || waypointIdFor(document, index)),
    waypoint_task_id: String(task.waypoint_task_id || ""),
  };
}

export function subtaskFromDocument(document) {
  return {
    change_loc: Boolean(document?.meta?.change_loc),
    map_url: String(document?.meta?.map_url || ""),
    pcd_url: String(document?.meta?.pcd_url || ""),
    subtask_name: String(document?.meta?.subtask_name || ""),
    waypoints: (document?.anchors || []).map((anchor, index) =>
      waypointFromAnchor(anchor, index, document),
    ),
  };
}

export function taskPayloadFromState(state, currentDocument = state.document) {
  if (state.documentType === "task_group") {
    const documents = [...(state.subtaskDocuments || [])];
    if (state.activeSubtaskIndex >= 0 && currentDocument) {
      documents[state.activeSubtaskIndex] = currentDocument;
    }
    return {
      document_type: "task_group",
      task_group: state.taskGroup,
      subtasks: documents.map(subtaskFromDocument),
      active_subtask_index: state.activeSubtaskIndex,
    };
  }
  return {
    document_type: "subtask",
    task_group: null,
    subtasks: currentDocument ? [subtaskFromDocument(currentDocument)] : [],
    active_subtask_index: currentDocument ? 0 : -1,
  };
}

export function createSubtaskComposerInitialState() {
  return {
    taskPath: "",
    documentType: "subtask",
    taskGroup: null,
    subtaskDocuments: [],
    subtaskNames: [],
    activeSubtaskIndex: 0,
    document: null,
    selectedIndex: -1,
    dirty: false,
    activeTool: "select",
    map: null,
    status: {
      message: "",
      error: false,
    },
    editorPanel: {
      collapsed: false,
      width: 360,
    },
    filePanel: {
      collapsed: false,
    },
  };
}

function rebuildSegments(document) {
  document.segments = buildLineSegments(document.anchors || []);
  return document;
}

function documentHistory(document) {
  return document?.history || { past: [], future: [] };
}

function syncActiveSubtaskDocument(state, document) {
  const documents = [...(state.subtaskDocuments || [])];
  if (state.activeSubtaskIndex >= 0) {
    documents[state.activeSubtaskIndex] = clone(document);
  }
  return documents;
}

function subtaskNamesFromDocuments(documents) {
  return documents.map((document, index) => document?.meta?.subtask_name || `subtask_${index}`);
}

function withDocumentHistory(state, document, extraState = {}) {
  const currentHistory = documentHistory(state.document);
  document.history = {
    past: [
      ...currentHistory.past,
      clone({
        ...state.document,
        history: { past: [], future: [] },
      }),
    ].slice(-50),
    future: [],
  };
  const subtaskDocuments = syncActiveSubtaskDocument(state, document);
  return {
    ...state,
    ...extraState,
    document,
    subtaskDocuments,
    subtaskNames: subtaskNamesFromDocuments(subtaskDocuments),
    dirty: true,
  };
}

function withoutHistory(document) {
  return {
    ...document,
    history: {
      past: [],
      future: [],
    },
  };
}

export function reduceSubtaskComposerState(state, action) {
  switch (action.type) {
    case "SET_TASK_DOCUMENT": {
      const documents = (action.subtaskDocuments || []).map((document) => withoutHistory(clone(document)));
      const activeIndex = Math.max(
        documents.length ? 0 : -1,
        Math.min(Number(action.activeSubtaskIndex ?? 0), documents.length - 1),
      );
      const document = activeIndex >= 0 ? clone(documents[activeIndex]) : null;
      return {
        ...state,
        taskPath: action.taskPath ?? state.taskPath,
        documentType: action.documentType || "subtask",
        taskGroup: clone(action.taskGroup),
        subtaskDocuments: documents,
        subtaskNames: action.subtaskNames || subtaskNamesFromDocuments(documents),
        activeSubtaskIndex: activeIndex,
        document,
        selectedIndex: document?.anchors?.length ? 0 : -1,
        dirty: action.dirty ?? false,
      };
    }
    case "SET_DOCUMENT":
      return {
        ...state,
        taskPath: action.taskPath ?? state.taskPath,
        documentType: "subtask",
        taskGroup: null,
        subtaskDocuments: [withoutHistory(clone(action.document))],
        subtaskNames: [action.document?.meta?.subtask_name || "subtask"],
        activeSubtaskIndex: 0,
        document: withoutHistory(clone(action.document)),
        selectedIndex: action.document?.anchors?.length ? 0 : -1,
        dirty: action.dirty ?? false,
      };
    case "SET_TOOL":
      return {
        ...state,
        activeTool: action.tool,
      };
    case "SET_STATUS":
      return {
        ...state,
        status: {
          message: action.message,
          error: Boolean(action.error),
        },
      };
    case "ADD_ANCHOR": {
      if (!state.document) {
        return state;
      }
      const document = clone(state.document);
      const index = document.anchors.length;
      document.anchors.push({
        x: Number(action.point.x || 0),
        y: Number(action.point.y || 0),
        z: Number(action.point.z || 0),
        yaw: document.anchors.at(-1)?.yaw || 0,
        waypoint_id: waypointIdFor(document, index),
        task: defaultTaskAttrs(),
      });
      rebuildSegments(document);
      return withDocumentHistory(state, document, { selectedIndex: index });
    }
    case "INSERT_ANCHOR": {
      if (!state.document) {
        return state;
      }
      const document = clone(state.document);
      const insertIndex = Math.max(0, Math.min(action.index, document.anchors.length));
      document.anchors.splice(insertIndex, 0, {
        x: Number(action.point.x || 0),
        y: Number(action.point.y || 0),
        z: Number(action.point.z || 0),
        yaw: 0,
        waypoint_id: waypointIdFor(document, insertIndex),
        task: defaultTaskAttrs(),
      });
      rebuildSegments(document);
      return withDocumentHistory(state, document, { selectedIndex: insertIndex });
    }
    case "MOVE_ANCHOR": {
      if (!state.document?.anchors?.[action.index]) {
        return state;
      }
      const document = clone(state.document);
      document.anchors[action.index] = {
        ...document.anchors[action.index],
        x: Number(action.point.x || 0),
        y: Number(action.point.y || 0),
        z: Number(action.point.z || 0),
      };
      rebuildSegments(document);
      return withDocumentHistory(state, document);
    }
    case "OFFSET_ANCHORS": {
      if (!state.document) {
        return state;
      }
      const document = clone(state.document);
      const dx = Number(action.dx || 0);
      const dy = Number(action.dy || 0);
      document.anchors = (document.anchors || []).map((anchor) => ({
        ...anchor,
        x: Number(anchor.x || 0) + dx,
        y: Number(anchor.y || 0) + dy,
      }));
      rebuildSegments(document);
      return withDocumentHistory(state, document);
    }
    case "SET_ANCHOR_YAW": {
      if (!state.document?.anchors?.[action.index]) {
        return state;
      }
      const document = clone(state.document);
      document.anchors[action.index].yaw = Number(action.yaw || 0);
      return withDocumentHistory(state, document);
    }
    case "DELETE_ANCHOR": {
      if (!state.document?.anchors?.[action.index]) {
        return state;
      }
      const document = clone(state.document);
      document.anchors.splice(action.index, 1);
      rebuildSegments(document);
      return withDocumentHistory(state, document, {
        selectedIndex: Math.min(action.index, document.anchors.length - 1),
      });
    }
    case "UPDATE_META": {
      if (!state.document) {
        return state;
      }
      const document = clone(state.document);
      document.meta = {
        ...document.meta,
        ...action.patch,
      };
      return withDocumentHistory(state, document);
    }
    case "SELECT_ANCHOR":
      return {
        ...state,
        selectedIndex: action.index,
      };
    case "SELECT_SUBTASK": {
      const targetIndex = Number(action.index);
      if (!state.subtaskDocuments?.[targetIndex]) {
        return state;
      }
      const currentDocuments = state.document
        ? syncActiveSubtaskDocument(state, state.document)
        : [...state.subtaskDocuments];
      const document = withoutHistory(clone(currentDocuments[targetIndex]));
      return {
        ...state,
        subtaskDocuments: currentDocuments,
        subtaskNames: subtaskNamesFromDocuments(currentDocuments),
        activeSubtaskIndex: targetIndex,
        document,
        selectedIndex: document.anchors?.length ? 0 : -1,
      };
    }
    case "UPDATE_SELECTED_TASK_ATTR": {
      if (!state.document?.anchors?.[state.selectedIndex]) {
        return state;
      }
      const document = clone(state.document);
      const anchor = document.anchors[state.selectedIndex];
      anchor.task = {
        ...defaultTaskAttrs(),
        ...(anchor.task || {}),
        ...action.patch,
      };
      if (action.patch?.waypoint_id !== undefined) {
        anchor.waypoint_id = action.patch.waypoint_id;
        delete anchor.task.waypoint_id;
      }
      return withDocumentHistory(state, document);
    }
    case "UNDO": {
      if (!state.document) {
        return state;
      }
      const history = documentHistory(state.document);
      const previous = history.past.at(-1);
      if (!previous) {
        return state;
      }
      const current = clone({
        ...state.document,
        history: { past: [], future: [] },
      });
      const document = clone(previous);
      document.history = {
        past: history.past.slice(0, -1),
        future: [current, ...history.future],
      };
      const subtaskDocuments = syncActiveSubtaskDocument(state, document);
      const selectedIndex = document.anchors?.length
        ? Math.min(Math.max(state.selectedIndex, 0), document.anchors.length - 1)
        : -1;
      return {
        ...state,
        document,
        subtaskDocuments,
        subtaskNames: subtaskNamesFromDocuments(subtaskDocuments),
        selectedIndex,
        dirty: true,
      };
    }
    case "SET_EDITOR_PANEL_WIDTH":
      return {
        ...state,
        editorPanel: {
          ...state.editorPanel,
          width: Math.max(260, Math.min(640, Number(action.width || state.editorPanel.width))),
        },
      };
    case "TOGGLE_EDITOR_PANEL":
      return {
        ...state,
        editorPanel: {
          ...state.editorPanel,
          collapsed: !state.editorPanel.collapsed,
        },
      };
    case "TOGGLE_FILE_PANEL":
      return {
        ...state,
        filePanel: {
          ...state.filePanel,
          collapsed: !state.filePanel?.collapsed,
        },
      };
    default:
      return state;
  }
}
