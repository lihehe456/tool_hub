# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


spec_dir = Path(SPECPATH).resolve()
package_root = spec_dir.parent
cpp_binary = package_root / "tool_hub_web" / "bin" / "outdoor_pcd_to_pgm"
chunker_binary = package_root / "tool_hub_web" / "bin" / "pcd_chunker"

datas = [
    (str(package_root / "tool_hub_web" / "static"), "tool_hub_web/static"),
    (str(package_root / "tool_hub_web" / "loc_configs"), "tool_hub_web/loc_configs"),
    (str(package_root / "path_editor_web" / "static"), "path_editor_web/static"),
    (str(package_root / "task_editor" / "static"), "task_editor/static"),
    (str(package_root / "task_execute_server" / "waypoints_attributes"), "task_execute_server/waypoints_attributes"),
    (str(package_root / "nav2_behavior_tree" / "nav2_tree_nodes.xml"), "nav2_behavior_tree"),
]

binaries = []
if cpp_binary.is_file():
    binaries.append((str(cpp_binary), "tool_hub_web/bin"))
if chunker_binary.is_file():
    binaries.append((str(chunker_binary), "tool_hub_web/bin"))

a = Analysis(
    [str(package_root / "tool_hub_web" / "launcher.py")],
    pathex=[str(package_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "path_editor_web.server",
        "path_editor_web.task_group_builder",
        "task_editor.server",
        "tool_hub_web.pcd_to_map",
        "tool_hub_web.outdoor_pcd_to_pgm",
        "tool_hub_web.server",
        "tool_hub_web.virtual_wall_builder",
        "tool_hub_web.waypoint_task_builder",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RY-Robot-Tool-Hub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RY-Robot-Tool-Hub",
)
