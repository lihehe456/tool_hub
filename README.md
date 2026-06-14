# Tool Hub Handover

这是为项目移交整理出的单文件夹版本，目标是让接手人不用在原工程里到处找代码和资源。

## 目录结构

```text
tool_hub_handover/
├── README.md
├── tool_hub_app/
│   ├── tool_hub_web/
│   ├── path_editor_web/
│   ├── task_editor/
│   ├── runtime_paths.py
│   ├── task_execute_server/
│   │   └── waypoints_attributes/
│   └── nav2_behavior_tree/
│       └── nav2_tree_nodes.xml
├── runtime/
│   └── ubuntu/
│       └── RY-Robot-Tool-Hub/
└── data/
    ├── paths/
    ├── maps/
    └── tasks/
```

## 各部分用途

### `tool_hub_app/`

开发源码。

如果接手人要继续开发、修改网页功能、重新打包，主要看这里。

### `runtime/ubuntu/`

已经打好的 Ubuntu 可运行版本。

如果只是要直接使用工具，不想先搭开发环境，可以直接运行这里面的可执行文件。

### `data/`

业务数据目录。

包含：

- 路径文件 `paths`
- 地图文件 `maps`
- 任务组文件 `tasks`

这些属于运行期数据，不是工具框架源码。

## Ubuntu 直接运行

进入：

```bash
cd runtime/ubuntu/RY-Robot-Tool-Hub
```

运行：

```bash
./RY-Robot-Tool-Hub
```

如果要指定外部数据目录：

```bash
./RY-Robot-Tool-Hub \
  --paths-root /your/paths \
  --maps-root /your/maps \
  --tasks-root /your/tasks \
  --waypoint-tasks-root /your/waypoint_tasks
```

## 继续开发

开发相关代码集中在：

- `tool_hub_app/tool_hub_web`
- `tool_hub_app/path_editor_web`
- `tool_hub_app/task_editor`
- `tool_hub_app/task_execute_server/waypoints_attributes`
- `tool_hub_app/nav2_behavior_tree/nav2_tree_nodes.xml`

## 打包说明

打包说明见：

- `tool_hub_app/tool_hub_web/PACKAGING.md`

## 说明

这里已经脱离了 `fcrp_master` 这层目录，接手人只需要理解 `tool_hub_app` 这一套结构即可。
