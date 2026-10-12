#!/usr/bin/env python3
"""Camera-ready micro-benchmark for the FIWARE smart-home PoC (host-side).
Measures: (1) southbound->Orion end-to-end update latency for HTTP/JSON and
MQTT/UL2.0; (2) app command latency (homeowner allowed, guest denied);
(3) Orion northbound update throughput at concurrency 1/4/16/64;
(4) IoT-Agent southbound ingest throughput at the same concurrency.
Writes JSON to bench/results_<label>.json. Only measured values are written."""
from __future__ import annotations
import asyncio, json, os, statistics, sys, time, random, platform
import httpx

ORION = "http://localhost:1026"; IOTA_S = "http://localhost:7896"; APP = "http://localhost:8080"
H = {"Fiware-Service": "smartHome", "Fiware-ServicePath": "/"}
LABEL = sys.argv[1] if len(sys.argv) > 1 else "core"
DO_MQTT = "--mqtt" in sys.argv
N_LAT = int(os.getenv("N_LAT", "200")); DUR = float(os.getenv("DUR", "15"))


def pct(xs, p):
    xs = sorted(xs); k = (len(xs) - 1) * p / 100; f = int(k); c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def summ(xs):
    return {"n": len(xs), "mean_ms": statistics.mean(xs), "p50_ms": pct(xs, 50), "p95_ms": pct(xs, 95),
            "p99_ms": pct(xs, 99), "max_ms": max(xs)}


def wait_value(c, eid, attr, val, t0, timeout=5.0):
    while time.perf_counter() - t0 < timeout:
        r = c.get(f"{ORION}/v2/entities/{eid}/attrs/{attr}/value", headers=H)
        if r.status_code == 200 and abs(float(r.text) - val) < 1e-6:
            return (time.perf_counter() - t0) * 1000
        time.sleep(0.002)
    return None


def e2e_http(c):
    out, miss = [], 0
    for i in range(N_LAT):
        v = round(15 + i * 0.01, 2)
        t0 = time.perf_counter()
        c.post(f"{IOTA_S}/iot/json?k=smartHomeKey&i=tmpKIT", json={"t": v})
        ms = wait_value(c, "Temperature:Kitchen", "temperature", v, t0)
        (out.append(ms) if ms else None); miss += ms is None
    return {**summ(out), "timeouts": miss}


def e2e_mqtt(c):
    import paho.mqtt.client as mqtt
    m = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bench"); m.connect("localhost", 1883); m.loop_start()
    out, miss = [], 0
    for i in range(N_LAT):
        v = round(40 + i * 0.01, 2)
        t0 = time.perf_counter()
        m.publish("/ulSmartHomeKey/ulTmpGAR/attrs", f"t|{v}", qos=1)
        ms = wait_value(c, "Temperature:Garage", "temperature", v, t0)
        (out.append(ms) if ms else None); miss += ms is None
    m.loop_stop()
    return {**summ(out), "timeouts": miss}


def app_cmd(c, email, pw, n=100):
    s = httpx.Client(base_url=APP, follow_redirects=False, timeout=15)
    r = s.post("/login", data={"email": email, "password": pw, "next": "/devices"})
    assert r.status_code == 303, r.status_code
    out, locs = [], {}
    for i in range(n):
        cmd = "fan_on" if i % 2 == 0 else "fan_off"
        t0 = time.perf_counter()
        r = s.post("/devices/Fan:LivingRoom/command", data={"command": cmd})
        out.append((time.perf_counter() - t0) * 1000)
        loc = r.headers.get("location", "")
        key = "denied" if "guest" in loc else ("failed" if "failed" in loc else "ok")
        locs[key] = locs.get(key, 0) + 1
    st = c.get(f"{ORION}/v2/entities/Fan:LivingRoom/attrs/state/value", headers=H).text
    return {**summ(out), "outcomes": locs, "final_state": st}


async def load(kind, conc):
    lat, err, stop = [], 0, time.perf_counter() + DUR
    async with httpx.AsyncClient(timeout=10, limits=httpx.Limits(max_connections=conc)) as c:
        async def worker(w):
            nonlocal err
            i = 0
            while time.perf_counter() < stop:
                i += 1; t0 = time.perf_counter()
                try:
                    if kind == "orion":
                        r = await c.patch(f"{ORION}/v2/entities/Temperature:Hallway/attrs", headers=H,
                                          json={"temperature": {"type": "Number", "value": random.uniform(18, 28)}})
                        ok = r.status_code == 204
                    else:
                        r = await c.post(f"{IOTA_S}/iot/json?k=smartHomeKey&i=lux{['LIV','BED','KIT','HAL'][w%4]}",
                                         json={"l": random.uniform(50, 900)})
                        ok = r.status_code == 200
                except Exception:
                    ok = False
                if ok: lat.append((time.perf_counter() - t0) * 1000)
                else: err += 1
        t = time.perf_counter()
        await asyncio.gather(*[worker(w) for w in range(conc)])
        el = time.perf_counter() - t
    return {"concurrency": conc, "duration_s": el, "ok": len(lat), "errors": err,
            "throughput_rps": len(lat) / el, **({k: v for k, v in summ(lat).items() if k != "n"} if lat else {})}


def main():
    res = {"label": LABEL, "started_local": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "python": platform.python_version()}
    with httpx.Client(timeout=10) as c:
        res["e2e_http_json"] = e2e_http(c); print("http", res["e2e_http_json"])
        if DO_MQTT:
            res["e2e_mqtt_ul"] = e2e_mqtt(c); print("mqtt", res["e2e_mqtt_ul"])
        res["app_cmd_homeowner"] = app_cmd(c, "homeowner@smarthome.local", "HomeOwner2022!"); print(res["app_cmd_homeowner"])
        res["app_cmd_guest"] = app_cmd(c, "guest@smarthome.local", "GuestView2022!"); print(res["app_cmd_guest"])
    for kind in ("orion", "iota"):
        res[f"load_{kind}"] = []
        for conc in (1, 4, 16, 64):
            r = asyncio.run(load(kind, conc)); print(kind, r); res[f"load_{kind}"].append(r)
    open(os.path.join(os.path.dirname(__file__), f"results_{LABEL}.json"), "w").write(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
