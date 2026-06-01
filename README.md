# megarover_ws

Megarover Ver.3.0 ROS2 ワークスペース（ZED2i + micro-ROS 対応）

## 構成

```
megarover_ws/
├── megarover.repos          # 全リポジトリの参照定義
├── arduino/                 # Arduino スケッチ (micro-ROS, vcs import で展開)
├── src/                     # ROS2 パッケージ (vcs import で展開)
│   ├── megarover3_ros2/
│   └── vs_rover_options_description/
├── uros_ws/                 # micro-ROS Agent ワークスペース
└── zed_ws/                  # ZED ROS2 Wrapper ワークスペース
```

## セットアップ

```bash
git clone https://github.com/BEL-NDA/megarover_ws.git ~/megarover_ws
cd ~/megarover_ws
vcs import < megarover.repos
```

### ROS2 ワークスペースのビルド

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

### ZED ワークスペースのビルド

```bash
cd ~/megarover_ws/zed_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --cmake-args=-DCMAKE_BUILD_TYPE=Release
```

### micro-ROS Agent のビルド

```bash
cd ~/megarover_ws/uros_ws
source /opt/ros/humble/setup.bash
ros2 run micro_ros_setup create_agent_ws.sh
colcon build
```

## 起動手順

```bash
# ターミナル1: micro-ROS エージェント
~/megarover_ws/arduino/start_megarover_agent.sh

# ターミナル2: Megarover (ZED2i あり)
source /opt/ros/humble/setup.bash
source ~/megarover_ws/install/setup.bash
ros2 launch megarover3_bringup robot.launch.py rover:=mega_zed

# ターミナル3: ZED2i カメラ
source ~/megarover_ws/zed_ws/install/setup.bash
ros2 launch zed_wrapper zed_camera.launch.py camera_model:=zed2i \
  publish_urdf:=false publish_tf:=false

# キーボード操縦
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -r /cmd_vel:=/rover_twist
```

## 環境

- OS: Ubuntu 22.04
- ROS2: Humble
- GPU: NVIDIA (CUDA 対応)
- カメラ: ZED2i (USB)
- ロボット MCU: ESP32 (VS-C3) / micro-ROS
