# megarover_ws

Megarover Ver.3.0 ROS2 ワークスペース（ZED2i + micro-ROS 対応）

## 構成

```
megarover_ws/
├── megarover.repos          # 全リポジトリの参照定義
├── arduino/                 # Arduino スケッチ (micro-ROS, vcs import で展開)
├── maps/                    # ZED エリアメモリファイル (.area)
├── src/                     # ROS2 パッケージ (vcs import で展開)
│   ├── megarover3_ros2/
│   └── vs_rover_options_description/
├── stop.sh                  # 全ノード停止スクリプト
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

### CycloneDDS の設定

ZED2i の大容量データ転送に最適化された DDS 設定です。

```bash
sudo apt install ros-humble-rmw-cyclonedds-cpp
sudo tee /etc/sysctl.d/60-zed-buffers.conf <<< $'net.ipv4.ipfrag_time=3\nnet.ipv4.ipfrag_high_thresh=134217728\nnet.core.rmem_max=2147483647' && sudo sysctl -p /etc/sysctl.d/60-zed-buffers.conf
```

`~/.bashrc` に追加済み：
```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/tsujita/cyclonedds.xml
```

### ZED メッシュの修正（初回のみ）

RViz でロボットモデルの ZED カメラ部分を表示するために必要：

```bash
sudo ln -s /opt/ros/humble/share/zed_description/meshes /opt/ros/humble/share/zed_msgs/meshes
```

## 起動手順

> **順番が重要です。** ZED を先に起動しないと RViz のカメラ映像が表示されません。

```bash
# ターミナル1: micro-ROS エージェント
~/megarover_ws/arduino/start_megarover_agent.sh

# ターミナル2: ZED2i カメラ（先に起動する）
source ~/megarover_ws/install/setup.bash
ros2 launch megarover3_bringup zed.launch.py od:=true
# 軽量版: ros2 launch megarover3_bringup zed.launch.py od:=true depth_mode:=NEURAL_LIGHT

# ターミナル3: Megarover + EKF + RViz（ZED 起動後に実行）
source ~/megarover_ws/install/setup.bash
ros2 launch megarover3_bringup robot.launch.py rover:=mega_zed od:=true

# キーボード操縦（任意）
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -r /cmd_vel:=/rover_twist
```

### 全ノード停止

```bash
~/megarover_ws/stop.sh
```

## Xbox コントローラ

メガローバーに付属の Xbox Wireless Controller で操縦できます。

### 接続方法

1. ロボットの電源を入れる
2. Xbox ボタンを押してコントローラをオン（初回はペアリングモード：Share ボタン 3 秒長押し）
3. 自動で ESP32 に BLE 接続される

### ボタン操作

| ボタン | 動作 |
|---|---|
| R1 + 左スティック | 低速走行（旋回上限 0.52 rad/s）|
| L1 + 左スティック | 中速走行 |
| R2 + 左スティック | 高速走行 |
| L2 + 左スティック | 最高速走行 |
| 十字キー ↑↓ | 低速前後進（300 mm/s）|
| 十字キー ←→ | 低速旋回 |
| Y/A（△/×） | 微速前後進 |
| X/B（□/〇） | 微速旋回 |

### 緊急停止

**View ボタン**（Xbox ボタン左の小ボタン）を押すと緊急停止トグル：
- ON: すべての速度指令がゼロになり、LED が 500ms 点滅
- ROS2 からの指令も無効化される
- `/rover_estop` トピック（std_msgs/Bool）で状態を配信
- もう一度押すと解除

```bash
# 緊急停止状態を確認
ros2 topic echo /rover_estop
```

### コントローラの電源オフ

Xbox ボタンを 3 秒長押し。

## 物体検出（Object Detection）

ZED SDK の AI 物体検出を有効にすると、カメラ映像から人・車などを 3D 位置付きでリアルタイム検出できます。

```bash
ros2 launch megarover3_bringup zed.launch.py od:=true
```

> **初回起動時の注意**: GPU 向けに AI モデルを最適化するため数分かかります。

| トピック | 型 | 内容 |
|---|---|---|
| `/zed/zed_node/obj_det/objects` | `zed_msgs/ObjectsStamped` | 検出オブジェクト一覧 |

RViz に **ObjectDetection**（バウンディングボックス）と **EStop**（緑/赤の球）が表示されます。

## SLAM（エリアメモリー）

ZED SDK の Visual SLAM 機能を使って環境の地図を保存・再利用します。

地図ファイルは `~/megarover_ws/maps/` に保存します。

### slam_mode の種類

| slam_mode | 動作 |
|---|---|
| `off`（デフォルト）| Area Memory 無効 |
| `mapping` | 地図を構築しながら走行。Ctrl+C 終了時に `.area` を保存 |
| `localization` | 保存済み `.area` を読み込み、再ローカリゼーション（地図更新なし）|

### Step 1: マッピング

```bash
ros2 launch megarover3_bringup zed.launch.py \
  slam_mode:=mapping \
  area_file:=$HOME/megarover_ws/maps/lab.area
```

**走行のコツ：** テクスチャのある壁・家具のある場所から開始、20m 以内のループを走行。

Ctrl+C で終了すると `lab.area` が保存されます。手動保存：

```bash
ros2 service call /zed/zed_node/save_area_memory zed_msgs/srv/SaveAreaMemory "{area_file_path: ''}"
```

### Step 2: ローカリゼーション

```bash
ros2 launch megarover3_bringup zed.launch.py \
  slam_mode:=localization \
  area_file:=$HOME/megarover_ws/maps/lab.area
```

ログに `Relocalizing...` → `OK` が出れば成功。RViz の **map** フレームが有効になり、**SLAM Landmarks**（黄色点群）が表示されます。

### Step 3: 地図を拡張する

mapping モードで同じファイルを指定すると既存地図に追加されます（Ctrl+C で上書き保存）。

### 地図ファイルの管理

```
~/megarover_ws/maps/
├── lab.area        # 研究室
├── corridor.area   # 廊下
└── ...
```

`.area` は SDK バージョンや depth_mode が変わると非互換になります。その場合は作り直してください。

## トラブルシューティング

### ノードが重複する / odom が振動する

```bash
~/megarover_ws/stop.sh
```

で全ノードを停止してから再起動してください。

### SLAM: `INCOMPATIBLE AREA FILE` エラー

`.area` ファイルが現在の SDK/設定と非互換です。削除して mapping からやり直してください。

### SLAM: `Relocalizing...` のまま固まる

照明変化・大幅なレイアウト変更が原因。mapping モードで地図を作り直してください。

### ZED 起動時に `getcwd() failed` が出る

削除済みディレクトリをカレントにしているターミナルで発生します。`cd ~` してから再実行してください。

### micro-ROS Agent が `Package not found` になる

`start_megarover_agent.sh` を使えば自動で source されます。

## 環境

- OS: Ubuntu 22.04
- ROS2: Humble
- DDS: CycloneDDS
- GPU: NVIDIA RTX 4060 (CUDA 対応)
- カメラ: ZED2i (USB) / ZED SDK 5.3
- ロボット MCU: ESP32 (VS-C3) / micro-ROS
- コントローラ: Xbox Wireless Controller (BLE)
- 深度モード: NEURAL_PLUS（デフォルト）/ NEURAL_LIGHT / NEURAL
