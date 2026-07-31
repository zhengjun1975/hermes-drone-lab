#!/usr/bin/env bash
# ============================================================
# Drone SITL Single Launch Script
# Usage: sitl_single.sh [model] [world] [headless]
#   model: iris (default), standard_vtol, plane, rover
#   world: empty (default), baylands, sonoma_raceway, etc.
#   headless: 1 (default), 0 (needs display)
# ============================================================
set -e

MODEL="${1:-iris}"
WORLD="${2:-empty}"
HEADLESS="${3:-1}"
PX4_HOME="$HOME/dev/PX4-Autopilot"

echo "╔══════════════════════════════════════════╗"
echo "║   PX4 SITL Single Drone Launcher        ║"
echo "╠══════════════════════════════════════════╣"
echo "║ Model:    $MODEL"
echo "║ World:    $WORLD"
echo "║ Headless: $HEADLESS"
echo "╚══════════════════════════════════════════╝"

# Source environment
source /opt/ros/humble/setup.bash 2>/dev/null
source /usr/share/gazebo/setup.sh 2>/dev/null
[ -f "$HOME/ros2_ws/install/setup.bash" ] && source "$HOME/ros2_ws/install/setup.bash" 2>/dev/null

export HEADLESS=$HEADLESS
export PX4_SIM_SPEED_FACTOR=1

cd "$PX4_HOME"

# Determine make target
if [ "$WORLD" = "empty" ]; then
    TARGET="gazebo-classic_${MODEL}"
else
    TARGET="gazebo-classic_${MODEL}__${WORLD}"
fi

echo ""
echo "[1/3] Building SITL target: $TARGET"
make px4_sitl "$TARGET" &
SITL_PID=$!
echo "      SITL PID: $SITL_PID"

# Wait for Gazebo to start
echo "[2/3] Waiting for Gazebo server..."
for i in $(seq 1 30); do
    if ps aux | grep -q "[g]zserver"; then
        echo "      Gazebo ready (${i}s)"
        break
    fi
    sleep 1
done

# Start MicroXRCEAgent
echo "[3/3] Starting MicroXRCEAgent..."
MicroXRCEAgent udp4 -p 8888 &
AGENT_PID=$!
echo "      Agent PID: $AGENT_PID"

sleep 3

# Verify
source /opt/ros/humble/setup.bash
TOPIC_COUNT=$(ros2 topic list 2>/dev/null | grep -c "/fmu/" || echo 0)
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   SITL Ready — $TOPIC_COUNT PX4 topics         ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Processes:"
echo "  SITL PID:  $SITL_PID"
echo "  Agent PID: $AGENT_PID"
echo ""
echo "To stop: kill $SITL_PID $AGENT_PID"
echo "To monitor: ros2 topic list | grep fmu"
echo ""

# Keep script running (wait for SITL)
wait $SITL_PID 2>/dev/null
