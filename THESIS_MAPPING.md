# Thesis component → this repository

**Source:** Abdussamad Bello, *Design and Implementation of IoT-Based Reference Architecture for Smart Homes*, MSc thesis, Atilim University, January 2022 — Chapter 6 / Table 6.1.

**Label:** thesis-faithful reimplementation 2026 (not a bit-for-bit copy of the original private PoC source).

| Thesis layer (Table 6.1) | Thesis technology | This repo |
|---|---|---|
| Devices → Virtual Things | Sensors & actuators (virtual) | `scripts/provision_and_simulate.py` — rooms LivingRoom, Bedroom, Kitchen, Hallway with Motion / Luminosity / Temperature sensors; Bulb, Fan, Door, Bell, HVAC actuators |
| IoT Gateway | FIWARE IoT Agent | `docker-compose.yml` service `iot-agent` (`quay.io/fiware/iotagent-json`) |
| Context Information management | Orion Context Broker & MongoDB | services `orion`, `mongo-db` |
| Device Management | Keyrock & MySQL | services `keyrock`, `mysql-db` (+ IoT Agent device registry) |
| Identity Management | Keyrock & MySQL | `keyrock` / `mysql-db`; web login in `app/main.py` (OAuth2 password + token API, local fallback) |
| Data Management | QuantumLeap, CrateDB & MongoDB | services `quantumleap`, `crate-db`, `redis-db`; Orion still on MongoDB |
| Smart Home Application | Web smart home application | `app/` (FastAPI + Jinja): login, devices, history, reports |

## Functional requirements coverage

| Requirement | Implementation |
|---|---|
| Sensors per room: motion, luminosity, thermometer | Simulator provisions all three per room |
| Bulbs respond to luminosity | Simulator auto-toggles bulb ON when lux &lt; 300 |
| Bells (remote) | `Bell:Entrance` + Ring command |
| Fans on/off | Fan entities + On/Off |
| Doors close remote | Door entities + Open/Close |
| HVAC with temperature | HVAC + Set °C |
| Login username/password (Keyrock/OAuth2) | `/login` → Keyrock, local demo fallback |
| View device rooms | `/devices` grouped by room |
| Toggle if authorized | Admin/homeowner can toggle; guest cannot; logged-out gets auth error |
| Motion history / luminosity realtime | `/history`, `/reports` via QuantumLeap (+ Orion live values) |
| Logout / reports | `/logout`, `/reports` |

## Non-functional

- Secure privileges: role-gated toggle (`can_toggle`)
- Modular: Compose profiles `always-on core` / `idm` / `history` / `app` / `full`
- Scalable: FIWARE GE pattern; production would use FIWARE Helm charts
