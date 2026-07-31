# Hermes Drone Lab

**AI-driven digital twin laboratory for multi-drone formation research.**

Hermes acts as the experiment operating system — orchestrating ROS2, PX4 SITL, and Gazebo. No real hardware needed. Pure simulation, full automation.

```
Hermes (AI Agent)
  └─ Mission Planner / Formation Planner / AI Scientist
       └─ ROS2 Topics
            └─ N × (PX4 SITL + Gazebo Classic)
                 └─ MicroXRCEAgent (DDS Bridge)
```

## Architecture

| Layer | Component | Role |
|-------|-----------|------|
| 3 — AI Scientist | `ai_scientist.py` | Auto param optimization, grid search, experiment comparison |
| 2 — Orchestration | `hermes_experiment.sh` | One-command experiment: launch → fly → record → analyze → cleanup |
| 1 — Simulation | PX4 SITL + Gazebo | Physics + flight controller simulation |

## Quick Start

### Prerequisites

```bash
# Ubuntu 22.04 with ROS2 Humble + PX4 + Gazebo
# See docs/SETUP.md for full installation guide
source /opt/ros/humble/setup.bash
source /usr/share/gazebo/setup.sh
```

### Single Drone

```bash
# Launch one Iris in empty world
bash scripts/sitl_single.sh iris empty

# In another terminal — bridge to ROS2
MicroXRCEAgent udp4 -p 8888

# Verify
ros2 topic list | grep /fmu/
```

### Formation Experiment (Hermes One-Click)

```bash
# 2 drones, V-formation, 10m altitude, 5m spacing, 60 seconds
bash formation/hermes_experiment.sh 2 v 10 5 60 empty true

# Parameters: <drones> <formation:v|circle|line> <alt_m> <spacing_m> <duration_s> <world> <record_bag>
```

### AI Scientist — Autonomous Optimization

```bash
# Dry-run demo (no SITL needed, instant)
python3 analysis/ai_scientist.py

# Grid search: 6 experiments, finds optimal spacing & altitude
python3 analysis/ai_scientist.py grid --spacings 3,5,7 --altitudes 5,10

# Hill-climbing optimization
python3 analysis/ai_scientist.py optimize --max-iter 5

# Analyze rosbag data
python3 analysis/bag_analyzer.py --bag ~/experiments/<exp>/rosbag --formation v --drones 2
```

### Cleanup

```bash
bash scripts/sitl_cleanup.sh
```

## File Overview

```
formation/
├── formation_controller.py    DroneController + FormationController classes
├── run_formation.py           ROS2 formation control node
├── multi_drone_exp.py         Python experiment manager
├── hermes_experiment.sh       ★ One-click full experiment pipeline
├── multi_sitl_dds.sh          Multi-drone SITL (uXRCE-DDS)
└── multi_make.sh              Multi-drone SITL (make approach)

scripts/
├── sitl_single.sh             Single drone SITL launcher
├── sitl_multi.sh              Multi-drone via PX4 built-in script
└── sitl_cleanup.sh            Kill all simulation processes

analysis/
├── ai_scientist.py            ★ Autonomous parameter optimizer
└── bag_analyzer.py            Rosbag → metrics + trajectory plots + report

SKILL.md                       Hermes skill definition
```

## Supported Formations

| Formation | Description | Use Case |
|-----------|-------------|----------|
| `v` | V-shaped with leader at front | Leader-follower, surveillance |
| `circle` | Equal spacing on circumference | Area coverage, perimeter monitoring |
| `line` | Linear along X-axis | Corridor scanning, border patrol |

## AI Scientist Capabilities

The AI Scientist can autonomously:

1. **Grid Search** — Exhaustively test all parameter combinations
2. **Hill Climbing** — Start from defaults, iteratively improve
3. **Compare & Rank** — Score experiments by formation tracking error
4. **Generate Reports** — JSON metrics + Markdown + trajectory plots

Example output after 6 experiments:
```
Best: spacing=5.0m, altitude=10.0m, quality=78.8/100
Insight: optimal spacing ≈ altitude × 0.5 for V-formation
```

## Experiment Output

Each experiment produces:
```
~/experiments/<timestamp>_<N>drone_<formation>/
├── rosbag/          Raw ROS2 data
├── formation.log    Controller output
├── agent.log        DDS bridge log
├── experiment.log   Full orchestration log
└── analysis/        (after running bag_analyzer)
    ├── metrics.json
    ├── report.md
    ├── trajectory_2d.png
    ├── trajectory_3d.png
    └── error_over_time.png
```

## Requirements

- Ubuntu 22.04
- ROS2 Humble (full desktop)
- PX4-Autopilot (SITL build)
- Gazebo Classic 11
- MicroXRCEAgent
- Python 3.10+ with numpy, matplotlib
- xvfb (for headless simulation)

## License

MIT
