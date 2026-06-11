# megarover_real

Megarover Ver.3.0 ROS2 ワークスペース（実機側。ZED2i + micro-ROS 対応）

このリポジトリ自体が ROS ワークスペースです。`src/` 配下に `vcs import` で展開した ROS パッケージを置き、`colcon build` の対象にします。

## 構成

`megarover_common` をこのリポジトリの隣に置いて、共有設定と RViz レイアウトをそこに分離します。

```
megarover_real/
├── megarover.repos          # 全リポジトリの参照定義
├── ../megarover_common/     # 共有設定・RViz レイアウト
├── arduino/                 # Arduino スケッチ (micro-ROS, vcs import で展開)
├── configs/                 # 実機専用の EKF 設定
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
git clone https://github.com/BEL-NDA/megarover_real.git ~/src/megarover/megarover_real
git clone https://github.com/BEL-NDA/megarover_common.git ~/src/megarover/megarover_common
cd ~/src/megarover/megarover_real
vcs import < megarover.repos
```

### ROS2 ワークスペースのビルド

```bash
cd ~/src/megarover/megarover_real
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

### ZED ワークスペースのビルド

```bash
cd ~/src/megarover/megarover_real/zed_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --cmake-args=-DCMAKE_BUILD_TYPE=Release
```

### micro-ROS Agent のビルド

```bash
cd ~/src/megarover/megarover_real/uros_ws
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

### 共有設定の参照

共有の FastDDS 設定、Nav2 の上位設定、RViz レイアウトは `~/src/megarover/megarover_common` に置きます。EKF の設定はこのリポジトリの `configs/` に置きます。

### ZED メッシュの修正（初回のみ）

RViz でロボットモデルの ZED カメラ部分を表示するために必要：

```bash
sudo ln -s /opt/ros/humble/share/zed_description/meshes /opt/ros/humble/share/zed_msgs/meshes
```

## 起動手順

> **順番が重要です。** ZED を先に起動しないと RViz のカメラ映像が表示されません。

### 実機ヘルパーGUI

実機用の起動GUIを使う場合:

```bash
cd ~/src/megarover/megarover_real
./scripts/start-megarover-real-gui.sh
```

GUIはシミュレーション側ヘルパーと同じ考え方で、`1. ロボット`、`2. センサ`、`3. ナビゲーション`、`4. 保守` に分けています。

- 共通: `ROS_DOMAIN_ID`、端末エミュレータ、ZED depth mode、Nav2 params はGUIで変更できます。
- 実機固有: `micro-ROS Agent`、`ZED2i`、`robot.launch.py rover:=mega_zed`、VS-C3/ESP32ファーム書き込み、`stop.sh` を扱います。
- Nav2共通設定: 隣の `../megarover_common/nav2/` を参照します。
- ESP32ファーム: VS-C3コントローラと `SELECT` 緊急停止トグル版を前提にします。
- `vcs import` 後の実配置は `~/src/megarover/{arduino,src,uros_ws,zed_ws,megarover_real,megarover_common}` の兄弟構成です。GUIの既定workspaceも `~/src/megarover` です。

```bash
# ターミナル1: micro-ROS エージェント
cd ~/src/megarover
source /opt/ros/humble/setup.bash
source uros_ws/install/local_setup.bash
ros2 run micro_ros_agent micro_ros_agent serial --dev /dev/ttyUSB0 --baudrate 921600 -v4

# ターミナル2: ZED2i カメラ（先に起動する）
source ~/src/megarover/megarover_real/install/setup.bash
ros2 launch megarover3_bringup zed.launch.py od:=true
# 軽量版: ros2 launch megarover3_bringup zed.launch.py od:=true depth_mode:=NEURAL_LIGHT

# ターミナル3: Megarover + EKF + RViz（ZED 起動後に実行）
source ~/src/megarover/megarover_real/install/setup.bash
ros2 launch megarover3_bringup robot.launch.py rover:=mega_zed \
  params_file:=~/src/megarover/megarover_real/configs/megarover-ekf.yaml

# キーボード操縦（任意）
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -r /cmd_vel:=/rover_twist
```

`rover:=mega_zed` では、車輪由来のraw odomは `/wheel/odom`、EKF統合後のodomは `/odom` です。
`/odom` と `odom -> base_footprint` TF は `robot_localization` だけがpublishします。
EKF のパラメータは `~/src/megarover/megarover_real/configs/megarover-ekf.yaml` を使います。

確認:

```bash
ros2 topic info /wheel/odom
ros2 topic info /odom
ros2 run tf2_ros tf2_echo odom base_footprint
```

実機テストでは、低速の短い左右旋回、短い前進、後退、約0.8mの低速直進、少し長めの左右旋回で `/wheel/odom`、`/zed/zed_node/odom`、`/odom` が大きく破綻しないことを確認しました。
ロボットを手で持ち上げて移動すると車輪odometryとZED odomの整合が崩れるため、その場合は Megarover + EKF と ZED wrapper を再起動して現在位置を新しい初期状態にしてください。

### 全ノード停止

```bash
~/src/megarover/megarover_real/stop.sh
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
| `/perception/people/tracks` | `megarover_perception_msgs/PersonTrackArray` | personだけを抽出した追跡結果 |

`/perception/people/tracks` は実機・シミュレーション共通の制御用topicです。各trackには `track_id`、`class_name`、`confidence`、`bbox_2d`、`position_3d`、`velocity_3d`、`bbox_3d`、`tracking_state` が入ります。ZED ROS messageにはSDK側のobject IDが出ていないため、`track_id` は3D位置の近傍対応で生成します。

RViz に **ObjectDetection**（バウンディングボックス）と **EStop**（緑/赤の球）が表示されます。

## SLAM（エリアメモリー）

ZED SDK の Visual SLAM 機能を使って環境の地図を保存・再利用します。

地図ファイルは `~/src/megarover/megarover_real/maps/` に保存します。

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
  area_file:=$HOME/src/megarover/megarover_real/maps/lab.area
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
  area_file:=$HOME/src/megarover/megarover_real/maps/lab.area
```

ログに `Relocalizing...` → `OK` が出れば成功。RViz の **map** フレームが有効になり、**SLAM Landmarks**（黄色点群）が表示されます。

### Step 3: 地図を拡張する

mapping モードで同じファイルを指定すると既存地図に追加されます（Ctrl+C で上書き保存）。

### 地図ファイルの管理

```
~/src/megarover/megarover_real/maps/
├── lab.area        # 研究室
├── corridor.area   # 廊下
└── ...
```

`.area` は SDK バージョンや depth_mode が変わると非互換になります。その場合は作り直してください。

## トラブルシューティング

### ノードが重複する / odom が振動する

```bash
~/src/megarover/megarover_real/stop.sh
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
