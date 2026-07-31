#!/usr/bin/env python3
"""Pure Circle Mission"""
import rclpy, math, time, threading
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand

class Drone(Node):
    def __init__(self):
        super().__init__("circle_mission")
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.TRANSIENT_LOCAL, depth=10)
        self.off_pub = self.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", qos)
        self.traj_pub = self.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", qos)
        self.cmd_pub = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", qos)
        self._active = False
        self.create_timer(0.1, self._hb)
    def _hb(self):
        if self._active:
            om = OffboardControlMode(); om.timestamp = 0; om.position = True
            self.off_pub.publish(om)
    def _cmd(self, cmd, p1=0.0, p2=0.0):
        c = VehicleCommand(); c.timestamp = 0; c.param1 = float(p1); c.param2 = float(p2)
        c.command = cmd; c.target_system = 1; c.target_component = 1
        c.source_system = 1; c.source_component = 1; c.from_external = True
        self.cmd_pub.publish(c)
    def offboard(self): self._cmd(176, 1.0, 6.0); self._active = True
    def arm(self): self._cmd(400, 1.0)
    def land(self): self._cmd(21); self._active = False
    def goto(self, x, y, z):
        sp = TrajectorySetpoint(); sp.timestamp = 0
        sp.position = [float(x), float(y), float(z)]; sp.yaw = 0.0
        self.traj_pub.publish(sp)

print("╔══════════════════╗")
print("║  Circle Mission  ║")
print("╚══════════════════╝")

rclpy.init()
d = Drone()
exec = rclpy.executors.SingleThreadedExecutor(); exec.add_node(d)
t = threading.Thread(target=exec.spin, daemon=True); t.start()

# Takeoff
d.offboard(); time.sleep(0.5); d.arm(); time.sleep(1)
d.goto(0, 0, -10); print("Takeoff 10m..."); time.sleep(8)

# Circle
R, C = 8.0, 40.0
print(f"Circle R={R}m {C}s...")
t0 = time.time()
while time.time() - t0 < C:
    a = (time.time() - t0) * 0.6
    d.goto(R * math.cos(a), R * math.sin(a), -10)
    time.sleep(0.1)

# Land
print("Landing...")
d.goto(0, 0, -10); time.sleep(2)
d.land(); time.sleep(5)
print("Done!")

try: exec.shutdown()
except: pass
