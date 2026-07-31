#!/usr/bin/env bash
# ============================================================
# Multi-Drone SITL Launch (Formation)
# Usage: sitl_multi.sh <num_drones> [world] [model]
# ============================================================
set -e

NUM_DRONES="${1:-2}"
WORLD="${2:-empty}"
MODEL="${3:-iris}"

echo "╔══════════════════════════════════════════╗"
echo "║   PX4 Multi-Drone Launch ($NUM_DRONES drones)  ║"
echo "╚══════════════════════════════════════════╝"

PX4_HOME="$HOME/dev/PX4-Autopilot"
source /opt/ros/humble/setup.bash 2>/dev/null
source /usr/share/gazebo/setup.sh 2>/dev/null

export HEADLESS=1
cd "$PX4_HOME"

# Use PX4's built-in multi-drone script
bash ./Tools/simulation/gazebo-classic/sitl_multiple_run.sh "$NUM_DRONES"
