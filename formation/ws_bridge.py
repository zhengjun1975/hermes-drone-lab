#!/usr/bin/env python3
"""
Simple WebSocket → ROS2 bridge. Uses subprocess to read ros2 data.
Zero rclpy dependency — never crashes from external shutdown.
"""
import asyncio
import json
import struct
import hashlib
import base64
import socket
import threading
import subprocess
import time
import re
import os

positions = {"1": {"x": 0, "y": 0, "z": 0, "t": 0}}
lock = threading.Lock()

def ros2_reader():
    """Read vehicle_odometry via ros2 topic echo subprocess"""
    env = os.environ.copy()
    env.pop("http_proxy", None)
    env.pop("https_proxy", None)
    env.pop("HTTP_PROXY", None)
    env.pop("HTTPS_PROXY", None)
    # Source ROS2
    source_cmd = "source /opt/ros/humble/setup.bash && source /home/ubuntu/ros2_ws/install/setup.bash 2>/dev/null && "
    cmd = source_cmd + "ros2 topic echo /fmu/out/vehicle_odometry --once"
    
    while True:
        try:
            proc = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=5, env=env)
            if proc.returncode == 0:
                # Parse position from ros2 topic echo YAML output
                x = y = z = 0.0
                t = 0.0
                in_position = False
                pos_idx = 0
                for line in proc.stdout.split('\n'):
                    ls = line.strip()
                    if 'timestamp:' in ls and 'sample' not in ls:
                        try: t = float(ls.split(':')[1].strip()) / 1e6
                        except: pass
                    if 'position:' in ls:
                        in_position = True
                        pos_idx = 0
                        continue
                    if in_position and ls.startswith('-'):
                        try:
                            val = float(ls.replace('- ', '').strip())
                            if pos_idx == 0: x = val
                            elif pos_idx == 1: y = val
                            else: z = val
                        except:
                            pass
                        pos_idx += 1
                        if pos_idx >= 3:
                            in_position = False

                with lock:
                    positions["1"] = {"x": x, "y": y, "z": z, "t": t}
        except Exception as e:
            pass
        time.sleep(0.1)

def ws_accept(key):
    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    return base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()

def encode_frame(data):
    payload = data.encode()
    frame = bytearray()
    frame.append(0x81)
    length = len(payload)
    if length < 126:
        frame.append(length)
    elif length < 65536:
        frame.append(126)
        frame.extend(struct.pack(">H", length))
    else:
        frame.append(127)
        frame.extend(struct.pack(">Q", length))
    frame.extend(payload)
    return bytes(frame)

def handle(conn):
    try:
        data = conn.recv(4096).decode()
        key = None
        for line in data.split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
                break
        if not key:
            conn.close()
            return
        accept = ws_accept(key)
        conn.sendall(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n".encode())
        print("[WS] Client connected")

        while True:
            time.sleep(0.1)
            with lock:
                data = {"drones": dict(positions)}
            try:
                frame = encode_frame(json.dumps(data))
                conn.sendall(frame)
            except:
                break
    except:
        pass
    finally:
        conn.close()
        print("[WS] Client disconnected")

def server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 9090))
    s.listen(5)
    print("[WS] Listening on :9090")

    while True:
        conn, addr = s.accept()
        print(f"[WS] Connection from {addr}")
        threading.Thread(target=handle, args=(conn,), daemon=True).start()

if __name__ == "__main__":
    # Start ROS2 reader in background
    threading.Thread(target=ros2_reader, daemon=True).start()
    print("[BRIDGE] Started — ws://192.168.112.251:9090")
    server()
