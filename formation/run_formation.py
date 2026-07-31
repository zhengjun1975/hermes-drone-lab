#!/usr/bin/env python3
"""
Formation Control Node — ROS2 node for commanding N drones in formation.
Hermes orchestrates this via launch scripts.
"""
import rclpy
import sys
sys.path.insert(0, "/home/ubuntu/dev/px4_formation")
from formation_controller import DroneController, FormationController
import threading
import time


def run_formation(num_drones: int, formation_type: str,
                  altitude: float, spacing: float, duration: float):
    """Run a formation experiment"""
    rclpy.init()

    # Create controllers
    drones = []
    executors = []
    for i in range(1, num_drones + 1):
        ns = f"px4_{i}"
        ctrl = DroneController(ns)
        drones.append(ctrl)
        exec = rclpy.executors.SingleThreadedExecutor()
        exec.add_node(ctrl)
        executors.append(exec)

    # Spin all in background
    threads = []
    for exec in executors:
        t = threading.Thread(target=exec.spin, daemon=True)
        t.start()
        threads.append(t)

    print(f"[FORMATION] {num_drones} drones, {formation_type} formation")
    print(f"[FORMATION] Altitude: {altitude}m, Spacing: {spacing}m")

    # Takeoff all drones
    print("[FORMATION] Taking off...")
    for i, drone in enumerate(drones):
        drone.takeoff(altitude=-(abs(float(altitude))))
        time.sleep(2.0)  # Stagger takeoffs

    # Wait for altitude
    print("[FORMATION] Holding position...")
    time.sleep(5.0)

    fc = FormationController()

    # Apply formation
    print(f"[FORMATION] Setting {formation_type} formation...")
    leader = drones[0]
    if formation_type == "v":
        fc.v_formation(drones, leader, altitude=-(abs(float(altitude))),
                       spacing=float(spacing))
    elif formation_type == "circle":
        fc.circle_formation(drones, center=(0, 0, -(abs(float(altitude)))),
                           radius=float(spacing))
    elif formation_type == "line":
        fc.line_formation(drones, start=(0, 0, -(abs(float(altitude)))),
                         spacing=float(spacing))
    else:
        print(f"Unknown formation: {formation_type}")

    print(f"[FORMATION] Running for {duration}s...")
    start = time.time()

    try:
        while time.time() - start < float(duration):
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

    # Land
    print("[FORMATION] Landing all drones...")
    for drone in drones:
        drone.land()
        time.sleep(1.0)

    time.sleep(3.0)
    print("[FORMATION] Experiment complete!")

    for exec in executors:
        exec.shutdown()
    rclpy.shutdown()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--drones", type=int, default=2)
    p.add_argument("--formation", default="v", choices=["v", "circle", "line"])
    p.add_argument("--altitude", type=float, default=10.0)
    p.add_argument("--spacing", type=float, default=5.0)
    p.add_argument("--duration", type=float, default=60.0)
    args = p.parse_args()

    run_formation(args.drones, args.formation,
                  args.altitude, args.spacing, args.duration)
