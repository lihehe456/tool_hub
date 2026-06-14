# Tool Hub Web Packaging Guide

本文档说明 `RY-Robot Tool Hub` 在 Ubuntu 和 Windows 下的打包与运行方式。

## 1. 目标产物

打包后的主程序为：

```text
dist/RY-Robot-Tool-Hub/RY-Robot-Tool-Hub
```

Windows 下对应为：

```text
dist\RY-Robot-Tool-Hub\RY-Robot-Tool-Hub.exe
```

打包产物是一个目录，不是单个文件。整个 `RY-Robot-Tool-Hub` 文件夹需要一起拷贝。

## 2. 已打包内容

当前打包配置已经包含以下资源：

- `tool_hub_web/static`
- `path_editor_web/static`
- `task_editor/static`
- `task_execute_server/waypoints_attributes`
- `nav2_behavior_tree/nav2_tree_nodes.xml`

因此打包后的程序可以直接打开主页面，并使用：

- Path Editor
- Task Group Builder
- Task Group Mixer
- Task Editor
- Waypoint Task Builder

## 3. Ubuntu 打包

### 3.1 环境准备

进入目录：

```bash
cd <repo>/tool_hub_app/tool_hub_web
```

安装打包依赖：

```bash
python3 -m pip install --user pyinstaller flask pyyaml
```

### 3.2 开始打包

执行：

```bash
bash build_linux.sh
```

打包成功后，输出目录为：

```text
<repo>/tool_hub_app/tool_hub_web/dist/RY-Robot-Tool-Hub
```

### 3.3 运行方式

直接运行：

```bash
cd <repo>/tool_hub_app/tool_hub_web/dist/RY-Robot-Tool-Hub
./RY-Robot-Tool-Hub
```

默认端口：

```text
http://127.0.0.1:7791
```

如果端口占用，可以改端口：

```bash
./RY-Robot-Tool-Hub --port 7792
```

### 3.4 指定业务目录

如果部署机器上的数据目录不同，可以启动时手动指定：

```bash
./RY-Robot-Tool-Hub \
  --paths-root /data/paths \
  --maps-root /data/maps \
  --tasks-root /data/tasks \
  --waypoint-tasks-root /data/waypoint_tasks
```

可选参数说明：

- `--paths-root`：路径文件浏览根目录
- `--maps-root`：地图文件浏览根目录
- `--tasks-root`：任务组文件浏览根目录
- `--waypoint-tasks-root`：路点任务 XML 浏览根目录
- `--attrs-dir`：`waypoints_attributes` 根目录
- `--host`：监听地址
- `--port`：监听端口
- `--open-browser`：启动后自动打开浏览器

## 4. Windows 打包

### 4.1 重要说明

Windows 包建议在 Windows 系统上打。

原因：

- `PyInstaller` 不能稳定地在 Linux 上直接产出 Windows 可执行文件
- Linux 和 Windows 的可执行格式不同
- 最稳妥的方式是在目标系统本机打包

也就是说：

- Ubuntu 包：在 Ubuntu 上打
- Windows 包：在 Windows 上打

### 4.2 Windows 环境准备

建议安装：

- Python 3.10
- pip

然后进入：

```bat
cd tool_hub_app\tool_hub_web
```

安装依赖：

```bat
py -m pip install pyinstaller flask pyyaml
```

### 4.3 开始打包

执行：

```bat
build_windows.bat
```

或者：

```bat
py -m PyInstaller --noconfirm tool_hub.spec
```

打包成功后，输出目录为：

```text
tool_hub_app\tool_hub_web\dist\RY-Robot-Tool-Hub
```

主程序一般为：

```text
RY-Robot-Tool-Hub.exe
```

### 4.4 Windows 运行方式

在 `dist\RY-Robot-Tool-Hub` 目录下运行：

```bat
RY-Robot-Tool-Hub.exe
```

如果端口冲突：

```bat
RY-Robot-Tool-Hub.exe --port 7792
```

如果需要指定数据目录：

```bat
RY-Robot-Tool-Hub.exe --paths-root D:\robot\paths --maps-root D:\robot\maps --tasks-root D:\robot\tasks --waypoint-tasks-root D:\robot\waypoint_tasks
```

## 5. 产物拷贝方式

不要只拷贝主程序文件。

必须拷贝整个目录：

```text
dist/RY-Robot-Tool-Hub/
```

因为 `_internal/` 下还有依赖库和资源文件。

## 6. 常见问题

### 6.1 端口被占用

启动时报：

```text
Address already in use
Port 7791 is in use
```

解决办法：

1. 换端口启动
2. 关闭旧进程

Ubuntu 查看占用：

```bash
ss -ltnp | rg ':7791\b'
```

### 6.2 双击后闪退

通常有几种原因：

- 端口已占用
- 路径参数不对
- 资源目录缺失

建议先在终端里启动，看报错信息：

Ubuntu：

```bash
./RY-Robot-Tool-Hub
```

Windows：

```bat
RY-Robot-Tool-Hub.exe
```

### 6.3 打包后找不到业务数据

打包程序内置的是页面资源和默认属性资源。

你的实际业务数据，例如：

- `paths`
- `maps`
- `tasks`
- `waypoint_tasks`

更推荐放在外部目录，通过启动参数指定。这样更方便迁移和更新。

## 7. 推荐发布方式

推荐最终给用户的发布包结构如下：

```text
RY-Robot-Tool-Hub/
├── RY-Robot-Tool-Hub(.exe)
├── _internal/
├── paths/                 # 可选，放默认路径文件
├── maps/                  # 可选，放默认地图
├── tasks/                 # 可选，放默认任务组
└── waypoint_tasks/        # 可选，放默认任务模板
```

如果你希望程序开箱即用，可以把这些业务目录一起放到发布目录里。

## 8. 当前状态

目前已经验证通过：

- Ubuntu 下 `PyInstaller` 可成功打包
- 生成的 Linux 可执行文件可成功启动
- 打包改造后的测试通过

验证结果：

- Python tests: `38 passed`
- Frontend tests: `50 passed`

