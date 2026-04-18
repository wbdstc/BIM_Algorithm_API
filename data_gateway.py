import base64
import json
import os

import requests


APP_KEY = os.getenv("BIMFACE_APP_KEY")
APP_SECRET = os.getenv("BIMFACE_APP_SECRET")
FILE_ID = os.getenv("BIMFACE_FILE_ID", "10000990421273")
PROJECT_NAME = os.getenv("BIM_PROJECT_NAME", "BIM Smart Site Planning Demo")
PROJECT_SYNC_URL = os.getenv("DATA_GATEWAY_SYNC_URL")

ROLE_MAP_IDS = {
    "center_crane": {
        "id": "5327272_5311976",
        "name": "QTZ60-1",
        "max_radius": 3200,
        "capacity_tons": 18,
        "priority_score": 1.0,
    },
    "other_cranes": [
        {
            "id": "5327272_5312858",
            "name": "QTZ60-2",
            "max_radius": 2800,
            "capacity_tons": 16,
            "priority_score": 0.96,
        },
        {
            "id": "5327272_5312036",
            "name": "QTZ60-3",
            "max_radius": 2800,
            "capacity_tons": 16,
            "priority_score": 0.94,
        },
    ],
    "buildings": {
        "building_1": {
            "name": "Main Building 1",
            "ids": [
                "5327272_5311496",
                "5327272_5311502",
                "5327272_5311484",
                "5327272_5311490",
            ],
        },
        "building_2": {
            "name": "Main Building 2",
            "ids": [
                "5327272_5311535",
                "5327272_5311529",
                "5327272_5311517",
                "5327272_5311523",
                "5327272_5311910",
            ],
        },
        "building_3": {
            "name": "Main Building 3",
            "ids": ["5327272_5314766", "5327272_5314769"],
        },
    },
    "road_segments": [
        "5327272_5312186",
        "5327272_5312297",
        "5327272_5312291",
        "5327272_5312285",
    ],
    "wall_segments": [
        "5327272_5313113",
        "5327272_5313098",
        "5327272_5313086",
        "5327272_5313074",
        "5327272_5314721",
        "5327272_5313062",
        "5327272_5313125",
        "5327272_5313137",
        "5327272_5313149",
    ],
}


def ensure_gateway_config():
    if not APP_KEY or not APP_SECRET:
        raise SystemExit("Missing BIMFACE_APP_KEY or BIMFACE_APP_SECRET in the environment.")


def get_access_token():
    credential = f"{APP_KEY}:{APP_SECRET}".encode("utf-8")
    headers = {
        "Authorization": f"Basic {base64.b64encode(credential).decode('utf-8')}",
    }
    response = requests.post(
        "https://api.bimface.com/oauth2/token",
        headers=headers,
        proxies={"http": None, "https": None},
    )
    response.raise_for_status()
    return response.json()["data"]["token"]


def fetch_raw_bbox(token, element_id):
    url = f"https://api.bimface.com/data/v2/files/{FILE_ID}/elements/{element_id}"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        proxies={"http": None, "https": None},
    )
    response.raise_for_status()
    return response.json().get("data", {}).get("boundingBox")


def extract_bbox_metrics(bbox):
    if not bbox:
        return None

    min_x = bbox["min"]["x"]
    min_y = bbox["min"]["y"]
    min_z = bbox["min"].get("z", 0.0)
    max_x = bbox["max"]["x"]
    max_y = bbox["max"]["y"]
    max_z = bbox["max"].get("z", 0.0)

    return {
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "min_z": min_z,
        "max_z": max_z,
        "x": (min_x + max_x) / 2,
        "y": (min_y + max_y) / 2,
        "length": max_x - min_x,
        "width": max_y - min_y,
        "height": max_z - min_z,
    }


def fetch_metrics(token, element_id):
    return extract_bbox_metrics(fetch_raw_bbox(token, element_id))


def envelope_from_metrics(metrics_list, origin_x, origin_y):
    if not metrics_list:
        return None

    return {
        "min_x": min(item["min_x"] for item in metrics_list) - origin_x,
        "max_x": max(item["max_x"] for item in metrics_list) - origin_x,
        "min_y": min(item["min_y"] for item in metrics_list) - origin_y,
        "max_y": max(item["max_y"] for item in metrics_list) - origin_y,
        "min_z": min(item["min_z"] for item in metrics_list),
        "max_z": max(item["max_z"] for item in metrics_list),
        "height": max(item["max_z"] for item in metrics_list) - min(item["min_z"] for item in metrics_list),
    }


def relative_corners_from_metrics(metrics, origin_x, origin_y):
    return [
        {"x": metrics["min_x"] - origin_x, "y": metrics["min_y"] - origin_y},
        {"x": metrics["max_x"] - origin_x, "y": metrics["min_y"] - origin_y},
        {"x": metrics["max_x"] - origin_x, "y": metrics["max_y"] - origin_y},
        {"x": metrics["min_x"] - origin_x, "y": metrics["max_y"] - origin_y},
    ]


def convex_hull(points):
    unique_points = sorted({(round(point["x"], 6), round(point["y"], 6)) for point in points})
    if len(unique_points) <= 1:
        return [{"x": x, "y": y} for x, y in unique_points]

    def cross(origin, left, right):
        return (
            (left[0] - origin[0]) * (right[1] - origin[1])
            - (left[1] - origin[1]) * (right[0] - origin[0])
        )

    lower = []
    for point in unique_points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper = []
    for point in reversed(unique_points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)

    hull = lower[:-1] + upper[:-1]
    return [{"x": x, "y": y} for x, y in hull]


def create_relative_obstacle(metrics, origin_x, origin_y, *, obstacle_id, name, kind, group_key=None):
    obstacle = {
        "id": obstacle_id,
        "name": name,
        "kind": kind,
        "x": metrics["x"] - origin_x,
        "y": metrics["y"] - origin_y,
        "length": metrics["length"],
        "width": metrics["width"],
        "min_z": metrics["min_z"],
        "max_z": metrics["max_z"],
        "height": metrics["height"],
    }
    if group_key:
        obstacle["group_key"] = group_key
    return obstacle


def default_phases():
    return [
        {
            "id": "phase-structure",
            "name": "主体施工",
            "sequence": 1,
            "objective": "围绕主体结构吊装、钢筋和模板堆场进行场布。",
            "start_day": 1,
            "end_day": 28,
            "status": "active",
        },
        {
            "id": "phase-envelope",
            "name": "外围封闭",
            "sequence": 2,
            "objective": "优先保证机电材料与外立面周转路径。",
            "start_day": 29,
            "end_day": 52,
            "status": "planned",
        },
        {
            "id": "phase-fitout",
            "name": "机电穿插",
            "sequence": 3,
            "objective": "控制小批量、多频次物料的临时落位和清运节奏。",
            "start_day": 53,
            "end_day": 84,
            "status": "planned",
        },
    ]


def default_control_zones(site_boundary, building_envelopes):
    building_1 = building_envelopes.get("building_1")
    building_2 = building_envelopes.get("building_2")
    building_3 = building_envelopes.get("building_3")
    if not building_1:
        return []

    north_center_x = (building_1["min_x"] + building_1["max_x"]) / 2
    north_center_y = building_1["max_y"] + 7.5
    west_center_x = building_1["min_x"] - 6.2
    west_center_y = (building_1["min_y"] + building_1["max_y"]) / 2
    south_center_x = (
        max(building_2["min_x"] - 10.5, site_boundary["min_x"] + 9)
        if building_2
        else site_boundary["min_x"] + 9
    )
    south_center_y = site_boundary["min_y"] + 8
    east_center_x = (
        min(site_boundary["max_x"] - 8, (building_3["max_x"] + site_boundary["max_x"]) / 2)
        if building_3
        else site_boundary["max_x"] - 8
    )
    east_center_y = (
        building_3["min_y"] - 14.0
        if building_3
        else (site_boundary["min_y"] + site_boundary["max_y"]) / 2
    )

    return [
        {
            "id": "zone-north-staging",
            "name": "北侧钢筋暂存区",
            "zone_type": "staging",
            "x": north_center_x,
            "y": north_center_y,
            "length": 18,
            "width": 10,
            "phase_id": "phase-structure",
            "blocking": False,
            "penalty_factor": 1.0,
        },
        {
            "id": "zone-west-buffer",
            "name": "西侧模板缓冲区",
            "zone_type": "staging",
            "x": west_center_x,
            "y": west_center_y,
            "length": 12,
            "width": 18,
            "phase_id": "phase-structure",
            "blocking": False,
            "penalty_factor": 1.1,
        },
        {
            "id": "zone-south-delivery",
            "name": "南侧卸料通道",
            "zone_type": "delivery_lane",
            "x": south_center_x,
            "y": south_center_y,
            "length": 18,
            "width": 6,
            "phase_id": "phase-structure",
            "blocking": True,
            "penalty_factor": 1.0,
        },
        {
            "id": "zone-east-emergency",
            "name": "东侧应急通廊",
            "zone_type": "emergency_access",
            "x": east_center_x,
            "y": east_center_y,
            "length": 8,
            "width": 26,
            "phase_id": None,
            "blocking": True,
            "penalty_factor": 1.0,
        },
    ]


def push_snapshot_to_fastapi(sync_url, payload):
    response = requests.put(
        sync_url,
        json=payload,
        proxies={"http": None, "https": None},
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    ensure_gateway_config()
    token = get_access_token()
    print("Starting BIM gateway extraction...\n")

    payload_for_ga = {
        "name": PROJECT_NAME,
        "site_boundary": {
            "min_x": float("inf"),
            "max_x": float("-inf"),
            "min_y": float("inf"),
            "max_y": float("-inf"),
        },
        "phases": default_phases(),
        "active_phase_id": "phase-structure",
        "control_zones": [],
        "working_cranes": [],
        "obstacles": [],
        "materials": [],
        "scene_guides": {
            "wall_envelope": None,
            "wall_boundary_path": [],
            "building_envelopes": {},
            "recommended_road_offset": 1500,
        },
    }

    crane_bbox = fetch_metrics(token, ROLE_MAP_IDS["center_crane"]["id"])
    if not crane_bbox:
        raise SystemExit("Failed to fetch center crane bounding box.")

    origin_x = crane_bbox["x"]
    origin_y = crane_bbox["y"]
    payload_for_ga["working_cranes"].append(
        {
            "id": ROLE_MAP_IDS["center_crane"]["id"],
            "name": ROLE_MAP_IDS["center_crane"]["name"],
            "x": 0.0,
            "y": 0.0,
            "max_radius": ROLE_MAP_IDS["center_crane"]["max_radius"],
            "capacity_tons": ROLE_MAP_IDS["center_crane"]["capacity_tons"],
            "priority_score": ROLE_MAP_IDS["center_crane"]["priority_score"],
        }
    )
    print(f"Center crane locked as origin: ({origin_x:.2f}, {origin_y:.2f})")

    for crane in ROLE_MAP_IDS["other_cranes"]:
        metrics = fetch_metrics(token, crane["id"])
        if not metrics:
            continue

        payload_for_ga["obstacles"].append(
            create_relative_obstacle(
                metrics,
                origin_x,
                origin_y,
                obstacle_id=crane["id"],
                name=crane["name"],
                kind="crane",
            )
        )
        payload_for_ga["working_cranes"].append(
            {
                "id": crane["id"],
                "name": crane["name"],
                "x": metrics["x"] - origin_x,
                "y": metrics["y"] - origin_y,
                "max_radius": crane["max_radius"],
                "capacity_tons": crane["capacity_tons"],
                "priority_score": crane["priority_score"],
            }
        )

    for group_key, config in ROLE_MAP_IDS["buildings"].items():
        group_metrics = []
        for index, element_id in enumerate(config["ids"], start=1):
            metrics = fetch_metrics(token, element_id)
            if not metrics:
                continue

            group_metrics.append(metrics)
            payload_for_ga["obstacles"].append(
                create_relative_obstacle(
                    metrics,
                    origin_x,
                    origin_y,
                    obstacle_id=element_id,
                    name=f"{config['name']} Part {index}",
                    kind="building",
                    group_key=group_key,
                )
            )

        group_envelope = envelope_from_metrics(group_metrics, origin_x, origin_y)
        if not group_envelope:
            continue

        payload_for_ga["scene_guides"]["building_envelopes"][group_key] = group_envelope

    for index, element_id in enumerate(ROLE_MAP_IDS["road_segments"], start=1):
        metrics = fetch_metrics(token, element_id)
        if not metrics:
            continue

        payload_for_ga["obstacles"].append(
            create_relative_obstacle(
                metrics,
                origin_x,
                origin_y,
                obstacle_id=element_id,
                name=f"Road Segment {index}",
                kind="road",
            )
        )

    wall_metrics = []
    wall_boundary_points = []
    for index, element_id in enumerate(ROLE_MAP_IDS["wall_segments"], start=1):
        metrics = fetch_metrics(token, element_id)
        if not metrics:
            continue

        wall_metrics.append(metrics)
        wall_boundary_points.extend(relative_corners_from_metrics(metrics, origin_x, origin_y))
        payload_for_ga["obstacles"].append(
            create_relative_obstacle(
                metrics,
                origin_x,
                origin_y,
                obstacle_id=element_id,
                name=f"Wall Segment {index}",
                kind="wall",
            )
        )

        payload_for_ga["site_boundary"]["min_x"] = min(
            payload_for_ga["site_boundary"]["min_x"],
            metrics["min_x"] - origin_x,
        )
        payload_for_ga["site_boundary"]["max_x"] = max(
            payload_for_ga["site_boundary"]["max_x"],
            metrics["max_x"] - origin_x,
        )
        payload_for_ga["site_boundary"]["min_y"] = min(
            payload_for_ga["site_boundary"]["min_y"],
            metrics["min_y"] - origin_y,
        )
        payload_for_ga["site_boundary"]["max_y"] = max(
            payload_for_ga["site_boundary"]["max_y"],
            metrics["max_y"] - origin_y,
        )

    payload_for_ga["scene_guides"]["wall_envelope"] = envelope_from_metrics(
        wall_metrics,
        origin_x,
        origin_y,
    )
    payload_for_ga["scene_guides"]["wall_boundary_path"] = convex_hull(wall_boundary_points)
    payload_for_ga["control_zones"] = default_control_zones(
        payload_for_ga["site_boundary"],
        payload_for_ga["scene_guides"]["building_envelopes"],
    )

    print(json.dumps(payload_for_ga, indent=4, ensure_ascii=False))

    if PROJECT_SYNC_URL:
        print(f"\nSyncing gateway payload to FastAPI: {PROJECT_SYNC_URL}")
        push_snapshot_to_fastapi(PROJECT_SYNC_URL, payload_for_ga)
        print("FastAPI project snapshot updated.")
