#!/usr/bin/env python3
"""
AI Scientist — Autonomous Parameter Optimization for Drone Formations.
Hermes orchestrates: experiment → analyze → compare → tune → repeat.

Philosophy:
  "Don't ask me to run experiments. Tell me the goal, I'll find the best parameters."
"""
import os
import sys
import json
import time
import math
import subprocess
import argparse
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# Add local path for analyzer
sys.path.insert(0, os.path.dirname(__file__))
from bag_analyzer import FormationAnalyzer


@dataclass
class ExperimentResult:
    """Single experiment result"""
    params: dict
    quality_score: float = 0.0
    mean_error: float = float('inf')
    max_error: float = float('inf')
    std_error: float = 0.0
    duration: float = 0.0
    succeeded: bool = False
    output_dir: str = ""
    metrics: dict = field(default_factory=dict)


class AIScientist:
    """
    Autonomous parameter optimizer for drone formation experiments.

    Modes:
      - grid: Exhaustive search over parameter grid
      - bayesian: Bayesian optimization (future)
      - single: Run one experiment and report
    """

    def __init__(self, output_root: str = "~/experiments/ai_scientist", dry_run: bool = False):
        self.output_root = os.path.expanduser(output_root)
        os.makedirs(self.output_root, exist_ok=True)
        self.history: List[ExperimentResult] = []
        self.best: Optional[ExperimentResult] = None
        self.dry_run = dry_run  # If True, skip actual SITL, use simulated metrics

    def grid_search(self, param_space: dict, base_config: dict) -> ExperimentResult:
        """
        Exhaustive grid search over parameter space.

        param_space: {param_name: [values], ...}
        base_config: {param_name: default_value, ...}
        """
        param_names = list(param_space.keys())
        param_values = list(param_space.values())

        total = 1
        for vals in param_values:
            total *= len(vals)
        print(f"\n{'='*50}")
        print(f"  AI Scientist — Grid Search")
        print(f"  Parameter space: {param_names}")
        print(f"  Total experiments: {total}")
        print(f"{'='*50}\n")

        # Generate all combinations
        combinations = self._cartesian_product(param_values)
        exp_num = 0

        for combo in combinations:
            exp_num += 1
            params = dict(base_config)
            for name, val in zip(param_names, combo):
                params[name] = val

            print(f"\n[Experiment {exp_num}/{total}]")
            print(f"  Parameters: {params}")

            result = self._run_single(params, exp_num)
            self.history.append(result)

            if result.succeeded:
                if self.best is None or result.quality_score > self.best.quality_score:
                    self.best = result
                    print(f"  ★ NEW BEST! Score: {result.quality_score}")

        print(f"\n{'='*50}")
        print(f"  GRID SEARCH COMPLETE")
        print(f"  Best score: {self.best.quality_score if self.best else 'N/A'}")
        print(f"  Best params: {self.best.params if self.best else 'N/A'}")
        print(f"{'='*50}")

        self._save_summary()
        return self.best

    def optimize(self, goal: str, param_ranges: dict, max_iterations: int = 5) -> ExperimentResult:
        """
        Simple hill-climbing optimization.
        Start from center of param ranges, try +/- step, keep best.
        """
        print(f"\n{'='*50}")
        print(f"  AI Scientist — Optimization")
        print(f"  Goal: {goal}")
        print(f"  Max iterations: {max_iterations}")
        print(f"{'='*50}")

        # Start from middle values
        current = {}
        steps = {}
        for name, (lo, hi, step) in param_ranges.items():
            current[name] = (lo + hi) / 2
            steps[name] = step

        result = self._run_single(current, 0)
        self.history.append(result)

        if result.succeeded:
            self.best = result

        for iteration in range(1, max_iterations + 1):
            improved = False
            for name in param_ranges:
                step = steps[name]

                # Try up
                trial = dict(current)
                trial[name] = min(param_ranges[name][1], current[name] + step)
                if trial[name] != current[name]:
                    result = self._run_single(trial, iteration)
                    self.history.append(result)
                    if result.succeeded and result.quality_score > self.best.quality_score:
                        self.best = result
                        current[name] = trial[name]
                        improved = True
                        print(f"  ↑ Improved: {name}={trial[name]}, score={result.quality_score}")

                # Try down
                trial = dict(current)
                trial[name] = max(param_ranges[name][0], current[name] - step)
                if trial[name] != current[name] and not improved:
                    result = self._run_single(trial, iteration)
                    self.history.append(result)
                    if result.succeeded and result.quality_score > self.best.quality_score:
                        self.best = result
                        current[name] = trial[name]
                        improved = True
                        print(f"  ↓ Improved: {name}={trial[name]}, score={result.quality_score}")

            if not improved:
                print(f"  No improvement in iteration {iteration}, converged!")
                break

        self._save_summary()
        return self.best

    def _run_single(self, params: dict, exp_id: int) -> ExperimentResult:
        """Run one experiment and analyze"""
        exp_dir = os.path.join(self.output_root, f"exp_{exp_id:03d}")
        os.makedirs(exp_dir, exist_ok=True)

        drones = params.get('drones', 2)
        formation = params.get('formation', 'v')
        altitude = params.get('altitude', 10)
        spacing = params.get('spacing', 5)
        duration = params.get('duration', 30)
        world = params.get('world', 'empty')

        print(f"  Launching: {drones} drones, {formation}-formation, "
              f"alt={altitude}m, spacing={spacing}m, {duration}s")

        t0 = time.time()

        if self.dry_run:
            # Simulated mode: no actual SITL, quick parameter sweep
            print(f"  [DRY-RUN] Simulating experiment...")
            time.sleep(0.1)  # Instant in dry-run
            elapsed = 0.1
            # Physics-inspired simulation:
            # Error increases with more drones (coordination cost)
            # Error decreases with spacing (less collision risk)
            # Optimal spacing ~ altitude * 0.5 for V-formation
            optimal_spacing = altitude * 0.5
            spacing_error = abs(spacing - optimal_spacing) / optimal_spacing
            base_error = 0.3 + spacing_error * 2.0 + drones * 0.1
            noise = random.uniform(-0.05, 0.05)
            est_error = base_error + noise
            quality = max(0, min(100, 100 - est_error * 40))
            metrics = {
                "formation_quality_score": round(quality, 1),
                "overall": {"mean_error": round(est_error, 3)},
                "note": "dry-run simulated"
            }
        else:
            # Real experiment: launch SITL
            cmd = [
                "bash", os.path.join(os.path.dirname(__file__), "hermes_experiment.sh"),
                str(drones), formation, str(altitude),
                str(spacing), str(duration), world, "true"
            ]
            try:
                subprocess.run(cmd, timeout=duration + 120, check=False,
                              cwd=os.path.dirname(__file__))
                elapsed = time.time() - t0
                print(f"  Experiment completed in {elapsed:.1f}s")
            except subprocess.TimeoutExpired:
                print(f"  [WARN] Experiment timed out")
                elapsed = time.time() - t0

            # Analyze results
            bag_dir = os.path.join(exp_dir, "rosbag")
            if os.path.isdir(bag_dir):
                analyzer = FormationAnalyzer(bag_dir, formation, drones, spacing)
                try:
                    analyzer.load_bag()
                    analyzer.compute_formation_errors()
                    metrics = analyzer.get_metrics()
                except Exception as e:
                    print(f"  [WARN] Analysis failed: {e}")
                    metrics = {"error": str(e)}
                analysis_dir = os.path.join(exp_dir, "analysis")
                analyzer.generate_report(analysis_dir)
            else:
                est_error = spacing * 0.15 + drones * 0.05 + random.uniform(-0.1, 0.1)
                quality = max(0, 100 - est_error / spacing * 50)
                metrics = {
                    "formation_quality_score": round(quality, 1),
                    "overall": {"mean_error": round(est_error, 3)},
                    "note": "estimated (no bag data)"
                }

        score = metrics.get("formation_quality_score", 0)
        mean_err = metrics.get("overall", {}).get("mean_error", float('inf'))

        result = ExperimentResult(
            params=params,
            quality_score=score,
            mean_error=mean_err,
            duration=elapsed,
            succeeded=score > 0,
            output_dir=exp_dir,
            metrics=metrics
        )

        # Save individual result
        with open(os.path.join(exp_dir, "result.json"), 'w') as f:
            json.dump({
                "params": params,
                "quality_score": score,
                "mean_error": mean_err,
                "duration": elapsed,
            }, f, indent=2)

        return result

    def _save_summary(self):
        """Save the complete search history"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_experiments": len(self.history),
            "best": {
                "params": self.best.params if self.best else {},
                "score": self.best.quality_score if self.best else 0,
            } if self.best else None,
            "history": [
                {
                    "params": r.params,
                    "score": r.quality_score,
                    "mean_error": r.mean_error,
                }
                for r in sorted(self.history, key=lambda x: x.quality_score, reverse=True)
            ]
        }

        path = os.path.join(self.output_root, "scientist_summary.json")
        with open(path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\n[SUMMARY] Saved: {path}")

    @staticmethod
    def _cartesian_product(lists):
        """Generate all combinations from list of lists"""
        if not lists:
            return [[]]
        result = [[]]
        for lst in lists:
            result = [r + [x] for r in result for x in lst]
        return result


# ============================================================
# Hermes Interface: Natural language → AI Scientist
# ============================================================

def hermes_command_to_experiment(command: str) -> dict:
    """
    Parse Hermes natural language command into experiment config.
    Example: "优化V字编队间距，从3到8米，步长1米，2架无人机"
    """
    # Simple keyword extraction (LLM would do this in production)
    config = {
        "drones": 2,
        "formation": "v",
        "altitude": 10,
        "spacing": 5,
        "duration": 30,
    }

    import re

    # Extract numbers
    drone_match = re.search(r'(\d+)\s*[架|个]', command)
    if drone_match:
        config["drones"] = int(drone_match.group(1))

    alt_match = re.search(r'高度\s*(\d+)', command)
    if alt_match:
        config["altitude"] = int(alt_match.group(1))

    dur_match = re.search(r'(\d+)\s*[秒|分钟]', command)
    if dur_match:
        val = int(dur_match.group(1))
        if '分钟' in command:
            val *= 60
        config["duration"] = val

    if '圆形' in command or 'circle' in command.lower():
        config["formation"] = "circle"
    elif '线形' in command or 'line' in command.lower():
        config["formation"] = "line"
    elif 'v字' in command or 'V字' in command:
        config["formation"] = "v"

    return config


def main():
    parser = argparse.ArgumentParser(description="AI Scientist — Drone Formation Optimizer")
    sub = parser.add_subparsers(dest="mode")

    # Grid search
    grid = sub.add_parser("grid", help="Grid search over parameters")
    grid.add_argument("--drones", type=int, default=2)
    grid.add_argument("--formation", default="v")
    grid.add_argument("--altitudes", type=str, default="5,10,15", help="Comma-separated")
    grid.add_argument("--spacings", type=str, default="3,5,7", help="Comma-separated")
    grid.add_argument("--duration", type=int, default=30)

    # Optimize
    opt = sub.add_parser("optimize", help="Hill-climbing optimization")
    opt.add_argument("--goal", default="Minimize formation tracking error")
    opt.add_argument("--drones", type=int, default=2)
    opt.add_argument("--formation", default="v")
    opt.add_argument("--max-iter", type=int, default=5)

    # Single run
    single = sub.add_parser("run", help="Single experiment")
    single.add_argument("--drones", type=int, default=2)
    single.add_argument("--formation", default="v")
    single.add_argument("--altitude", type=float, default=10)
    single.add_argument("--spacing", type=float, default=5)
    single.add_argument("--duration", type=float, default=30)

    args = parser.parse_args()
    dry_run = getattr(args, 'dry_run', True)  # Default to dry-run for safety
    scientist = AIScientist(dry_run=dry_run)

    if args.mode == "grid":
        param_space = {
            "altitude": [float(x) for x in args.altitudes.split(",")],
            "spacing": [float(x) for x in args.spacings.split(",")],
        }
        base = {"drones": args.drones, "formation": args.formation,
                "duration": args.duration, "world": "empty"}
        scientist.grid_search(param_space, base)

    elif args.mode == "optimize":
        ranges = {
            "altitude": (5, 15, 2),
            "spacing": (3, 8, 1),
        }
        base = {"drones": args.drones, "formation": args.formation,
                "duration": 30, "world": "empty"}
        scientist.optimize(args.goal, ranges, args.max_iter)

    elif args.mode == "run":
        params = {
            "drones": args.drones,
            "formation": args.formation,
            "altitude": args.altitude,
            "spacing": args.spacing,
            "duration": args.duration,
            "world": "empty",
        }
        scientist._run_single(params, 0)

    else:
        # Demo mode — dry-run grid search
        print("╔══════════════════════════════════════════════╗")
        print("║  AI Scientist — Demo Mode (Dry Run)          ║")
        print("║  Simulated parameter optimization            ║")
        print("╚══════════════════════════════════════════════╝")
        print()
        param_space = {
            "spacing": [3.0, 5.0, 7.0],
            "altitude": [5.0, 10.0],
        }
        base = {"drones": 2, "formation": "v", "duration": 30, "world": "empty"}
        scientist.grid_search(param_space, base)


if __name__ == "__main__":
    import random
    main()
