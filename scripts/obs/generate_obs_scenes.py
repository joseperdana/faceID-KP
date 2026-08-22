import json
import uuid
import os
from pathlib import Path

def make_uuid():
    return str(uuid.uuid4())

def generate_4cam_scene_collection(
    collection_name="KPBromo 4-Cam Setup",
    room_id="kpbromo",
    canvas_w=1920,
    canvas_h=1080
):
    # Camera IDs and VDO.ninja view URLs
    cams = [
        {"id": "kp_cam1", "name": "Cam 1 - Main Front", "uuid": make_uuid()},
        {"id": "kp_cam2", "name": "Cam 2 - Left Angle", "uuid": make_uuid()},
        {"id": "kp_cam3", "name": "Cam 3 - Right Angle", "uuid": make_uuid()},
        {"id": "kp_cam4", "name": "Cam 4 - Wide / Overhead", "uuid": make_uuid()},
    ]

    sources = []

    # 1. Create Browser Sources for each camera
    for cam in cams:
        sources.append({
            "prev_ver": 537001986,
            "name": cam["name"],
            "uuid": cam["uuid"],
            "id": "browser_source",
            "versioned_id": "browser_source",
            "settings": {
                "url": f"https://vdo.ninja/?view={cam['id']}&autoplay=1&cleanoutput=1",
                "width": canvas_w,
                "height": canvas_h,
                "fps": 60,
                "reroute_audio": True,
                "restart_when_active": True,
                "shutdown": False
            },
            "mixers": 255,
            "sync": 0,
            "flags": 0,
            "volume": 1.0,
            "balance": 0.5,
            "enabled": True,
            "muted": False,
            "push-to-mute": False,
            "push-to-mute-delay": 0,
            "push-to-talk": False,
            "push-to-talk-delay": 0,
            "hotkeys": {
                "libobs.mute": [],
                "libobs.unmute": [],
                "libobs.push-to-mute": [],
                "libobs.push-to-talk": [],
                "ObsBrowser.Refresh": []
            },
            "deinterlace_mode": 0,
            "deinterlace_field_order": 0,
            "monitoring_type": 0,
            "private_settings": {}
        })

    def make_scene_item(cam, pos_x, pos_y, scale_x=1.0, scale_y=1.0, item_id=1):
        return {
            "name": cam["name"],
            "source_uuid": cam["uuid"],
            "visible": True,
            "locked": False,
            "rot": 0.0,
            "scale_ref": {"x": float(canvas_w), "y": float(canvas_h)},
            "align": 5,  # Top-Left align
            "bounds_type": 0,
            "bounds_align": 0,
            "bounds_crop": False,
            "crop_left": 0,
            "crop_top": 0,
            "crop_right": 0,
            "crop_bottom": 0,
            "id": item_id,
            "group_item_backup": False,
            "pos": {"x": float(pos_x), "y": float(pos_y)},
            "pos_rel": {"x": float(pos_x) / float(canvas_w), "y": float(pos_y) / float(canvas_h)},
            "scale": {"x": float(scale_x), "y": float(scale_y)},
            "scale_rel": {"x": float(scale_x), "y": float(scale_y)},
            "bounds": {"x": 0.0, "y": 0.0},
            "bounds_rel": {"x": 0.0, "y": 0.0},
            "scale_filter": "disable",
            "blend_method": "default",
            "blend_type": "normal",
            "show_transition": {"duration": 300},
            "hide_transition": {"duration": 300},
            "private_settings": {}
        }

    # 2. Build Scenes
    scenes = []

    # Scene A: 4 Solo Scenes
    for idx, cam in enumerate(cams):
        scene_uuid = make_uuid()
        scenes.append({
            "name": f"Solo - {cam['name']}",
            "uuid": scene_uuid,
            "id": "scene",
            "versioned_id": "scene",
            "settings": {
                "id_counter": 2,
                "custom_size": False,
                "items": [
                    make_scene_item(cam, 0, 0, 1.0, 1.0, item_id=1)
                ]
            },
            "mixers": 0,
            "sync": 0,
            "flags": 0,
            "volume": 1.0,
            "balance": 0.5,
            "enabled": True,
            "muted": False,
            "push-to-mute": False,
            "push-to-mute-delay": 0,
            "push-to-talk": False,
            "push-to-talk-delay": 0,
            "hotkeys": {
                "OBSBasic.SelectScene": []
            },
            "deinterlace_mode": 0,
            "deinterlace_field_order": 0,
            "monitoring_type": 0,
            "canvas_uuid": "6c69626f-6273-4c00-9d88-c5136d61696e",
            "private_settings": {}
        })

    # Scene B: 2x2 Grid Multiview (4 Cameras)
    grid_items = [
        make_scene_item(cams[0], 0, 0, 0.5, 0.5, item_id=1),
        make_scene_item(cams[1], 960, 0, 0.5, 0.5, item_id=2),
        make_scene_item(cams[2], 0, 540, 0.5, 0.5, item_id=3),
        make_scene_item(cams[3], 960, 540, 0.5, 0.5, item_id=4),
    ]
    scenes.append({
        "name": "Grid - 4-Way Multiview",
        "uuid": make_uuid(),
        "id": "scene",
        "versioned_id": "scene",
        "settings": {
            "id_counter": 5,
            "custom_size": False,
            "items": grid_items
        },
        "mixers": 0,
        "sync": 0,
        "flags": 0,
        "volume": 1.0,
        "balance": 0.5,
        "enabled": True,
        "muted": False,
        "push-to-mute": False,
        "push-to-mute-delay": 0,
        "push-to-talk": False,
        "push-to-talk-delay": 0,
        "hotkeys": {"OBSBasic.SelectScene": []},
        "deinterlace_mode": 0,
        "deinterlace_field_order": 0,
        "monitoring_type": 0,
        "canvas_uuid": "6c69626f-6273-4c00-9d88-c5136d61696e",
        "private_settings": {}
    })

    # Scene C: Host Focus + 3 Guest Sidebar
    sidebar_items = [
        make_scene_item(cams[0], 0, 180, 0.6666666666666666, 0.6666666666666666, item_id=1),
        make_scene_item(cams[1], 1280, 0, 0.3333333333333333, 0.3333333333333333, item_id=2),
        make_scene_item(cams[2], 1280, 360, 0.3333333333333333, 0.3333333333333333, item_id=3),
        make_scene_item(cams[3], 1280, 720, 0.3333333333333333, 0.3333333333333333, item_id=4),
    ]
    scenes.append({
        "name": "Layout - Host + 3 Sidebars",
        "uuid": make_uuid(),
        "id": "scene",
        "versioned_id": "scene",
        "settings": {
            "id_counter": 5,
            "custom_size": False,
            "items": sidebar_items
        },
        "mixers": 0,
        "sync": 0,
        "flags": 0,
        "volume": 1.0,
        "balance": 0.5,
        "enabled": True,
        "muted": False,
        "push-to-mute": False,
        "push-to-mute-delay": 0,
        "push-to-talk": False,
        "push-to-talk-delay": 0,
        "hotkeys": {"OBSBasic.SelectScene": []},
        "deinterlace_mode": 0,
        "deinterlace_field_order": 0,
        "monitoring_type": 0,
        "canvas_uuid": "6c69626f-6273-4c00-9d88-c5136d61696e",
        "private_settings": {}
    })

    # Add all scenes to sources list
    sources.extend(scenes)

    # 3. Build Full Collection
    scene_order = [{"name": s["name"]} for s in scenes]
    
    collection = {
        "name": collection_name,
        "sources": sources,
        "groups": [],
        "scene_order": scene_order,
        "current_scene": "Grid - 4-Way Multiview",
        "current_program_scene": "Grid - 4-Way Multiview",
        "canvases": [],
        "current_transition": "Fade",
        "transition_duration": 300,
        "transitions": [],
        "quick_transitions": [
            {"name": "Cut", "duration": 300, "hotkeys": [], "id": 1, "fade_to_black": False},
            {"name": "Fade", "duration": 300, "hotkeys": [], "id": 2, "fade_to_black": False},
            {"name": "Fade", "duration": 300, "hotkeys": [], "id": 3, "fade_to_black": True}
        ],
        "saved_projectors": [],
        "preview_locked": False,
        "scaling_enabled": False,
        "scaling_level": 1,
        "scaling_off_x": 0.0,
        "scaling_off_y": 0.0,
        "virtual-camera": {"type2": 3},
        "modules": {
            "scripts-tool": [],
            "output-timer": {
                "streamTimerHours": 0,
                "streamTimerMinutes": 0,
                "streamTimerSeconds": 30,
                "recordTimerHours": 0,
                "recordTimerMinutes": 0,
                "recordTimerSeconds": 30,
                "autoStartStreamTimer": False,
                "autoStartRecordTimer": False,
                "pauseRecordTimer": True
            },
            "auto-scene-switcher": {
                "interval": 300,
                "non_matching_scene": "",
                "switch_if_not_matching": False,
                "active": False,
                "switches": []
            }
        },
        "version": 2
    }

    return collection

if __name__ == "__main__":
    obs_scenes_dir = Path.home() / "Library/Application Support/obs-studio/basic/scenes"
    obs_scenes_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = obs_scenes_dir / "KPBromo_4Cam_Setup.json"
    data = generate_4cam_scene_collection()
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    print(f"✅ Successfully generated OBS Scene Collection at: {file_path}")
