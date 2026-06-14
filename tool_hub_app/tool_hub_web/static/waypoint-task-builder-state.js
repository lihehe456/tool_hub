function cloneDocument(document) {
  return document ? structuredClone(document) : null;
}

function escapeXml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function serializeNode(node, depth = 2) {
  const indent = "  ".repeat(depth);
  const attrs = Object.entries(node.attrs ?? {})
    .filter(([, value]) => value !== "" && value !== null && value !== undefined)
    .map(([key, value]) => `${key}="${escapeXml(value)}"`)
    .join(" ");
  if (!(node.children ?? []).length) {
    return `${indent}${attrs ? `<${node.type} ${attrs} />` : `<${node.type} />`}`;
  }
  const openTag = attrs ? `<${node.type} ${attrs}>` : `<${node.type}>`;
  const children = node.children.map((child) => serializeNode(child, depth + 1)).join("\n");
  return `${indent}${openTag}\n${children}\n${indent}</${node.type}>`;
}

function serializeDocument(document) {
  if (!document?.tree) {
    return "";
  }
  return [
    '<root main_tree_to_execute="MainTree">',
    '  <BehaviorTree ID="MainTree">',
    serializeNode(document.tree, 2),
    "  </BehaviorTree>",
    "</root>",
  ].join("\n");
}

function generateNodeId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `node-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function visitNode(node, callback, parent = null) {
  if (!node) {
    return false;
  }
  if (callback(node, parent)) {
    return true;
  }
  for (const child of node.children ?? []) {
    if (visitNode(child, callback, node)) {
      return true;
    }
  }
  return false;
}

function findNode(document, nodeId) {
  let found = null;
  visitNode(document?.tree, (node, parent) => {
    if (node.id === nodeId) {
      found = { node, parent };
      return true;
    }
    return false;
  });
  return found;
}

function removeNodeFromTree(tree, nodeId) {
  if (!tree || tree.id === nodeId) {
    return false;
  }
  for (let index = 0; index < (tree.children ?? []).length; index += 1) {
    if (tree.children[index].id === nodeId) {
      tree.children.splice(index, 1);
      return true;
    }
    if (removeNodeFromTree(tree.children[index], nodeId)) {
      return true;
    }
  }
  return false;
}

function nodeContainsId(node, nodeId) {
  if (!node) {
    return false;
  }
  if (node.id === nodeId) {
    return true;
  }
  return (node.children ?? []).some((child) => nodeContainsId(child, nodeId));
}

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

export function createNodeFromSchema(nodeType, schema) {
  return {
    id: generateNodeId(),
    type: nodeType,
    attrs: Object.fromEntries((schema.fields ?? []).map((field) => [field.name, field.default ?? ""])),
    children: [],
  };
}

export function createWaypointTaskBuilderInitialState() {
  return {
    taskPath: "",
    taskDirectory: "",
    taskName: "",
    nodes: {},
    document: null,
    selectedNodeId: "",
    xmlText: "",
    status: {
      message: "",
      error: false,
    },
    dragPayload: null,
  };
}

export function reduceWaypointTaskBuilderState(state, action) {
  switch (action.type) {
    case "SET_SCHEMA":
      return {
        ...state,
        nodes: action.nodes,
      };
    case "SET_STATUS":
      return {
        ...state,
        status: {
          message: action.message,
          error: action.error ?? false,
        },
      };
    case "SET_DOCUMENT":
      return {
        ...state,
        taskPath: action.taskPath ?? state.taskPath,
        taskDirectory: action.taskDirectory ?? state.taskDirectory,
        taskName: action.document?.task_name ?? "",
        document: cloneDocument(action.document),
        selectedNodeId: action.document?.tree?.id ?? "",
        xmlText: action.xmlText ?? serializeDocument(action.document),
        status: { message: "", error: false },
      };
    case "SET_TASK_PATH":
      return {
        ...state,
        taskPath: action.taskPath,
      };
    case "SET_TASK_DIRECTORY":
      return {
        ...state,
        taskDirectory: action.taskDirectory,
      };
    case "SET_TASK_NAME":
      return {
        ...state,
        taskName: action.taskName,
        document: state.document
          ? (() => {
              const nextDocument = {
                ...state.document,
                task_name: action.taskName,
              };
              return nextDocument;
            })()
          : state.document,
        xmlText: state.document
          ? serializeDocument({
              ...state.document,
              task_name: action.taskName,
            })
          : state.xmlText,
      };
    case "SET_XML_TEXT":
      return {
        ...state,
        xmlText: action.xmlText,
      };
    case "SELECT_NODE":
      return {
        ...state,
        selectedNodeId: action.nodeId,
      };
    case "ADD_NODE_AS_CHILD": {
      if (!state.document) {
        return state;
      }
      const nextDocument = cloneDocument(state.document);
      const target = findNode(nextDocument, action.parentNodeId);
      const targetSchema = state.nodes[target?.node?.type];
      if (!target || targetSchema?.kind !== "control") {
        return state;
      }
      target.node.children = [...(target.node.children ?? []), structuredClone(action.nodeTemplate)];
      return {
        ...state,
        document: nextDocument,
        selectedNodeId: action.nodeTemplate.id,
        xmlText: serializeDocument(nextDocument),
      };
    }
    case "ADD_ROOT_NODE": {
      if (!state.document || state.document.tree) {
        return state;
      }
      const nextDocument = cloneDocument(state.document);
      nextDocument.tree = structuredClone(action.nodeTemplate);
      return {
        ...state,
        document: nextDocument,
        selectedNodeId: action.nodeTemplate.id,
        xmlText: serializeDocument(nextDocument),
      };
    }
    case "UPDATE_NODE_ATTR": {
      if (!state.document) {
        return state;
      }
      const nextDocument = cloneDocument(state.document);
      const target = findNode(nextDocument, action.nodeId);
      if (!target) {
        return state;
      }
      target.node.attrs = {
        ...(target.node.attrs ?? {}),
        [action.fieldName]: action.value,
      };
      return {
        ...state,
        document: nextDocument,
        xmlText: serializeDocument(nextDocument),
      };
    }
    case "MOVE_NODE": {
      if (!state.document) {
        return state;
      }
      const nextDocument = cloneDocument(state.document);
      const target = findNode(nextDocument, action.nodeId);
      if (!target?.parent) {
        return state;
      }
      const siblings = target.parent.children ?? [];
      const fromIndex = siblings.findIndex((node) => node.id === action.nodeId);
      const toIndex = action.direction === "up" ? fromIndex - 1 : fromIndex + 1;
      target.parent.children = moveItem(siblings, fromIndex, toIndex);
      return {
        ...state,
        document: nextDocument,
        xmlText: serializeDocument(nextDocument),
      };
    }
    case "REMOVE_NODE": {
      if (!state.document || !state.document.tree) {
        return state;
      }
      const nextDocument = cloneDocument(state.document);
      if (nextDocument.tree.id === action.nodeId) {
        nextDocument.tree = null;
        return {
          ...state,
          document: nextDocument,
          selectedNodeId: "",
          xmlText: serializeDocument(nextDocument),
        };
      }
      removeNodeFromTree(nextDocument.tree, action.nodeId);
      return {
        ...state,
        document: nextDocument,
        selectedNodeId: nextDocument.tree?.id ?? "",
        xmlText: serializeDocument(nextDocument),
      };
    }
    case "CLEAR_TREE": {
      if (!state.document) {
        return state;
      }
      const nextDocument = cloneDocument(state.document);
      nextDocument.tree = null;
      return {
        ...state,
        document: nextDocument,
        selectedNodeId: "",
        xmlText: serializeDocument(nextDocument),
      };
    }
    case "SET_DRAG_PAYLOAD":
      return {
        ...state,
        dragPayload: action.dragPayload,
      };
    case "MOVE_NODE_TO_CHILD_END": {
      if (!state.document || !state.document.tree || action.nodeId === action.parentNodeId) {
        return state;
      }
      const nextDocument = cloneDocument(state.document);
      const moving = findNode(nextDocument, action.nodeId);
      const target = findNode(nextDocument, action.parentNodeId);
      if (!moving?.parent || !target || nodeContainsId(moving.node, action.parentNodeId)) {
        return state;
      }
      const targetSchema = state.nodes[target.node.type];
      if (!targetSchema || targetSchema.kind !== "control") {
        return state;
      }
      removeNodeFromTree(nextDocument.tree, action.nodeId);
      target.node.children = [...(target.node.children ?? []), moving.node];
      return {
        ...state,
        document: nextDocument,
        selectedNodeId: action.nodeId,
        xmlText: serializeDocument(nextDocument),
      };
    }
    default:
      return state;
  }
}
