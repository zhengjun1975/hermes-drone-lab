#!/usr/bin/env bash
# ============================================================
# SITL Cleanup — kill all drone sim processes
# ============================================================
echo "Stopping all SITL processes..."

pkill -f "px4_sitl" 2>/dev/null && echo "  px4_sitl: stopped"
pkill -f "gzserver" 2>/dev/null && echo "  gzserver: stopped"
pkill -f "gzclient" 2>/dev/null && echo "  gzclient: stopped"
pkill -f "MicroXRCEAgent" 2>/dev/null && echo "  MicroXRCEAgent: stopped"
pkill -f "xvfb-run" 2>/dev/null && echo "  xvfb: stopped"

sleep 1
REMAINING=$(ps aux | grep -E "px4|gzserver|gzclient|MicroXRCEAgent" | grep -v grep | wc -l)
echo ""
echo "All stopped. Remaining processes: $REMAINING"
