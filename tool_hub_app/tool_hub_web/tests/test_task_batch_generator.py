import json

from tool_hub_web.task_batch_generator import (
    discover_template_pairs,
    generate_task_files,
    infer_source_floor,
    preview_task_files,
)


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sample_template(task_group_name, task_id):
    return {
        "task_group_name": task_group_name,
        "subtasks": [
            {
                "subtask_name": "main_road",
                "waypoints": [
                    {"waypoint_id": "p0", "waypoint_task_id": task_id},
                    {"waypoint_id": "p1", "waypoint_task_id": "demo_close_elevdoor_5"},
                ],
            }
        ],
    }


def test_discover_template_pairs_lists_all_valid_pairs(tmp_path):
    write_json(tmp_path / "A_5_501.json", sample_template("A_5_501", "demo_elevator_in_3_x"))
    write_json(tmp_path / "A_5_503.json", sample_template("A_5_503", "demo_elevator_out_3_5"))
    write_json(tmp_path / "B_7_701.json", sample_template("B_7_701", "demo_elevator_in_3_x"))
    write_json(tmp_path / "B_7_703.json", sample_template("B_7_703", "demo_elevator_out_3_7"))
    write_json(tmp_path / "noise.json", {"task_group_name": "noise", "subtasks": []})

    pairs = discover_template_pairs(tmp_path)

    assert len(pairs) == 2
    assert pairs[0]["prefix"] == "A"
    assert pairs[0]["template_floor"] == 5
    assert pairs[0]["source_floor"] == 3
    assert pairs[0]["template_01_path"].endswith("A_5_501.json")
    assert pairs[0]["template_03_path"].endswith("A_5_503.json")
    assert pairs[1]["prefix"] == "B"


def test_preview_task_files_builds_output_names_and_rewrite_summary(tmp_path):
    template_01 = tmp_path / "A_5_501.json"
    template_03 = tmp_path / "A_5_503.json"
    write_json(template_01, sample_template("A_5_501", "demo_elevator_out_3_5"))
    write_json(template_03, sample_template("A_5_503", "demo_elevator_in_5_3"))

    preview = preview_task_files(
        template_01=template_01,
        template_03=template_03,
        start=8,
        end=9,
        elevator_floor=3,
        output_dir=tmp_path,
    )

    assert preview["pair"]["prefix"] == "A"
    assert preview["pair"]["source_floor"] == 3
    assert [item["output_name"] for item in preview["generated_files"]] == [
        "A_8_801",
        "A_8_803",
        "A_9_901",
        "A_9_903",
    ]
    assert preview["generated_files"][0]["rewrites"][0]["after"] == "demo_elevator_out_3_8"
    assert preview["generated_files"][1]["rewrites"][0]["after"] == "demo_elevator_in_8_3"


def test_generate_task_files_writes_outputs_with_rewritten_task_ids(tmp_path):
    template_01 = tmp_path / "A_5_501.json"
    template_03 = tmp_path / "A_5_503.json"
    write_json(template_01, sample_template("A_5_501", "demo_elevator_out_3_5"))
    write_json(template_03, sample_template("A_5_503", "demo_elevator_in_5_3"))

    result = generate_task_files(
        template_01=template_01,
        template_03=template_03,
        start=8,
        end=8,
        elevator_floor=3,
        output_dir=tmp_path,
        overwrite=True,
    )

    assert len(result["created_files"]) == 2
    generated_01 = json.loads((tmp_path / "A_8_801.json").read_text(encoding="utf-8"))
    generated_03 = json.loads((tmp_path / "A_8_803.json").read_text(encoding="utf-8"))

    assert generated_01["task_group_name"] == "A_8_801"
    assert generated_01["subtasks"][0]["waypoints"][0]["waypoint_task_id"] == "demo_elevator_out_3_8"
    assert generated_01["subtasks"][0]["waypoints"][1]["waypoint_task_id"] == "demo_close_elevdoor_8"
    assert generated_03["subtasks"][0]["waypoints"][0]["waypoint_task_id"] == "demo_elevator_in_8_3"


def realistic_template(task_group_name, target_floor, suffix):
    return {
        "task_group_name": task_group_name,
        "subtasks": [
            {
                "subtask_name": "main_road",
                "waypoints": [
                    {"waypoint_id": "a", "waypoint_task_id": "demo_elevator_in_3_x"},
                    {"waypoint_id": "b", "waypoint_task_id": f"demo_elevator_out_3_{target_floor}"},
                ],
            },
            {
                "subtask_name": "elevator_hall",
                "waypoints": [
                    {"waypoint_id": "c", "waypoint_task_id": f"demo_close_elevdoor_{target_floor}"},
                    {"waypoint_id": "d", "waypoint_task_id": "place_water"},
                ],
            },
            {
                "subtask_name": "elevator_hall_r",
                "waypoints": [
                    {"waypoint_id": "e", "waypoint_task_id": f"demo_elevator_in_{target_floor}_3"},
                    {"waypoint_id": "f", "waypoint_task_id": f"demo_elevator_out_{target_floor}_3"},
                ],
            },
            {
                "subtask_name": "main_road_r",
                "waypoints": [
                    {"waypoint_id": "g", "waypoint_task_id": "demo_close_elevdoor_3"},
                ],
            },
        ],
    }


def test_infer_source_floor_and_rewrite_realistic_task_family(tmp_path):
    template_01 = tmp_path / "A_10_1001.json"
    template_03 = tmp_path / "A_10_1003.json"
    write_json(template_01, realistic_template("A_10_1001", 10, "01"))
    write_json(template_03, realistic_template("A_10_1003", 10, "03"))

    data = json.loads(template_01.read_text(encoding="utf-8"))
    assert infer_source_floor(data, 10) == 3

    preview = preview_task_files(
        template_01=template_01,
        template_03=template_03,
        start=12,
        end=12,
        output_dir=tmp_path,
    )

    assert preview["pair"]["source_floor"] == 3
    preview_ids = [item["after"] for item in preview["generated_files"][0]["rewrites"]]
    assert "demo_elevator_out_3_12" in preview_ids
    assert "demo_close_elevdoor_12" in preview_ids
    assert "demo_elevator_in_12_3" in preview_ids
    assert "demo_elevator_out_12_3" in preview_ids
    assert "demo_close_elevdoor_3" not in preview_ids
