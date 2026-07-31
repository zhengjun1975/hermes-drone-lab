#!/usr/bin/env python3
"""
Multi-Drone Formation Controller
Hermes-compatible offboard control for PX4 SITL drones.
Supports: Takeoff, Land, GoTo, Path Following, V-Formation, Circle Formation
"""
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from px4_msgs.msg import (
    OffboardControlMode, TrajectorySetpoint, VehicleCommand,
    VehicleStatus, VehicleOdometry
)
import math
import time
import threading
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DroneState:
    """Track state of a single drone"""
    ns: str
    armed: bool = False
    mode: str = "unknown"
    position: tuple = (0.0, 0.0, 0.0)
    target: tuple = (0.0, 0.0, -5.0)


class DroneController(Node):
    """Offboard controller for a single PX4 drone"""

    def __init__(self, drone_ns: str = ""):
        prefix = f"/{drone_ns}" if drone_ns else ""
        super().__init__(f"drone_controller_{drone_ns or 'default'}")

        self.drone_ns = drone_ns
        self.armed = False
        self.current_mode = "unknown"

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=10
        )

        # Publishers
        self.offboard_pub = self.create_publisher(
            OffboardControlMode, f"{prefix}/fmu/in/offboard_control_mode", qos)
        self.trajectory_pub = self.create_publisher(
            TrajectorySetpoint, f"{prefix}/fmu/in/trajectory_setpoint", qos)
        self.cmd_pub = self.create_publisher(
            VehicleCommand, f"{prefix}/fmu/in/vehicle_command", qos)

        # Subscribers
        self.status_sub = self.create_subscription(
            VehicleStatus, f"{prefix}/fmu/out/vehicle_status",
            self._status_cb, qos)
        self.odom_sub = self.create_subscription(
            VehicleOdometry, f"{prefix}/fmu/out/vehicle_odometry",
            self._odom_cb, qos)

        self.current_position = (0.0, 0.0, 0.0)
        self._timer = self.create_timer(0.1, self._offboard_loop)
        self._offboard_active = False

    def _status_cb(self, msg):
        self.armed = (msg.arming_state == 2)
        modes = {0: "manual", 1: "altctl", 2: "posctl", 3: "auto",
                 4: "acro", 5: "stabilized", 14: "offboard"}
        self.current_mode = modes.get(msg.nav_state, str(msg.nav_state))

    def _odom_cb(self, msg):
        self.current_position = (msg.position[0], msg.position[1], msg.position[2])

    def _offboard_loop(self):
        """Publish offboard heartbeat + current setpoint"""
        if not self._offboard_active:
            return
        # Offboard control mode heartbeat
        om = OffboardControlMode()
        om.timestamp = 0
        om.position = True
        om.velocity = False
        om.acceleration = False
        om.attitude = False
        om.body_rate = False
        self.offboard_pub.publish(om)

    def set_offboard_mode(self):
        """Switch to offboard mode"""
        cmd = VehicleCommand()
        cmd.timestamp = 0
        cmd.param1 = 1
        cmd.param2 = 6  # PX4 offboard mode
        cmd.command = 176
        cmd.target_system = 1
        cmd.target_component = 1
        cmd.source_system = 1
        cmd.source_component = 1
        cmd.from_external = True
        self.cmd_pub.publish(cmd)
        self._offboard_active = True
        self.get_logger().info(f"[{self.drone_ns}] Offboard mode set")

    def arm(self):
        """Arm the drone"""
        cmd = VehicleCommand()
        cmd.timestamp = 0
        cmd.param1 = 1.0  # Arm
        cmd.command = 400
        cmd.target_system = 1
        cmd.target_component = 1
        cmd.source_system = 1
        cmd.source_component = 1
        cmd.from_external = True
        self.cmd_pub.publish(cmd)
        self.get_logger().info(f"[{self.drone_ns}] Arm command sent")

    def disarm(self):
        cmd = VehicleCommand()
        cmd.timestamp = 0
        cmd.param1 = 0.0  # Disarm
        cmd.command = 400
        cmd.target_system = 1
        cmd.target_component = 1
        cmd.source_system = 1
        cmd.source_component = 1
        cmd.from_external = True
        self.cmd_pub.publish(cmd)

    def goto(self, x: float, y: float, z: float, yaw: float = 0.0):
        """Send position setpoint (NED frame: z negative = up)"""
        sp = TrajectorySetpoint()
        sp.timestamp = 0
        sp.position = [float(x), float(y), float(z)]
        sp.yaw = float(yaw)
        self.trajectory_pub.publish(sp)

    def takeoff(self, altitude: float = -5.0):
        """Takeoff to given altitude (NED: negative z = up)"""
        self.set_offboard_mode()
        time.sleep(0.5)
        self.arm()
        time.sleep(1.0)
        self.goto(0.0, 0.0, altitude)
        self.get_logger().info(f"[{self.drone_ns}] Taking off to {abs(altitude)}m")

    def land(self):
        """Land at current position"""
        cmd = VehicleCommand()
        cmd.timestamp = 0
        cmd.param1 = 0.0
        cmd.param2 = 0.0
        cmd.param4 = 0.0  # Land at current position
        cmd.command = 21  # MAV_CMD_NAV_LAND
        cmd.target_system = 1
        cmd.target_component = 1
        cmd.source_system = 1
        cmd.source_component = 1
        cmd.from_external = True
        self.cmd_pub.publish(cmd)
        self._offboard_active = False
        self.get_logger().info(f"[{self.drone_ns}] Landing")

    def follow_path(self, waypoints: List[tuple], speed: float = 2.0):
        """Follow a list of waypoints [(x,y,z), ...]"""
        self.get_logger().info(f"[{self.drone_ns}] Following {len(waypoints)} waypoints")
        for wp in waypoints:
            self.goto(wp[0], wp[1], wp[2])
            # Wait to reach waypoint (simplified: fixed time)
            # Production: check distance to waypoint
            time.sleep(2.0 / speed)


class FormationController:
    """Manages multiple drones in formation"""

    @staticmethod
    def v_formation(drones: List[DroneController], leader: DroneController,
                    altitude: float = -10.0, spacing: float = 3.0):
        """
        V-Formation: leader at front, followers form V behind
        """
        n = len(drones)
        for i, drone in enumerate(drones):
            if drone is leader:
                drone.goto(0.0, 0.0, altitude)
            else:
                side = 1 if i % 2 == 1 else -1
                row = (i + 1) // 2
                dx = -row * spacing
                dy = side * row * spacing * 0.7
                drone.goto(dx, dy, altitude)

    @staticmethod
    def circle_formation(drones: List[DroneController], center: tuple = (0, 0, -10),
                         radius: float = 5.0):
        """Circular formation around center"""
        n = len(drones)
        for i, drone in enumerate(drones):
            angle = 2 * math.pi * i / n
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            z = center[2]
            drone.goto(x, y, z)

    @staticmethod
    def line_formation(drones: List[DroneController], start: tuple = (0, 0, -10),
                       spacing: float = 3.0, axis: str = "x"):
        """Line formation along x or y axis"""
        for i, drone in enumerate(drones):
            if axis == "x":
                drone.goto(start[0] + i * spacing, start[1], start[2])
            else:
                drone.goto(start[0], start[1] + i * spacing, start[2])
