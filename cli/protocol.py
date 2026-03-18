"""
LotusLamp X BLE command protocol.

Reverse-engineered from the Android app (E1Achieve, BlePackagingDevice,
EncryptionDecryptionKt, AppConstant).

MELK-OA10 (SYMPHONY type=30) uses E1Achieve with plain 9-byte frames:
  - EncryptionIdentifier = "ELK-*" → isEncryptedDevice = false for MELK names
  - instructionVersion = E1 (only COLORFUL_CAR overrides to E2)
  - isBroadcast = false → GATT write path, no fillDataForComplete padding
  - writeType = WRITE_TYPE_NO_RESPONSE
"""

from __future__ import annotations

import os
from enum import IntEnum

# ---------------------------------------------------------------------------
# GATT UUIDs  (service 0xFFF0, write 0xFFF3, read/notify 0xFFF4)
# ---------------------------------------------------------------------------

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
READ_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"


# ---------------------------------------------------------------------------
# ElkCMD — command IDs extracted from AppConstant$ElkCMD.getValue()
# ---------------------------------------------------------------------------

class ElkCMD(IntEnum):
    BRIGHTNESS = 1
    SPEED = 2
    MODE = 3
    ON_OFF = 4
    COLOR = 5
    MIC = 6
    MIC_ON_OFF = 7
    PHONE_MAI_RHYTHM = 8
    CUSTOM = 10
    TIMER = 13
    HUMAN_SENSOR = 0x12
    WARM_COLD = 0x40
    SET_SCENE = 0x31
    SET_OFF_TIME = 0x76
    SET_RESTORE_FACTORY = 0x87


ENCRYPTED_CMDS = {ElkCMD.ON_OFF, ElkCMD.MODE, ElkCMD.BRIGHTNESS}


# ---------------------------------------------------------------------------
# Frame builder  (mirrors E1Achieve.achieve)
# ---------------------------------------------------------------------------

def _protocol_len(cmd: ElkCMD) -> int:
    """Return the ``len`` field value for a given command."""
    if cmd == ElkCMD.BRIGHTNESS:
        return 4
    return 7


def _to_hex(value: int) -> int:
    """Equivalent of BleExtKt.toHex — clamp int to unsigned byte."""
    return value & 0xFF


def build_e1_frame(cmd: ElkCMD, params: bytes | list[int]) -> bytes:
    """
    Build a 9-byte E1 command frame.

    Frame layout::

        [0x7E, len, cmd, p0, p1, p2, p3, 0x00, 0xEF]

    *params* fills indices 3–7.  Unused param slots default to 0xFF;
    index 7 defaults to 0x00 and index 8 is always 0xEF.
    """
    frame = bytearray(9)
    frame[0] = 0x7E
    frame[1] = _protocol_len(cmd)
    frame[2] = _to_hex(cmd)
    frame[3] = 0xFF
    frame[4] = 0xFF
    frame[5] = 0xFF
    frame[6] = 0xFF
    frame[7] = 0x00
    frame[8] = 0xEF

    for i, b in enumerate(params):
        slot = 3 + i
        if slot >= 8:
            break
        frame[slot] = _to_hex(b)

    return bytes(frame)


# ---------------------------------------------------------------------------
# App constants embedded in BlePackagingDevice
# ---------------------------------------------------------------------------

APP_TYPE = 0x02
APP_VERSION = 0x01
LAMP_TYPE_RGB = 1


# ---------------------------------------------------------------------------
# High-level command helpers  (mirror BlePackagingDevice GATT path)
# ---------------------------------------------------------------------------

def cmd_on_off(on: bool, lamp_type: int = LAMP_TYPE_RGB) -> bytes:
    """
    ON_OFF command via GATT (BlePackagingDevice.rgbOpen).

    Params: [on?0xFF:0x00, lamp_type, on?1:0, APP_TYPE, APP_VERSION]
    """
    return build_e1_frame(ElkCMD.ON_OFF, [
        0xFF if on else 0x00,
        lamp_type,
        1 if on else 0,
        APP_TYPE,
        APP_VERSION,
    ])


def cmd_brightness(brightness: int) -> bytes:
    """BRIGHTNESS command — brightness 0-255."""
    return build_e1_frame(ElkCMD.BRIGHTNESS, [brightness])


def cmd_color(r: int, g: int, b: int) -> bytes:
    """COLOR command — params [3, R, G, B, 16]."""
    return build_e1_frame(ElkCMD.COLOR, [3, r, g, b, 16])


def cmd_mode(mode_id: int) -> bytes:
    """MODE command — params [mode_id, 3]."""
    return build_e1_frame(ElkCMD.MODE, [mode_id, 3])


def cmd_speed(speed: int) -> bytes:
    """SPEED command — speed 0-255."""
    return build_e1_frame(ElkCMD.SPEED, [speed])


def cmd_warm_cold(warm: int, cold: int) -> bytes:
    """Warm/cold white via COLOR with sub-type 2 (BlePackagingDevice.warmCold)."""
    return build_e1_frame(ElkCMD.COLOR, [2, warm, cold, APP_TYPE, APP_VERSION])


def cmd_mic_toggle(on: bool) -> bytes:
    """Toggle mic-reactive mode (BlePackagingDevice.setMicOpen)."""
    return build_e1_frame(ElkCMD.MIC_ON_OFF, [1 if on else 0])


def cmd_mic_sensitivity(level: int) -> bytes:
    """Set mic sensitivity 0-255 (BlePackagingDevice.sens)."""
    return build_e1_frame(ElkCMD.MIC, [level])


def cmd_scene(scene_id: int) -> bytes:
    """Activate built-in scene preset (BlePackagingDevice.setScene)."""
    return build_e1_frame(ElkCMD.SET_SCENE, [scene_id, 0xFF])


def cmd_off_timer(seconds: int) -> bytes:
    """Auto-off countdown in seconds, 16-bit LE (BlePackagingDevice.setOffTime)."""
    return build_e1_frame(ElkCMD.SET_OFF_TIME, [seconds & 0xFF, (seconds >> 8) & 0xFF])


def cmd_human_sensor(on: bool, delay_seconds: int = 30) -> bytes:
    """Motion sensor toggle with delay in seconds (BlePackagingDevice.setHumanSensor)."""
    return build_e1_frame(ElkCMD.HUMAN_SENSOR, [
        1 if on else 0,
        delay_seconds & 0xFF,
        (delay_seconds >> 8) & 0xFF,
    ])


def cmd_factory_reset() -> bytes:
    """Factory reset (BlePackagingDevice.restoreFactory)."""
    return build_e1_frame(ElkCMD.SET_RESTORE_FACTORY, [0xFF])


# ---------------------------------------------------------------------------
# Encryption  (mirrors EncryptionDecryptionKt)
# ---------------------------------------------------------------------------

_PRESET_KEY = bytes([
    0x2A, 0x7F, 0xC1, 0x94, 0x33, 0xDE, 0x45, 0xE0,
    0x8B, 0x11, 0x5C, 0xA6, 0x09, 0xF2, 0x7D, 0xB8,
])


def _generate_random(n: int = 12) -> bytes:
    return os.urandom(n)


def _generate_keystream(random_data: bytes) -> bytes:
    """Derive a 9-byte keystream from 12 random bytes."""
    ks = bytearray(9)
    for i in range(9):
        a = (random_data[i] & 0xFF) * 27 & 0xFF
        b = ((random_data[(i + 3) % 12] & 0xFF) + 55) & 0xFF
        c = ((random_data[(i + 7) % 12] & 0xFF) >> 2) & 0xFF
        d = (i * 85) & 0xFF
        ks[i] = a ^ b ^ c ^ d
    return bytes(ks)


def _xor_encrypt_random(rand_in: bytes) -> bytes:
    out = bytearray(12)
    for i in range(12):
        out[i] = (rand_in[i] & 0xFF) ^ (_PRESET_KEY[i % 16] & 0xFF)
    return bytes(out)


def encrypt_bytes(plaintext: bytes) -> bytes:
    """
    Encrypt a 9-byte plaintext into a 21-byte ciphertext.

    Layout of ciphertext::

        [0..8]   plaintext XOR keystream
        [9..20]  random XOR preset_key
    """
    assert len(plaintext) == 9, f"plaintext must be 9 bytes, got {len(plaintext)}"
    rand = _generate_random(12)
    ks = _generate_keystream(rand)
    ct = bytearray(21)
    for i in range(9):
        ct[i] = plaintext[i] ^ ks[i]
    enc_rand = _xor_encrypt_random(rand)
    for i in range(12):
        ct[9 + i] = enc_rand[i]
    return bytes(ct)


def maybe_encrypt(frame: bytes, encrypted: bool) -> bytes:
    """
    If *encrypted* is True **and** the command is one of ON_OFF / MODE /
    BRIGHTNESS, swap header/tail to 0xAA/0x55 and encrypt into 21 bytes.
    Otherwise return *frame* unchanged.
    """
    if not encrypted:
        return frame
    cmd_byte = frame[2]
    if cmd_byte not in {int(c) for c in ENCRYPTED_CMDS}:
        return frame
    buf = bytearray(frame)
    buf[0] = 0xAA
    buf[8] = 0x55
    return encrypt_bytes(bytes(buf))
