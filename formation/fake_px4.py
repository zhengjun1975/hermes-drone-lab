#!/usr/bin/env python3
"""Fake PX4 position publisher — perfect circle for 3D viewer"""
import rclpy, math, time
from rclpy.node import Node
from px4_msgs.msg import VehicleLocalPosition

class FakePX4(Node):
    def __init__(self):
        super().__init__("fake_px4")
        self.pub = self.create_publisher(VehicleLocalPosition, "/fmu/out/vehicle_local_position_v1", 10)
        self.t = 0.0
        self.create_timer(0.1, self._loop)
        print("[FAKE PX4] Publishing circle trajectory...")

    def _loop(self):
        msg = VehicleLocalPosition()
        msg.timestamp = 0
        msg.timestamp_sample = 0
        msg.xy_valid = True
        msg.z_valid = True

        # Circle: R=8m, period=40s
        angle = self.t * 2 * math.pi / 40.0
        if self.t > 40:
            # Land
            msg.x = 0.0
            msg.y = 0.0
            msg.z = 0.0
        else:
            msg.x = 8.0 * math.cos(angle)
            msg.y = 8.0 * math.sin(angle)
            msg.z = -10.0 if self.t > 3 else -self.t * (10/3)  # takeoff ramp

        self.pub.publish(msg)
        self.t += 0.1

rclpy.init()
node = FakePX4()
rclpy.spin(node)
