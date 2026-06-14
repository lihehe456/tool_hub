import assert from "node:assert/strict";
import test from "node:test";

import { renderWaypointTaskBuilderView } from "../waypoint-task-builder-view.js";

function createMockElements() {
  return {
    taskPath: { value: "" },
    taskDirectory: { value: "" },
    taskName: { value: "" },
    status: { textContent: "", dataset: {} },
    palette: { innerHTML: "" },
    tree: { innerHTML: "" },
    fields: { innerHTML: "" },
    xmlPreview: { value: "" },
  };
}

test("renderWaypointTaskBuilderView renders inline field editors and port summaries in tree nodes", () => {
  const elements = createMockElements();
  const state = {
    taskPath: "/tmp/demo.xml",
    taskDirectory: "/tmp",
    taskName: "demo",
    status: { message: "", error: false },
    selectedNodeId: "wait-node",
    xmlText: "<root />",
    nodes: {
      Sequence: {
        kind: "control",
        fields: [{ name: "name", default: "" }],
        input_ports: [{ name: "name", direction: "input" }],
        output_ports: [],
      },
      Wait: {
        kind: "action",
        fields: [
          { name: "wait_duration", default: "" },
          { name: "server_name", default: "" },
        ],
        input_ports: [
          { name: "wait_duration", direction: "input" },
          { name: "server_name", direction: "input" },
        ],
        output_ports: [{ name: "done", direction: "output" }],
      },
    },
    document: {
      task_name: "demo",
      tree: {
        id: "root",
        type: "Sequence",
        attrs: { name: "MainTree" },
        children: [
          {
            id: "wait-node",
            type: "Wait",
            attrs: { wait_duration: "3", server_name: "/wait" },
            children: [],
          },
        ],
      },
    },
  };

  renderWaypointTaskBuilderView(elements, state);

  assert.match(elements.tree.innerHTML, /data-inline-field-name="wait_duration"/);
  assert.match(elements.tree.innerHTML, /data-inline-field-name="server_name"/);
  assert.match(elements.tree.innerHTML, /入口/);
  assert.match(elements.tree.innerHTML, /出口/);
  assert.match(elements.tree.innerHTML, /wait_duration/);
});

test("renderWaypointTaskBuilderView shows a root dropzone when the tree is empty", () => {
  const elements = createMockElements();
  const state = {
    taskPath: "",
    taskDirectory: "",
    taskName: "demo",
    status: { message: "", error: false },
    selectedNodeId: "",
    xmlText: "",
    nodes: {
      Sequence: {
        kind: "control",
        fields: [{ name: "name", default: "" }],
        input_ports: [{ name: "name", direction: "input" }],
        output_ports: [],
      },
    },
    document: {
      task_name: "demo",
      tree: null,
    },
  };

  renderWaypointTaskBuilderView(elements, state);

  assert.match(elements.tree.innerHTML, /根节点/);
  assert.match(elements.tree.innerHTML, /data-root-dropzone="true"/);
});
