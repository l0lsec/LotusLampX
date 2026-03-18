#!/usr/bin/env python3
"""
lotuslamp -- CLI tool for controlling LotusLamp X BLE lights.

Usage examples:

    python main.py scan --name MELK --all
    python main.py --device AA:BB:CC:DD:EE:FF on
    python main.py --device AA:BB:CC:DD:EE:FF off
    python main.py --all on                        # all MELK devices
    python main.py --all color 255 0 128           # all MELK devices
    python main.py --device AA:BB:CC:DD:EE:FF debug
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from ble_client import LotusLampClient, scan
from protocol import (
    cmd_brightness,
    cmd_color,
    cmd_factory_reset,
    cmd_human_sensor,
    cmd_mic_sensitivity,
    cmd_mic_toggle,
    cmd_mode,
    cmd_off_timer,
    cmd_on_off,
    cmd_scene,
    cmd_speed,
    cmd_warm_cold,
    maybe_encrypt,
)

ENV_DEVICE = "LOTUSLAMP_DEVICE"
ENV_ENCRYPTED = "LOTUSLAMP_ENCRYPTED"


SCAN_NAME_FILTER = "MELK"
SCAN_TIMEOUT = 5.0


def _resolve_device(args: argparse.Namespace) -> str:
    addr = getattr(args, "device", None) or os.environ.get(ENV_DEVICE)
    if not addr:
        print(
            "Error: no device address. Use --device <addr>, --all, or set "
            f"${ENV_DEVICE}.",
            file=sys.stderr,
        )
        sys.exit(1)
    return addr


def _resolve_encrypted(args: argparse.Namespace) -> bool:
    if getattr(args, "encrypted", False):
        return True
    return os.environ.get(ENV_ENCRYPTED, "").lower() in ("1", "true", "yes")


async def _resolve_targets(args: argparse.Namespace) -> list[str]:
    """Return list of device addresses: either from --all scan or single --device."""
    if getattr(args, "all_devices", False):
        print(f"Scanning for MELK devices ({SCAN_TIMEOUT}s) ...")
        results = await scan(
            timeout=SCAN_TIMEOUT,
            name_filter=SCAN_NAME_FILTER,
            service_filter=False,
        )
        if not results:
            print("No MELK devices found.", file=sys.stderr)
            sys.exit(1)
        for r in results:
            print(f"  Found: {r.name}  ({r.address})")
        return [r.address for r in results]
    return [_resolve_device(args)]


async def _send(args: argparse.Namespace, frame: bytes) -> None:
    targets = await _resolve_targets(args)
    encrypted = _resolve_encrypted(args)
    payload = maybe_encrypt(frame, encrypted)
    for addr in targets:
        print(f"Connecting to {addr} ...")
        async with LotusLampClient(addr) as client:
            print(f"  Sending {len(payload)} bytes: {payload.hex()}")
            await client.write(payload)
            print(f"  Done.")


# ---- subcommand handlers --------------------------------------------------

async def handle_scan(args: argparse.Namespace) -> None:
    print(f"Scanning for {args.timeout}s ...")
    results = await scan(
        timeout=args.timeout,
        name_filter=args.name or None,
        service_filter=not args.all,
    )
    if not results:
        print("No devices found.")
        return
    print(f"{'Address':<40} {'RSSI':>5}  Name")
    print("-" * 65)
    for r in results:
        print(f"{r.address:<40} {r.rssi:>5}  {r.name}")


async def handle_on(args: argparse.Namespace) -> None:
    await _send(args, cmd_on_off(True))


async def handle_off(args: argparse.Namespace) -> None:
    await _send(args, cmd_on_off(False))


async def handle_color(args: argparse.Namespace) -> None:
    await _send(args, cmd_color(args.r, args.g, args.b))


async def handle_brightness(args: argparse.Namespace) -> None:
    await _send(args, cmd_brightness(args.level))


async def handle_mode(args: argparse.Namespace) -> None:
    await _send(args, cmd_mode(args.mode_id))


async def handle_speed(args: argparse.Namespace) -> None:
    await _send(args, cmd_speed(args.level))


async def handle_warm(args: argparse.Namespace) -> None:
    await _send(args, cmd_warm_cold(args.warm, args.cold))


async def handle_mic(args: argparse.Namespace) -> None:
    on = args.state.lower() == "on"
    await _send(args, cmd_mic_toggle(on))


async def handle_sensitivity(args: argparse.Namespace) -> None:
    await _send(args, cmd_mic_sensitivity(args.level))


async def handle_scene(args: argparse.Namespace) -> None:
    await _send(args, cmd_scene(args.scene_id))


async def handle_timer(args: argparse.Namespace) -> None:
    await _send(args, cmd_off_timer(args.seconds))


async def handle_sensor(args: argparse.Namespace) -> None:
    on = args.state.lower() == "on"
    await _send(args, cmd_human_sensor(on, args.delay))


async def handle_reset(args: argparse.Namespace) -> None:
    answer = input("Factory reset all targeted devices? [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return
    await _send(args, cmd_factory_reset())


async def handle_debug(args: argparse.Namespace) -> None:
    """Connect, enumerate GATT, send ON then OFF, report every step."""
    addr = _resolve_device(args)
    client = LotusLampClient(addr)

    print(f"[debug] Connecting to {addr} ...")
    await client.connect()
    print("[debug] Connected. Enumerating GATT services ...")
    client.dump_gatt_profile()

    on_frame = cmd_on_off(True)
    off_frame = cmd_on_off(False)

    print(f"\n[debug] Writing ON frame: {on_frame.hex()}")
    await client.write(on_frame)
    print("[debug] ON frame written. Waiting 3 s ...")
    await asyncio.sleep(3.0)

    print(f"[debug] Writing OFF frame: {off_frame.hex()}")
    await client.write(off_frame)
    print("[debug] OFF frame written. Waiting 1 s before disconnect ...")
    await asyncio.sleep(1.0)

    await client.disconnect()
    print("[debug] Disconnected. Debug session complete.")


# ---- argument parser -------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lotuslamp",
        description="Control LotusLamp X BLE lights from the command line.",
    )
    parser.add_argument(
        "--device", "-d",
        help=f"BLE device address (or set ${ENV_DEVICE}).",
    )
    parser.add_argument(
        "--all",
        dest="all_devices",
        action="store_true",
        default=False,
        help="Send command to all discovered MELK devices.",
    )
    parser.add_argument(
        "--encrypted", "-e",
        action="store_true",
        default=False,
        help="Use encrypted 21-byte frames for ELK-* devices.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = sub.add_parser("scan", help="Discover nearby BLE lights.")
    p_scan.add_argument("--timeout", "-t", type=float, default=5.0,
                        help="Scan duration in seconds (default 5).")
    p_scan.add_argument("--name", "-n", type=str, default="",
                        help="Filter by device name substring.")
    p_scan.add_argument("--all", "-a", action="store_true", default=False,
                        help="Show all BLE devices, not just LotusLamp service.")

    # on / off
    sub.add_parser("on", help="Turn the light on.")
    sub.add_parser("off", help="Turn the light off.")

    # color
    p_color = sub.add_parser("color", help="Set RGB color.")
    p_color.add_argument("r", type=int, help="Red (0-255).")
    p_color.add_argument("g", type=int, help="Green (0-255).")
    p_color.add_argument("b", type=int, help="Blue (0-255).")

    # brightness
    p_bright = sub.add_parser("brightness", help="Set brightness level.")
    p_bright.add_argument("level", type=int, help="Brightness (0-255).")

    # mode
    p_mode = sub.add_parser("mode", help="Set lighting mode.")
    p_mode.add_argument("mode_id", type=int, help="Mode ID (integer).")

    # speed
    p_speed = sub.add_parser("speed", help="Set effect speed.")
    p_speed.add_argument("level", type=int, help="Speed (0-255).")

    # warm/cold white
    p_warm = sub.add_parser("warm", help="Set warm/cold white temperature.")
    p_warm.add_argument("warm", type=int, help="Warm white level (0-255).")
    p_warm.add_argument("cold", type=int, help="Cold white level (0-255).")

    # mic reactive
    p_mic = sub.add_parser("mic", help="Toggle mic-reactive mode.")
    p_mic.add_argument("state", choices=["on", "off"], help="on or off.")

    # mic sensitivity
    p_sens = sub.add_parser("sensitivity", help="Set mic sensitivity.")
    p_sens.add_argument("level", type=int, help="Sensitivity (0-255).")

    # scene preset
    p_scene = sub.add_parser("scene", help="Activate a built-in scene preset.")
    p_scene.add_argument("scene_id", type=int, help="Scene ID (integer).")

    # auto-off timer
    p_timer = sub.add_parser("timer", help="Auto-off countdown timer.")
    p_timer.add_argument("seconds", type=int,
                         help="Seconds until auto-off (0 = cancel).")

    # human/motion sensor
    p_sensor = sub.add_parser("sensor", help="Toggle motion sensor mode.")
    p_sensor.add_argument("state", choices=["on", "off"], help="on or off.")
    p_sensor.add_argument("--delay", type=int, default=30,
                          help="Delay in seconds before turning off (default 30).")

    # factory reset
    sub.add_parser("reset", help="Factory reset the device.")

    # debug
    sub.add_parser("debug", help="Connect, enumerate GATT, send ON/OFF, report.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "scan": handle_scan,
        "on": handle_on,
        "off": handle_off,
        "color": handle_color,
        "brightness": handle_brightness,
        "mode": handle_mode,
        "speed": handle_speed,
        "warm": handle_warm,
        "mic": handle_mic,
        "sensitivity": handle_sensitivity,
        "scene": handle_scene,
        "timer": handle_timer,
        "sensor": handle_sensor,
        "reset": handle_reset,
        "debug": handle_debug,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    asyncio.run(handler(args))


if __name__ == "__main__":
    main()
