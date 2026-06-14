import json

from tool_hub_web.task_attribute_batch_generator import (
    generate_task_attribute_files,
    preview_task_attribute_files,
)


def write_text(path, text):
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def reference_task_payload(variable_floor, fixed_floor):
    return {
        "task_group_name": f"demo_{variable_floor}",
        "subtasks": [
            {
                "subtask_name": "main_road",
                "waypoints": [
                    {"waypoint_task_id": f"demo_elevator_in_{fixed_floor}_x"},
                    {"waypoint_task_id": f"demo_elevator_out_{fixed_floor}_{variable_floor}"},
                ],
            },
            {
                "subtask_name": "elevator_hall",
                "waypoints": [
                    {"waypoint_task_id": f"demo_close_elevdoor_{variable_floor}"},
                ],
            },
            {
                "subtask_name": "elevator_hall_r",
                "waypoints": [
                    {"waypoint_task_id": f"demo_elevator_in_{variable_floor}_{fixed_floor}"},
                    {"waypoint_task_id": f"demo_elevator_out_{variable_floor}_{fixed_floor}"},
                ],
            },
            {
                "subtask_name": "main_road_r",
                "waypoints": [
                    {"waypoint_task_id": f"demo_close_elevdoor_{fixed_floor}"},
                ],
            },
        ],
    }


def test_preview_close_elevdoor_rewrites_filename_and_command(tmp_path):
    task_path = tmp_path / "demo_10_1001.json"
    xml_path = tmp_path / "demo_close_elevdoor_10.xml"
    write_json(task_path, reference_task_payload(10, 3))
    write_text(
        xml_path,
        """
<root>
  <BehaviorTree ID="MainTree">
    <Sequence name="WaitForElevator">
      <ElevatorDoorKeeper command="10-"/>
    </Sequence>
  </BehaviorTree>
</root>
""",
    )

    preview = preview_task_attribute_files(
        reference_task_path=task_path,
        template_xml_path=xml_path,
        start=12,
        end=12,
        output_dir=tmp_path,
    )

    record = preview["generated_files"][0]
    assert record["output_name"] == "demo_close_elevdoor_12.xml"
    assert record["attribute_type"] == "close_elevdoor"
    assert any(change["after"] == 'command="12-"' for change in record["rewrites"])


def test_preview_elevator_in_rewrites_variable_first_position_and_xml_fields(tmp_path):
    task_path = tmp_path / "demo_10_1001.json"
    xml_path = tmp_path / "demo_elevator_in_10_3.xml"
    write_json(task_path, reference_task_payload(10, 3))
    write_text(
        xml_path,
        """
<root>
  <BehaviorTree ID="MainTree">
    <Sequence name="WaitForElevator">
      <ElevatorCaller elevid="{elevator_id}" target_floor="10"/>
      <ElevatorDoorKeeper command="10+"/>
      <ElevatorDoorKeeper command="10-"/>
    </Sequence>
  </BehaviorTree>
</root>
""",
    )

    preview = preview_task_attribute_files(
        reference_task_path=task_path,
        template_xml_path=xml_path,
        start=12,
        end=12,
        output_dir=tmp_path,
    )

    record = preview["generated_files"][0]
    assert record["output_name"] == "demo_elevator_in_12_3.xml"
    assert record["variant_role"] == "variable_fixed"
    after_values = [change["after"] for change in record["rewrites"]]
    assert 'target_floor="12"' in after_values
    assert 'command="12+"' in after_values
    assert 'command="12-"' in after_values


def test_preview_elevator_out_fixed_variable_rewrites_target_floor_and_open_command(tmp_path):
    task_path = tmp_path / "demo_10_1001.json"
    xml_path = tmp_path / "demo_elevator_out_3_10.xml"
    write_json(task_path, reference_task_payload(10, 3))
    write_text(
        xml_path,
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
""",
    )

    preview = preview_task_attribute_files(
        reference_task_path=task_path,
        template_xml_path=xml_path,
        start=12,
        end=12,
        output_dir=tmp_path,
    )

    record = preview["generated_files"][0]
    assert record["output_name"] == "demo_elevator_out_3_12.xml"
    assert record["variant_role"] == "fixed_variable"
    after_values = [change["after"] for change in record["rewrites"]]
    assert 'target_floor="12"' in after_values
    assert 'command="12+"' in after_values
    assert 'command="3-"' not in after_values


def test_generate_elevator_out_variable_fixed_uses_reference_task_as_truth(tmp_path):
    task_path = tmp_path / "demo_10_1001.json"
    xml_path = tmp_path / "demo_elevator_out_10_3.xml"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    write_json(task_path, reference_task_payload(10, 3))
    write_text(
        xml_path,
        """
<root>
  <BehaviorTree ID="MainTree">
    <Sequence name="OutBack">
      <ElevatorDoorKeeper command="10-"/>
      <ElevatorCaller elevid="{elevator_id}" target_floor="3"/>
      <ElevatorDoorKeeper command="3+"/>
    </Sequence>
  </BehaviorTree>
</root>
""",
    )

    result = generate_task_attribute_files(
        reference_task_path=task_path,
        template_xml_path=xml_path,
        start=12,
        end=12,
        output_dir=output_dir,
        overwrite=True,
    )

    assert len(result["created_files"]) == 1
    generated_path = output_dir / "demo_elevator_out_12_3.xml"
    text = generated_path.read_text(encoding="utf-8")
    assert 'command="12-"' in text
    assert 'target_floor="3"' in text
    assert 'command="3+"' in text


def test_preview_accepts_template_with_different_sample_variable_floor_same_fixed_position(tmp_path):
    task_path = tmp_path / "demo_10_1001.json"
    xml_path = tmp_path / "demo_elevator_in_4_3.xml"
    write_json(task_path, reference_task_payload(10, 3))
    write_text(
        xml_path,
        """
<root>
  <BehaviorTree ID="MainTree">
    <Sequence name="WaitForElevator">
      <ElevatorCaller elevid="{elevator_id}" target_floor="4"/>
      <ElevatorDoorKeeper command="4+"/>
      <ElevatorDoorKeeper command="4-"/>
    </Sequence>
  </BehaviorTree>
</root>
""",
    )

    preview = preview_task_attribute_files(
        reference_task_path=task_path,
        template_xml_path=xml_path,
        start=12,
        end=12,
        output_dir=tmp_path,
    )

    record = preview["generated_files"][0]
    assert record["output_name"] == "demo_elevator_in_12_3.xml"
    assert record["variant_role"] == "variable_fixed"
    after_values = [change["after"] for change in record["rewrites"]]
    assert 'target_floor="12"' in after_values
    assert 'command="12+"' in after_values
    assert 'command="12-"' in after_values
