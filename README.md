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

## 物体検出（Object Detection）

ZED SDK の AI 物体検出を有効にすると、カメラ映像から人・車・バッグなどを 3D 位置付きでリアルタイム検出できます。

### 起動方法

```bash
source ~/megarover_ws/install/setup.bash
ros2 launch megarover3_bringup zed.launch.py od:=true
```

他の引数と組み合わせ可能です：

```bash
# 物体検出 + 軽量深度モード
ros2 launch megarover3_bringup zed.launch.py od:=true depth_mode:=NEURAL_LIGHT

# 物体検出 + SLAM マッピング
ros2 launch megarover3_bringup zed.launch.py od:=true slam_mode:=mapping area_file:=$HOME/megarover_ws/maps/lab.area
```

> **初回起動時の注意**: GPU 向けに AI モデルを最適化するため数分かかります。`/usr/local/zed/resources/` にキャッシュされ、2 回目以降は即座に起動します。

### 検出結果のトピック

| トピック | 型 | 内容 |
|---|---|---|
| `/zed/zed_node/obj_det/objects` | `zed_msgs/ObjectsStamped` | 検出オブジェクト一覧（3D位置・クラス・追跡ID） |

```bash
# 検出結果を確認
ros2 topic echo /zed/zed_node/obj_det/objects
```

### 検出クラスと設定

`config/zed_megarover.yaml` の `object_detection.class` で各クラスの有効/無効と信頼度しきい値を調整できます。デフォルトでは **people**（人）と **vehicle**（車）のみ有効です。

| クラス | デフォルト | 信頼度しきい値 |
|---|---|---|
| people（人） | 有効 | 65% |
| vehicle（車両） | 有効 | 60% |
| bag（バッグ） | 無効 | 40% |
| animal（動物） | 無効 | 40% |
| electronics（電子機器） | 無効 | 45% |

### 検出モデルの変更

`zed_megarover.yaml` の `detection_model` で速度と精度をトレードオフできます：

| モデル | 速度 | 精度 |
|---|---|---|
| `MULTI_CLASS_BOX_FAST` | 速い（デフォルト） | 標準 |
| `MULTI_CLASS_BOX_MEDIUM` | 中程度 | 高め |
| `MULTI_CLASS_BOX_ACCURATE` | 遅い | 最高 |

### 動的な有効化（起動中に切り替え）

ZED ノード起動中にサービスで切り替えることもできます：

```bash
# 有効化
ros2 service call /zed/zed_node/enable_obj_det std_srvs/srv/SetBool "{data: true}"
# 無効化
ros2 service call /zed/zed_node/enable_obj_det std_srvs/srv/SetBool "{data: false}"
```

## SLAM（エリアメモリー）

ZED SDK の Visual SLAM 機能（Area Memory）を使うと、環境の地図（`.area` ファイル）を保存・再利用して、ループクロージャと再ローカリゼーションを行えます。

地図ファイルは `~/megarover_ws/maps/` に保存します。

### slam_mode の種類

| slam_mode | 動作 |
|---|---|
| `off`（デフォルト）| Area Memory 無効。起動のたびに odometry がリセット |
| `mapping` | 地図を構築しながら走行。Ctrl+C 終了時に `.area` ファイルを保存 |
| `localization` | 保存済みの `.area` ファイルを読み込み、再ローカリゼーションのみ（地図更新なし） |

### Step 1: マッピング（初回・地図を作る）

新しい環境を走行して地図を保存します。

```bash
# ターミナル3: ZED を mapping モードで起動
source ~/megarover_ws/install/setup.bash
ros2 launch megarover3_bringup zed.launch.py \
  slam_mode:=mapping \
  area_file:=$HOME/megarover_ws/maps/lab.area
```

**走行のコツ（公式推奨）：**
- 視覚的な特徴が豊富な場所（テクスチャのある壁や家具）から開始する
- カメラを下に向けない
- 20 m 以内のループ状のルートを走行するのが理想的
- 大きな空間は複数のセクションに分割する

走行が終わったら **Ctrl+C** で ZED ノードを終了すると、自動的に `maps/lab.area` が保存されます。

#### 走行中に手動で保存する場合

Ctrl+C を待たずにサービスコールで保存できます：

```bash
# 引数なし → area_file_path パラメータで指定したパスに保存
ros2 service call /zed/zed_node/save_area_memory zed_msgs/srv/SaveAreaMemory "{area_file_path: ''}"

# パスを直接指定する場合
ros2 service call /zed/zed_node/save_area_memory zed_msgs/srv/SaveAreaMemory \
  "{area_file_path: '/home/tsujita/megarover_ws/maps/lab.area'}"
```

エクスポートの進捗確認（`NONE` → `RUNNING` → `SUCCESS`）：

```bash
ros2 topic echo /zed/zed_node/pos_tracking/status | grep area_memory_state
```

### Step 2: ローカリゼーション（2 回目以降・地図を使う）

保存した `.area` ファイルを読み込み、既知の環境内で安定したポジション追跡を行います。

```bash
# ターミナル3: ZED を localization モードで起動
source ~/megarover_ws/install/setup.bash
ros2 launch megarover3_bringup zed.launch.py \
  slam_mode:=localization \
  area_file:=$HOME/megarover_ws/maps/lab.area
```

起動後、カメラがマッピング時の環境を認識するまで数秒かかります。
ログに `Relocalizing...` → `OK` と表示されれば再ローカリゼーション完了です。

### Step 3: 地図を拡張する

既存の地図を読み込みながら新しいエリアを追加したい場合は mapping モードで同じファイルを指定します：

```bash
ros2 launch megarover3_bringup zed.launch.py \
  slam_mode:=mapping \
  area_file:=$HOME/megarover_ws/maps/lab.area
```

終了時に同じファイルが更新されます（上書き）。別名で保存したい場合は別のパスを指定してください。

### 地図ファイルの管理

```
~/megarover_ws/maps/
├── lab.area        # 研究室
├── corridor.area   # 廊下
└── ...
```

`.area` ファイルはコンパクトなバイナリ形式です。環境が変わった（大きなレイアウト変更など）場合は mapping モードで地図を作り直します。

## トラブルシューティング

### SLAM: 起動時に `Relocalizing...` のまま固まる

`.area` ファイルに対応しない環境（照明変化・大幅なレイアウト変更など）で発生します。
mapping モードで地図を作り直してください。

### SLAM: `slam_mode:=localization requires area_file to be set` エラー

`localization` モードでは `area_file` の指定が必須です：

```bash
ros2 launch megarover3_bringup zed.launch.py \
  slam_mode:=localization \
  area_file:=$HOME/megarover_ws/maps/lab.area
```

### SLAM: Ctrl+C 後に `.area` ファイルが生成されない

ZED ノードが正常終了する前に強制終了（SIGKILL 等）すると保存されません。
必ず Ctrl+C（SIGTERM）で終了するか、`save_area_memory` サービスを使って先に手動保存してください。

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
