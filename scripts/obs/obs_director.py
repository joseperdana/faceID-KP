#!/usr/bin/env python3
"""
OBS Director CLI & Automation Script for KPBromo Multi-Camera Setup.
Controls OBS Studio via OBS WebSocket v5 protocol.
"""

import os
import sys
import time
import argparse
import obsws_python as obs

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4455
# Previously a hardcoded password, committed to a public repository and echoed
# to stdout on every connection failure. Set OBS_WS_PASSWORD in the environment.
DEFAULT_PASS = os.getenv("OBS_WS_PASSWORD", "")

def get_client(host=DEFAULT_HOST, port=DEFAULT_PORT, password=DEFAULT_PASS):
    try:
        return obs.ReqClient(host=host, port=port, password=password, timeout=3)
    except Exception as e:
        print(f"❌ Failed to connect to OBS WebSocket at {host}:{port}.")
        print(f"   Reason: {e}")
        print("\n💡 Pastikan:")
        print("   1. OBS Studio sedang terbuka di Mac.")
        print("   2. WebSocket Server aktif di OBS: Menu 'Tools' -> 'WebSocket Server Settings' -> Centang 'Enable WebSocket server'.")
        print(f"   3. Server Port: {port}; set OBS_WS_PASSWORD di environment.")
        sys.exit(1)

def list_scenes(client):
    res = client.get_scene_list()
    print(f"\n🎬 Current Program Scene: {res.current_program_scene_name}")
    print("📋 Available Scenes:")
    for idx, scene in enumerate(res.scenes, 1):
        marker = "👉" if scene['sceneName'] == res.current_program_scene_name else "  "
        print(f"   {marker} [{idx}] {scene['sceneName']}")

def switch_scene(client, scene_name):
    client.set_current_program_scene(scene_name)
    print(f"✅ Switched active scene to: '{scene_name}'")

def toggle_record(client, action="toggle"):
    status = client.get_record_status()
    is_recording = status.output_active
    
    if action == "start":
        if not is_recording:
            client.start_record()
            print("🔴 Recording STARTED!")
        else:
            print("⚠️ Already recording.")
    elif action == "stop":
        if is_recording:
            res = client.stop_record()
            print(f"⏹️ Recording STOPPED! Saved file: {res.output_path}")
        else:
            print("⚠️ Not currently recording.")
    elif action == "toggle":
        client.toggle_record()
        time.sleep(0.5)
        new_status = client.get_record_status()
        state = "RECORDING 🔴" if new_status.output_active else "STOPPED ⏹️"
        print(f"🔄 Record toggled -> Current state: {state}")

def auto_director(client, interval=10, loop_count=5):
    """
    Simulates an automated switcher cycling through cameras.
    """
    res = client.get_scene_list()
    scenes = [s['sceneName'] for s in res.scenes]
    
    if not scenes:
        print("❌ No scenes found.")
        return
        
    print(f"🤖 Starting Auto-Director mode (Switching every {interval}s, {loop_count} cycles)...")
    for i in range(loop_count):
        for scene in scenes:
            print(f"\n🎥 [Cycle {i+1}/{loop_count}] Switching to: {scene}")
            client.set_current_program_scene(scene)
            time.sleep(interval)
            
    print("\n🏁 Auto-Director cycle completed.")

def main():
    parser = argparse.ArgumentParser(description="OBS Studio Controller for 4-Cam VDO.Ninja Setup")
    parser.add_argument("--host", default=DEFAULT_HOST, help="OBS WebSocket host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="OBS WebSocket port")
    parser.add_argument("--password", default=DEFAULT_PASS, help="OBS WebSocket password")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    subparsers.add_parser("list", help="List all scenes and current active scene")
    
    switch_parser = subparsers.add_parser("switch", help="Switch active scene")
    switch_parser.add_argument("scene_name", help="Exact name of the scene to switch to")
    
    rec_parser = subparsers.add_parser("record", help="Control recording")
    rec_parser.add_argument("action", choices=["start", "stop", "toggle", "status"], default="toggle", nargs="?")
    
    director_parser = subparsers.add_parser("auto-director", help="Run AI / automatic scene switcher")
    director_parser.add_argument("--interval", type=int, default=8, help="Seconds per scene")
    director_parser.add_argument("--cycles", type=int, default=3, help="Number of loops")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    client = get_client(args.host, args.port, args.password)
    
    if args.command == "list":
        list_scenes(client)
    elif args.command == "switch":
        switch_scene(client, args.scene_name)
    elif args.command == "record":
        if args.action == "status":
            st = client.get_record_status()
            print(f"Recording: {'Active 🔴' if st.output_active else 'Inactive ⏹️'} | Duration: {st.output_duration / 1000:.1f}s")
        else:
            toggle_record(client, args.action)
    elif args.command == "auto-director":
        auto_director(client, interval=args.interval, loop_count=args.cycles)

if __name__ == "__main__":
    main()
