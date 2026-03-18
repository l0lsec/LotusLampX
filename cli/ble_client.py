"""
Async BLE wrapper for LotusLamp devices using **bleak**.

Mirrors the Android app's connection sequence:
  1. connectGatt(context, autoConnect=false, callback, TRANSPORT_LE)
  2. onConnectionStateChanged -> discoverServices()
  3. onServicesDiscovered -> readDeviceInformation (optional)
  4. short delay (modifyDelayTime, typically 10 ms for non-color cmds)
  5. writeValue(device, SERVICE_UUID, CHAR_UUID, data)
     with writeType = WRITE_TYPE_NO_RESPONSE (1)

bleak handles steps 1-3 inside BleakClient.connect(), but we add an
explicit post-connect delay and thorough GATT validation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from bleak import BleakClient, BleakScanner

from protocol import SERVICE_UUID, WRITE_UUID

POST_CONNECT_DELAY = 0.3
POST_WRITE_DELAY = 0.05
MAX_CONNECT_RETRIES = 3
RETRY_BACKOFF = 1.0


@dataclass
class ScanResult:
    address: str
    name: str
    rssi: int


async def scan(
    timeout: float = 5.0,
    name_filter: Optional[str] = None,
    service_filter: bool = True,
) -> list[ScanResult]:
    """Discover BLE devices, optionally filtering by name or service UUID."""
    results: list[ScanResult] = []
    devices = await BleakScanner.discover(
        timeout=timeout,
        return_adv=True,
    )
    for device, adv_data in devices.values():
        name = adv_data.local_name or device.name or ""
        if name_filter and name_filter.lower() not in name.lower():
            continue
        if service_filter and SERVICE_UUID not in (adv_data.service_uuids or []):
            continue
        results.append(ScanResult(
            address=device.address,
            name=name,
            rssi=adv_data.rssi,
        ))
    results.sort(key=lambda r: r.rssi, reverse=True)
    return results


class LotusLampClient:
    """Manages a GATT connection to a single LotusLamp device."""

    def __init__(self, address: str) -> None:
        self._address = address
        self._client: Optional[BleakClient] = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def connect(self, timeout: float = 10.0) -> None:
        """
        Connect with retries, validate GATT profile, wait for stability.

        Retries up to MAX_CONNECT_RETRIES times with exponential backoff
        on connection failure.
        """
        last_err: Optional[Exception] = None
        for attempt in range(1, MAX_CONNECT_RETRIES + 1):
            try:
                self._client = BleakClient(self._address, timeout=timeout)
                await self._client.connect()

                self._validate_gatt()

                await asyncio.sleep(POST_CONNECT_DELAY)
                return
            except Exception as exc:
                last_err = exc
                if self._client is not None:
                    try:
                        await self._client.disconnect()
                    except Exception:
                        pass
                    self._client = None

                if attempt < MAX_CONNECT_RETRIES:
                    wait = RETRY_BACKOFF * attempt
                    print(
                        f"  Connection attempt {attempt} failed: {exc}. "
                        f"Retrying in {wait:.1f}s ..."
                    )
                    await asyncio.sleep(wait)

        raise RuntimeError(
            f"Failed to connect to {self._address} after "
            f"{MAX_CONNECT_RETRIES} attempts: {last_err}"
        )

    def _validate_gatt(self) -> None:
        """Ensure the device exposes the expected service and write char."""
        assert self._client is not None
        svcs = self._client.services
        if svcs is None:
            raise RuntimeError("Service discovery returned nothing")

        svc = svcs.get_service(SERVICE_UUID)
        if svc is None:
            raise RuntimeError(
                f"Device lacks service {SERVICE_UUID}. "
                f"Available: {[s.uuid for s in svcs]}"
            )

        write_char = svcs.get_characteristic(WRITE_UUID)
        if write_char is None:
            raise RuntimeError(
                f"Service {SERVICE_UUID} lacks write char {WRITE_UUID}. "
                f"Available: {[c.uuid for c in svc.characteristics]}"
            )

        if "write-without-response" not in write_char.properties:
            print(
                f"  Warning: {WRITE_UUID} properties are {write_char.properties}; "
                f"expected write-without-response"
            )

    def dump_gatt_profile(self) -> None:
        """Print every service and characteristic for debugging."""
        assert self._client is not None
        svcs = self._client.services
        if svcs is None:
            print("  (no services discovered)")
            return
        for svc in svcs:
            print(f"  Service: {svc.uuid}")
            for char in svc.characteristics:
                props = ", ".join(char.properties)
                print(f"    Char: {char.uuid}  [{props}]")
                for desc in char.descriptors:
                    print(f"      Desc: {desc.uuid}")

    async def write(self, payload: bytes) -> None:
        """Write payload to the write characteristic (no response)."""
        if not self.is_connected:
            raise RuntimeError("Not connected -- call connect() first")
        assert self._client is not None
        await self._client.write_gatt_char(WRITE_UUID, payload, response=False)
        await asyncio.sleep(POST_WRITE_DELAY)

    async def disconnect(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

    async def __aenter__(self) -> "LotusLampClient":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.disconnect()
