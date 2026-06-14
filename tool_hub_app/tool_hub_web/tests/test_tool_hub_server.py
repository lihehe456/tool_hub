import pytest

from tool_hub_web.server import create_app


@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


def test_hub_home_and_tool_routes_are_available(client):
    home = client.get("/")
    path_editor = client.get("/path-editor")
    task_groups = client.get("/task-groups")
    mixer = client.get("/task-group-mixer")
    task_editor = client.get("/task-editor")
    waypoint_task_builder = client.get("/waypoint-task-builder")
    task_batch_generator = client.get("/task-batch-generator")
    task_attribute_batch_generator = client.get("/task-attribute-batch-generator")
    virtual_wall_builder = client.get("/virtual-wall-builder")

    assert home.status_code == 200
    assert b"RY-Robot Tool Hub" in home.data
    assert b"Waypoint Task Builder" in home.data
    assert b"Task Batch Generator" in home.data
    assert b"Task Attribute Batch Generator" in home.data
    assert b"Virtual Wall Builder" in home.data
    assert path_editor.status_code == 200
    assert b"Path Editor Web" in path_editor.data
    assert task_groups.status_code == 200
    assert mixer.status_code == 200
    assert task_editor.status_code == 200
    assert b"Task Editor" in task_editor.data
    assert waypoint_task_builder.status_code == 200
    assert b"/home/lmy/LMY/2_Source/path_task/waypoints_attributes/waypoint_tasks" not in waypoint_task_builder.data
    assert task_batch_generator.status_code == 200
    assert b"Task Batch Generator" in task_batch_generator.data
    assert task_attribute_batch_generator.status_code == 200
    assert b"Task Attribute Batch Generator" in task_attribute_batch_generator.data
    assert virtual_wall_builder.status_code == 200
    assert b"Virtual Wall Builder" in virtual_wall_builder.data


def test_waypoint_task_builder_runtime_config_exposes_current_root(client, tmp_path):
    app = client.application
    app.config["WAYPOINT_TASKS_ROOT"] = str(tmp_path / "waypoint_tasks")
    response = client.get("/waypoint-task-builder/api/runtime_config")

    assert response.status_code == 200
    assert response.get_json()["waypoint_tasks_root"] == str(tmp_path / "waypoint_tasks")


def test_task_editor_api_is_mounted_under_prefixed_route(client, tmp_path):
    task_path = tmp_path / "demo.json"
    task_path.write_text('{"task_group_name":"demo","subtasks":[]}', encoding="utf-8")

    response = client.post(
        "/task-editor/api/load_task_bundle",
        json={"path": str(task_path)},
    )

    assert response.status_code == 200
    assert response.get_json()["task"]["task_group_name"] == "demo"


def test_task_editor_runtime_config_is_available_under_hub_mount(client):
    response = client.get("/task-editor/api/runtime_config")
    payload = response.get_json()

    assert response.status_code == 200
    assert "default_waypoint_tasks_path" in payload
    assert "default_speed_modes_path" in payload
    assert payload["default_browse_root"] == "/opt/ry"


@pytest.mark.parametrize(
    ("endpoint", "field"),
    [
        ("/waypoint-task-builder/api/runtime_config", "waypoint_tasks_root"),
        ("/task-batch-generator/api/runtime_config", "default_root"),
        ("/task-attribute-batch-generator/api/runtime_config", "default_root"),
        ("/virtual-wall-builder/api/runtime_config", "default_root"),
    ],
)
def test_tool_runtime_configs_default_to_opt_ry(client, endpoint, field):
    response = client.get(endpoint)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload[field] == "/opt/ry"


def test_virtual_wall_builder_save_and_load_apis(client, tmp_path):
    wall_path = tmp_path / "virtual_walls.yaml"

    save_response = client.post(
        "/virtual-wall-builder/api/save",
        json={
            "path": str(wall_path),
            "map_origin": [5.0, -1.0, 0.0],
            "polylines": [
                {
                    "points": [
                        {"x": 6.0, "y": 1.0, "z": 0.0},
                        {"x": 8.0, "y": 1.0, "z": 0.0},
                    ],
                    "thickness": 0.12,
                }
            ],
        },
    )
    load_response = client.post(
        "/virtual-wall-builder/api/load",
        json={"path": str(wall_path), "current_map_origin": [10.0, 10.0, 0.0]},
    )

    assert save_response.status_code == 200
    assert save_response.get_json()["path"] == str(wall_path)
    assert load_response.status_code == 200
    assert load_response.get_json()["document"]["polylines"][0]["points"] == [
        {"x": 11.0, "y": 12.0, "z": 0.0},
        {"x": 13.0, "y": 12.0, "z": 0.0},
    ]


def test_virtual_wall_builder_canvas_does_not_depend_on_wall_list_height(client):
    response = client.get("/virtual-wall-builder")

    assert response.status_code == 200
    assert b"<details class=\"wall-collapsible\"" in response.data
    assert b"id=\"map-files-panel\"" in response.data
    assert b"id=\"wall-files-panel\"" in response.data


@pytest.mark.parametrize(
    "endpoint",
    [
        "/virtual-wall-builder/api/browse",
        "/waypoint-task-builder/api/browse",
        "/task-batch-generator/api/browse",
        "/task-attribute-batch-generator/api/browse",
    ],
)
def test_tool_browsers_allow_root_directory(client, endpoint):
    response = client.post(endpoint, json={"path": "/"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["cwd"] == "/"


def test_waypoint_task_builder_schema_and_load_save_apis(client, tmp_path):
    tasks_dir = tmp_path / "waypoint_tasks"
    tasks_dir.mkdir()
    sample_path = tasks_dir / "demo_task.xml"
    sample_path.write_text(
        """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence name="Demo">
      <ChangeUssStatus status="true"/>
    </Sequence>
  </BehaviorTree>
</root>
""".strip(),
        encoding="utf-8",
    )
    app = client.application
    app.config["WAYPOINT_TASKS_ROOT"] = str(tasks_dir)

    schema_response = client.get("/waypoint-task-builder/api/schema")
    browse_response = client.post("/waypoint-task-builder/api/browse", json={"path": str(tasks_dir)})
    load_response = client.post("/waypoint-task-builder/api/load", json={"path": str(sample_path)})
    save_response = client.post(
        "/waypoint-task-builder/api/save",
        json={
            "directory": str(tasks_dir),
            "task_name": "saved_task",
            "document": {
                "task_name": "saved_task",
                "tree": {
                    "type": "Sequence",
                    "attrs": {"name": "Saved"},
                    "children": [
                        {"type": "Wait", "attrs": {"wait_duration": "2"}, "children": []},
                    ],
                },
            },
        },
    )
    parse_response = client.post(
        "/waypoint-task-builder/api/parse_xml",
        json={
            "task_name": "parsed_task",
            "xml_text": """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence name="Parsed">
      <Wait wait_duration="3"/>
    </Sequence>
  </BehaviorTree>
</root>
""".strip(),
        },
    )

    assert schema_response.status_code == 200
    assert "Sequence" in schema_response.get_json()["nodes"]
    assert schema_response.get_json()["nodes"]["Wait"]["input_ports"][0]["name"] == "wait_duration"
    assert schema_response.get_json()["nodes"]["SetPoseFromOdom"]["output_ports"][0]["name"] == "pose"
    assert browse_response.status_code == 200
    assert any(entry["name"] == "demo_task.xml" and entry["is_xml"] for entry in browse_response.get_json()["entries"])
    assert load_response.status_code == 200
    assert load_response.get_json()["document"]["tree"]["children"][0]["type"] == "ChangeUssStatus"
    assert save_response.status_code == 200
    assert parse_response.status_code == 200
    assert parse_response.get_json()["document"]["tree"]["children"][0]["type"] == "Wait"
    assert (tasks_dir / "saved_task.xml").exists()


def test_waypoint_task_builder_save_rejects_empty_tree(client, tmp_path):
    response = client.post(
        "/waypoint-task-builder/api/save",
        json={
            "directory": str(tmp_path),
            "task_name": "empty_task",
            "document": {
                "task_name": "empty_task",
                "tree": None,
            },
        },
    )

    assert response.status_code == 400
    assert "empty" in response.get_json()["error"].lower()


def test_task_batch_generator_scan_preview_and_generate_apis(client, tmp_path):
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    template_01 = template_dir / "A_5_501.json"
    template_03 = template_dir / "A_5_503.json"
    template_01.write_text(
        """
{
  "task_group_name": "A_5_501",
  "subtasks": [
    {
      "subtask_name": "main_road",
      "waypoints": [
        {"waypoint_id": "p0", "waypoint_task_id": "demo_elevator_out_3_5"}
      ]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    template_03.write_text(
        """
{
  "task_group_name": "A_5_503",
  "subtasks": [
    {
      "subtask_name": "main_road_r",
      "waypoints": [
        {"waypoint_id": "p0", "waypoint_task_id": "demo_elevator_in_5_3"}
      ]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    scan_response = client.post(
        "/task-batch-generator/api/scan",
        json={"directory": str(template_dir)},
    )
    scan_payload = scan_response.get_json()

    preview_response = client.post(
        "/task-batch-generator/api/preview",
        json={
            "template_01": str(template_01),
            "template_03": str(template_03),
            "start": 8,
            "end": 8,
            "output_dir": str(output_dir),
            "elevator_floor": 3,
        },
    )
    preview_payload = preview_response.get_json()

    generate_response = client.post(
        "/task-batch-generator/api/generate",
        json={
            "template_01": str(template_01),
            "template_03": str(template_03),
            "start": 8,
            "end": 8,
            "output_dir": str(output_dir),
            "elevator_floor": 3,
            "overwrite": True,
        },
    )
    generate_payload = generate_response.get_json()

    assert scan_response.status_code == 200
    assert len(scan_payload["pairs"]) == 1
    assert scan_payload["pairs"][0]["template_01_path"] == str(template_01)
    assert scan_payload["pairs"][0]["source_floor"] == 3
    assert preview_response.status_code == 200
    assert preview_payload["generated_files"][0]["output_name"] == "A_8_801"
    assert generate_response.status_code == 200
    assert len(generate_payload["created_files"]) == 2
    assert (output_dir / "A_8_801.json").exists()


def test_task_attribute_batch_generator_preview_and_generate_apis(client, tmp_path):
    task_path = tmp_path / "demo_10_1001.json"
    xml_dir = tmp_path / "waypoint_tasks"
    xml_dir.mkdir()
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    xml_path = xml_dir / "demo_elevator_out_3_10.xml"

    task_path.write_text(
        """
{
  "task_group_name": "demo_10_1001",
  "subtasks": [
    {
      "subtask_name": "main_road",
      "waypoints": [
        {"waypoint_task_id": "demo_elevator_in_3_x"},
        {"waypoint_task_id": "demo_elevator_out_3_10"}
      ]
    },
    {
      "subtask_name": "elevator_hall",
      "waypoints": [
        {"waypoint_task_id": "demo_close_elevdoor_10"}
      ]
    },
    {
      "subtask_name": "elevator_hall_r",
      "waypoints": [
        {"waypoint_task_id": "demo_elevator_in_10_3"},
        {"waypoint_task_id": "demo_elevator_out_10_3"}
      ]
    },
    {
      "subtask_name": "main_road_r",
      "waypoints": [
        {"waypoint_task_id": "demo_close_elevdoor_3"}
      ]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    xml_path.write_text(
        """
<root>
  <BehaviorTree ID="MainTree">
    <Sequence name="Out">
      <ElevatorDoorKeeper command="3-"/>
      <ElevatorCaller elevid="{elevator_id}" target_floor="10"/>
      <ElevatorDoorKeeper command="10+"/>
    </Sequence>
  </BehaviorTree>
</root>
""".strip(),
        encoding="utf-8",
    )

    runtime_response = client.get("/task-attribute-batch-generator/api/runtime_config")
    browse_response = client.post(
        "/task-attribute-batch-generator/api/browse",
        json={"path": str(tmp_path)},
    )
    preview_response = client.post(
        "/task-attribute-batch-generator/api/preview",
        json={
            "reference_task_path": str(task_path),
            "template_xml_path": str(xml_path),
            "start": 12,
            "end": 12,
            "output_dir": str(output_dir),
        },
    )
    generate_response = client.post(
        "/task-attribute-batch-generator/api/generate",
        json={
            "reference_task_path": str(task_path),
            "template_xml_path": str(xml_path),
            "start": 12,
            "end": 12,
            "output_dir": str(output_dir),
            "overwrite": True,
        },
    )

    assert runtime_response.status_code == 200
    assert "default_root" in runtime_response.get_json()
    assert browse_response.status_code == 200
    assert any(entry["name"] == "demo_10_1001.json" and entry["is_json"] for entry in browse_response.get_json()["entries"])
    assert any(entry["name"] == "waypoint_tasks" and entry["is_dir"] for entry in browse_response.get_json()["entries"])
    assert preview_response.status_code == 200
    preview_payload = preview_response.get_json()
    assert preview_payload["template"]["attribute_type"] == "elevator_out"
    assert preview_payload["generated_files"][0]["output_name"] == "demo_elevator_out_3_12.xml"
    assert generate_response.status_code == 200
    assert (output_dir / "demo_elevator_out_3_12.xml").exists()
