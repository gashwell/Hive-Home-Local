# Hive Home Local

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)

A unified local Home Assistant integration for the **complete Hive heating ecosystem** — all devices, no Hive cloud, no subscription.

Merges the best of two projects:
- **[Hive-TRV-Local](https://github.com/gashwell/Hive-TRV-Local)** — UK7004240 TRV support with full schedule, boost, room groups, holiday mode, and geofencing
- **[HA-Hive-Local-Thermostat](https://github.com/andrew-codechimp/HA-Hive-Local-Thermostat)** by [@andrew-codechimp](https://github.com/andrew-codechimp) — SLR1/SLR2/OTR1 hub support with heating and hot water control

---

## Supported devices

| Device | Model | Family | Features |
|---|---|---|---|
| Hive Radiator Valve | UK7004240 / TRV001 | TRV | Setpoint, boost, weekly schedule, room groups, holiday, geofencing |
| Single Channel Receiver | SLR1 | Hub | Heating control, boost |
| Dual Channel Receiver | SLR2 | Hub | Heating + hot water control, boost |
| Thermostat Receiver | OTR1 | Hub | Heating control |

---

## Requirements

- Home Assistant 2024.1+
- Zigbee2MQTT (any version supporting your devices)
- MQTT broker (Mosquitto)
- Devices already paired to Zigbee2MQTT

---

## Installation

### Via HACS

1. HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/gashwell/Hive-Home-Local` as type **Integration**
3. Install **Hive Home Local** and restart HA

### Manual

Copy `custom_components/hive_home_local/` to your HA `config/custom_components/` directory and restart.

---

## Setup

Settings → Integrations → Add → **Hive Home Local**

You'll be asked which device type to add. You can add **both** — one config entry per device family.

### Hub (SLR1 / SLR2 / OTR1)

Enter the Zigbee2MQTT MQTT topic for your hub device (e.g. `zigbee2mqtt/Hive Hub`) and select the model. For SLR2, optionally enable the Schedule preset mode for heating and hot water.

### TRVs (UK7004240)

Enter your Zigbee2MQTT base topic (default: `zigbee2mqtt`). TRVs are discovered automatically. Optionally configure a boiler entity and person entities for geofencing.

---

## TRV features

- **Auto-discovery** from Z2M `bridge/devices` with 30-second sweep fallback
- **Mode state machine**: off / manual / schedule / boost / away / holiday
- **Weekly schedules** — HA manages the schedule, pushes setpoints to TRVs
- **Advance schedule** — skip to the next slot immediately
- **Boost** — timed override at configurable temperature, auto-restores on expiry
- **Room groups** — aggregate multiple TRVs and external temperature sensors into one climate entity
- **Holiday mode** — frost protection for a date range, restores automatically on return
- **Geofencing** — all tracked persons away → frost protection activates automatically
- **Boiler demand management** — drives your boiler/receiver entity from aggregate heat demand

## Hub features

- **Heating control** — set temperature, mode, boost via MQTT
- **Hot water control** — SLR2 hot water boost and mode (schedule, manual, off)
- **Boost** — timed heating/water boost with configurable duration and temperature
- **Diagnostics** — full MQTT payload exposed via diagnostics

---

## Services

### Hub services

| Service | Description |
|---|---|
| `hive_home_local.boost_heating` | Start timed heating boost |
| `hive_home_local.cancel_boost_heating` | Cancel heating boost |
| `hive_home_local.boost_water` | Start timed hot water boost (SLR2) |
| `hive_home_local.cancel_boost_water` | Cancel hot water boost |

### TRV services

| Service | Description |
|---|---|
| `hive_home_local.boost_trv` | Start timed boost on a TRV or room |
| `hive_home_local.end_boost_trv` | Cancel TRV boost |
| `hive_home_local.set_trv_schedule` | Set weekly heating schedule |
| `hive_home_local.clear_trv_schedule` | Remove schedule |
| `hive_home_local.advance_trv_schedule` | Skip to next scheduled slot |
| `hive_home_local.set_holiday` | Activate holiday frost protection |
| `hive_home_local.cancel_holiday` | Cancel holiday mode |
| `hive_home_local.add_room` | Create a room group |
| `hive_home_local.remove_room` | Remove a room group |

---

## Credits

Hub device support is based on [HA-Hive-Local-Thermostat](https://github.com/andrew-codechimp/HA-Hive-Local-Thermostat) by [@andrew-codechimp](https://github.com/andrew-codechimp). Brand logo from the [Home Assistant brands repository](https://github.com/home-assistant/brands).

---

## License

MIT
