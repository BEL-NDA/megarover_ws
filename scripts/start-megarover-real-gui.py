#!/usr/bin/env python3
import os
import shlex
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEGAROVER_ROOT = PROJECT_ROOT.parent
COMMON_ROOT = PROJECT_ROOT.parent / "megarover_common"


def q(value):
    return shlex.quote(str(value))


def which(command):
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        path = Path(directory) / command
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def env_bool(value):
    return "1" if value else "0"


def choose_terminal(preferred=""):
    if preferred:
        if which(preferred):
            return preferred
        messagebox.showerror("端末エラー", f"端末エミュレータが見つかりません: {preferred}")
        return None

    for candidate in ("gnome-terminal", "terminator", "konsole", "xfce4-terminal", "mate-terminal", "xterm"):
        if which(candidate):
            return candidate

    messagebox.showerror("端末エラー", "対応する端末エミュレータが見つかりません。詳細設定で指定してください。")
    return None


def set_status(text):
    status_var.set(text)


def run_in_terminal(title, command, env=None, cwd=PROJECT_ROOT):
    override_env = env or {}
    process_env = {**os.environ, **override_env}
    terminal = choose_terminal(process_env.get("TERMINAL_EMULATOR", "").strip())
    if not terminal:
        return

    exports = " ".join(f"export {key}={q(value)};" for key, value in sorted(override_env.items()) if key.isupper())
    wrapped = (
        f"{exports} cd {q(cwd)} && {command}; "
        "status=$?; echo; "
        f"echo '[{title}] exited with status '${{status}}; "
        "exec bash"
    )

    if terminal == "gnome-terminal":
        args = [terminal, "--title", title, "--", "bash", "-lc", wrapped]
    elif terminal == "terminator":
        args = [terminal, "-T", title, "-x", "bash", "-lc", wrapped]
    elif terminal == "konsole":
        args = [terminal, "--new-tab", "-p", f"tabtitle={title}", "-e", "bash", "-lc", wrapped]
    elif terminal == "xfce4-terminal":
        args = [terminal, "--title", title, "--command", f"bash -lc {q(wrapped)}"]
    elif terminal == "mate-terminal":
        args = [terminal, "--title", title, "--", "bash", "-lc", wrapped]
    elif terminal == "xterm":
        args = [terminal, "-T", title, "-e", "bash", "-lc", wrapped]
    else:
        args = [terminal, "-e", "bash", "-lc", wrapped]

    try:
        subprocess.Popen(args, cwd=str(cwd), env=process_env, start_new_session=True)
        set_status(f"{title} を起動しました。")
    except Exception as exc:
        messagebox.showerror("起動エラー", f"{title} の起動に失敗しました。\n{exc}")


def real_prefix():
    ws = workspace_var.get().strip() or str(MEGAROVER_ROOT)
    return (
        f"cd {q(ws)} && "
        "source /opt/ros/humble/setup.bash && "
        "for setup in $HOME/megarover_ws/install/setup.bash $HOME/megarover_ws/install/local_setup.bash "
        "install/setup.bash install/local_setup.bash "
        "megarover_real/install/setup.bash megarover_real/install/local_setup.bash "
        "zed_ws/install/setup.bash zed_ws/install/local_setup.bash "
        "uros_ws/install/setup.bash uros_ws/install/local_setup.bash; do "
        "[[ -f \"$setup\" ]] && source \"$setup\"; "
        "done"
    )


def common_env():
    return {
        "ROS_DOMAIN_ID": ros_domain_var.get().strip() or "11",
        "TERMINAL_EMULATOR": terminal_var.get().strip(),
    }


def zed_args():
    args = [
        "od:=true",
        f"depth_mode:={q(zed_depth_var.get().strip() or 'NEURAL_LIGHT')}",
    ]
    if zed_slam_mode_var.get().strip() != "off":
        args.append(f"slam_mode:={q(zed_slam_mode_var.get().strip())}")
        args.append(f"area_file:={q(area_file_var.get().strip())}")
    return " ".join(args)


def start_micro_ros():
    port = esp_port_var.get().strip() or "/dev/ttyUSB0"
    script = Path.home() / "Arduino" / "megarover3_ros2" / "start_megarover_agent.sh"
    cmd = (
        f"kill $(lsof -t {q(port)} 2>/dev/null) 2>/dev/null || true; "
        "sleep 1; "
        f"{q(script)}"
    )
    run_in_terminal("Real micro-ROS Agent", f"{real_prefix()} && {cmd}", common_env())


def start_zed():
    cmd = zed_command_var.get().strip()
    if not cmd:
        cmd = f"ros2 launch megarover3_bringup zed.launch.py {zed_args()}"
    run_in_terminal("Real ZED2i", f"{real_prefix()} && {cmd}", common_env())


def start_bringup():
    params = ekf_params_var.get().strip() or str(PROJECT_ROOT / "configs" / "megarover-ekf.yaml")
    cmd = bringup_command_var.get().strip()
    if not cmd:
        cmd = f"ros2 launch megarover3_bringup robot.launch.py rover:=mega_zed params_file:={q(params)}"
    run_in_terminal("Real Megarover Bringup", f"{real_prefix()} && {cmd}", common_env())


def start_full_stack():
    start_micro_ros()
    delay_zed = delay_zed_var.get().strip() or "2"
    delay_robot = delay_robot_var.get().strip() or "8"
    zed_cmd = zed_command_var.get().strip() or f"ros2 launch megarover3_bringup zed.launch.py {zed_args()}"
    params = ekf_params_var.get().strip() or str(PROJECT_ROOT / "configs" / "megarover-ekf.yaml")
    robot_cmd = bringup_command_var.get().strip() or f"ros2 launch megarover3_bringup robot.launch.py rover:=mega_zed params_file:={q(params)}"
    run_in_terminal("Real ZED2i", f"sleep {q(delay_zed)} && {real_prefix()} && {zed_cmd}", common_env())
    run_in_terminal("Real Megarover Bringup", f"sleep {q(delay_robot)} && {real_prefix()} && {robot_cmd}", common_env())


def track_follow_controller_command():
    script = PROJECT_ROOT / "scripts" / "track_follow_controller.py"
    return (
        f"python3 {q(script)} "
        "--port 50112 "
        "--tracks_topic /perception/people/tracks "
        "--cmd_vel_topic /rover_twist "
        "--kp 0.50 --ki 0.0 --kd 0.04 "
        "--max_angular_z 0.50 "
        "--finish_angle_deg 5.0 "
        "--max_target_jump_m 2.0 "
        "--max_yaw_jump_deg 45.0 "
        "--command_timeout 300.0"
    )


def start_track_follow_controller(delay="0"):
    cmd = track_follow_controller_command()
    run_in_terminal(
        "Real Track Follow Controller",
        f"sleep {q(delay)} && {real_prefix()} && {cmd}",
        common_env(),
    )


def start_full_stack_demo():
    start_full_stack()
    delay_controller = delay_controller_var.get().strip() or "14"
    start_track_follow_controller(delay_controller)


def start_teleop():
    topic = teleop_topic_var.get().strip() or "/rover_twist"
    cmd = f"ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r /cmd_vel:={q(topic)}"
    run_in_terminal("Real Keyboard Teleop", f"{real_prefix()} && {cmd}", common_env())


def start_rviz():
    config = rviz_config_var.get().strip()
    if config:
        cmd = f"rviz2 -d {q(config)}"
    else:
        cmd = "rviz2 -d $(ros2 pkg prefix megarover3_bringup)/share/megarover3_bringup/rviz/mega_zed.rviz"
    run_in_terminal("Real RViz", f"{real_prefix()} && {cmd}", common_env())


def start_nav2():
    cmd = nav_command_var.get().strip()
    if not cmd:
        params = nav_params_var.get().strip() or str(COMMON_ROOT / "nav2" / "zed_pointcloud_odom_nav2_mppi_params.yaml")
        cmd = (
            "ros2 launch megarover3_navigation zed_pointcloud_random_nav.launch.py "
            "use_sim_time:=false start_nav2:=true start_random_goals:=false "
            f"start_coverage_goals:={env_bool(nav_coverage_var.get())} "
            f"start_occupancy_mapper:={env_bool(nav_occupancy_var.get())} "
            f"params_file:={q(params)}"
        )
    run_in_terminal("Real Nav2", f"{real_prefix()} && {cmd}", common_env())


def save_area_memory():
    area = area_file_var.get().strip()
    cmd = f"ros2 service call /zed/zed_node/save_area_memory zed_msgs/srv/SaveAreaMemory \"{{area_file_path: '{area}'}}\""
    run_in_terminal("Real Save ZED Area", f"{real_prefix()} && {cmd}", common_env())


def stop_all():
    cmd = stop_command_var.get().strip() or "./megarover_real/stop.sh"
    run_in_terminal("Real Stop", f"{real_prefix()} && {cmd}", common_env())


def esp_upload():
    cmd = (
        "export PATH=\"$HOME/.local/bin:$PATH\" && "
        "arduino --upload --board esp32:esp32:esp32:UploadSpeed=921600 "
        f"--port {q(esp_port_var.get().strip() or '/dev/ttyUSB0')} "
        f"{q(str(MEGAROVER_ROOT / 'arduino' / 'megarover3_ros2.ino'))}"
    )
    run_in_terminal("Real ESP32 Upload", cmd, common_env())


def build_micro_ros_agent():
    cmd = (
        "source /opt/ros/humble/setup.bash && "
        "cd uros_ws && "
        "if [[ ! -d src/micro_ros_agent ]]; then ros2 run micro_ros_setup create_agent_ws.sh; fi && "
        "colcon build"
    )
    run_in_terminal("Build micro-ROS Agent", cmd, common_env())


def open_options():
    top = tk.Toplevel(root)
    top.title("実機GUI 詳細設定")
    top.geometry("820x640")
    top.columnconfigure(0, weight=1)
    top.rowconfigure(0, weight=1)

    frame = ttk.Frame(top, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(1, weight=1)

    fields = [
        ("TERMINAL_EMULATOR", terminal_var),
        ("ROS_DOMAIN_ID", ros_domain_var),
        ("workspace", workspace_var),
        ("micro-ROS command", micro_ros_command_var),
        ("ZED command override", zed_command_var),
        ("bringup command override", bringup_command_var),
        ("EKF params", ekf_params_var),
        ("teleop topic", teleop_topic_var),
        ("RViz config", rviz_config_var),
        ("Nav2 command override", nav_command_var),
        ("Nav2 params", nav_params_var),
        ("stop command", stop_command_var),
        ("ESP port", esp_port_var),
        ("full-stack ZED delay sec", delay_zed_var),
        ("full-stack robot delay sec", delay_robot_var),
        ("full-stack demo controller delay sec", delay_controller_var),
    ]

    for row, (label, var) in enumerate(fields):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(frame, textvariable=var).grid(row=row, column=1, sticky="ew", pady=3)


def add_button(parent, text, command, row, column=0):
    button = ttk.Button(parent, text=text, command=command)
    button.grid(row=row, column=column, sticky="ew", pady=5, padx=4)
    return button


root = tk.Tk()
root.title("Megarover 実機ヘルパー")
root.geometry("860x620")
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)

terminal_var = tk.StringVar(value=os.environ.get("TERMINAL_EMULATOR", ""))
ros_domain_var = tk.StringVar(value=os.environ.get("ROS_DOMAIN_ID", "11"))
workspace_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_WS", str(MEGAROVER_ROOT)))
micro_ros_command_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_MICRO_ROS_COMMAND", ""))
zed_command_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_ZED_COMMAND", ""))
bringup_command_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_BRINGUP_COMMAND", ""))
ekf_params_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_EKF_PARAMS", str(PROJECT_ROOT / "configs" / "megarover-ekf.yaml")))
teleop_topic_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_TELEOP_TOPIC", "/rover_twist"))
rviz_config_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_RVIZ_CONFIG", ""))
nav_command_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_NAV_COMMAND", ""))
nav_params_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_NAV_PARAMS", str(COMMON_ROOT / "nav2" / "zed_pointcloud_odom_nav2_mppi_params.yaml")))
stop_command_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_STOP_COMMAND", "./megarover_real/stop.sh"))
esp_port_var = tk.StringVar(value=os.environ.get("MEGAROVER_ESP_PORT", "/dev/ttyUSB0"))
delay_zed_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_ZED_DELAY_SEC", "2"))
delay_robot_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_ROBOT_DELAY_SEC", "8"))
delay_controller_var = tk.StringVar(value=os.environ.get("MEGAROVER_REAL_CONTROLLER_DELAY_SEC", "14"))

zed_depth_var = tk.StringVar(value=os.environ.get("MEGAROVER_ZED_DEPTH_MODE", "NEURAL_LIGHT"))
zed_slam_mode_var = tk.StringVar(value=os.environ.get("MEGAROVER_ZED_SLAM_MODE", "off"))
area_file_var = tk.StringVar(value=os.environ.get("MEGAROVER_ZED_AREA_FILE", str(PROJECT_ROOT / "maps" / "lab.area")))
nav_coverage_var = tk.BooleanVar(value=os.environ.get("MEGAROVER_NAV2_COVERAGE", "0") == "1")
nav_occupancy_var = tk.BooleanVar(value=os.environ.get("MEGAROVER_NAV2_OCCUPANCY", "0") == "1")
status_var = tk.StringVar(value="待機中")

main = ttk.Frame(root, padding=10)
main.grid(row=0, column=0, sticky="nsew")
main.columnconfigure(0, weight=1)
main.rowconfigure(0, weight=1)

tabs = ttk.Notebook(main)
tabs.grid(row=0, column=0, sticky="nsew")

robot_tab = ttk.Frame(tabs, padding=12)
sensor_tab = ttk.Frame(tabs, padding=12)
nav_tab = ttk.Frame(tabs, padding=12)
maint_tab = ttk.Frame(tabs, padding=12)
for tab in (robot_tab, sensor_tab, nav_tab, maint_tab):
    tab.columnconfigure(0, weight=1)
tabs.add(robot_tab, text="1. ロボット")
tabs.add(sensor_tab, text="2. センサ")
tabs.add(nav_tab, text="3. ナビゲーション")
tabs.add(maint_tab, text="4. 保守")

ttk.Label(robot_tab, text="実機は micro-ROS Agent、ZED2i、Megarover bringup の順に起動します。").grid(row=0, column=0, sticky="w", pady=(0, 10))
add_button(robot_tab, "micro-ROS Agent 起動", start_micro_ros, 1)
add_button(robot_tab, "ZED2i 起動", start_zed, 2)
add_button(robot_tab, "Megarover + EKF + RViz 起動", start_bringup, 3)
add_button(robot_tab, "基本スタック一括起動", start_full_stack, 4)
add_button(robot_tab, "フルスタックデモ起動", start_full_stack_demo, 5)
add_button(robot_tab, "全ノード停止", stop_all, 6)

ttk.Label(sensor_tab, text="ZED2iのdepth/SLAM設定。通常はNEURAL_LIGHT、SLAMはoffから開始します。").grid(row=0, column=0, sticky="w", pady=(0, 10))
sensor_box = ttk.LabelFrame(sensor_tab, text="ZED2i", padding=10)
sensor_box.grid(row=1, column=0, sticky="ew", pady=(0, 10))
sensor_box.columnconfigure(1, weight=1)
ttk.Label(sensor_box, text="depth_mode").grid(row=0, column=0, sticky="w")
ttk.Combobox(sensor_box, textvariable=zed_depth_var, values=("NEURAL_LIGHT", "NEURAL_PLUS", "PERFORMANCE", "QUALITY"), width=18).grid(row=0, column=1, sticky="w")
ttk.Label(sensor_box, text="slam_mode").grid(row=1, column=0, sticky="w", pady=(6, 0))
ttk.Combobox(sensor_box, textvariable=zed_slam_mode_var, values=("off", "mapping", "localization"), width=18).grid(row=1, column=1, sticky="w", pady=(6, 0))
ttk.Label(sensor_box, text="area_file").grid(row=2, column=0, sticky="w", pady=(6, 0))
ttk.Entry(sensor_box, textvariable=area_file_var).grid(row=2, column=1, sticky="ew", pady=(6, 0))
add_button(sensor_tab, "ZED2i 起動", start_zed, 2)
add_button(sensor_tab, "Area Memory 保存", save_area_memory, 3)
add_button(sensor_tab, "RViz 起動", start_rviz, 4)

ttk.Label(nav_tab, text="実機操作とNav2起動。Nav2の共通設定は隣の megarover_common を参照します。").grid(row=0, column=0, sticky="w", pady=(0, 10))
ttk.Checkbutton(nav_tab, text="Nav2起動時にcoverage goalsを有効化", variable=nav_coverage_var).grid(row=1, column=0, sticky="w")
ttk.Checkbutton(nav_tab, text="Nav2起動時にoccupancy mapperを有効化", variable=nav_occupancy_var).grid(row=2, column=0, sticky="w")
add_button(nav_tab, "キーボード teleop 起動", start_teleop, 3)
add_button(nav_tab, "Nav2 起動", start_nav2, 4)

ttk.Label(maint_tab, text="ファーム書き込み、micro-ROS Agentビルド、詳細設定。ESP32はVS-C3/SELECT E-STOP版を前提にします。").grid(row=0, column=0, sticky="w", pady=(0, 10))
add_button(maint_tab, "ESP32 ファーム書き込み", esp_upload, 1)
add_button(maint_tab, "micro-ROS Agent ビルド", build_micro_ros_agent, 2)
add_button(maint_tab, "詳細設定", open_options, 3)

status = ttk.Label(main, textvariable=status_var, relief="sunken", anchor="w", padding=(6, 3))
status.grid(row=1, column=0, sticky="ew", pady=(8, 0))

root.mainloop()
