# Task Editor

基于 Web 的任务路点编排工具，用于快速编辑 FusionCloudRobot 任务 JSON 文件。

## 启动

```bash
cd tool_hub_app/task_editor
python3 server.py
```

浏览器打开 http://127.0.0.1:7788

## 依赖

```bash
pip3 install flask pyyaml
```

## 文件结构

```
task_editor/
├── server.py        # Flask 后端
├── static/
│   └── index.html   # 前端单页应用
└── README.md
```

## 使用流程

### 1. 加载任务

- 点击「浏览」按钮，在文件选择器中导航到任务 JSON 文件（蓝色高亮）并点击
- 或直接在输入框填入绝对路径，点击「加载」
- 加载时会同时检查同目录下是否存在同名旁路文件：
  - 任务组：`demo.json`
  - 旁路文件：`demo.workspace.json`

### 2. 切换子任务

顶部 Tab 栏显示任务组内所有子任务（最多 6 个），点击切换：
- 自动加载对应地图（读取子任务的 `map_url` 字段）
- 地图为 `.yaml` + `.pgm` 格式，origin/resolution 自动解析用于坐标转换
- 右侧“当前子任务属性”区域会同步显示该子任务的 `change_loc`

### 3. 地图交互

| 操作 | 功能 |
|------|------|
| 滚轮 | 缩放 |
| 右键/中键拖拽 | 平移 |
| 左键点击路点 | 选中路点 |

### 4. 编辑单个路点

点击地图上的路点圆点或右侧列表中的路点，右侧面板显示编辑表单：

子任务级属性：
- **change_loc**：是否在执行该子任务前切换定位

路点级属性：

- **speed_mode**：下拉选择
  - 普通路点：从 `speed_modes/` 目录读取
  - 勾选 `is_single_point` 后：自动切换为 `speed_modes/single_point/` 目录下的选项
- **waypoint_task_id**：带自动补全（从 `waypoint_tasks/` 目录读取），仅在勾选 `is_task_point` 后可编辑
- **is_task_point**：是否为任务执行点
- **is_single_point**：是否为单点导航

点击「应用」保存修改。

### 5. 批量修改 speed_mode

在路点列表中勾选多个路点的复选框（或点击「全选」），底部出现批量操作栏：
- 选择目标 speed_mode，点击「应用」批量更新
- 点击「清除选择」取消所有勾选

### 6. 保存

点击顶部「保存」按钮，会同时执行两件事：

- 覆盖写回原任务组 JSON 文件
- 同步更新同名旁路 `*.workspace.json`

如果当前任务组还没有旁路文件，可以先点击顶部「生成旁路」按钮创建；如果直接保存，系统也会自动补建旁路文件。

## 旁路文件用途

旁路文件不参与下游任务执行，只用于保留任务组和子任务对之间的可逆关系，方便后续：

- 从已生成任务组反向拆解回子任务对
- 在 `path_editor_web` 的 `Task Group Builder` 中继续重组
- 在编辑任务组语义字段后同步更新子任务快照

## 路点颜色说明

| 颜色 | 含义 |
|------|------|
| 蓝色 | high_speed |
| 绿色 | normal / low_speed |
| 黄色 | task_point / single_point |
| 紫色 | elevator_in |
| 橙色 | backward |
| 红色 | 当前选中 |
| 橙黄色 | 批量选中 |

## 属性文件夹

速度模式和路点任务选项从以下路径自动读取（文件名即选项名）：

```
task_execute_server/waypoints_attributes/
├── speed_modes/          # 普通速度模式
│   └── single_point/     # 单点速度模式
└── waypoint_tasks/       # 路点任务
```
