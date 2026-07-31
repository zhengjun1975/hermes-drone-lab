#!/usr/bin/env bash
# ============================================================
# Hermes Experiment Orchestrator
# "N drones, V formation, H altitude, S spacing, T duration"
# ============================================================
set -e

# Defaults
NUM_DRONES="${1:-2}"
FORMATION="${2:-v}"
ALTITUDE="${3:-10}"
SPACING="${4:-5}"
DURATION="${5:-60}"
WORLD="${6:-empty}"
RECORD_BAG="${7:-true}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EXP_DIR="$HOME/experiments/${TIMESTAMP}_${NUM_DRONES}drone_${FORMATION}"
LOG_FILE="$EXP_DIR/experiment.log"

mkdir -p "$EXP_DIR"

echo "╔══════════════════════════════════════════════╗"
echo "║  Hermes Drone Experiment Orchestrator        ║"
echo "╠══════════════════════════════════════════════╣"
echo "║ Experiment: ${NUM_DRONES} drones, ${FORMATION}-formation"
echo "║ Altitude:   ${ALTITUDE}m"
echo "║ Spacing:    ${SPACING}m"
echo "║ Duration:   ${DURATION}s"
echo "║ World:      ${WORLD}"
echo "║ Record:     ${RECORD_BAG}"
echo "║ Output:     ${EXP_DIR}"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Source environment
source /opt/ros/humble/setup.bash 2>/dev/null
source /usr/share/gazebo/setup.sh 2>/dev/null
source "$HOME/ros2_ws/install/setup.bash" 2>/dev/null
export HEADLESS=1

# Phase 1: Launch Simulation
echo "[Phase 1/5] Launching ${NUM_DRONES} drones in ${WORLD}..."
cd "$HOME/dev/PX4-Autopilot"
bash ./Tools/simulation/gazebo-classic/sitl_multiple_run.sh "$NUM_DRONES" > "$LOG_FILE" 2>&1 &
SITL_PID=$!
echo "  SITL PID: $SITL_PID"

# Wait for Gazebo + all PX4 instances
echo "  Waiting for simulation..."
for i in $(seq 1 30); do
    PX4_COUNT=$(ps aux | grep -c "[p]x4.*etc" 2>/dev/null || echo 0)
    if [ "$PX4_COUNT" -ge "$NUM_DRONES" ]; then
        echo "  All $PX4_COUNT PX4 instances ready (${i}s)"
        break
    fi
    sleep 1
done

# Phase 2: DDS Bridge
echo "[Phase 2/5] Starting DDS bridge..."
MicroXRCEAgent udp4 -p 8888 > "$EXP_DIR/agent.log" 2>&1 &
AGENT_PID=$!
echo "  Agent PID: $AGENT_PID"
sleep 5

# Phase 3: Start rosbag recording
if [ "$RECORD_BAG" = "true" ]; then
    echo "[Phase 3/5] Starting rosbag recording..."
    ros2 bag record -a -o "$EXP_DIR/rosbag" > "$EXP_DIR/bag.log" 2>&1 &
    BAG_PID=$!
    echo "  Bag PID: $BAG_PID"
else
    echo "[Phase 3/5] Skipping rosbag (RECORD_BAG=false)"
    BAG_PID=""
fi
sleep 2

# Phase 4: Run Formation
echo "[Phase 4/5] Running formation..."
python3 "$HOME/dev/px4_formation/run_formation.py" \
    --drones "$NUM_DRONES" \
    --formation "$FORMATION" \
    --altitude "$ALTITUDE" \
    --spacing "$SPACING" \
    --duration "$DURATION" \
    > "$EXP_DIR/formation.log" 2>&1

echo "  Formation complete!"

# Phase 5: Cleanup
echo "[Phase 5/5] Cleaning up..."
if [ -n "$BAG_PID" ]; then
    kill "$BAG_PID" 2>/dev/null && echo "  Rosbag stopped"
fi
kill "$AGENT_PID" 2>/dev/null && echo "  Agent stopped"
kill "$SITL_PID" 2>/dev/null
pkill -f "px4_sitl" 2>/dev/null
pkill -f "gzserver" 2>/dev/null
pkill -f "MicroXRCEAgent" 2>/dev/null
sleep 2

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Experiment Complete!                        ║"
echo "╠══════════════════════════════════════════════╣"
echo "║ Duration:   ${DURATION}s"
echo "║ Data:       ${EXP_DIR}"
echo "║ Rosbag:     ${EXP_DIR}/rosbag/"
echo "║ Formation:  ${EXP_DIR}/formation.log"
echo "╚══════════════════════════════════════════════╝"

# List data files
echo ""
ls -lh "$EXP_DIR/" 2>/dev/null
