#!/usr/bin/env python3
"""
Provision FIWARE IoT Agent service group + virtual smart-home devices,
create Orion entities / QuantumLeap subscriptions, then simulate sensor traffic.
Thesis-faithful reimplementation 2026.
"""
from __future__ import annotations

import os
import random
import time
from datetime import datetime, timezone

import httpx

ORION = os.getenv("ORION_URL", "http://orion:1026").rstrip("/")
IOTA = os.getenv("IOTA_URL", "http://iot-agent:4041").rstrip("/")
IOTA_SOUTH = os.getenv("IOTA_SOUTH_URL", "http://iot-agent:7896").rstrip("/")
QL = os.getenv("QUANTUMLEAP_URL", "http://quantumleap:8668").rstrip("/")
SERVICE = os.getenv("FIWARE_SERVICE", "smartHome")
SERVICE_PATH = os.getenv("FIWARE_SERVICEPATH", "/")
API_KEY = os.getenv("API_KEY", "smartHomeKey")
INTERVAL = float(os.getenv("SIM_INTERVAL_SEC", "10"))

ROOMS = ["LivingRoom", "Bedroom", "Kitchen", "Hallway"]

HEADERS = {
    "Fiware-Service": SERVICE,
    "Fiware-ServicePath": SERVICE_PATH,
    "Content-Type": "application/json",
}


def wait_http(url: str, name: str, timeout: int = 180) -> None:
    print(f"[wait] {name} at {url} ...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(url, timeout=3.0)
            if r.status_code < 500:
                print(f"[wait] {name} ready ({r.status_code})")
                return
        except Exception:
            pass
        time.sleep(3)
    print(f"[wait] {name} not ready after {timeout}s — continuing anyway")


def provision_service_group(client: httpx.Client) -> None:
    body = {
        "services": [
            {
                "apikey": API_KEY,
                "cbroker": f"{ORION}",
                "entity_type": "Thing",
                "resource": "/iot/json",
            }
        ]
    }
    r = client.post(f"{IOTA}/iot/services", headers=HEADERS, json=body)
    print(f"[provision] service group -> {r.status_code} {r.text[:200]}")


def device_defs() -> list[dict]:
    devices = []
    for room in ROOMS:
        short = room[:3].upper()
        # Sensors
        devices.append(
            {
                "device_id": f"mot{short}",
                "entity_name": f"Motion:{room}",
                "entity_type": "MotionSensor",
                "attributes": [{"object_id": "m", "name": "motion", "type": "Boolean"}],
                "static_attributes": [
                    {"name": "refRoom", "type": "Text", "value": room},
                    {"name": "category", "type": "Text", "value": "sensor"},
                ],
            }
        )
        devices.append(
            {
                "device_id": f"lux{short}",
                "entity_name": f"Luminosity:{room}",
                "entity_type": "LuminositySensor",
                "attributes": [{"object_id": "l", "name": "luminosity", "type": "Number"}],
                "static_attributes": [
                    {"name": "refRoom", "type": "Text", "value": room},
                    {"name": "category", "type": "Text", "value": "sensor"},
                ],
            }
        )
        devices.append(
            {
                "device_id": f"tmp{short}",
                "entity_name": f"Temperature:{room}",
                "entity_type": "TemperatureSensor",
                "attributes": [{"object_id": "t", "name": "temperature", "type": "Number"}],
                "static_attributes": [
                    {"name": "refRoom", "type": "Text", "value": room},
                    {"name": "category", "type": "Text", "value": "sensor"},
                ],
            }
        )
        # Actuators
        devices.append(
            {
                "device_id": f"bulb{short}",
                "entity_name": f"Bulb:{room}",
                "entity_type": "Bulb",
                "attributes": [
                    {"object_id": "s", "name": "state", "type": "Text"},
                    {"object_id": "lt", "name": "luminosityTarget", "type": "Number"},
                ],
                "commands": [
                    {"name": "on", "type": "command"},
                    {"name": "off", "type": "command"},
                ],
                "static_attributes": [
                    {"name": "refRoom", "type": "Text", "value": room},
                    {"name": "category", "type": "Text", "value": "actuator"},
                ],
            }
        )
        devices.append(
            {
                "device_id": f"fan{short}",
                "entity_name": f"Fan:{room}",
                "entity_type": "Fan",
                "attributes": [{"object_id": "s", "name": "state", "type": "Text"}],
                "commands": [
                    {"name": "on", "type": "command"},
                    {"name": "off", "type": "command"},
                ],
                "static_attributes": [
                    {"name": "refRoom", "type": "Text", "value": room},
                    {"name": "category", "type": "Text", "value": "actuator"},
                ],
            }
        )
        devices.append(
            {
                "device_id": f"hvac{short}",
                "entity_name": f"HVAC:{room}",
                "entity_type": "HVAC",
                "attributes": [
                    {"object_id": "s", "name": "state", "type": "Text"},
                    {"object_id": "tt", "name": "targetTemperature", "type": "Number"},
                ],
                "commands": [{"name": "setTemperature", "type": "command"}],
                "static_attributes": [
                    {"name": "refRoom", "type": "Text", "value": room},
                    {"name": "category", "type": "Text", "value": "actuator"},
                ],
            }
        )
    # Shared remote actuators: bell + doors
    devices.append(
        {
            "device_id": "bellMAIN",
            "entity_name": "Bell:Entrance",
            "entity_type": "Bell",
            "attributes": [
                {"object_id": "s", "name": "state", "type": "Text"},
                {"object_id": "lr", "name": "lastRing", "type": "DateTime"},
            ],
            "commands": [{"name": "ring", "type": "command"}],
            "static_attributes": [
                {"name": "refRoom", "type": "Text", "value": "Hallway"},
                {"name": "category", "type": "Text", "value": "actuator"},
            ],
        }
    )
    for room in ("Hallway", "LivingRoom"):
        short = room[:3].upper()
        devices.append(
            {
                "device_id": f"door{short}",
                "entity_name": f"Door:{room}",
                "entity_type": "Door",
                "attributes": [{"object_id": "s", "name": "state", "type": "Text"}],
                "commands": [
                    {"name": "open", "type": "command"},
                    {"name": "close", "type": "command"},
                ],
                "static_attributes": [
                    {"name": "refRoom", "type": "Text", "value": room},
                    {"name": "category", "type": "Text", "value": "actuator"},
                ],
            }
        )
    return devices


def provision_devices(client: httpx.Client, devices: list[dict]) -> None:
    # IoT Agent accepts batches; chunk to be safe
    chunk = 10
    for i in range(0, len(devices), chunk):
        batch = devices[i : i + chunk]
        payload = []
        for d in batch:
            item = {
                "device_id": d["device_id"],
                "entity_name": d["entity_name"],
                "entity_type": d["entity_type"],
                "protocol": "IoTA-JSON",
                "transport": "HTTP",
                "attributes": d.get("attributes", []),
                "static_attributes": d.get("static_attributes", []),
            }
            if d.get("commands"):
                item["commands"] = d["commands"]
            payload.append(item)
        r = client.post(f"{IOTA}/iot/devices", headers=HEADERS, json={"devices": payload})
        print(f"[provision] devices {i}-{i+len(batch)} -> {r.status_code}")
        if r.status_code >= 400:
            print(r.text[:300])


def upsert_orion_entities(client: httpx.Client, devices: list[dict]) -> None:
    """Ensure entities exist even if IoT Agent registration is slow."""
    for d in devices:
        etype = d["entity_type"]
        eid = d["entity_name"]
        room = next((a["value"] for a in d.get("static_attributes", []) if a["name"] == "refRoom"), "Unknown")
        attrs = {
            "refRoom": {"type": "Text", "value": room},
            "category": {
                "type": "Text",
                "value": next((a["value"] for a in d.get("static_attributes", []) if a["name"] == "category"), "device"),
            },
        }
        if etype == "MotionSensor":
            attrs["motion"] = {"type": "Boolean", "value": False}
        elif etype == "LuminositySensor":
            attrs["luminosity"] = {"type": "Number", "value": 200}
        elif etype == "TemperatureSensor":
            attrs["temperature"] = {"type": "Number", "value": 22.0}
        elif etype in ("Bulb", "Fan"):
            attrs["state"] = {"type": "Text", "value": "OFF"}
            if etype == "Bulb":
                attrs["luminosityTarget"] = {"type": "Number", "value": 0}
        elif etype == "Door":
            attrs["state"] = {"type": "Text", "value": "CLOSED"}
        elif etype == "Bell":
            attrs["state"] = {"type": "Text", "value": "IDLE"}
        elif etype == "HVAC":
            attrs["state"] = {"type": "Text", "value": "OFF"}
            attrs["targetTemperature"] = {"type": "Number", "value": 22}
        entity = {"id": eid, "type": etype, **attrs}
        r = client.post(f"{ORION}/v2/entities?options=upsert", headers=HEADERS, json=entity)
        if r.status_code not in (201, 204):
            # fallback upsert via PATCH after POST
            r2 = client.post(f"{ORION}/v2/entities", headers=HEADERS, json=entity)
            if r2.status_code not in (201, 422):
                print(f"[orion] upsert {eid} -> {r.status_code}/{r2.status_code}")


def create_ql_subscriptions(client: httpx.Client) -> None:
    types = [
        "MotionSensor",
        "LuminositySensor",
        "TemperatureSensor",
        "Bulb",
        "Fan",
        "Door",
        "Bell",
        "HVAC",
    ]
    for t in types:
        sub = {
            "description": f"Notify QuantumLeap of {t}",
            "subject": {
                "entities": [{"idPattern": ".*", "type": t}],
                "condition": {"attrs": []},
            },
            "notification": {
                "http": {"url": f"{QL}/v2/notify"},
                "attrsFormat": "normalized",
                "metadata": ["dateCreated", "dateModified"],
            },
            "throttling": 1,
        }
        r = client.post(f"{ORION}/v2/subscriptions", headers=HEADERS, json=sub)
        print(f"[subscription] {t} -> {r.status_code}")


def simulate_once(client: httpx.Client, devices: list[dict]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for d in devices:
        did = d["device_id"]
        etype = d["entity_type"]
        eid = d["entity_name"]
        payload = None
        orion_attrs = None
        if etype == "MotionSensor":
            motion = random.random() < 0.25
            payload = {"m": motion}
            orion_attrs = {"motion": {"type": "Boolean", "value": motion}}
        elif etype == "LuminositySensor":
            lux = round(random.uniform(50, 900), 1)
            payload = {"l": lux}
            orion_attrs = {"luminosity": {"type": "Number", "value": lux}}
            # Auto bulb response to luminosity (thesis: bulbs respond to luminosity)
            bulb_id = f"Bulb:{eid.split(':', 1)[1]}"
            state = "ON" if lux < 300 else "OFF"
            client.patch(
                f"{ORION}/v2/entities/{bulb_id}/attrs",
                headers=HEADERS,
                json={
                    "state": {"type": "Text", "value": state},
                    "luminosityTarget": {"type": "Number", "value": 800 if state == "ON" else 0},
                },
            )
        elif etype == "TemperatureSensor":
            temp = round(random.uniform(18.0, 28.0), 1)
            payload = {"t": temp}
            orion_attrs = {"temperature": {"type": "Number", "value": temp}}
        elif etype in ("Bulb", "Fan", "Door", "Bell", "HVAC"):
            # occasional heartbeat of current state — skip southbound for actuators
            continue

        if payload is not None:
            url = f"{IOTA_SOUTH}/iot/json?k={API_KEY}&i={did}"
            try:
                r = client.post(url, headers={"Content-Type": "application/json"}, json=payload)
                if r.status_code >= 400:
                    # direct Orion update fallback
                    if orion_attrs:
                        client.patch(f"{ORION}/v2/entities/{eid}/attrs", headers=HEADERS, json=orion_attrs)
            except Exception as e:
                if orion_attrs:
                    client.patch(f"{ORION}/v2/entities/{eid}/attrs", headers=HEADERS, json=orion_attrs)
                print(f"[sim] southbound fail {did}: {e}")
    print(f"[sim] tick {now}")


def main() -> None:
    wait_http(f"{ORION}/version", "Orion")
    wait_http(f"{IOTA}/iot/about", "IoT Agent")
    # QuantumLeap optional
    try:
        httpx.get(f"{QL}/version", timeout=3.0)
        ql_up = True
    except Exception:
        ql_up = False
        print("[wait] QuantumLeap not reachable — history subscriptions may fail")

    devices = device_defs()
    with httpx.Client(timeout=30.0) as client:
        provision_service_group(client)
        provision_devices(client, devices)
        upsert_orion_entities(client, devices)
        if ql_up:
            create_ql_subscriptions(client)
        print(f"[sim] starting loop every {INTERVAL}s with {len(devices)} devices")
        while True:
            try:
                simulate_once(client, devices)
            except Exception as e:
                print(f"[sim] error: {e}")
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
