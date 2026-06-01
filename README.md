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

# ターミナル2: Megarover + EKF + RViz
source ~/megarover_ws/install/setup.bash
ros2 launch megarover3_bringup robot.launch.py rover:=mega_zed

# ターミナル3: ZED2i カメラ（深度モード選択可）
source ~/megarover_ws/install/setup.bash
ros2 launch megarover3_bringup zed.launch.py
# 軽量版: ros2 launch megarover3_bringup zed.launch.py depth_mode:=NEURAL_LIGHT
# 最高精度: ros2 launch megarover3_bringup zed.launch.py depth_mode:=NEURAL_PLUS

# キーボード操縦
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -r /cmd_vel:=/rover_twist
```

## トラブルシューティング

### ノードが重複して odom が振動する

launch を Ctrl+C で終了した後もノードが残存することがあります。
以下のコマンドで強制終了してから再起動してください。

```bash
pkill -9 -f "ekf_node|pub_odom|rviz2|robot_state_publisher|joint_state_publisher|robot.launch"
```

確認：

```bash
ros2 node list | grep -E "ekf|pub_odom|rviz|robot_state|joint_state"
# 何も表示されなければ OK
```

### ZED 起動時に `getcwd() failed` が出る

削除済みの古いディレクトリ（`~/zed_ws` 等）をカレントにしているターミナルで発生します。
`cd ~` してから再実行してください。

### micro-ROS Agent が `Package not found` になる

ターミナルで `source ~/megarover_ws/install/local_setup.bash` が実行されていません。
`start_megarover_agent.sh` を使えば自動で source されます。

## 環境

- OS: Ubuntu 22.04
- ROS2: Humble
- GPU: NVIDIA RTX 4060 (CUDA 対応)
- カメラ: ZED2i (USB)
- ロボット MCU: ESP32 (VS-C3) / micro-ROS
- 深度モード: NEURAL（デフォルト）/ NEURAL_LIGHT / NEURAL_PLUS
