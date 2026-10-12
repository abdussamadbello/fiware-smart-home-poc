#!/usr/bin/env python3
"""Second southbound interface (camera-ready 2026): UltraLight 2.0 over MQTT.

Different transport (MQTT vs HTTP) AND different payload model
(UL2.0 pipe-delimited 'h|55|t|23.1' vs JSON {"t": 23.1}) than the default
simulator. Devices are provisioned on the IoT Agent UL and normalised into the
same Orion NGSI-v2 context (same Fiware-Service, same entity types/attr names
where semantics match, e.g. TemperatureSensor.temperature).
"""
from __future__ import annotations
import os, random, time
import httpx
import paho.mqtt.client as mqtt

ORION = os.getenv("ORION_URL", "http://localhost:1026")
IOTA_UL = os.getenv("IOTA_UL_URL", "http://localhost:4061")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
API_KEY = os.getenv("UL_API_KEY", "ulSmartHomeKey")
H = {"Fiware-Service": os.getenv("FIWARE_SERVICE", "smartHome"),
     "Fiware-ServicePath": os.getenv("FIWARE_SERVICEPATH", "/"),
     "Content-Type": "application/json"}

DEVICES = [
    {"device_id": "ulTmpGAR", "entity_name": "Temperature:Garage", "entity_type": "TemperatureSensor",
     "attributes": [{"object_id": "t", "name": "temperature", "type": "Number"}], "room": "Garage"},
    {"device_id": "ulHumGAR", "entity_name": "Humidity:Garage", "entity_type": "HumiditySensor",
     "attributes": [{"object_id": "h", "name": "relativeHumidity", "type": "Number"}], "room": "Garage"},
    {"device_id": "ulPlugKIT", "entity_name": "SmartPlug:Kitchen", "entity_type": "SmartPlug",
     "attributes": [{"object_id": "p", "name": "activePower", "type": "Number"},
                    {"object_id": "s", "name": "state", "type": "Text"}], "room": "Kitchen"},
]


def provision(c: httpx.Client) -> None:
    r = c.post(f"{IOTA_UL}/iot/services", headers=H, json={"services": [{
        "apikey": API_KEY, "cbroker": "http://orion:1026", "entity_type": "Thing", "resource": "/iot/d"}]})
    print("[ul] service group", r.status_code, r.text[:120])
    devs = [{"device_id": d["device_id"], "entity_name": d["entity_name"], "entity_type": d["entity_type"],
             "protocol": "PDI-IoTA-UltraLight", "transport": "MQTT", "attributes": d["attributes"],
             "static_attributes": [{"name": "refRoom", "type": "Text", "value": d["room"]},
                                   {"name": "category", "type": "Text", "value": "sensor"},
                                   {"name": "southbound", "type": "Text", "value": "MQTT/UL2.0"}]}
            for d in DEVICES]
    r = c.post(f"{IOTA_UL}/iot/devices", headers=H, json={"devices": devs})
    print("[ul] devices", r.status_code, r.text[:200])


def ul_payload(d: dict) -> str:
    t = d["entity_type"]
    if t == "TemperatureSensor":
        return f"t|{round(random.uniform(18, 34), 1)}"
    if t == "HumiditySensor":
        return f"h|{round(random.uniform(30, 90), 1)}"
    on = random.random() < 0.5
    return f"p|{round(random.uniform(5, 1500), 1) if on else 0}|s|{'ON' if on else 'OFF'}"


def connect() -> mqtt.Client:
    cl = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ul-sim")
    cl.connect(MQTT_HOST, MQTT_PORT)
    cl.loop_start()
    return cl


def main() -> None:
    with httpx.Client(timeout=20) as c:
        provision(c)
    cl = connect()
    n = int(os.getenv("UL_TICKS", "0"))  # 0 = forever
    i = 0
    while n == 0 or i < n:
        for d in DEVICES:
            cl.publish(f"/{API_KEY}/{d['device_id']}/attrs", ul_payload(d), qos=1)
        i += 1
        time.sleep(float(os.getenv("SIM_INTERVAL_SEC", "10")))


if __name__ == "__main__":
    main()
