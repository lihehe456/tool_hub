# Tool Hub Web

统一入口服务，提供 `RY-Robot Tool Hub` 主页面，并集中挂载：

- `Path Editor`
- `Task Group Builder`
- `Task Group Mixer`
- `Task Editor`
- `Waypoint Task Builder`
- `Task Batch Generator`
- `Task Attribute Batch Generator`
- `Virtual Wall Builder`
- `PCD to 2D Map`

详细使用说明请看：

```text
USER_GUIDE.md
```

HTTP 错误码整理请看：

```text
ERROR_CODES.md
```

## 启动

```bash
cd tool_hub_app/tool_hub_web
python3 server.py
```

浏览器打开：

```text
http://127.0.0.1:7791/
```

或使用统一启动入口：

```bash
cd tool_hub_app/tool_hub_web
python3 launcher.py --open-browser
```

可选目录参数：

```bash
python3 launcher.py \
  --paths-root /your/paths \
  --maps-root /your/maps \
  --tasks-root /your/tasks \
  --waypoint-tasks-root /your/waypoint_tasks
```

## 打包

先安装依赖：

```bash
pip3 install flask pyyaml pyinstaller
```

Ubuntu/Linux：

```bash
cd tool_hub_app/tool_hub_web
./build_linux.sh
```

Windows：

```bat
cd tool_hub_app\tool_hub_web
build_windows.bat
```

打包输出目录：

```text
tool_hub_app/tool_hub_web/dist/RY-Robot-Tool-Hub/
```

运行可执行文件后，也可以继续通过命令行参数指定外部数据目录，而不是把业务数据写死在包里。

## 路由

- `/`：主页面门户
- `/path-editor`：路径编辑器
- `/task-groups`：任务组工作区
- `/task-group-mixer`：任务组混编页
- `/task-editor`：任务编辑器
- `/waypoint-task-builder`：路点任务模板可视化编辑器
- `/pcd-to-map`：点云切片转 2D 地图工具

## 说明

- `path_editor_web` 仍可单独运行
- `task_editor` 仍可单独运行
- `tool_hub_web` 是新的统一入口，不替代旧工具的独立启动能力
- `Waypoint Task Builder` 面向现有 `waypoint_tasks/*.xml` 模板，支持加载、树结构编辑、参数编辑、XML 预览和保存
- `PCD to 2D Map` 按原 `pcd2pgm` 链路预览不同高度切片并导出 `PGM/YAML`
