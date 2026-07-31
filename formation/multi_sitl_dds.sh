#!/usr/bin/env bash
# ============================================================
# Multi-Drone SITL with uXRCE-DDS (ROS2 native)
# Each PX4 instance gets unique uXRCE-DDS port + namespace
# ============================================================
set -e

NUM_DRONES="${1:-2}"
WORLD="${2:-empty}"
MODEL="${3:-iris}"

PX4_HOME="$HOME/dev/PX4-Autopilot"
BUILD_DIR="$PX4_HOME/build/px4_sitl_default"
source /opt/ros/humble/setup.bash 2>/dev/null
source /usr/share/gazebo/setup.sh 2>/dev/null
export HEADLESS=1

echo "╔══════════════════════════════════════════╗"
echo "║  Multi-Drone SITL (uXRCE-DDS native)     ║"
echo "║  Drones: $NUM_DRONES | World: $WORLD       ║"
echo "╚══════════════════════════════════════════╝"

# Start single Gazebo server
WORLD_FILE="$PX4_HOME/Tools/simulation/gazebo-classic/sitl_gazebo-classic/worlds/${WORLD}.world"
echo "[1] Starting Gazebo with $WORLD..."
gzserver "$WORLD_FILE" --verbose &
GZSERVER_PID=$!
sleep 3

# Launch PX4 instances with sequential uXRCE-DDS ports
PIDS=()
for i in $(seq 0 $((NUM_DRONES - 1))); do
    INSTANCE_ID=$i
    UXRCE_PORT=$((8888 + i))
    
    echo "[2] Drone $i: PX4 instance=$INSTANCE_ID uXRCE-DDS port=$UXRCE_PORT"
    
    # Set environment for this instance
    export PX4_SIM_MODEL="$MODEL"
    export PX4_INSTANCE="$INSTANCE_ID"
    export UXRCE_DDS_PORT="$UXRCE_PORT"
    
    # Build the SITL command with args
    "$BUILD_DIR/bin/px4" \
        -i "$INSTANCE_ID" \
        -d \
        "$BUILD_DIR/etc" \
        > "/tmp/px4_drone_${i}.log" 2>&1 &
    PIDS+=($!)
    
    sleep 2
done

# Start MicroXRCEAgents (one per drone port)
echo "[3] Starting MicroXRCEAgents..."
for i in $(seq 0 $((NUM_DRONES - 1))); do
    UXRCE_PORT=$((8888 + i))
    MicroXRCEAgent udp4 -p "$UXRCE_PORT" > "/tmp/agent_drone_${i}.log" 2>&1 &
    AGENT_PIDS+=($!)
    echo "    Agent $i: port=$UXRCE_PORT PID=${AGENT_PIDS[-1]}"
done

sleep 5
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  All drones ready!                       ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Drone PIDs: ${PIDS[@]}"
echo "Agent PIDs: ${AGENT_PIDS[@]}"
echo "Gazebo PID: $GZSERVER_PID"
echo ""
echo "To monitor: ros2 topic list 2>/dev/null | grep px4"
echo "To stop:    bash ~/dev/scripts/sitl_cleanup.sh"

# Wait
wait $GZSERVER_PID 2>/dev/null
