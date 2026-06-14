function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function kindLabel(kind) {
  if (kind === "control") {
    return "控制";
  }
  if (kind === "action") {
    return "叶子";
  }
  return kind || "unknown";
}

function renderPortSection(title, ports, toneClass) {
  if (!ports?.length) {
    return "";
  }
  return `
    <div class="builder-port-section">
      <span class="builder-port-title">${title}</span>
      <div class="builder-port-list">
        ${ports
          .map(
            (port) => `
              <span class="builder-port-badge ${toneClass}" title="${escapeHtml(port.description ?? "")}">
                ${escapeHtml(port.name)}
              </span>
            `,
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderPalette(nodes) {
  const entries = Object.entries(nodes).sort(([leftName, leftSchema], [rightName, rightSchema]) => {
    if ((leftSchema.kind === "control") !== (rightSchema.kind === "control")) {
      return leftSchema.kind === "control" ? -1 : 1;
    }
    return leftName.localeCompare(rightName);
  });
  if (!entries.length) {
    return "<p class=\"panel-empty\">正在加载节点库...</p>";
  }
  return `
    <div class="builder-palette">
      ${entries
        .map(
          ([nodeType, schema]) => `
            <button
              class="builder-palette-item"
              type="button"
              draggable="true"
              data-node-type="${nodeType}"
            >
              <strong>${nodeType}</strong>
              <span>${kindLabel(schema.kind)}</span>
              <small>入口 ${schema.input_ports?.length ?? 0} / 出口 ${schema.output_ports?.length ?? 0}</small>
            </button>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderInlineFields(node, schema) {
  const fields = schema?.fields ?? [];
  if (!fields.length) {
    return "";
  }
  return `
    <div class="builder-inline-fields">
      ${fields
        .map(
          (field) => `
            <label class="builder-inline-field">
              <span>${escapeHtml(field.name)}</span>
              <input
                type="text"
                data-inline-field-name="${field.name}"
                data-node-id="${node.id}"
                value="${escapeHtml(node.attrs?.[field.name] ?? field.default ?? "")}"
              >
            </label>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderTreeNode(node, selectedNodeId, nodes) {
  const schema = nodes[node.type] ?? { kind: "unknown", fields: [], input_ports: [], output_ports: [] };
  const selected = node.id === selectedNodeId ? "true" : "false";
  const canHaveChildren = schema.kind === "control";
  return `
    <li class="builder-tree-item" data-selected="${selected}">
      <div
        class="builder-tree-card"
        data-node-id="${node.id}"
        draggable="true"
      >
        <div class="builder-tree-card-head">
          <div class="builder-tree-card-main">
            <button type="button" class="builder-node-select" data-action="select-node" data-node-id="${node.id}">
              ${node.type}
            </button>
            <span class="builder-kind-badge">${kindLabel(schema.kind)}</span>
          </div>
          <div class="builder-tree-actions">
            <button type="button" data-action="move-node-up" data-node-id="${node.id}">上移</button>
            <button type="button" data-action="move-node-down" data-node-id="${node.id}">下移</button>
            <button type="button" data-action="remove-node" data-node-id="${node.id}">删除</button>
          </div>
        </div>
        <div class="builder-tree-card-body">
          ${renderPortSection("入口", schema.input_ports, "is-input")}
          ${renderPortSection("出口", schema.output_ports, "is-output")}
          ${renderInlineFields(node, schema)}
        </div>
      </div>
      ${
        canHaveChildren
          ? `
              <div class="builder-dropzone" data-drop-parent-id="${node.id}">
                拖入这里作为子节点
              </div>
            `
          : ""
      }
      ${
        node.children?.length
          ? `<ul class="builder-tree-list">${node.children
              .map((child) => renderTreeNode(child, selectedNodeId, nodes))
              .join("")}</ul>`
          : ""
      }
    </li>
  `;
}

function renderTree(document, selectedNodeId, nodes) {
  if (!document) {
    return "<p class=\"panel-empty\">先新建或加载一个任务模板。</p>";
  }
  if (!document.tree) {
    return `
      <div class="builder-root-dropzone" data-root-dropzone="true">
        <strong>根节点</strong>
        <span>从左侧拖一个节点到这里，作为新的树根。</span>
      </div>
    `;
  }
  return `<ul class="builder-tree-list">${renderTreeNode(document.tree, selectedNodeId, nodes)}</ul>`;
}

function renderFields(selectedNode, schema) {
  if (!selectedNode || !schema) {
    return "<p class=\"panel-empty\">选择一个节点来编辑参数。</p>";
  }
  return `
    <div class="builder-form">
      <h3>${selectedNode.type}</h3>
      ${(schema.fields ?? [])
        .map(
          (field) => `
            <label>
              <span>${field.name}</span>
              <input
                type="text"
                data-field-name="${field.name}"
                value="${escapeHtml(selectedNode.attrs?.[field.name] ?? field.default ?? "")}"
              >
            </label>
          `,
        )
        .join("")}
      ${renderPortSection("入口", schema.input_ports, "is-input")}
      ${renderPortSection("出口", schema.output_ports, "is-output")}
    </div>
  `;
}

export function renderWaypointTaskBuilderView(elements, state) {
  elements.taskPath.value = state.taskPath ?? "";
  elements.taskDirectory.value = state.taskDirectory ?? "";
  elements.taskName.value = state.taskName ?? "";
  elements.status.textContent = state.status.message || "准备就绪";
  elements.status.dataset.error = state.status.error ? "true" : "false";
  elements.palette.innerHTML = renderPalette(state.nodes);
  elements.tree.innerHTML = renderTree(state.document, state.selectedNodeId, state.nodes);

  const selectedNode = (() => {
    let result = null;
    function search(node) {
      if (!node || result) {
        return;
      }
      if (node.id === state.selectedNodeId) {
        result = node;
        return;
      }
      for (const child of node.children ?? []) {
        search(child);
      }
    }
    search(state.document?.tree);
    return result;
  })();

  elements.fields.innerHTML = renderFields(selectedNode, state.nodes[selectedNode?.type]);
  elements.xmlPreview.value = state.xmlText ?? "";
}
