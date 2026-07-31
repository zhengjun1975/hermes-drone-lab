#!/usr/bin/env bash
# ============================================================
# Multi-Drone SITL via make (proven working approach)
# Each drone gets its own make invocation with unique ports
# ============================================================
set -e
NUM_DRONES="${1:-2}"
MODEL="${2:-iris}"
WORLD="${3:-empty}"

source /opt/ros/humble/setup.bash 2>/dev/null
source /usr/share/gazebo/setup.sh 2>/dev/null
source "$HOME/ros2_ws/install/setup.bash" 2>/dev/null
export HEADLESS=1

echo "Launching $NUM_DRONES drones via make (each with uXRCE-DDS)..."

PX4_HOME="$HOME/dev/PX4-Autopilot"

# First drone starts Gazebo
echo "[Drone 1] Starting with Gazebo..."
cd "$PX4_HOME"
export PX4_SYS_AUTOSTART=10016  # HILStar
xvfb-run -a make px4_sitl "gazebo-classic_${MODEL}__${WORLD}" &
PIDS+=($!)
sleep 15

# Additional drones join the running Gazebo
for i in $(seq 2 $NUM_DRONES); do
    echo "[Drone $i] Joining simulation..."
    SITL_PID=$(( $i + 1 ))
    "$PX4_HOME/build/px4_sitl_default/bin/px4" \
        -i $((i-1)) -d \
        "$PX4_HOME/build/px4_sitl_default/etc" &
    PIDS+=($!)
    sleep 2
done

# Single MicroXRCEAgent (PX4 uses port 8888 by default)
MicroXRCEAgent udp4 -p 8888 &
PIDS+=($!)

echo "All drones started. PIDs: ${PIDS[@]}"
wait
