# bench/ — camera-ready measurements (Paper 215, SustainableAIoT-Afrasia 2026)

Run 21 Oct 2026 (WAT) on the host in `host_specs.txt`. Values in the paper come only from these files.

| File | Content | Paper |
|---|---|---|
| `results_core.json`, `results_full.json` | `bench.py core` / `bench.py full --mqtt`: E2E latency (n=200), app commands (n=100/role), 15 s throughput at c=1/4/16/64 | Table III |
| `stats_{core,full}_idle.csv` | `dstats.sh` 5 idle samples | Table II |
| `stats_{core,full}_load_{orion,iota}.csv`, `load60_*.json` | `stats_under_load.sh`: 10 samples during a 60 s c=4 workload | Table II |
| `stats_summary.json` | `summarize.py` output | Table II |
| `interop_*.json`, `interop_ql_garage.json` | Orion entities from both agents; QuantumLeap series for the MQTT/UL sensor | Sec. III |
| `ql_throttle_window.txt` | QuantumLeap record counts per entity over 120 s, before/after removing the 1 s subscription throttle | Sec. V |
| `security_probe.txt` | unauthenticated Orion PATCH / IoT Agent measurement status codes | Sec. V |
| `run-2026-10-12/` | earlier run (vfs storage driver, throttled subscriptions); superseded, not used in the paper | — |
| `superseded/` | load samples taken at uncontrolled phases of bench.py; replaced by the fixed 60 s workload | — |

Reproduce: `docker compose --profile app up -d` (core) or `--profile full up -d`; for full also run `scripts/simulate_ul_mqtt.py`; then `python bench.py <label> [--mqtt]`, `sh dstats.sh stats_<label>_idle.csv 5`, `sh stats_under_load.sh <label>`, `python summarize.py`.
