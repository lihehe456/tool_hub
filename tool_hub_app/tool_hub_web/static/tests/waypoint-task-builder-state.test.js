import assert from "node:assert/strict";
import test from "node:test";

import {
  createWaypointTaskBuilderInitialState,
  reduceWaypointTaskBuilderState,
} from "../waypoint-task-builder-state.js";

function demoDocument() {
  return {
    task_name: "demo_task",
    tree: {
      id: "root-seq",
      type: "Sequence",
      attrs: { name: "Main" },
      children: [
        {
          id: "child-a",
          type: "ChangeUssStatus",
          attrs: { status: "true" },
          children: [],
        },
      ],
    },
  };
}

test("SET_DOCUMENT stores document and selects root node", () => {
  const next = reduceWaypointTaskBuilderState(createWaypointTaskBuilderInitialState(), {
    type: "SET_DOCUMENT",
    taskPath: "/tmp/demo_task.xml",
    document: demoDocument(),
  });

  assert.equal(next.taskPath, "/tmp/demo_task.xml");
  assert.equal(next.selectedNodeId, "root-seq");
  assert.equal(next.document.tree.type, "Sequence");
});

test("ADD_NODE_AS_CHILD appends new node under selected control node", () => {
  const state = {
    ...createWaypointTaskBuilderInitialState(),
    nodes: {
      Sequence: {
        kind: "control",
      },
    },
    document: demoDocument(),
    selectedNodeId: "root-seq",
  };

  const next = reduceWaypointTaskBuilderState(state, {
    type: "ADD_NODE_AS_CHILD",
    parentNodeId: "root-seq",
    nodeTemplate: {
      id: "new-node",
      type: "Wait",
      attrs: { wait_duration: "2" },
      children: [],
    },
  });

  assert.equal(next.document.tree.children.length, 2);
  assert.equal(next.document.tree.children[1].type, "Wait");
});

test("UPDATE_NODE_ATTR updates a node field in place", () => {
  const state = {
    ...createWaypointTaskBuilderInitialState(),
    document: demoDocument(),
    selectedNodeId: "child-a",
  };

  const next = reduceWaypointTaskBuilderState(state, {
    type: "UPDATE_NODE_ATTR",
    nodeId: "child-a",
    fieldName: "status",
    value: "false",
  });

  assert.equal(next.document.tree.children[0].attrs.status, "false");
});

test("MOVE_NODE_DOWN reorders siblings", () => {
  const state = {
    ...createWaypointTaskBuilderInitialState(),
    document: {
      task_name: "demo_task",
      tree: {
        id: "root-seq",
        type: "Sequence",
        attrs: {},
        children: [
          { id: "a", type: "ChangeUssStatus", attrs: {}, children: [] },
          { id: "b", type: "Wait", attrs: {}, children: [] },
        ],
      },
    },
    selectedNodeId: "a",
  };

  const next = reduceWaypointTaskBuilderState(state, {
    type: "MOVE_NODE",
    nodeId: "a",
    direction: "down",
  });

  assert.deepEqual(
    next.document.tree.children.map((node) => node.id),
    ["b", "a"],
  );
});

test("REMOVE_NODE removes subtree and keeps a valid selection", () => {
  const state = {
    ...createWaypointTaskBuilderInitialState(),
    document: demoDocument(),
    selectedNodeId: "child-a",
  };

  const next = reduceWaypointTaskBuilderState(state, {
    type: "REMOVE_NODE",
    nodeId: "child-a",
  });

  assert.equal(next.document.tree.children.length, 0);
  assert.equal(next.selectedNodeId, "root-seq");
});

test("REMOVE_NODE can remove the root node and leave an empty tree", () => {
  const state = {
    ...createWaypointTaskBuilderInitialState(),
    document: {
      task_name: "demo_task",
      tree: {
        id: "root-seq",
        type: "Sequence",
        attrs: { name: "Main" },
        children: [],
      },
    },
    selectedNodeId: "root-seq",
  };

  const next = reduceWaypointTaskBuilderState(state, {
    type: "REMOVE_NODE",
    nodeId: "root-seq",
  });

  assert.equal(next.document.tree, null);
  assert.equal(next.selectedNodeId, "");
});

test("CLEAR_TREE removes all root children and keeps root selected", () => {
  const state = {
    ...createWaypointTaskBuilderInitialState(),
    document: demoDocument(),
    selectedNodeId: "child-a",
  };

  const next = reduceWaypointTaskBuilderState(state, {
    type: "CLEAR_TREE",
  });

  assert.equal(next.document.tree, null);
  assert.equal(next.selectedNodeId, "");
});

test("ADD_ROOT_NODE restores a root after clearing", () => {
  const state = {
    ...createWaypointTaskBuilderInitialState(),
    document: {
      task_name: "demo_task",
      tree: null,
    },
    nodes: {
      Sequence: {
        kind: "control",
      },
    },
    selectedNodeId: "",
  };

  const next = reduceWaypointTaskBuilderState(state, {
    type: "ADD_ROOT_NODE",
    nodeTemplate: {
      id: "new-root",
      type: "Sequence",
      attrs: { name: "MainSequence" },
      children: [],
    },
  });

  assert.equal(next.document.tree.id, "new-root");
  assert.equal(next.selectedNodeId, "new-root");
});

test("SET_XML_TEXT stores manual XML draft for reverse parsing", () => {
  const state = createWaypointTaskBuilderInitialState();

  const next = reduceWaypointTaskBuilderState(state, {
    type: "SET_XML_TEXT",
    xmlText: "<root />",
  });

  assert.equal(next.xmlText, "<root />");
});

test("SET_XML_TEXT does not mutate the current document snapshot", () => {
  const state = {
    ...createWaypointTaskBuilderInitialState(),
    document: demoDocument(),
    xmlText: "<root><BehaviorTree ID=\"MainTree\" /></root>",
  };

  const next = reduceWaypointTaskBuilderState(state, {
    type: "SET_XML_TEXT",
    xmlText: "<root><BehaviorTree ID=\"MainTree\"><Sequence /></BehaviorTree></root>",
  });

  assert.equal(next.document.tree.type, "Sequence");
  assert.equal(next.document.tree.children[0].type, "ChangeUssStatus");
  assert.equal(
    next.xmlText,
    "<root><BehaviorTree ID=\"MainTree\"><Sequence /></BehaviorTree></root>",
  );
});
