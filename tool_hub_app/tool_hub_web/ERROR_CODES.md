# RY-Robot Tool Hub HTTP 错误码说明

本文档整理 了Web 工具接口的 HTTP 错误码和常见原因。

## 1. 返回格式

大多数已处理错误会返回 JSON：

```json
{
  "error": "错误原因"
}
```

常见成功响应为 `200 OK`，错误响应主要为 `400 Bad Request` 和 `404 Not Found`。如果请求方法不对，Flask 会返回 `405 Method Not Allowed`。如果出现未捕获异常，则返回 `500 Internal Server Error`。

## 2. 通用 HTTP 错误码

| HTTP 码 | 含义 | 常见原因 | 处理办法 |
| --- | --- | --- | --- |
| `400 Bad Request` | 请求参数不合法或业务校验失败 | 缺少必填字段、路径不是绝对路径、文件后缀不符合要求、XML/JSON 内容不符合工具规则、模板命名不符合批量生成规则、目标文件已存在但未允许覆盖 | 根据返回的 `error` 文本补齐参数、修正路径或文件内容 |
| `404 Not Found` | 请求的文件或目录不存在 | 地图 YAML 不存在、PGM 图片不存在、路径 JSON 不存在、任务 JSON 不存在、工作区文件不存在、扫描目录不存在 | 检查页面中填写或选择的文件路径，确认文件在磁盘上真实存在 |
| `405 Method Not Allowed` | 请求方法错误 | 对只支持 `POST` 的接口使用了 `GET`，或反过来 | 按接口定义使用正确的请求方法；网页正常操作一般不会触发 |
| `500 Internal Server Error` | 服务端未捕获异常 | 文件内容损坏、JSON 解析失败、磁盘权限不足、保存目录不可写、代码缺陷或运行环境异常 | 查看终端日志中的 Python traceback，优先检查文件格式和目录权限 |

## 3. 路径编辑器

涉及页面：

- `Path Editor`
- `Task Group Builder`
- `Task Group Mixer`

### 3.1 `400 Bad Request`

| 场景 | 典型错误文本 | 原因 |
| --- | --- | --- |
| 加载地图 | `yaml_path is required` | 未传入地图 YAML 路径 |
| 加载地图 | `Map yaml missing image field` | 地图 YAML 中缺少 `image` 字段 |
| 浏览用户文件 | `path must be an absolute path` | 浏览路径不是绝对路径 |
| 加载路径 | `path is required` | 未传入路径 JSON 路径 |
| 生成子任务对 | `generated_subtask_name is required` | 没有填写生成的子任务名称 |
| 保存路径 | `document is required` | 请求中没有路径文档内容 |
| 工作区路径 | `workspace_path is required` | 未填写工作区文件路径 |
| 工作区路径 | `workspace_path must be an absolute path` | 工作区路径不是绝对路径 |
| 工作区路径 | `workspace_path must point to a .json file` | 工作区路径不是 `.json` 文件 |
| 混编导入 | `source_workspace_path must point to a .workspace.json file` | 导入源不是旁路工作区文件 |
| 混编导入 | `source workspace missing subtasks` | 源工作区缺少 `subtasks` 列表 |
| 添加或替换子任务对 | `forward_subtask and return_subtask are required` | 去程或返程子任务缺失 |
| 替换子任务对 | `old_pair_id is required` | 没有指定要替换的子任务对 |
| 导出任务组 | `task_group_name is required before export` | 工作区未填写任务组名称 |
| 重命名路径 | `src_path and dst_path are required` | 源路径或目标路径缺失 |
| 重命名路径 | `Destination already exists` | 目标文件已经存在 |

### 3.2 `404 Not Found`

| 场景 | 典型错误文本 | 原因 |
| --- | --- | --- |
| 加载地图 | `Map yaml not found` | 地图 YAML 文件不存在 |
| 加载地图 | `PGM not found` | 地图 YAML 指向的 PGM 文件不存在 |
| 浏览路径或地图目录 | `Directory not found` | 要浏览的目录不存在 |
| 加载/保存/删除路径 | `Path file not found` | 路径 JSON 文件不存在 |
| 读取/导入/导出工作区 | `Workspace file not found` | 工作区 JSON 文件不存在 |

## 4. 任务编辑器

涉及页面：

- `Task Editor`

### 4.1 `400 Bad Request`

| 场景 | 典型错误文本 | 原因 |
| --- | --- | --- |
| 自定义属性目录 | `waypoint_tasks_path must be an absolute path` | 路点任务目录不是绝对路径 |
| 自定义属性目录 | `speed_modes_path must be an absolute path` | 速度模式目录不是绝对路径 |
| 自定义属性目录 | `directory not found` | 指定的路点任务目录或速度模式目录不存在 |
| 保存任务 | `No path provided` | 保存时未传入任务文件路径 |
| 保存任务并同步旁路文件 | `No path provided` | 保存任务组时未传入任务文件路径 |

### 4.2 `404 Not Found`

| 场景 | 典型错误文本 | 原因 |
| --- | --- | --- |
| 加载任务 | `File not found` | 任务组 JSON 文件不存在 |
| 加载任务组和旁路文件 | `File not found` | 任务组 JSON 文件不存在 |
| 从任务组生成旁路文件 | `File not found` | 任务组 JSON 文件不存在 |
| 加载地图 | `map_url empty or not found` | 任务中的 `map_url` 为空或地图 YAML 不存在 |
| 加载地图 | `PGM not found` | 地图 YAML 指向的 PGM 文件不存在 |

## 5. 虚拟墙工具

涉及页面：

- `Virtual Wall Builder`

### 5.1 `400 Bad Request`

| 场景 | 典型错误文本 | 原因 |
| --- | --- | --- |
| 浏览文件 | `path must be an absolute path` | 浏览路径不是绝对路径 |
| 保存虚拟墙 | `path is required` | 未传入保存路径 |
| 保存虚拟墙 | `path must be an absolute path` | 保存路径不是绝对路径 |
| 保存虚拟墙 | `path must point to a .yaml or .yml file` | 保存文件不是 YAML 后缀 |
| 保存虚拟墙 | `map_origin must contain at least x and y` | 地图原点数据不完整 |
| 保存虚拟墙 | `Invalid point` | 虚拟墙点数据格式不正确 |
| 加载虚拟墙 | `Invalid virtual wall file: missing virtual_walls` | YAML 文件不是工具支持的虚拟墙结构 |
| 加载地图 | `yaml_path is required` | 未传入地图 YAML 路径 |
| 加载地图 | `Map yaml missing image field` | 地图 YAML 缺少 `image` 字段 |

### 5.2 `404 Not Found`

| 场景 | 典型错误文本 | 原因 |
| --- | --- | --- |
| 加载地图 | `Map yaml not found` | 地图 YAML 文件不存在 |
| 加载地图 | `PGM not found` | 地图 YAML 指向的 PGM 文件不存在 |

说明：虚拟墙文件不存在时，当前实现通常会通过 `ValueError` 返回 `400`，错误文本为 `Virtual wall file not found`。

## 6. 路点任务生成器

涉及页面：

- `Waypoint Task Builder`

### 6.1 `400 Bad Request`

| 场景 | 典型错误文本 | 原因 |
| --- | --- | --- |
| 浏览文件 | `path is required` | 未传入浏览路径 |
| 浏览文件 | `path must be an absolute path` | 浏览路径不是绝对路径 |
| 解析 XML | `xml_text is required` | XML 预览/反向解析时内容为空 |
| 解析 XML | `Root element must be <root>` | XML 根节点不是 `<root>` |
| 解析 XML | `main_tree_to_execute must be MainTree` | 主树入口不是 `MainTree` |
| 解析 XML | `BehaviorTree ID must be MainTree` | 行为树 ID 不符合工具规则 |
| 解析 XML | `MainTree must contain exactly one top-level node` | 主树顶层节点不是唯一节点 |
| 解析 XML | `Unsupported node` | XML 中出现工具节点库不支持的节点 |
| 解析 XML 或保存 | `Waypoint task tree is empty` | 树结构为空 |
| 保存 XML | `task_name is required` | 未填写任务名 |
| 保存 XML | `document is required` | 未传入树结构文档 |
| 保存 XML | `Leaf node ... cannot have children` | 叶子节点下挂了子节点 |
| 保存 XML | `Node ... supports at most ... children` | 节点子节点数量超过限制 |
| 保存 XML | `Node ... requires at least ... children` | 节点子节点数量不足 |

### 6.2 `404 Not Found`

| 场景 | 典型错误文本 | 原因 |
| --- | --- | --- |
| 加载 XML | `Task file not found` | 路点任务 XML 文件不存在 |

## 7. 任务批量生成器

涉及页面：

- `Task Batch Generator`

### 7.1 `400 Bad Request`

| 场景 | 典型错误文本 | 原因 |
| --- | --- | --- |
| 浏览目录 | `directory must be an absolute path` | 目录不是绝对路径 |
| 预览/生成 | `template_01 is required` | 缺少 01 模板任务文件 |
| 预览/生成 | `template_03 is required` | 缺少 03 模板任务文件 |
| 预览/生成 | `output_dir is required` | 缺少输出目录 |
| 预览/生成 | `Expected n01 sample` | 传入的模板不是 `*01` 样例 |
| 预览/生成 | `Expected n03 sample` | 传入的模板不是 `*03` 样例 |
| 预览/生成 | `Sample prefixes do not match` | 两个模板前缀不一致 |
| 预览/生成 | `Sample floors do not match` | 两个模板楼层不一致 |
| 预览/生成 | `Unable to infer source floor from template task ids` | 无法从模板任务内部推断源楼层 |
| 预览/生成 | `Start floor must be less than or equal to end floor` | 起始楼层大于结束楼层 |
| 扫描模板 | `Duplicate sample file` | 同一目录下有重复样例文件 |
| 生成文件 | `Target file already exists` | 目标文件已存在，且未开启覆盖 |

### 7.2 `404 Not Found`

| 场景 | 典型错误文本 | 原因 |
| --- | --- | --- |
| 扫描模板 | `Directory not found` | 模板扫描目录不存在 |

## 8. 任务属性批量生成器

涉及页面：

- `Task Attribute Batch Generator`

### 8.1 `400 Bad Request`

| 场景 | 典型错误文本 | 原因 |
| --- | --- | --- |
| 浏览目录 | `directory must be an absolute path` | 目录不是绝对路径 |
| 预览/生成 | `reference_task_path is required` | 缺少参考任务 JSON |
| 预览/生成 | `template_xml_path is required` | 缺少模板 XML |
| 预览/生成 | `output_dir is required` | 缺少输出目录 |
| 预览/生成 | `not found` | 指定参考任务、模板 XML 或输出目录不存在 |
| 预览/生成 | `Unsupported attribute template filename` | 模板 XML 文件名不符合支持的属性模板命名 |
| 预览/生成 | `Unable to infer fixed and variable floors from reference task` | 无法从参考任务推断固定楼层和变量楼层 |
| 预览/生成 | `Unsupported attribute filename format` | 任务内部引用的属性文件名格式不支持 |
| 预览/生成 | `Unsupported attribute type` | 当前模板属性类型不支持 |
| 预览/生成 | `Start floor must be less than or equal to end floor` | 起始楼层大于结束楼层 |
| 生成文件 | `Target file already exists` | 目标 XML 已存在，且未开启覆盖 |

## 9. 排查建议

1. 先看网页弹出的错误文本，它通常就是后端返回的 `error` 字段。
2. 如果是 `400`，优先检查输入参数、文件后缀、文件内容格式和模板命名规则。
3. 如果是 `404`，优先检查绝对路径是否真实存在，尤其是地图 YAML 与 PGM 是否在同一目录并正确关联。
4. 如果是 `500`，查看运行工具的终端日志；常见根因是 JSON/YAML/XML 文件内容损坏、权限不足或代码未覆盖的异常。
5. 打包版和源码版都支持从页面输入绝对路径；默认工作路径为 `/opt/ry`。
