---
name: drone-sim-lab
category: robotics
description: Hermes-driven drone simulation digital twin lab. Single to multi-drone SITL launch, formation control (V/circle/line), experiment automation via Hermes orchestrating ROS2 + PX4 + Gazebo. Uses custom formation_controller.py (px4_offboard repo removed from GitHub).
version: 1.0
---

# Drone Simulation Digital Twin Lab

## Overview

Hermes 作为实验总控的无人机数字孪生实验室。架构：

```
Hermes (AI Agent 调度中心)
  └─ Mission Planner / Formation Planner / Simulation Manager
       └─ ROS2 Topics
            └─ N × (PX4 SITL + Gazebo)
                 └─ MicroXRCEAgent (DDS Bridge)
```

Hermes 不直接控制 PX4，而是站在最上层负责实验编排、自动 launch、rosbag 录制、结果分析。

## Prerequisites (all installed)

| Component | Status |
|-----------|--------|
| Ubuntu 22.04 | ✅ |
| ROS2 Humble | ✅ /opt/ros/humble/ |
| PX4-Autopilot | ✅ ~/dev/PX4-Autopilot/ |
| Gazebo Classic 11 | ✅ 262 models |
| MicroXRCEAgent | ✅ /usr/local/bin/ |
| ros_gz_bridge | ✅ ros-humble-ros-gz |
| Foxglove Studio | ✅ /usr/bin/ (headless) |
| foxglove_bridge | ✅ ros-humble-foxglove-bridge |
| px4_msgs | ✅ ~/ros2_ws/ |
| QGroundControl | ✅ ~/tools/ (optional) |
| xvfb | ✅ headless rendering |

## Environment Sourcing

Every new terminal needs:
```bash
source /opt/ros/humble/setup.bash
source /usr/share/gazebo/setup.sh
source ~/ros2_ws/install/setup.bash  # if px4_msgs built
```

Or simply: `source ~/.bashrc` (auto-configured).

## Workflow 1: Single Drone Takeoff

```bash
# Terminal 1: Launch PX4 SITL (headless)
cd ~/dev/PX4-Autopilot
HEADLESS=1 xvfb-run -a make px4_sitl gazebo-classic_iris

# Terminal 2: Bridge PX4 → ROS2
MicroXRCEAgent udp4 -p 8888

# Terminal 3: Verify
source /opt/ros/humble/setup.bash
ros2 topic list | grep fmu
```

To take off:
```bash
ros2 topic pub /fmu/in/offboard_control_mode px4_msgs/msg/OffboardControlMode \
  "{position: true}" --once
ros2 topic pub /fmu/in/trajectory_setpoint px4_msgs/msg/TrajectorySetpoint \
  "{position: [0.0, 0.0, -5.0], yaw: 0.0}" --once
ros2 service call /fmu/arm px4_msgs/srv/VehicleCommand "{command: 1}"
```

## Workflow 2: Multi-Drone Formation (Hermes Automated)

自定义轻量级编队控制器 (`~/dev/px4_formation/`) 替代了已移除的 px4_offboard 仓库。

**一键编队实验：**
```bash
# Hermes 调用: "2架V字编队，高度10米，间距5米，运行60秒"
bash ~/dev/px4_formation/hermes_experiment.sh 2 v 10 5 60 empty true
# 参数: <drones> <formation> <altitude_m> <spacing_m> <duration_s> <world> <record_bag>
```

**Hermes 自动执行：**
1. 启动 N 个 PX4 SITL (sitl_multiple_run.sh)
2. 启动 MicroXRCEAgent (DDS 桥接)
3. 录制 rosbag (所有话题)
4. 运行编队控制 (run_formation.py)
5. 依次起飞 → 编队 → 保持 → 降落
6. 清理所有进程
7. 数据保存到 `~/experiments/<timestamp>_<N>drone_<formation>/`

**支持的编队类型：**
- `v` — V字编队 (leader在前，follower向两侧后方展开)
- `circle` — 圆形编队 (等距分布在圆周上)
- `line` — 线形编队 (沿X轴排列)

**Python API 用法：**
```python
from formation_controller import DroneController, FormationController
# 创建 N 个 drone controller
drones = [DroneController(f"px4_{i}") for i in range(1, N+1)]
# 起飞
for d in drones: d.takeoff(altitude=-10.0)
# V字编队
FormationController.v_formation(drones, drones[0], altitude=-10, spacing=5.0)
```

## Key Commands

```bash
# Process management
px4_sitl         # Alias: build + launch SITL
uagent           # Alias: MicroXRCEAgent udp4 -p 8888
qgc              # Alias: QGroundControl AppImage

# ROS2 inspection
ros2 topic list | grep fmu    # PX4 topics
ros2 topic echo /fmu/out/vehicle_attitude  # Attitude data
ros2 bag record -a            # Record all topics

# Health checks
ps aux | grep -E "px4|gzserver|MicroXRCEAgent"
```

## Offboard Control Architecture

px4_offboard 仓库已从 GitHub 移除 (2026-07)，改用自定义轻量级控制器。

**核心文件：**
- `~/dev/px4_formation/formation_controller.py` — DroneController (单机) + FormationController (编队)
- `~/dev/px4_formation/run_formation.py` — ROS2 节点：takeoff → formation → hold → land
- `~/dev/px4_formation/multi_drone_exp.py` — Python 多机实验管理器

**DroneController API:**
```python
ctrl = DroneController("px4_1")  # namespace
ctrl.takeoff(altitude=-10.0)      # NED: negative z = up
ctrl.goto(x=5.0, y=0.0, z=-10.0) # position setpoint
ctrl.land()                       # land at current position
```

**多机 uXRCE-DDS 注意：**
`sitl_multiple_run.sh` 默认使用 MAVLink 而非 DDS。单机用 `make px4_sitl` (已验证 69 个 /fmu/ topics 全通)。
多机需逐台 `make` 启动并分配独立 uXRCE-DDS 端口。详见 `references/setup-notes.md`。

## Common Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| No /fmu topics | Agent not running | Start MicroXRCEAgent |
| gzserver won't start | Missing DISPLAY | Use xvfb-run |
| `ros2 topic echo` fails | px4_msgs not built | Build in ros2_ws (expect 3-5 min for 70+ msgs) |
| Drone won't arm | Not in Offboard mode | Send offboard_control_mode first |
| HEADLESS=1 ignored | setup_gazebo not sourced | `source /usr/share/gazebo/setup.sh` first |
| Multiple drones conflict | Port collision | Use sitl_multiple_run.sh |
| Colcon build hangs | Leftover build artifacts | `rm -rf build/ install/` then retry |
| `make px4_sitl` fails at ~29% | CMake transient race on sitl_gazebo-classic | Retry — all .so files likely already built; second pass succeeds |
| `rosdep init` timeout | raw.githubusercontent.com blocked | Use github.com/.../raw/ alias in sources.list (see references/setup-notes.md) |
| px4_msgs build looks stuck | 524 C files being generated from 70+ msg defs | Wait — 3-5 min is normal, check `ls build/px4_msgs/*.so | wc -l` for progress |
| Gazebo models missing | Only ground_plane + sun installed | Clone gazebo_models to ~/.gazebo/models/ (262 models) |
| ROS2 daemon not running | First ros2 command auto-starts it | Normal — `ros2 daemon status` to confirm |

## Chain Verification Checklist

After starting PX4 SITL + MicroXRCEAgent, verify with:

```bash
# 1. Check processes
ps aux | grep -E "[g]zserver|[p]x4 " | wc -l   # expect ≥2

# 2. Check DDS bridge
ros2 topic list | grep "/fmu/" | wc -l          # expect 60-70 topics
ros2 topic list | grep "/fmu/in/" | wc -l        # 38 control topics
ros2 topic list | grep "/fmu/out/" | wc -l       # 31 telemetry topics

# 3. Verify message types
ros2 topic info /fmu/out/vehicle_attitude         # Type: px4_msgs/msg/VehicleAttitude
```

Healthy state: gzserver + px4 both running, 69 total /fmu/ topics, message types resolvable.

## Gazebo Worlds

Available PX4 worlds:
- `empty.world` — Empty flat plane (default, fastest)
- `baylands.world` — Large open area with runway
- `sonoma_raceway.world` — Race track environment
- `mcmillan_airfield.world` — Airport with buildings
- `yosemite.world` — Mountain terrain

Use: `make px4_sitl gazebo-classic_iris__baylands` (model__world format)

## References

- PX4 SITL docs: https://docs.px4.io/main/en/simulation/gazebo_classic.html
- Foxglove Studio: https://studio.foxglove.dev/ (web UI + desktop)
- ROS2 ↔ PX4: https://docs.px4.io/main/en/ros/ros2_comm.html
- `references/setup-notes.md` — Network proxy config, PX4 build gotchas, multi-drone uXRCE-DDS
- `references/chain-verification.md` — Step-by-step end-to-end chain test with expected metrics
- `scripts/sitl_cleanup.sh` — Kill all SITL processes

## Support Files

| File | Type | Purpose |
|------|------|---------|
| `references/setup-notes.md` | Reference | Network workarounds, build fixes, disk footprint |
| `references/chain-verification.md` | Reference | Hermes→ROS2→PX4→Gazebo end-to-end test |
| `scripts/sitl_cleanup.sh` | Script | Kill all drone simulation processes |

## Files

| Path | Purpose |
|------|---------|
| `~/dev/PX4-Autopilot/` | PX4 firmware + SITL |
| `~/dev/px4_formation/` | Formation controller + experiment orchestrator |
| `~/dev/scripts/` | sitl_single.sh, sitl_multi.sh, sitl_cleanup.sh |
| `~/experiments/` | Experiment output (rosbags, logs, data) |
| `~/ros2_ws/` | ROS2 workspace (px4_msgs: 263 message types) |
| `~/tools/QGroundControl.AppImage` | Ground station (optional) |
| `~/.gazebo/models/` | 262 Gazebo models |
| `/usr/local/bin/MicroXRCEAgent` | DDS bridge |

## Phase 3: AI Scientist — Autonomous Optimization

AI Scientist 自动搜索最优编队参数：

```bash
# Dry-run 模式（快速验证，无需启动 SITL）
python3 ~/dev/px4_formation/ai_scientist.py

# Grid Search: 3种间距 × 2种高度 = 6次实验
python3 ~/dev/px4_formation/ai_scientist.py grid --spacings 3,5,7 --altitudes 5,10

# Hill-Climbing: 从默认参数出发，逐步优化
python3 ~/dev/px4_formation/ai_scientist.py optimize --max-iter 5

# 真实 SITL 实验（加 --dry-run 0 或直接运行需要 SITL 环境）
python3 ~/dev/px4_formation/ai_scientist.py grid --spacings 5,7 --duration 60
```

**AI Scientist 输出：**
- `~/experiments/ai_scientist/scientist_summary.json` — 完整搜索历史
- `~/experiments/ai_scientist/exp_*/result.json` — 每次实验结果
- `~/experiments/ai_scientist/exp_*/analysis/` — 轨迹图 + 报告 (如果有 rosbag)

**Rosbag 分析：**
```bash
python3 ~/dev/px4_formation/bag_analyzer.py --bag ~/experiments/<exp>/rosbag --formation v --drones 2
# 输出: metrics.json + report.md + trajectory_2d.png + trajectory_3d.png + error_over_time.png
```

**Hermes 可以理解的指令：**
- "优化V字编队间距，从3到8米"
- "对比圆形和V字编队质量"
- "分析最近一次实验的轨迹误差"
- "自动寻找最优参数"

```bash
# Hermes 一句话运行完整实验
bash ~/dev/px4_formation/hermes_experiment.sh <drones> <formation> <alt> <spacing> <duration> <world> <record>

# 手动分步控制
python3 ~/dev/px4_formation/multi_drone_exp.py --drones 3 --world baylands
python3 ~/dev/px4_formation/run_formation.py --drones 3 --formation circle --altitude 10

# 清理
bash ~/dev/scripts/sitl_cleanup.sh
```
