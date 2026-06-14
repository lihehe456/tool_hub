from tool_hub_web.waypoint_task_builder import (
    create_default_waypoint_task_document,
    parse_waypoint_task_xml,
    serialize_waypoint_task_document,
    supported_waypoint_task_nodes,
)


def test_supported_waypoint_task_nodes_include_control_and_action_entries():
    nodes = supported_waypoint_task_nodes()

    assert "Sequence" in nodes
    assert nodes["Sequence"]["kind"] == "control"
    assert "RetryUntilSuccessful" in nodes
    assert nodes["RetryUntilSuccessful"]["max_children"] == 1
    assert "Fallback" in nodes
    assert nodes["Fallback"]["kind"] == "control"
    assert "PipelineSequence" in nodes
    assert nodes["PipelineSequence"]["kind"] == "control"
    assert "RoundRobin" in nodes
    assert nodes["RoundRobin"]["kind"] == "control"
    assert "ReactiveFallback" in nodes
    assert nodes["ReactiveFallback"]["kind"] == "control"
    assert "ReactiveSequence" in nodes
    assert nodes["ReactiveSequence"]["kind"] == "control"
    assert "RecoveryNode" in nodes
    assert nodes["RecoveryNode"]["kind"] == "control"
    assert "ChangeUssStatus" in nodes
    assert any(field["name"] == "status" for field in nodes["ChangeUssStatus"]["fields"])
    assert "Wait" in nodes
    assert [field["name"] for field in nodes["Wait"]["fields"]] == [
        "wait_duration",
        "server_name",
        "server_timeout",
    ]
    assert [port["name"] for port in nodes["Wait"]["input_ports"]] == [
        "wait_duration",
        "server_name",
        "server_timeout",
    ]
    assert "SetPoseFromOdom" in nodes
    assert [port["name"] for port in nodes["SetPoseFromOdom"]["output_ports"]] == [
        "pose",
        "message",
    ]
    assert nodes["SetTfBroadcast"]["fields"][0]["default"] == "true"
    assert "DoorControl" in nodes
    assert "EnableAmcl" in nodes
    assert "ComputePathToPose" in nodes
    assert "ComputePathThroughPoses" in nodes
    assert "FollowPath" in nodes
    assert "ClearEntireCostmap" in nodes
    assert "RemovePassedGoals" in nodes
    assert "GoalUpdated" in nodes
    assert "RateController" in nodes
    assert "Spin" in nodes
    assert "MoveForward" in nodes
    assert "WaitForReturnSignal" in nodes
    assert "RotateToGoalYawWithScan" in nodes
    assert "ClampWater" in nodes
    assert "OpenPlatform" in nodes
    assert "PlaceWater" in nodes
    assert "VirtualElevatorJudge" in nodes


def test_create_default_waypoint_task_document_uses_main_tree_sequence():
    document = create_default_waypoint_task_document("demo_task")

    assert document["task_name"] == "demo_task"
    assert document["tree"]["type"] == "Sequence"
    assert document["tree"]["children"] == []


def test_parse_and_serialize_waypoint_task_xml_round_trip():
    xml_text = """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence name="WaitForElevator">
      <ChangeUssStatus status="true"/>
      <RetryUntilSuccessful num_attempts="10">
        <Sequence name="CallAndCheckDoor">
          <PublishTaskStatus status_code="300"/>
          <Wait wait_duration="2"/>
        </Sequence>
      </RetryUntilSuccessful>
    </Sequence>
  </BehaviorTree>
</root>
""".strip()

    document = parse_waypoint_task_xml(xml_text, task_name="demo_task")
    rendered = serialize_waypoint_task_document(document)

    assert document["tree"]["type"] == "Sequence"
    assert document["tree"]["attrs"]["name"] == "WaitForElevator"
    assert document["tree"]["children"][1]["type"] == "RetryUntilSuccessful"
    assert document["tree"]["children"][1]["children"][0]["children"][1]["type"] == "Wait"
    assert '<RetryUntilSuccessful num_attempts="10">' in rendered
    assert '<PublishTaskStatus status_code="300" />' in rendered


def test_parse_waypoint_task_xml_rejects_unsupported_nodes():
    xml_text = """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence>
      <TotallyUnsupported />
    </Sequence>
  </BehaviorTree>
</root>
""".strip()

    try:
        parse_waypoint_task_xml(xml_text, task_name="bad_task")
    except ValueError as exc:
        assert "Unsupported node" in str(exc)
    else:
        raise AssertionError("Expected unsupported node parse failure")


def test_parse_waypoint_task_xml_accepts_fallback_control_node():
    xml_text = """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <Sequence name="FallbackDemo">
      <Fallback name="CheckDoorOrWaitBeforeRetry">
        <ElevatorStatus enable="true" car_status="in"/>
        <Sequence name="WaitBeforeRetry">
          <Wait wait_duration="20"/>
          <AlwaysFailure/>
        </Sequence>
      </Fallback>
    </Sequence>
  </BehaviorTree>
</root>
""".strip()

    document = parse_waypoint_task_xml(xml_text, task_name="fallback_demo")

    assert document["tree"]["children"][0]["type"] == "Fallback"
    assert document["tree"]["children"][0]["children"][1]["type"] == "Sequence"


def test_parse_waypoint_task_xml_accepts_navigation_recovery_nodes():
    xml_text = """
<root main_tree_to_execute="MainTree">
  <BehaviorTree ID="MainTree">
    <RecoveryNode number_of_retries="6" name="NavigateRecovery">
      <PipelineSequence name="NavigateWithReplanning">
        <RateController hz="0.333">
          <RecoveryNode number_of_retries="1" name="ComputePathToPose">
            <ReactiveSequence>
              <ComputePathToPose goal="{goal}" path="{path}" planner_id="GridBased"/>
            </ReactiveSequence>
            <ClearEntireCostmap service_name="global_costmap/clear_entirely_global_costmap"/>
          </RecoveryNode>
        </RateController>
        <FollowPath path="{path}" controller_id="FollowPath"/>
      </PipelineSequence>
    </RecoveryNode>
  </BehaviorTree>
</root>
""".strip()

    document = parse_waypoint_task_xml(xml_text, task_name="nav_recovery")

    assert document["tree"]["type"] == "RecoveryNode"
    assert document["tree"]["children"][0]["type"] == "PipelineSequence"


def test_serialize_waypoint_task_document_rejects_empty_tree():
    try:
        serialize_waypoint_task_document(
            {
                "task_name": "empty_task",
                "tree": None,
            }
        )
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("Expected empty tree serialize failure")
