#!/usr/bin/env python3
"""
LotusLamp X Web Control Dashboard — FastAPI backend.

Wraps cli/protocol.py and cli/ble_client.py to expose every light-control
command as a REST endpoint, served alongside a single-page frontend.

    cd web && pip install -r requirements.txt && python server.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Make cli/ importable
# ---------------------------------------------------------------------------
CLI_DIR = str(Path(__file__).resolve().parent.parent / "cli")
if CLI_DIR not in sys.path:
    sys.path.insert(0, CLI_DIR)

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
from ble_client import LotusLampClient, scan, ScanResult

# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------

app = FastAPI(title="LotusLamp X Control", version="1.0.0")

_cached_devices: list[ScanResult] = []
_selected_device: Optional[str] = None
_encrypted: bool = False


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ColorBody(BaseModel):
    r: int
    g: int
    b: int

class LevelBody(BaseModel):
    level: int

class ModeBody(BaseModel):
    mode_id: int

class WarmColdBody(BaseModel):
    warm: int
    cold: int

class ToggleBody(BaseModel):
    state: str  # "on" | "off"

class SensitivityBody(BaseModel):
    level: int

class SceneBody(BaseModel):
    scene_id: int

class TimerBody(BaseModel):
    seconds: int

class SensorBody(BaseModel):
    state: str  # "on" | "off"
    delay: int = 30

class DeviceSelectBody(BaseModel):
    address: str
    encrypted: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_device() -> str:
    if not _selected_device:
        raise HTTPException(status_code=400, detail="No device selected. Scan and select a device first.")
    return _selected_device


async def _send(frame: bytes) -> dict:
    addr = _require_device()
    payload = maybe_encrypt(frame, _encrypted)
    try:
        async with LotusLampClient(addr) as client:
            await client.write(payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"BLE error: {exc}")
    return {"ok": True, "device": addr, "bytes": len(payload)}


# ---------------------------------------------------------------------------
# Device management endpoints
# ---------------------------------------------------------------------------

@app.get("/api/scan")
async def api_scan(timeout: float = 5.0, name: str = "MELK"):
    global _cached_devices
    try:
        results = await scan(
            timeout=timeout,
            name_filter=name or None,
            service_filter=not name,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Scan failed: {exc}")
    _cached_devices = results
    return [{"address": r.address, "name": r.name, "rssi": r.rssi} for r in results]


@app.get("/api/devices")
async def api_devices():
    return {
        "devices": [{"address": r.address, "name": r.name, "rssi": r.rssi} for r in _cached_devices],
        "selected": _selected_device,
        "encrypted": _encrypted,
    }


@app.post("/api/device/select")
async def api_select_device(body: DeviceSelectBody):
    global _selected_device, _encrypted
    _selected_device = body.address
    _encrypted = body.encrypted
    return {"ok": True, "selected": _selected_device, "encrypted": _encrypted}


# ---------------------------------------------------------------------------
# Light control endpoints
# ---------------------------------------------------------------------------

@app.post("/api/on")
async def api_on():
    return await _send(cmd_on_off(True))


@app.post("/api/off")
async def api_off():
    return await _send(cmd_on_off(False))


@app.post("/api/color")
async def api_color(body: ColorBody):
    return await _send(cmd_color(body.r, body.g, body.b))


@app.post("/api/brightness")
async def api_brightness(body: LevelBody):
    return await _send(cmd_brightness(body.level))


@app.post("/api/mode")
async def api_mode(body: ModeBody):
    return await _send(cmd_mode(body.mode_id))


@app.post("/api/speed")
async def api_speed(body: LevelBody):
    return await _send(cmd_speed(body.level))


@app.post("/api/warm")
async def api_warm(body: WarmColdBody):
    return await _send(cmd_warm_cold(body.warm, body.cold))


@app.post("/api/mic")
async def api_mic(body: ToggleBody):
    on = body.state.lower() == "on"
    return await _send(cmd_mic_toggle(on))


@app.post("/api/sensitivity")
async def api_sensitivity(body: SensitivityBody):
    return await _send(cmd_mic_sensitivity(body.level))


@app.post("/api/scene")
async def api_scene(body: SceneBody):
    return await _send(cmd_scene(body.scene_id))


@app.post("/api/timer")
async def api_timer(body: TimerBody):
    return await _send(cmd_off_timer(body.seconds))


@app.post("/api/sensor")
async def api_sensor(body: SensorBody):
    on = body.state.lower() == "on"
    return await _send(cmd_human_sensor(on, body.delay))


@app.post("/api/reset")
async def api_reset(x_confirm: Optional[str] = Header(None)):
    if x_confirm != "yes-factory-reset":
        raise HTTPException(
            status_code=400,
            detail="Send header X-Confirm: yes-factory-reset to confirm.",
        )
    return await _send(cmd_factory_reset())


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).resolve().parent / "static"

@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    print("Starting LotusLamp X Web Dashboard on http://localhost:9000")
    uvicorn.run(app, host="0.0.0.0", port=9000)
