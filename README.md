# Sifely Smart Lock — Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Conexo-Casa/sifely-ha.svg)](https://github.com/Conexo-Casa/sifely-ha/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Integrate your **Sifely smart locks** with Home Assistant.  Each lock in your
Sifely account appears as a `lock` entity, letting you lock, unlock, and
monitor battery level and state directly from your dashboard, automations, and
scripts.

> **Developed by [Conexo Casa](https://conexo.casa)** — a 501(c)(3) nonprofit
> building accessible smart-home solutions for people with neurocognitive
> impairments and the elderly.

---

## Features

| Feature | Supported |
|---|---|
| Lock / Unlock via gateway | ✅ |
| Lock state polling (every 30 s) | ✅ |
| Battery level attribute | ✅ |
| Gateway online/offline awareness | ✅ |
| Multiple locks per account | ✅ |
| HACS installation | ✅ |
| Config-flow UI setup | ✅ |
| Automatic token refresh | ✅ |

---

## Prerequisites

1. **Sifely locks** connected to at least one **Sifely Gateway** (the gateway
   must be online for remote lock/unlock to work).
2. A **Sifely developer account** with a **Client ID** — obtain yours from the
   [Sifely API Access portal](https://app-smart-manager.sifely.com/Login.html).
3. Home Assistant **2024.1.0** or later.

---

## Installation

### Option A — HACS (recommended)

1. Open HACS in your Home Assistant instance.
2. Select **Integrations** → **⋮ (menu)** → **Custom repositories**.
3. Add `https://github.com/Conexo-Casa/sifely-ha` as an **Integration**.
4. Search for **Sifely Smart Lock** and click **Download**.
5. Restart Home Assistant.

### Option B — Manual

1. Download the [latest release](https://github.com/Conexo-Casa/sifely-ha/releases/latest).
2. Copy the `custom_components/sifely` directory into your HA
   `config/custom_components/` directory.
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
2. Search for **Sifely Smart Lock**.
3. Enter your credentials:

| Field | Description |
|---|---|
| **Client ID** | Your Sifely API Client ID (from the developer portal) |
| **Username** | Your Sifely account email address or phone number |
| **Password** | Your Sifely account password |

4. Click **Submit**.  The integration will validate your credentials and create
   one lock entity per lock in your account.

---

## Usage

### Lock entities

Each lock appears as a `lock.<lock_alias>` entity.  States:

| State | Meaning |
|---|---|
| `locked` | Lock reports bolt engaged |
| `unlocked` | Lock reports bolt retracted |
| `unavailable` | HA cannot reach the Sifely API |

### Extra state attributes

| Attribute | Description |
|---|---|
| `battery` | Battery level (0–100 %) |
| `lock_id` | Numeric Sifely lock ID |
| `lock_mac` | Bluetooth MAC address |
| `has_gateway` | `true` if paired with a gateway |
| `remote_enabled` | `true` if remote unlock is permitted |
| `firmware_revision` | Installed firmware string |
| `auto_lock_time` | Auto-lock delay in seconds |
| `is_frozen` | `true` if the lock is administratively frozen |

### Services

Use the built-in `lock.lock` and `lock.unlock` HA services, or the
entity card controls.

```yaml
# Example automation — lock the front door at midnight
automation:
  alias: Lock front door at midnight
  trigger:
    - platform: time
      at: "00:00:00"
  action:
    - service: lock.lock
      target:
        entity_id: lock.front_door
```

> **Note:** Remote lock/unlock requires the lock's gateway to be online.
> If the gateway is offline you will see an error in the HA log.

---

## Limitations

- **Gateway required for remote operation.** BLE-only locks can report state
  but cannot be controlled remotely.
- **State polling.** The integration polls every 30 seconds; there may be a
  short delay between a physical action and HA reflecting the new state.
- **Sifely API rate limits.** 30 req/min · 1,000/hr · 20,000/day.  With many
  locks you may want to increase the poll interval in `const.py`.

---

## Troubleshooting

| Symptom | Likely cause & fix |
|---|---|
| `invalid_auth` on setup | Wrong Client ID, username, or password |
| Entity shows `unavailable` | Sifely API unreachable or token expired — HA will retry |
| Lock/unlock returns no error but lock doesn't move | Gateway offline |
| Entity stays `unknown` state | Lock does not have a gateway; state cannot be polled remotely |

Enable debug logging to get detailed API traces:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.sifely: debug
```

---

## Contributing

Pull requests are welcome!  Please open an issue first for significant changes.

1. Fork the repo and create a feature branch.
2. Follow the existing code style (Black + isort).
3. Add or update tests in `tests/`.
4. Submit a PR against `main`.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgements

Built on the [Sifely Open API](https://apidocs.sifely.com/) and the
[Home Assistant custom integration framework](https://developers.home-assistant.io/).
