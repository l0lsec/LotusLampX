# LotusLamp X -- BLE Light Controller

Control LotusLamp X-compatible BLE LED devices using the same GATT protocol as
the official app. No phone required.

Two interfaces are included:

| Interface | Path | Description |
|-----------|------|-------------|
| **Web UI** | `web/` | Browser-based dashboard with color picker, sliders, scene grid, and all controls |
| **CLI** | `cli/` | Command-line tool for scripting and quick one-off commands |

Both share the same BLE protocol library (`cli/protocol.py` and `cli/ble_client.py`).

## Requirements

- **Python 3.10+**
- **macOS** (CoreBluetooth) or **Linux** (BlueZ 5.43+, kernel 5.10+ recommended)
- Bluetooth adapter

---

## Web UI

A browser-based dashboard for controlling your lights visually.

### Install & Run

```bash
cd web
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open **http://localhost:8000** in your browser.

### Features

- **Device scanner** -- discover nearby BLE lights and select one from a dropdown
- **Power** -- on/off toggle
- **Color picker** -- color wheel, RGB inputs, and 16 preset swatches
- **Brightness** -- slider (0-255)
- **White temperature** -- warm/cold dual sliders
- **Effects** -- mode buttons (Jump, Strobe, Breathe, Warning) + speed slider
- **156 scene presets** -- scrollable grid (Sunrise, Sunset, Birthday, etc.)
- **Mic reactive** -- toggle + sensitivity slider
- **Auto-off timer** -- quick presets (15m, 30m, 1h, 2h) or custom seconds
- **Motion sensor** -- toggle + configurable delay
- **Factory reset** -- with confirmation modal
- **Encrypted mode** -- toggle for ELK-* devices

---

## CLI

### Install

```bash
cd cli
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Cheatsheet

```bash
# ── SETUP ──────────────────────────────────────────────────
# Optional: set default device to skip --device every time
export LOTUSLAMP_DEVICE="CF0920A2-7CD6-980C-2856-7BA5F73F8336"

# Activate the venv
cd cli && source .venv/bin/activate

# ── SCAN ───────────────────────────────────────────────────
python main.py scan                          # devices advertising fff0 service
python main.py scan --all                    # all BLE devices
python main.py scan --name MELK              # filter by name substring
python main.py scan --name MELK --timeout 10 # longer scan window

# ── YOUR DEVICES ───────────────────────────────────────────
# MELK-OA10 86 → CF0920A2-7CD6-980C-2856-7BA5F73F8336
# MELK-OA10 BA → 89C50AE0-4AA3-D743-5FD2-5BBDBAFA9196

# ── ON / OFF ───────────────────────────────────────────────
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 on
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 off
python main.py -d 89C50AE0-4AA3-D743-5FD2-5BBDBAFA9196 on
python main.py -d 89C50AE0-4AA3-D743-5FD2-5BBDBAFA9196 off

# ── ALL DEVICES AT ONCE ───────────────────────────────────
python main.py --all on
python main.py --all off
python main.py --all color 255 0 0
python main.py --all brightness 128

# ── COLOR (R G B, each 0-255) ─────────────────────────────
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 color 255 0 0     # red
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 color 0 255 0     # green
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 color 0 0 255     # blue
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 color 255 255 255 # white
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 color 255 0 128   # pink

# ── BRIGHTNESS (0-255) ────────────────────────────────────
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 brightness 255  # max
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 brightness 128  # 50%
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 brightness 30   # dim

# ── MODE (basic animation pattern, see table below) ──────
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 mode 1   # jump
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 mode 2   # strobe
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 mode 3   # breathe
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 mode 4   # warning

# ── SPEED (effect speed, 0-255) ───────────────────────────
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 speed 50   # slow
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 speed 150  # medium
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 speed 255  # fast

# ── WARM / COLD WHITE (each 0-255) ───────────────────────
python main.py --all warm 255 0     # full warm white
python main.py --all warm 0 255     # full cold white
python main.py --all warm 200 100   # warm-biased mix

# ── MIC REACTIVE MODE ────────────────────────────────────
python main.py --all mic on         # enable music-reactive mode
python main.py --all mic off        # disable

# ── MIC SENSITIVITY (0-255) ──────────────────────────────
python main.py --all sensitivity 128  # medium
python main.py --all sensitivity 255  # max

# ── SCENE PRESETS (see table below for full list) ────────
python main.py --all scene 1       # sunrise
python main.py --all scene 10      # disco
python main.py --all scene 16      # ocean
python main.py --all scene 154     # meteor

# ── AUTO-OFF TIMER (seconds, 0 = cancel) ─────────────────
python main.py --all timer 300      # turn off in 5 minutes
python main.py --all timer 3600     # turn off in 1 hour
python main.py --all timer 0        # cancel timer

# ── MOTION SENSOR ─────────────────────────────────────────
python main.py --all sensor on              # enable, 30s default delay
python main.py --all sensor on --delay 60   # enable, 60s delay
python main.py --all sensor off             # disable

# ── FACTORY RESET (prompts for confirmation) ─────────────
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 reset

# ── DEBUG (GATT enumeration + ON/OFF test) ────────────────
python main.py -d CF0920A2-7CD6-980C-2856-7BA5F73F8336 debug

# ── ENCRYPTED MODE (for ELK-* devices only, NOT MELK) ────
python main.py -d <ELK_DEVICE_ADDR> -e on
python main.py -d <ELK_DEVICE_ADDR> -e off
```

### Environment variables

| Variable | Description |
|---|---|
| `LOTUSLAMP_DEVICE` | Default device address so you don't need `--device` every time. |
| `LOTUSLAMP_ENCRYPTED` | Set to `1` / `true` to always use encrypted frames. |

### All commands

```
lotuslamp [-d DEVICE] [--all] [-e] <command>

Commands:
  scan              Discover nearby BLE lights
  on                Turn the light on
  off               Turn the light off
  color R G B       Set RGB color (each 0-255)
  brightness N      Set brightness (0-255)
  mode ID           Set lighting mode
  speed N           Set effect speed (0-255)
  warm W C          Set warm/cold white levels (each 0-255)
  mic on|off        Toggle mic-reactive mode
  sensitivity N     Set mic sensitivity (0-255)
  scene ID          Activate built-in scene preset
  timer SECONDS     Auto-off countdown (0 = cancel)
  sensor on|off     Toggle motion sensor (--delay N for seconds)
  reset             Factory reset (prompts for confirmation)
  debug             Connect, enumerate GATT, send ON/OFF test

Options:
  -d, --device     BLE address (or $LOTUSLAMP_DEVICE)
  --all            Send to all discovered MELK devices
  -e, --encrypted  Use encrypted frames (ELK-* devices only)
```

---

## Reference

### Mode IDs

Basic animation patterns sent with the `mode` command:

| ID | Effect |
|----|--------|
| 1 | Jump (color jumping) |
| 2 | Strobe |
| 3 | Breathe (fade in/out) |
| 4 | Warning (flash) |

### Scene IDs

Preset lighting scenes sent with the `scene` command.  Extracted from the
app's `ELKSymphonyScene` enum for SYMPHONY (MELK) devices:

| ID | Scene | ID | Scene |
|----|-------|----|-------|
| 1 | Sunrise | 18 | Reading |
| 2 | Sunset | 19 | Working |
| 3 | Birthday | 20 | Dazzle |
| 4 | Candlelight | 21 | Gentle |
| 5 | Fireworks | 22 | Wedding |
| 6 | Party | 23 | Snow |
| 7 | Dating | 24 | Fire |
| 8 | Starry Sky | 25 | Lightning |
| 9 | Romantic | 26 | Valentine's Day |
| 10 | Disco | 27 | Halloween |
| 11 | Rainbow | 28 | Warning |
| 12 | Movie | 150 | Time Machine |
| 13 | Christmas | 152 | Time Machine 2 |
| 14 | Flowing | 154 | Meteor |
| 15 | Sleeping | 155 | Meteor 2 |
| 16 | Ocean | 156 | Fireworks Show |
| 17 | Forest | | |

### Platform notes

#### macOS

Bluetooth must be enabled in System Settings.  No special permissions are
needed beyond the terminal being allowed Bluetooth access.

On macOS, bleak uses CoreBluetooth UUIDs as device addresses, which look like
`12345678-ABCD-1234-ABCD-123456789ABC` rather than MAC addresses.

#### Linux

Needs BlueZ 5.43+.  On modern kernels (5.10+) no root is required.  On older
setups you may need `sudo` or `cap_net_raw`:

```bash
sudo setcap cap_net_raw+eip $(readlink -f $(which python3))
```

### Protocol reference

See `CONNECTION_AND_CONTROL_FLOW.md` in the parent directory for the full
reverse-engineering writeup.
