# Smoke-test log — 2026-09-22 (WAT / Africa/Lagos)

## Result: **PASS (failures=0)**

Full stack brought up on this box:

| Service | Status |
|---|---|
| Orion + MongoDB | healthy |
| IoT Agent JSON | healthy |
| Web app | healthy |
| Device simulator | running (27 virtual devices) |
| Keyrock + MySQL | up (Keyrock `/version` OK) |
| QuantumLeap + CrateDB + Redis | healthy |

### Happy path verified

1. Login as `homeowner@smarthome.local` → devices listed by room  
2. Actuator command (Fan) accepted for homeowner  
3. Guest `guest@smarthome.local` denied toggle (`Unauthorized: guest role cannot toggle actuators`)  
4. Logged-out device view shows auth error  
5. QuantumLeap history for `Motion:LivingRoom/motion` returns time series  
6. `./scripts/smoke_test.sh` → failures=0  

### Workarounds applied on this host

- Docker bridge **ICC broken** → `extra_hosts: host-gateway` for service DNS  
- Orion CLI: `-dbhost mongo-db` (not `-dbURI` with conflicting defaults)  
- IoT Agent: `IOTA_MQTT_DISABLED` / `IOTA_AMQP_DISABLED`  
- Healthchecks without `curl` where image lacks it  
- `CRATE_HEAP_SIZE=512m` for ~5 GiB free RAM  
- `AUTH_MODE=local` for reliable demo (Keyrock still running for IdM)

### Memory after full stack

~10 GiB used / ~5 GiB available (no swap).
