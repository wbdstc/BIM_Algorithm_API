import base64
import json
import os

import requests


APP_KEY = "HB35SuUr16CKDSdwCFIO5O8FqorB8kDg"
APP_SECRET = "HnxoLayhiOgXzSlo7bg42ej9bizr1Wku"
FILE_ID = "10000990421273"
PROJECT_NAME = "BIM 智慧工地 AI 场布示范项目"
PROJECT_SYNC_URL = os.getenv("DATA_GATEWAY_SYNC_URL")

ROLE_MAP_IDS = {
    "center_crane": {
        "id": "5327272_5311976",
        "name": "main_crane_1",
        "max_radius": 3200,
        "capacity_tons": 18,
        "priority_score": 1.0,
    },
    "other_cranes": [
        {
            "id": "5327272_5312858",
            "name": "副塔吊_2",
            "max_radius": 2800,
            "capacity_tons": 16,
            "priority_score": 0.96,
        },
        {
            "id": "5327272_5312036",
            "name": "副塔吊_3",
            "max_radius": 2800,
            "capacity_tons": 16,
            "priority_score": 0.94,
        },
    ],
    "buildings": {
        "building_1": {
            "name": "主体建筑1",
            "ids": [
                "5327272_5311496",
                "5327272_5311502",
                "5327272_5311484",
                "5327272_5311490",
            ],
        },
        "building_2": {
            "name": "主体建筑2",
            "ids": [
                "5327272_5311535",
                "5327272_5311529",
                "5327272_5311517",
                "5327272_5311523",
                "5327272_5311910",
            ],
        },
        "building_3": {
            "name": "主体建筑3",
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


def push_snapshot_to_fastapi(sync_url, payload):
    response = requests.put(
        sync_url,
        json=payload,
        proxies={"http": None, "https": None},
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
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
        "working_cranes": [],
        "obstacles": [],
        "materials": [],
        "scene_guides": {
            "wall_envelope": None,
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
        group_metrics = [metrics for element_id in config["ids"] if (metrics := fetch_metrics(token, element_id))]
        group_envelope = envelope_from_metrics(group_metrics, origin_x, origin_y)
        if not group_envelope:
            continue

        payload_for_ga["scene_guides"]["building_envelopes"][group_key] = group_envelope
        payload_for_ga["obstacles"].append(
            {
                "id": group_key,
                "name": config["name"],
                "kind": "building",
                "group_key": group_key,
                "x": (group_envelope["min_x"] + group_envelope["max_x"]) / 2,
                "y": (group_envelope["min_y"] + group_envelope["max_y"]) / 2,
                "length": group_envelope["max_x"] - group_envelope["min_x"],
                "width": group_envelope["max_y"] - group_envelope["min_y"],
                "min_z": group_envelope["min_z"],
                "max_z": group_envelope["max_z"],
                "height": group_envelope["height"],
            }
        )

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
                name=f"道路段_{index}",
                kind="road",
            )
        )

    wall_metrics = []
    for index, element_id in enumerate(ROLE_MAP_IDS["wall_segments"], start=1):
        metrics = fetch_metrics(token, element_id)
        if not metrics:
            continue

        wall_metrics.append(metrics)
        payload_for_ga["obstacles"].append(
            create_relative_obstacle(
                metrics,
                origin_x,
                origin_y,
                obstacle_id=element_id,
                name=f"围墙段_{index}",
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

    print(json.dumps(payload_for_ga, indent=4, ensure_ascii=False))

    if PROJECT_SYNC_URL:
        print(f"\nSyncing gateway payload to FastAPI: {PROJECT_SYNC_URL}")
        push_snapshot_to_fastapi(PROJECT_SYNC_URL, payload_for_ga)
        print("FastAPI project snapshot updated.")
