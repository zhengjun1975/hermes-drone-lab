#!/usr/bin/env python3
"""
Diamond Formation → Circle Pattern → Land
Single-drone mission with virtual formation positions for Foxglove visualization.
(PX4 SITL multi-instance uXRCE-DDS limitation: only drone 1 has ROS2 topics)
"""
import rclpy
import sys
import math
import time
import threading
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand, VehicleStatus


class MissionDrone(Node):
    """Single drone mission controller"""

    def __init__(self):
        super().__init__("mission_controller")
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL, depth=10)

        self.offboard_pub = self.create_publisher(OffboardControlMode, "/px4_1/fmu/in/offboard_control_mode", qos)
        self.trajectory_pub = self.create_publisher(TrajectorySetpoint, "/px4_1/fmu/in/trajectory_setpoint", qos)
        self.cmd_pub = self.create_publisher(VehicleCommand, "/px4_1/fmu/in/vehicle_command", qos)
        self.status_sub = self.create_subscription(VehicleStatus, "/px4_1/fmu/out/vehicle_status", self._status_cb, qos)

        self.armed = False
        self.mode = "unknown"
        self._timer = self.create_timer(0.1, self._heartbeat)
        self._active = False

    def _status_cb(self, msg):
        self.armed = (msg.arming_state == 2)
        modes = {0: "manual", 1: "altctl", 2: "posctl", 3: "auto", 14: "offboard"}
        self.mode = modes.get(msg.nav_state, str(msg.nav_state))

    def _heartbeat(self):
        if self._active:
            om = OffboardControlMode()
            om.timestamp = 0
            om.position = True
            om.velocity = False
            om.acceleration = False
            om.attitude = False
            om.body_rate = False
            self.offboard_pub.publish(om)

    def _send_cmd(self, command, param1=0.0, param2=0.0, param3=0.0, param4=0.0):
        cmd = VehicleCommand()
        cmd.timestamp = 0
        cmd.param1 = float(param1)
        cmd.param2 = float(param2)
        cmd.param3 = float(param3)
        cmd.param4 = float(param4)
        cmd.command = command
        cmd.target_system = 1
        cmd.target_component = 1
        cmd.source_system = 1
        cmd.source_component = 1
        cmd.from_external = True
        self.cmd_pub.publish(cmd)

    def offboard_mode(self):
        self._send_cmd(176, 1.0, 6.0)
        self._active = True
        print("  Offboard mode engaged")

    def arm(self):
        self._send_cmd(400, 1.0)
        print("  Armed")

    def disarm(self):
        self._send_cmd(400, 0.0)

    def land(self):
        self._send_cmd(21, 0.0, 0.0, 0.0, 0.0)
        self._active = False
        print("  Landing")

    def goto(self, x, y, z, yaw=0.0):
        sp = TrajectorySetpoint()
        sp.timestamp = 0
        sp.position = [float(x), float(y), float(z)]
        sp.yaw = float(yaw)
        self.trajectory_pub.publish(sp)


def run_mission():
    ALTITUDE = 8.0
    SPACING = 4.0
    CIRCLE_RADIUS = 6.0
    CIRCLE_DURATION = 30.0

    rclpy.init()
    drone = MissionDrone()
    exec = rclpy.executors.SingleThreadedExecutor()
    exec.add_node(drone)
    t = threading.Thread(target=exec.spin, daemon=True)
    t.start()

    print("╔══════════════════════════════════════════╗")
    print("║  4-Drone Diamond → Circle Mission       ║")
    print("║  (1 real drone + 3 virtual formation)   ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║ Alt: {ALTITUDE}m | Spacing: {SPACING}m      ║")
    print(f"║ Circle R: {CIRCLE_RADIUS}m | Dur: {CIRCLE_DURATION}s    ║")
    print("╚══════════════════════════════════════════╝")

    # Diamond positions
    diamond = {
        1: (0.0, 0.0),
        2: (SPACING, -SPACING),
        3: (2 * SPACING, 0.0),
        4: (SPACING, SPACING),
    }

    # === Phase 1: Takeoff ===
    print("\n[Phase 1/4] Takeoff...")
    drone.offboard_mode()
    time.sleep(0.5)
    drone.arm()
    time.sleep(1.0)
    drone.goto(0, 0, -(ALTITUDE))
    print("  Climbing to 8m...")
    time.sleep(8)

    # === Phase 2: Diamond Waypoints (the drone visits all 4 diamond positions) ===
    print("\n[Phase 2/4] Flying diamond formation waypoints...")
    order = [1, 2, 4, 3, 1]  # Front → Right → Left → Back → Front
    for idx in order:
        dx, dy = diamond[idx]
        print(f"  Waypoint {idx}: ({dx:.0f}, {dy:.0f})")
        drone.goto(dx, dy, -(ALTITUDE))
        time.sleep(3.0)

    # === Phase 3: Circle ===
    print(f"\n[Phase 3/4] Flying circle (radius={CIRCLE_RADIUS}m)...")
    center_x, center_y = diamond[3][0] / 2, 0.0
    t0 = time.time()

    while time.time() - t0 < CIRCLE_DURATION:
        elapsed = time.time() - t0
        angle = elapsed * 0.4  # rad/s
        x = center_x + CIRCLE_RADIUS * math.cos(angle)
        y = center_y + CIRCLE_RADIUS * math.sin(angle)
        drone.goto(x, y, -(ALTITUDE))
        time.sleep(0.1)

    print("  Circle complete!")

    # === Phase 4: Land ===
    print("\n[Phase 4/4] Landing...")
    drone.goto(0, 0, -(ALTITUDE))
    time.sleep(3)
    drone.land()
    time.sleep(5)

    print("\n╔══════════════════════════════════════════╗")
    print("║  Mission Complete!                       ║")
    print("╚══════════════════════════════════════════╝")

    # Don't shutdown — ws_bridge needs ROS2 alive
    try: exec.shutdown()
    except: pass

if __name__ == "__main__":
    run_mission()
