#!/usr/bin/env python3
"""
Rosbag Data Analyzer — Extract trajectories, compute formation errors, generate plots.
Hermes-compatible: outputs structured JSON + PNG files.
"""
import os
import sys
import json
import math
import argparse
from collections import defaultdict
from datetime import datetime

# Non-ROS dependencies: numpy, matplotlib
try:
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')  # Headless
    import matplotlib.pyplot as plt
except ImportError:
    print("[WARN] numpy/matplotlib not installed. Install with:")
    print("  pip3 install numpy matplotlib")
    print("  (Plots disabled, metrics only)")
    HAS_PLOT = False
else:
    HAS_PLOT = True

try:
    from rosidl_runtime_py.utilities import get_message
    from rclpy.serialization import deserialize_message
    import rosbag2_py
except ImportError:
    print("[WARN] ROS2 packages not available. Install with:")
    print("  sudo apt install ros-humble-rosbag2-py ros-humble-rosidl-runtime-py")
    HAS_ROS = False
else:
    HAS_ROS = True


class FormationAnalyzer:
    """Analyze multi-drone formation quality from rosbag"""

    def __init__(self, bag_path: str, formation_type: str = "v",
                 num_drones: int = 2, spacing: float = 5.0):
        self.bag_path = bag_path
        self.formation_type = formation_type
        self.num_drones = num_drones
        self.spacing = spacing
        self.trajectories = defaultdict(list)  # drone_id → [(t, x, y, z), ...]
        self.errors = defaultdict(list)        # drone_id → [(t, error), ...]

    def load_bag(self):
        """Extract vehicle_odometry from rosbag using rosbag2_py"""
        if not HAS_ROS:
            print("[ERROR] ROS2 packages not available, cannot read bag")
            return False

        reader = rosbag2_py.SequentialReader()
        storage_options = rosbag2_py.StorageOptions(uri=self.bag_path, storage_id='sqlite3')
        converter_options = rosbag2_py.ConverterOptions(
            input_serialization_format='cdr',
            output_serialization_format='cdr'
        )

        try:
            reader.open(storage_options, converter_options)
        except Exception as e:
            print(f"[ERROR] Cannot open bag: {e}")
            return False

        print(f"[ANALYZE] Reading rosbag: {self.bag_path}")
        count = 0
        topic_filter = "/fmu/out/vehicle_odometry"

        while reader.has_next():
            topic_name, msg_data, timestamp = reader.read_next()
            if topic_filter in topic_name:
                try:
                    msg_type = get_message('px4_msgs/msg/VehicleOdometry')
                    msg = deserialize_message(msg_data, msg_type)
                    t = timestamp / 1e9  # nanoseconds to seconds
                    x = msg.position[0]
                    y = msg.position[1]
                    z = msg.position[2]

                    # Determine drone ID from topic
                    drone_id = 1
                    for part in topic_name.split('/'):
                        if 'px4_' in part:
                            drone_id = int(part.split('_')[1])
                            break

                    self.trajectories[drone_id].append((t, x, y, z))
                    count += 1
                except Exception:
                    pass

        print(f"[ANALYZE] Extracted {count} odometry messages")
        return len(self.trajectories) > 0

    def compute_formation_errors(self):
        """Compute each drone's distance from desired formation position"""
        if not self.trajectories:
            print("[ANALYZE] No trajectory data to analyze")
            return False

        # Find time-aligned positions across drones
        all_times = set()
        for drone_id, points in self.trajectories.items():
            for t, x, y, z in points:
                all_times.add(round(t, 1))  # 0.1s resolution

        # Get desired formation positions
        desired_positions = self._get_desired_positions()

        print(f"[ANALYZE] Computing errors for {self.formation_type} formation...")
        sample_count = 0

        for t in sorted(all_times):
            positions = {}
            for drone_id, points in self.trajectories.items():
                # Find closest time point
                best = min(points, key=lambda p: abs(p[0] - t))
                if abs(best[0] - t) < 0.2:  # Within 200ms
                    positions[drone_id] = (best[1], best[2], best[3])

            if len(positions) >= self.num_drones:
                for drone_id, pos in positions.items():
                    desired = desired_positions.get(drone_id)
                    if desired:
                        dx = pos[0] - desired[0]
                        dy = pos[1] - desired[1]
                        dz = pos[2] - desired[2]
                        error = math.sqrt(dx*dx + dy*dy + dz*dz)
                        self.errors[drone_id].append((t, error))
                sample_count += 1

        print(f"[ANALYZE] Analyzed {sample_count} time samples")
        return True

    def _get_desired_positions(self):
        """Return desired (x,y,z) for each drone in the formation"""
        positions = {}
        if self.formation_type == "v":
            # Leader at origin
            positions[1] = (0.0, 0.0, -10.0)
            for i in range(2, self.num_drones + 1):
                side = 1 if i % 2 == 0 else -1
                row = (i - 1) // 2 + 1
                positions[i] = (
                    -row * self.spacing,
                    side * row * self.spacing * 0.7,
                    -10.0
                )
        elif self.formation_type == "circle":
            for i in range(1, self.num_drones + 1):
                angle = 2 * math.pi * (i - 1) / self.num_drones
                positions[i] = (
                    self.spacing * math.cos(angle),
                    self.spacing * math.sin(angle),
                    -10.0
                )
        elif self.formation_type == "line":
            for i in range(1, self.num_drones + 1):
                positions[i] = ((i - 1) * self.spacing, 0.0, -10.0)
        return positions

    def get_metrics(self) -> dict:
        """Compute summary metrics"""
        metrics = {
            "formation_type": self.formation_type,
            "num_drones": self.num_drones,
            "spacing": self.spacing,
            "trajectory_points": sum(len(v) for v in self.trajectories.values()),
        }

        if self.errors:
            all_errors = []
            per_drone = {}
            for drone_id, err_list in self.errors.items():
                errors_only = [e for _, e in err_list]
                if errors_only:
                    per_drone[f"drone_{drone_id}"] = {
                        "mean_error": round(np.mean(errors_only), 3),
                        "max_error": round(np.max(errors_only), 3),
                        "std_error": round(np.std(errors_only), 3),
                        "samples": len(errors_only),
                    }
                    all_errors.extend(errors_only)

            metrics["per_drone"] = per_drone
            if all_errors:
                metrics["overall"] = {
                    "mean_error": round(np.mean(all_errors), 3),
                    "max_error": round(np.max(all_errors), 3),
                    "std_error": round(np.std(all_errors), 3),
                    "total_samples": len(all_errors),
                }

            # Formation quality score (0-100, higher = better)
            # Based on mean error relative to spacing
            if all_errors:
                quality = max(0, 100 - (np.mean(all_errors) / self.spacing * 50))
                metrics["formation_quality_score"] = round(quality, 1)

        return metrics

    def plot_trajectories(self, output_dir: str):
        """Generate 2D and 3D trajectory plots"""
        if not HAS_PLOT:
            print("[PLOT] matplotlib not available, skipping plots")
            return []

        os.makedirs(output_dir, exist_ok=True)
        plots = []

        # 2D Top-down view
        fig, ax = plt.subplots(figsize=(10, 8))
        colors = plt.cm.tab10(np.linspace(0, 1, self.num_drones))

        for drone_id, points in sorted(self.trajectories.items()):
            xs = [p[1] for p in points]
            ys = [p[2] for p in points]
            ax.plot(xs, ys, color=colors[drone_id-1],
                    label=f'Drone {drone_id}', alpha=0.8, linewidth=1)
            # Mark start and end
            if xs:
                ax.scatter(xs[0], ys[0], color=colors[drone_id-1], marker='o', s=80)
                ax.scatter(xs[-1], ys[-1], color=colors[drone_id-1], marker='x', s=80)

        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_title(f'{self.formation_type.upper()} Formation — {self.num_drones} Drones (Top View)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')

        path = os.path.join(output_dir, 'trajectory_2d.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        plots.append(path)
        print(f"[PLOT] Saved: {path}")

        # 3D view
        fig = plt.figure(figsize=(12, 9))
        ax = fig.add_subplot(111, projection='3d')

        for drone_id, points in sorted(self.trajectories.items()):
            xs = [p[1] for p in points]
            ys = [p[2] for p in points]
            zs = [-p[3] for p in points]  # NED→ENU (flip z)
            ax.plot(xs, ys, zs, color=colors[drone_id-1],
                    label=f'Drone {drone_id}', alpha=0.8, linewidth=1)

        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_zlabel('Altitude (m)')
        ax.set_title(f'{self.formation_type.upper()} Formation — {self.num_drones} Drones (3D)')
        ax.legend()

        path = os.path.join(output_dir, 'trajectory_3d.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        plots.append(path)
        print(f"[PLOT] Saved: {path}")

        # Error over time
        if self.errors:
            fig, ax = plt.subplots(figsize=(10, 5))
            for drone_id, err_list in sorted(self.errors.items()):
                ts = [e[0] - self.errors[1][0][0] if self.errors[1] else 0 for e in err_list]
                es = [e[1] for e in err_list]
                ax.plot(ts, es, color=colors[drone_id-1],
                        label=f'Drone {drone_id}', alpha=0.8)

            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Formation Error (m)')
            ax.set_title('Formation Tracking Error Over Time')
            ax.legend()
            ax.grid(True, alpha=0.3)

            path = os.path.join(output_dir, 'error_over_time.png')
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            plots.append(path)
            print(f"[PLOT] Saved: {path}")

        return plots

    def generate_report(self, output_dir: str) -> str:
        """Generate a full Markdown report"""
        metrics = self.get_metrics()
        plots = self.plot_trajectories(output_dir) if HAS_PLOT else []

        report = f"""# Drone Formation Experiment Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Formation:** {self.formation_type.upper()}
**Drones:** {self.num_drones}
**Spacing:** {self.spacing}m

---

## Summary Metrics

"""
        if "overall" in metrics:
            o = metrics["overall"]
            q = metrics.get("formation_quality_score", "N/A")
            report += f"""| Metric | Value |
|--------|-------|
| Mean Error | {o['mean_error']} m |
| Max Error | {o['max_error']} m |
| Std Error | {o['std_error']} m |
| Quality Score | {q}/100 |
| Data Points | {o['total_samples']} |
"""

        if "per_drone" in metrics:
            report += "\n## Per-Drone Performance\n\n"
            report += "| Drone | Mean Error | Max Error | Std Error | Samples |\n"
            report += "|-------|-----------|----------|----------|--------|\n"
            for drone_id, d in sorted(metrics["per_drone"].items()):
                report += f"| {drone_id} | {d['mean_error']}m | {d['max_error']}m | {d['std_error']}m | {d['samples']} |\n"

        if plots:
            report += "\n## Visualizations\n\n"
            for p in plots:
                fname = os.path.basename(p)
                report += f"![{fname}]({fname})\n\n"

        report += "\n---\n*Report generated by Hermes AI Scientist*\n"

        report_path = os.path.join(output_dir, 'report.md')
        with open(report_path, 'w') as f:
            f.write(report)

        # Also save JSON
        json_path = os.path.join(output_dir, 'metrics.json')
        with open(json_path, 'w') as f:
            json.dump(metrics, f, indent=2)

        print(f"[REPORT] Saved: {report_path}")
        print(f"[METRICS] Saved: {json_path}")
        return report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Formation Experiment Analyzer")
    parser.add_argument("--bag", required=True, help="Path to rosbag directory")
    parser.add_argument("--formation", default="v", choices=["v", "circle", "line"])
    parser.add_argument("--drones", type=int, default=2)
    parser.add_argument("--spacing", type=float, default=5.0)
    parser.add_argument("--output", default=None, help="Output directory")
    args = parser.parse_args()

    if args.output is None:
        args.output = os.path.join(os.path.dirname(args.bag), 'analysis')

    analyzer = FormationAnalyzer(args.bag, args.formation, args.drones, args.spacing)
    analyzer.load_bag()
    analyzer.compute_formation_errors()
    metrics = analyzer.get_metrics()
    print(json.dumps(metrics, indent=2))
    analyzer.generate_report(args.output)
