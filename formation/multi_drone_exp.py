#!/usr/bin/env python3
"""
Multi-Drone Formation Experiment Launcher
Hermes-compatible: single command to run N drones in formation.

Usage: python3 multi_drone_exp.py --drones 3 --formation v --altitude 10
"""
import subprocess
import sys
import time
import signal
import os
import argparse


class MultiDroneExperiment:
    def __init__(self, num_drones: int = 2, model: str = "iris",
                 world: str = "empty", headless: bool = True):
        self.num_drones = num_drones
        self.model = model
        self.world = world
        self.headless = headless
        self.processes = []
        self.px4_home = os.path.expanduser("~/dev/PX4-Autopilot")

    def start(self):
        """Launch N PX4 SITL drones + MicroXRCEAgent"""
        print(f"╔══════════════════════════════════════════╗")
        print(f"║  Multi-Drone Experiment                 ║")
        print(f"╠══════════════════════════════════════════╣")
        print(f"║ Drones: {self.num_drones}")
        print(f"║ Model:  {self.model}")
        print(f"║ World:  {self.world}")
        print(f"╚══════════════════════════════════════════╝")
        print()

        # Source environment
        env = os.environ.copy()
        env["HEADLESS"] = "1" if self.headless else "0"

        # Use PX4's multi-drone script
        cmd = [
            "bash",
            f"{self.px4_home}/Tools/simulation/gazebo-classic/sitl_multiple_run.sh",
            str(self.num_drones)
        ]

        print(f"[1/4] Launching {self.num_drones} drone SITL instances...")
        self.sitl_proc = subprocess.Popen(
            cmd, env=env, cwd=self.px4_home,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        self.processes.append(self.sitl_proc)

        # Wait for Gazebo
        print("[2/4] Waiting for Gazebo + PX4...")
        time.sleep(15)

        # Start MicroXRCEAgent
        print("[3/4] Starting MicroXRCEAgent...")
        self.agent_proc = subprocess.Popen(
            ["MicroXRCEAgent", "udp4", "-p", "8888"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        self.processes.append(self.agent_proc)
        time.sleep(5)

        print("[4/4] Experiment ready!")
        print()
        print("All drones online. Use:")
        print("  ros2 topic list | grep fmu")
        print("  python3 formation_controller.py --drones N --formation v")
        print()
        return True

    def stop(self):
        """Kill all processes"""
        print("Stopping experiment...")
        for proc in self.processes:
            try:
                proc.terminate()
            except Exception:
                pass
        time.sleep(2)
        # Force kill remaining
        for name in ["px4", "gzserver", "gzclient", "MicroXRCEAgent"]:
            subprocess.run(["pkill", "-f", name], capture_output=True)
        print("All processes stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Drone Formation Experiment")
    parser.add_argument("--drones", type=int, default=2, help="Number of drones")
    parser.add_argument("--model", default="iris", help="Drone model")
    parser.add_argument("--world", default="empty", help="Gazebo world")
    parser.add_argument("--headless", type=int, default=1, help="Headless mode (1/0)")
    args = parser.parse_args()

    exp = MultiDroneExperiment(
        num_drones=args.drones,
        model=args.model,
        world=args.world,
        headless=bool(args.headless)
    )

    def signal_handler(sig, frame):
        print("\nShutting down...")
        exp.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        exp.start()
        print("Press Ctrl+C to stop...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        exp.stop()
