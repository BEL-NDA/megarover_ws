#!/usr/bin/env bash
set -euo pipefail

patterns=(
  "micro_ros_agent"
  "teleop_twist_keyboard"
  "ros2 launch megarover3_bringup robot.launch.py"
  "ros2 launch megarover3_bringup zed.launch.py"
  "ros2 launch megarover3_navigation"
  "ekf_node"
  "rviz2"
  "zed_node"
  "component_container"
  "robot_state_publisher"
  "joint_state_publisher"
  "pub_odom"
  "odom_to_path"
  "zed_person_tracks"
  "person_tracks_to_markers"
  "zed_objects_to_markers"
)

for pattern in "${patterns[@]}"; do
  pids="$(pgrep -f "${pattern}" || true)"
  if [[ -n "${pids}" ]]; then
    echo "Stopping ${pattern}: ${pids}"
    kill ${pids} 2>/dev/null || true
  fi
done

sleep 1

for pattern in "${patterns[@]}"; do
  pids="$(pgrep -f "${pattern}" || true)"
  if [[ -n "${pids}" ]]; then
    echo "Force stopping ${pattern}: ${pids}"
    kill -9 ${pids} 2>/dev/null || true
  fi
done

echo "Megarover real robot processes stopped."
