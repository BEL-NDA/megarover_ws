#!/usr/bin/env python3
import argparse
import json
import math
import socket
import threading
import time

import rclpy
from geometry_msgs.msg import Twist
from megarover_perception_msgs.msg import PersonTrackArray


def clamp(value, limit):
    limit = abs(float(limit))
    return max(-limit, min(limit, float(value)))


def normalize_angle(angle):
    return math.atan2(math.sin(float(angle)), math.cos(float(angle)))


class TrackFollowController:
    def __init__(self, args):
        self.args = args
        self.lock = threading.Lock()
        self.enabled = False
        self.track_id = None
        self.command_stamp = 0.0
        self.latest_tracks = []
        self.latest_tracks_stamp = 0.0
        self.prev_xy = None
        self.prev_yaw = None
        self.prev_target_stamp = None
        self.prev_error = None
        self.prev_error_stamp = None
        self.integral_error = 0.0
        self.last_cmd = 0.0
        self.last_log = 0.0
        self.stop_event = threading.Event()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((args.bind, int(args.port)))
        self.sock.settimeout(0.2)

        self.node = rclpy.create_node("track_follow_controller")
        self.pub = self.node.create_publisher(Twist, args.cmd_vel_topic, 10)
        self.sub = self.node.create_subscription(
            PersonTrackArray,
            args.tracks_topic,
            self.tracks_callback,
            int(args.qos_depth),
        )

    def start_udp_thread(self):
        thread = threading.Thread(target=self.udp_loop, name="track_follow_udp", daemon=True)
        thread.start()
        return thread

    def udp_loop(self):
        while not self.stop_event.is_set():
            try:
                data, _addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                msg = json.loads(data.decode("ascii"))
                enable = bool(msg.get("enable", True))
                track_id = msg.get("track_id", None)
                if enable and track_id is None:
                    raise ValueError("enable command requires track_id")
            except Exception as exc:
                print(f"bad track-follow UDP packet: {exc}", flush=True)
                continue

            with self.lock:
                self.enabled = enable
                self.track_id = int(track_id) if enable else None
                self.command_stamp = time.monotonic()
                self.prev_xy = None
                self.prev_yaw = None
                self.prev_target_stamp = None
                self.prev_error = None
                self.prev_error_stamp = None
                self.integral_error = 0.0
                self.last_cmd = 0.0
            if enable:
                print(f"TRACK_FOLLOW command enable track_id={int(track_id)}", flush=True)
            else:
                print("TRACK_FOLLOW command disable", flush=True)
                self.publish_zero()

    def tracks_callback(self, msg):
        now = time.monotonic()
        tracks = []
        for track in msg.tracks:
            tracks.append(
                {
                    "track_id": int(track.track_id),
                    "x": float(track.position_3d.x),
                    "y": float(track.position_3d.y),
                    "z": float(track.position_3d.z),
                    "confidence": float(track.confidence),
                    "tracking_state": int(track.tracking_state),
                }
            )
        with self.lock:
            self.latest_tracks = tracks
            self.latest_tracks_stamp = now

    def publish_zero(self):
        msg = Twist()
        self.pub.publish(msg)

    def find_target_locked(self, track_id):
        for track in self.latest_tracks:
            if int(track["track_id"]) == int(track_id):
                return track
        return None

    def target_xy_yaw(self, track):
        # PersonTrack positions are already expressed with x forward and y left
        # in the current real-robot perception stack.
        base_x = float(track["x"])
        base_y = float(track["y"])
        if not math.isfinite(base_x) or not math.isfinite(base_y):
            return None
        if math.hypot(base_x, base_y) < 0.05:
            return None
        return (base_x, base_y), math.atan2(base_y, base_x)

    def validate_target_motion_locked(self, xy, yaw, now):
        if self.prev_xy is None or self.prev_yaw is None or self.prev_target_stamp is None:
            self.prev_xy = xy
            self.prev_yaw = float(yaw)
            self.prev_target_stamp = float(now)
            return True

        dt = max(1e-3, float(now) - float(self.prev_target_stamp))
        if dt > 1.0:
            self.prev_xy = xy
            self.prev_yaw = float(yaw)
            self.prev_target_stamp = float(now)
            return True

        xy_jump = math.hypot(float(xy[0]) - float(self.prev_xy[0]), float(xy[1]) - float(self.prev_xy[1]))
        yaw_jump = abs(normalize_angle(float(yaw) - float(self.prev_yaw)))
        self.prev_xy = xy
        self.prev_yaw = float(yaw)
        self.prev_target_stamp = float(now)

        return (
            xy_jump <= float(self.args.max_target_jump_m)
            and yaw_jump <= math.radians(float(self.args.max_yaw_jump_deg))
        )

    def compute_cmd_locked(self, yaw_error, now):
        dt = 0.0
        if self.prev_error_stamp is not None:
            dt = max(1e-3, min(0.5, float(now) - float(self.prev_error_stamp)))

        derivative = 0.0
        if dt > 0.0 and self.prev_error is not None:
            derivative = normalize_angle(float(yaw_error) - float(self.prev_error)) / dt
            self.integral_error += float(yaw_error) * dt
            integral_limit = max(
                math.radians(5.0),
                abs(float(self.args.max_angular_z)) / max(float(self.args.ki), 1e-6),
            )
            self.integral_error = clamp(self.integral_error, integral_limit)

        self.prev_error = float(yaw_error)
        self.prev_error_stamp = float(now)

        raw_cmd = (
            float(self.args.kp) * float(yaw_error)
            + float(self.args.ki) * float(self.integral_error)
            + float(self.args.kd) * float(derivative)
        )
        return clamp(raw_cmd, float(self.args.max_angular_z))

    def update(self):
        now = time.monotonic()
        with self.lock:
            enabled = bool(self.enabled)
            track_id = self.track_id
            command_age = now - float(self.command_stamp)
            tracks_age = now - float(self.latest_tracks_stamp)

            if not enabled or track_id is None:
                cmd = 0.0
                reason = "disabled"
                yaw_error = None
                xy = None
            elif command_age > float(self.args.command_timeout):
                self.enabled = False
                self.track_id = None
                cmd = 0.0
                reason = "command_timeout"
                yaw_error = None
                xy = None
            elif tracks_age > float(self.args.tracks_timeout):
                cmd = 0.0
                reason = "tracks_stale"
                yaw_error = None
                xy = None
            else:
                target = self.find_target_locked(track_id)
                if target is None:
                    cmd = 0.0
                    reason = "target_missing"
                    yaw_error = None
                    xy = None
                else:
                    xy_yaw = self.target_xy_yaw(target)
                    if xy_yaw is None:
                        cmd = 0.0
                        reason = "bad_target_position"
                        yaw_error = None
                        xy = None
                    else:
                        xy, yaw_error = xy_yaw
                        if not self.validate_target_motion_locked(xy, yaw_error, now):
                            self.enabled = False
                            self.track_id = None
                            cmd = 0.0
                            reason = "target_jump"
                        elif abs(float(yaw_error)) <= math.radians(float(self.args.finish_angle_deg)):
                            cmd = 0.0
                            reason = "deadband"
                        else:
                            cmd = self.compute_cmd_locked(yaw_error, now)
                            reason = "publish"
            self.last_cmd = float(cmd)

        msg = Twist()
        msg.angular.z = float(cmd)
        self.pub.publish(msg)

        if now - self.last_log >= float(self.args.log_interval):
            self.last_log = now
            if yaw_error is None or xy is None:
                print(f"TRACK_FOLLOW reason={reason} cmd={cmd:.3f}", flush=True)
            else:
                print(
                    "TRACK_FOLLOW "
                    f"reason={reason} track_id={int(track_id)} "
                    f"yaw_error_deg={math.degrees(float(yaw_error)):.2f} "
                    f"cmd={float(cmd):.3f} "
                    f"target_x={float(xy[0]):.2f} target_y={float(xy[1]):.2f}",
                    flush=True,
                )

    def close(self):
        self.stop_event.set()
        try:
            self.publish_zero()
            time.sleep(0.05)
            self.publish_zero()
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
        self.node.destroy_node()


def main():
    parser = argparse.ArgumentParser(description="Track-id UDP command to /rover_twist controller")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=50112)
    parser.add_argument("--tracks_topic", default="/perception/people/tracks")
    parser.add_argument("--cmd_vel_topic", default="/rover_twist")
    parser.add_argument("--rate", type=float, default=30.0)
    parser.add_argument("--qos_depth", type=int, default=10)
    parser.add_argument("--kp", type=float, default=0.40)
    parser.add_argument("--ki", type=float, default=0.0)
    parser.add_argument("--kd", type=float, default=0.02)
    parser.add_argument("--max_angular_z", type=float, default=0.35)
    parser.add_argument("--finish_angle_deg", type=float, default=2.0)
    parser.add_argument("--max_target_jump_m", type=float, default=2.0)
    parser.add_argument("--max_yaw_jump_deg", type=float, default=45.0)
    parser.add_argument("--tracks_timeout", type=float, default=0.5)
    parser.add_argument("--command_timeout", type=float, default=30.0)
    parser.add_argument("--log_interval", type=float, default=0.5)
    args = parser.parse_args()

    rclpy.init()
    controller = TrackFollowController(args)
    udp_thread = controller.start_udp_thread()
    print(
        "TRACK_FOLLOW controller listening on "
        f"{args.bind}:{int(args.port)}, tracking {args.tracks_topic}, publishing {args.cmd_vel_topic}",
        flush=True,
    )

    period = 1.0 / max(float(args.rate), 1.0)
    try:
        while rclpy.ok():
            rclpy.spin_once(controller.node, timeout_sec=0.0)
            controller.update()
            time.sleep(period)
    finally:
        controller.close()
        udp_thread.join(timeout=0.5)
        rclpy.shutdown()


if __name__ == "__main__":
    main()
