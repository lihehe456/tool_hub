# RY-Robot Tool Hub 使用说明

本文档记录 `RY-Robot Tool Hub` 中各功能模块的用途、操作流程、输入输出文件和注意事项。文档面向工具使用者和项目移交人员，重点说明“怎么用”和“生成什么文件”。

## 1. 总览

`RY-Robot Tool Hub` 是 FusionCloudRobot 工程中的网页工具集合入口。它把路径绘制、任务组装、任务编辑、路点任务 XML 编辑、批量生成和虚拟墙绘制集中到一个主页面。

默认访问地址：

```text
http://127.0.0.1:7791/
```

主页面标题：

```text
RY-Robot Tool Hub
```

当前包含以下功能入口：

- `Path Editor`：路径编辑、地图加载、路径点绘制，以及从路径生成去程/返程子任务对。
- `Task Group Builder`：从一个工作区中选择、排序、改名并导出任务组 JSON。
- `Task Group Mixer`：从多个旁路工作区导入子任务对，跨任务组自由混编。
- `Task Editor`：编辑已生成任务组中的路点语义字段，并同步旁路文件。
- `Waypoint Task Builder`：用树结构编辑路点任务 XML。
- `Task Batch Generator`：按任务模板对批量生成任务组 JSON。
- `Task Attribute Batch Generator`：按参考任务和模板 XML 批量生成路点任务属性 XML。
- `Virtual Wall Builder`：加载 2D 地图并绘制虚拟墙，导出旧 `VirtualWallManager` 可加载的 YAML。
- `PCD to 2D Map`：按 `pcd2pgm` 算法预览不同高度切片，并导出 `PGM/YAML` 地图。

推荐主流程：

```text
Path Editor -> Task Group Builder / Task Group Mixer -> Task Editor
```

独立维护流程：

```text
Waypoint Task Builder -> Task Editor
Task Batch Generator -> Task Editor
Task Attribute Batch Generator -> Task Editor
PCD to 2D Map -> Path Editor / Virtual Wall Builder
Virtual Wall Builder -> ROS VirtualWallManager
```

## 2. 启动方式

### 2.1 源码启动

从工程根目录进入：

```bash
cd <repo>/tool_hub_app/tool_hub_web
python3 server.py
```

浏览器打开：

```text
http://127.0.0.1:7791/
```

也可以使用统一启动器：

```bash
cd <repo>/tool_hub_app/tool_hub_web
python3 launcher.py --open-browser
```

### 2.2 指定目录启动

如果项目迁移到其他目录，可以在启动时指定业务数据根目录：

```bash
python3 launcher.py \
  --paths-root /data/paths \
  --maps-root /data/maps \
  --tasks-root /data/tasks \
  --waypoint-tasks-root /data/waypoint_tasks \
  --attrs-dir /data/waypoints_attributes
```

参数说明：

- `--paths-root`：路径 JSON 文件浏览根目录。
- `--maps-root`：地图 YAML 文件浏览根目录。
- `--tasks-root`：任务组 JSON 文件浏览根目录。
- `--waypoint-tasks-root`：路点任务 XML 文件浏览根目录。
- `--attrs-dir`：`waypoints_attributes` 根目录，通常包含 `speed_modes/` 和 `waypoint_tasks/`。
- `--host`：监听地址，默认 `127.0.0.1`。
- `--port`：监听端口，默认 `7791`。
- `--open-browser`：启动后自动打开浏览器。

### 2.3 打包版运行

Ubuntu 打包输出目录通常为：

```text
tool_hub_app/tool_hub_web/dist/RY-Robot-Tool-Hub/
```

运行：

```bash
cd <repo>/tool_hub_app/tool_hub_web/dist/RY-Robot-Tool-Hub
./RY-Robot-Tool-Hub
```

如果端口被占用：

```bash
./RY-Robot-Tool-Hub --port 7792
```

Windows 下运行：

```bat
RY-Robot-Tool-Hub.exe
```

注意：打包产物是整个 `RY-Robot-Tool-Hub` 文件夹，不要只拷贝单个可执行文件。

## 3. 通用文件概念

### 3.1 地图文件

地图使用 ROS 2D map 常见结构：

```text
map.yaml
map.pgm
```

`map.yaml` 中的关键字段：

- `image`：对应 `.pgm` 图片文件。
- `resolution`：分辨率，单位通常为米/像素。
- `origin`：建图原点，通常为 `[x, y, yaw]`。

路径编辑器、任务编辑器和虚拟墙编辑器都会使用 `origin` 和 `resolution` 做坐标转换。

### 3.2 路径文件

路径文件通常为 JSON，保存几何路径、地图路径和楼栋/楼层等元数据。`Path Editor` 会编辑这类文件。

### 3.3 任务组文件

任务组文件通常为 JSON，是下游任务执行使用的文件。常见结构包含：

- `task_group_name`
- `subtasks`
- `subtask_name`
- `waypoints`
- `map_url`
- `change_loc`
- `speed_mode`
- `waypoint_task_id`

### 3.4 工作区文件

工作区文件是工具内部用于保存中间状态的 JSON，不直接参与机器人运行。

常见形式：

```text
xxx.workspace.json
```

用途：

- 保存从路径生成的去程/返程子任务对。
- 记录当前任务组选择顺序。
- 支持浏览器关闭后恢复。
- 支持任务编辑器反向同步。
- 支持 `Task Group Mixer` 跨任务组混编。

### 3.5 旁路文件

旁路文件是任务组 JSON 的同名工作区文件，例如：

```text
delivery_demo.json
delivery_demo.workspace.json
```

用途：

- 不参与下游任务执行。
- 记录任务组和子任务对之间的关系。
- 允许任务组编辑后继续拆解、重组和混编。

### 3.6 路点任务 XML

路点任务 XML 位于 `waypoint_tasks/` 目录，表示路点执行语义，例如开门、等待、电梯进出、状态切换等。

### 3.7 速度模式

速度模式通常从以下目录读取：

```text
waypoints_attributes/speed_modes/
waypoints_attributes/speed_modes/single_point/
```

普通路点读取 `speed_modes/`，单点路点读取 `speed_modes/single_point/`。

### 3.8 虚拟墙 YAML

`Virtual Wall Builder` 输出旧 `VirtualWallManager` 兼容 YAML。推荐输出格式：

```yaml
virtual_walls:
  coordinate_mode: image_relative
  frame_id: map
  map_origin: [0.0, 0.0, 0.0]
  thickness: 0.1
  segments:
    - start: [1.0, 2.0, 0.0]
      end: [3.0, 2.0, 0.0]
      thickness: 0.1
```

其中 `segments` 中的点是相对地图建图原点的坐标。

## 4. Hub 首页

入口：

```text
/
```

用途：

- 作为所有工具的集中导航页。
- 每个卡片对应一个工具模块。
- 每个模块页面顶部都有“返回导航页”快捷入口。

使用方式：

1. 启动 Tool Hub。
2. 浏览器打开 `http://127.0.0.1:7791/`。
3. 点击对应工具卡片的“进入工具”。

注意事项：

- 如果从打包版启动，所有页面仍通过浏览器访问。
- 如果端口被占用，请使用 `--port` 改端口。

## 5. Path Editor

入口：

```text
/path-editor
```

用途：

- 加载地图。
- 新建、打开、编辑、保存路径 JSON。
- 在地图上绘制路径点。
- 从单个路径生成去程/返程子任务对。
- 将子任务对加入任务组工作区。

### 5.1 基本操作

顶部区域提供：

- `新建`：创建新路径文档。
- `加载地图`：加载 2D 地图。
- `保存`：覆盖保存当前路径文件。
- `另存为`：保存到新路径。
- `返回导航页`：回到 Tool Hub 首页。
- `收起`：折叠顶部栏，给地图画布留出更多空间。

### 5.2 路径编辑工具

工具栏包含：

- `选择`：选择已有点或路径元素。
- `加点`：在地图上新增路径点。
- `插点`：在已有两点之间插入新路径点。
- `移点`：拖动已有点修改位置。
- `调朝向`：调整路径点 yaw。
- `删点`：删除路径点。

地图交互：

- 鼠标滚轮缩放。
- 右键或中键拖动平移。
- 地图上显示 2D map 的建图原点。
- 绘制或移动点时可参考辅助线。

### 5.3 路径属性

路径属性面板包含：

- `path_name`
- `community`
- `building`
- `unit`
- `floor`
- `door`
- `point_interval`
- `map_url`
- `pcd_url`

这些字段会进入路径文件，并用于后续生成子任务。

### 5.4 生成子任务对

右侧 `Subtask Builder` 面板用于从路径生成任务子任务。

典型步骤：

1. 在 `工作区文件` 输入一个绝对路径，例如：

   ```text
   /home/lmy/data/tasks/demo.workspace.json
   ```

2. 打开一个路径 JSON。
3. 点击 `生成子任务对`。
4. 工具会生成：

   - 去程子任务。
   - 返程子任务。

5. 点击 `生成工作区文件` 创建工作区文件。
6. 点击 `加入工作区` 将子任务对追加到工作区。
7. 如果路径修改后重新生成，可以点击 `替换同源对子任务`。

### 5.5 跳转任务组页面

生成子任务对后，可以跳转到：

- `Task Group Builder`：整理同一工作区中的子任务。
- `Task Group Mixer`：跨工作区混编子任务。

### 5.6 输出文件

主要输出：

- 路径 JSON。
- 工作区 JSON。
- 由后续 `Task Group Builder` 导出的任务组 JSON。

注意事项：

- 单个路径文件对应一个去程子任务和一个返程子任务。
- 工作区文件由用户指定位置，便于项目迁移。
- 修改路径后不会自动刷新工作区，需要手动重新生成并替换。

## 6. Task Group Builder

入口：

```text
/task-groups
```

用途：

- 加载单个工作区文件。
- 从工作区中选择子任务组成任务组。
- 调整子任务顺序。
- 修改任务组名称和子任务名称。
- 导出最终任务组 JSON。

### 6.1 加载工作区

输入：

```text
/abs/path/to/task-group-workspace.json
```

点击：

```text
加载工作区
```

页面会显示：

- `全部子任务`
- `当前任务组`

### 6.2 选择与排序

在 `全部子任务` 中添加需要的子任务到 `当前任务组`。

在 `当前任务组` 中可以：

- 移除子任务。
- 上移或下移子任务。
- 修改子任务名称。
- 清空当前任务组。

### 6.3 导出任务组

需要填写：

- `任务组名称`
- `输出目录`

点击：

```text
导出任务组
```

保存文件名规则：

```text
任务组名称.json
```

例如任务组名称为 `delivery_demo`，输出文件为：

```text
delivery_demo.json
```

注意事项：

- 输出目录必须是绝对路径。
- 工作区文件会保存中间状态。
- 导出的任务组 JSON 是下游运行使用的文件。

## 7. Task Group Mixer

入口：

```text
/task-group-mixer
```

用途：

- 创建一个独立混编工作区。
- 导入多个 `*.workspace.json` 旁路文件。
- 从不同任务组中自由组合子任务对。
- 导出新的任务组 JSON。

### 7.1 创建或加载混编工作区

输入：

```text
/abs/path/to/mixer.json
```

点击：

```text
加载/创建
```

如果文件不存在，会创建新的混编工作区。

### 7.2 导入来源旁路文件

输入来源文件：

```text
/abs/path/to/source.workspace.json
```

点击：

```text
导入/替换
```

页面会把来源子任务复制到混编工作区，并记录来源路径。

如果再次导入同一个来源，会执行“替换”，避免旧版本和新版本同时存在。

### 7.3 混编任务组

页面区域：

- `来源列表`：显示已导入的工作区来源。
- `来源子任务池`：显示当前来源中的可选子任务。
- `当前混编结果`：显示最终任务组选择结果。

操作：

- 从来源子任务池添加子任务。
- 从当前结果移除子任务。
- 调整当前结果顺序。
- 修改最终任务组名称。

### 7.4 导出

填写：

- `任务组名称`
- `输出目录`

点击：

```text
导出任务组
```

输出：

```text
任务组名称.json
```

注意事项：

- `Task Group Mixer` 适合跨多个任务组复用子任务。
- 导入文件必须是旁路 `*.workspace.json`，不要直接导入普通任务组 JSON。
- 混编工作区也是用户指定位置的 JSON 文件，可以长期保存。

## 8. Task Editor

入口：

```text
/task-editor
```

用途：

- 编辑已生成任务组 JSON。
- 修改子任务 `change_loc`。
- 修改路点 `speed_mode`。
- 修改路点 `waypoint_task_id`。
- 修改 `is_task_point` 和 `is_single_point`。
- 保存时同步更新同名旁路文件。

### 8.1 加载任务

输入任务 JSON 绝对路径，或点击 `浏览` 选择任务文件。

点击：

```text
加载
```

加载时会检查同目录下是否有同名旁路文件：

```text
demo.json
demo.workspace.json
```

如果没有旁路文件，可以点击：

```text
生成旁路
```

保存时也会自动补建旁路文件。

### 8.2 属性目录配置

左侧可折叠栏可设置：

- `waypoint_tasks` 绝对路径。
- `speed_modes` 绝对路径。

设置后点击：

```text
刷新属性
```

用途：

- 路点任务下拉/自动补全从 `waypoint_tasks` 读取。
- 普通速度模式从 `speed_modes` 读取。
- 单点速度模式从 `speed_modes/single_point` 读取。

### 8.3 切换子任务

顶部 Tab 显示任务组内的子任务。

点击子任务 Tab 后：

- 地图自动加载该子任务的 `map_url`。
- 当前子任务的路点显示在地图上。
- 右侧属性栏显示当前子任务属性。

### 8.4 编辑子任务属性

当前支持：

- `change_loc`：是否在执行该子任务前切换定位。

勾选后会自动更新当前子任务。

### 8.5 编辑路点属性

点击地图上的路点或右侧列表中的路点后，可编辑：

- `speed_mode`
- `waypoint_task_id`
- `is_task_point`
- `is_single_point`

说明：

- 勾选 `is_task_point` 后，`waypoint_task_id` 可编辑。
- 勾选 `is_single_point` 后，速度模式下拉切换到 `single_point` 目录。
- 点击 `应用` 保存当前路点修改。
- 点击 `翻转朝向 180°` 可反转当前路点朝向。

### 8.6 批量修改速度模式

在路点列表中勾选多个路点。

底部批量操作栏中选择目标 `speed_mode`，点击：

```text
应用
```

可以一次更新多个路点。

### 8.7 保存

点击：

```text
保存
```

会同时执行：

- 覆盖原任务组 JSON。
- 同步更新同名旁路 `*.workspace.json`。

注意事项：

- 旁路文件不参与机器人运行，但会保留可逆关系。
- 编辑任务组后建议保留旁路文件，方便后续混编。

## 9. Waypoint Task Builder

入口：

```text
/waypoint-task-builder
```

用途：

- 通过可视化树结构编辑路点任务 XML。
- 从节点库拖放节点组成行为树。
- 编辑节点参数。
- 支持 XML 预览。
- 支持从 XML 文本反向还原树结构。

### 9.1 加载 XML

输入：

```text
/abs/path/to/task.xml
```

点击：

```text
加载
```

也可以点击 `浏览文件` 选择 XML。

### 9.2 新建 XML

点击：

```text
新建
```

然后在保存区域填写：

- 输出目录。
- 任务名称。

### 9.3 节点库

节点库从 `nav2_tree_nodes.xml` 读取，并识别节点输入/输出端口。

常见节点类型包括：

- 控制节点，例如 `Sequence`、`Fallback`。
- 动作节点，例如等待、切换地图、状态切换、电梯相关动作等。

具体节点以当前工程的 `nav2_tree_nodes.xml` 为准。

### 9.4 树结构编辑

操作：

- 从节点库拖动节点到树结构中。
- 点击树节点进行选择。
- 在节点参数栏修改字段。
- 使用移动/删除类操作调整结构。
- 点击 `清空树` 清除当前树结构。

### 9.5 XML 预览和反向导入

右侧 XML 区域显示当前树结构生成的 XML。

也可以在 XML 框中粘贴 XML 内容，然后点击：

```text
从 XML 还原
```

系统会解析 XML 并显示为树结构。

### 9.6 保存

填写：

- `保存目录`
- `任务名称`

点击：

```text
保存 XML
```

输出：

```text
任务名称.xml
```

注意事项：

- 本工具不依赖 BehaviorTree.CPP 运行库，只面向当前项目 XML 流程。
- 如果 XML 中有未支持节点，需先确认 `nav2_tree_nodes.xml` 中是否存在该节点定义。

## 10. Task Batch Generator

入口：

```text
/task-batch-generator
```

用途：

- 从样本目录识别任务模板对。
- 批量生成不同楼层的任务组 JSON。
- 保持原有 `origin_tasks` 批量生成逻辑。

### 10.1 输入

需要填写：

- `样本目录`：包含模板任务 JSON 的目录。
- `输出目录`：生成文件保存目录。
- `起始楼层`
- `结束楼层`
- `源楼层`：可留空自动识别，也可手动指定。
- `overwrite`：是否覆盖已有文件。

### 10.2 扫描样本对

点击：

```text
扫描样本对
```

页面会显示识别到的模板对。

常见模板对命名和内部关联基于现有任务文件规律，例如 `01 / 03` 或 `n01 / n03` 样本对。

### 10.3 预览生成

选择样本对后，点击：

```text
预览生成
```

页面会列出将要生成的文件和字段替换结果。

### 10.4 开始生成

确认预览后点击：

```text
开始生成
```

输出为任务组 JSON 文件。

注意事项：

- 建议先预览，再生成。
- 如果输出目录已有同名文件且未勾选 `overwrite`，会拒绝覆盖。
- 源楼层如果自动识别失败，可手动指定。

## 11. Task Attribute Batch Generator

入口：

```text
/task-attribute-batch-generator
```

用途：

- 在原有任务 JSON 批量生成之外，批量生成路点任务属性 XML。
- 适合批量派生电梯门控、进出电梯、楼层变化相关 XML。

### 11.1 输入

需要填写：

- `参考任务文件`：一个真实任务组 JSON，用于确定任务内部关联和楼层信息。
- `样本属性 XML`：一个已有的 waypoint task XML 模板。
- `输出目录`
- `起始楼层`
- `结束楼层`
- `overwrite`

### 11.2 浏览文件

页面提供：

- `浏览任务文件`
- `浏览属性 XML`
- `浏览输出目录`

### 11.3 预览生成

点击：

```text
预览生成
```

页面会显示：

- 识别结果。
- 将生成的文件名。
- 内部字段替换情况。

### 11.4 开始生成

确认预览后点击：

```text
开始生成
```

输出为 XML 文件。

注意事项：

- 模板类型不同，内部字段替换规则可能不同。
- `elevator_out_A_B` 等格式存在不同变体，工具会根据参考任务和模板识别。
- 如果提示模板和参考任务楼层不匹配，需要检查源楼层、目标楼层和样本 XML 是否对应。

## 12. PCD to 2D Map

入口：

```text
/pcd-to-map
```

用途：

- 读取 `.pcd` 点云文件。
- 按原 `pcd2pgm` 算法链路生成 2D 占据栅格。
- 一次预览多个高度范围切片。
- 选择满意切片后导出 `map.pgm` 和 `map.yaml`。

### 12.1 算法链路

该功能对齐原 `pcd2pgm` 功能包：

- 根据 `odom_to_lidar_odom` 对点云做逆变换。
- 按 `Z min / Z max` 做 PassThrough 高度切片。
- 根据 `flag_pass_through` 决定保留范围内点或反选范围外点。
- 按 `thre_radius` 和 `thres_point_count` 做半径离群滤波。
- 以过滤后点云的 `x_min / y_min` 作为地图 `origin`。
- 按 `map_resolution` 投影到 XY 栅格。
- 命中点的栅格作为占用区域导出。

### 12.2 基本参数

输入：

- `PCD 文件`：绝对路径，例如 `/opt/ry/maps/demo/map.pcd`。
- `输出目录`：生成 `pgm/yaml` 的目录。
- `地图名称`：导出文件名前缀，例如 `map` 会生成 `map.pgm` 和 `map.yaml`。
- `分辨率 map_resolution`：默认 `0.05`。
- `半径 thre_radius`：半径离群滤波半径。
- `邻居数 thres_point_count`：半径内最少点数。
- `flag_pass_through`：勾选后反选高度范围。
- `odom_to_lidar_odom`：`x,y,z,roll,pitch,yaw` 六个数。

### 12.3 预览高度切片

在 `高度切片范围` 中添加多个 `Z min / Z max`。

点击：

```text
生成预览
```

页面会显示每个切片的：

- 预览图。
- 点数。
- 地图宽高。
- 分辨率。
- 地图原点 `origin`。

点击某个预览卡片即可选中该切片。

### 12.4 导出地图

选中预览切片后点击：

```text
导出选中切片
```

输出：

```text
<地图名称>.pgm
<地图名称>.yaml
```

`yaml` 中的 `origin` 使用过滤后点云的最小 `x/y`，与原 `pcd2pgm` 生成 `OccupancyGrid` 的规则一致。

注意事项：

- 当前支持常见 `ascii`、`binary` 和 PCL `binary_compressed` PCD。
- 点云很大时，预览多个切片会耗时，建议先用 2 到 3 个候选高度范围。
- 导出的地图可直接用于 Path Editor 或 Virtual Wall Builder 加载。

## 13. Virtual Wall Builder

入口：

```text
/virtual-wall-builder
```

用途：

- 脱离 RViz 绘制虚拟墙。
- 加载 2D map YAML。
- 在网页画布中绘制、选择、移动、插点和删除虚拟墙。
- 导出旧 `VirtualWallManager` 可直接加载的 YAML。

### 13.1 加载地图

展开 `地图文件` 面板。

输入：

```text
/abs/path/to/map.yaml
```

点击：

```text
加载地图
```

地图加载后会显示：

- 2D 地图图像。
- 地图建图原点。
- 辅助网格。

### 13.2 虚拟墙文件

展开 `虚拟墙文件` 面板。

输入：

```text
/abs/path/to/virtual_walls.yaml
```

可点击：

- `加载墙文件`
- `保存墙文件`

加载支持：

- `coordinate_mode: image_relative` 的 `segments` 格式。
- 旧版 `walls[].points` 多点格式。
- 旧版 `segments[].start/end` 格式。

保存默认输出：

```text
image_relative / segments
```

### 13.3 选择模式

默认进入选择模式。

选择模式用途：

- 点击已有墙，选中整条墙。
- 点击已有点，选中该点。
- 拖动已有点，移动点位置。
- 点击 `删除选中点` 删除当前点。
- 点击 `删除选中墙` 删除整条墙。
- 按 `Delete` 优先删除选中点；如果没有选中点，则删除选中墙。

选择模式不会新增点，因此适合检查和微调。

### 13.4 绘制模式

点击：

```text
绘制模式
```

绘制模式用途：

- 点击空白地图，新增当前墙的路径点。
- 点击已有墙线段附近，在线段中插入新点。
- 双击或按 `Enter` 完成当前墙。
- `Backspace` 撤销当前未完成墙的最后一个点。
- `Escape` 取消当前未完成墙。

### 13.5 通用地图操作

- 鼠标滚轮：缩放。
- 鼠标右键拖动：平移。
- `完成当前墙`：结束当前正在绘制的墙。
- `撤销点`：撤销当前未完成墙的最后一个点。
- `撤销墙`：删除最后一条墙。
- `清空`：清空所有墙和草稿。

### 13.6 输出格式说明

保存时会把世界坐标减去地图 YAML 的建图原点，生成 `image_relative` 坐标。

示例：

```yaml
virtual_walls:
  coordinate_mode: image_relative
  frame_id: map
  map_origin: [10.0, -3.0, 0.0]
  thickness: 0.1
  segments:
    - start: [1.25, 0.5, 0.0]
      end: [2.25, 1.0, 0.0]
      thickness: 0.1
```

旧 `VirtualWallManager` 加载时会再加当前地图原点，恢复到世界坐标。

注意事项：

- 这里的原点是 2D map 的建图原点，不是像素左上角。
- 保存前必须加载地图，否则无法确定 `map_origin`。
- 一条墙至少需要 2 个点；删除点导致不足 2 点时，会自动删除整条墙。

## 14. 打包与移交

### 14.1 Ubuntu 打包

```bash
cd <repo>/tool_hub_app/tool_hub_web
bash build_linux.sh
```

输出：

```text
dist/RY-Robot-Tool-Hub/
```

### 14.2 Windows 打包

在 Windows 环境中执行：

```bat
cd tool_hub_app\tool_hub_web
build_windows.bat
```

输出：

```text
dist\RY-Robot-Tool-Hub\
```

### 14.3 移交时需要包含

如果移交源码：

- `tool_hub_web/`
- `path_editor_web/`
- `task_editor/`
- `runtime_paths.py`
- `task_execute_server/waypoints_attributes/`
- `tool_hub_app/nav2_behavior_tree/nav2_tree_nodes.xml`

如果移交打包版：

- 整个 `dist/RY-Robot-Tool-Hub/` 目录。
- 外部业务数据目录，例如地图、路径、任务、路点任务 XML、速度模式等。

### 14.4 常见问题

端口占用：

```text
Address already in use
Port 7791 is in use
```

解决：

```bash
./RY-Robot-Tool-Hub --port 7792
```

找不到文件：

- 检查是否使用绝对路径。
- 检查启动时 `--paths-root`、`--maps-root`、`--tasks-root` 是否指向正确目录。
- 打包版不要只拷贝单个可执行文件。

下拉框没有选项：

- 检查 `waypoint_tasks` 和 `speed_modes` 路径。
- 单点速度模式需要放在 `speed_modes/single_point/`。
- 修改路径后在 Task Editor 中点击 `刷新属性`。

虚拟墙坐标不对：

- 确认加载的是正确的地图 YAML。
- 确认 YAML 中 `origin` 是目标地图的建图原点。
- 不要把像素原点当成地图原点。

## 15. 建议使用习惯

- 路径修改后，手动重新生成子任务对，并替换工作区中的同源子任务对。
- 任务组 JSON 和同名 `*.workspace.json` 建议一起保存。
- 批量生成前先预览。
- Task Editor 保存后检查旁路文件是否同步更新。
- Virtual Wall Builder 默认使用选择模式，需要新增点时再切换绘制模式。
- 打包移交时保留本文档，方便现场人员快速上手。
