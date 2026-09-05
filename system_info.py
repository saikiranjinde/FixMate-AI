"""Fast, informational Windows system snapshot for FixMate-AI."""
from __future__ import annotations

import json
import platform
import re
import socket
import subprocess
import winreg
from typing import Any

import psutil


def _powershell_json(command: str) -> Any:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout.strip())
    except Exception:
        return None


def _read_windows_info() -> dict[str, str]:
    info = {}
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        ) as key:
            for out_key, reg_key in (
                ("windows_display_name", "ProductName"),
                ("windows_version", "DisplayVersion"),
                ("windows_build", "CurrentBuild"),
                ("windows_build_full", "CurrentBuildNumber"),
                ("windows_ubr", "UBR"),
            ):
                try:
                    value, _ = winreg.QueryValueEx(key, reg_key)
                    info[out_key] = str(value)
                except OSError:
                    pass
    except OSError:
        pass
    return info


def _cpu_generation_series(name: str, vendor: str) -> tuple[str, str]:
    text = " ".join(str(name or "").split())
    upper = text.upper()
    generation = "Not detected"
    series = "Not detected"

    if "INTEL" in upper:
        m = re.search(r"CORE(?:\([^)]*\))?\s+(I[3579])[- ]([0-9]{4,5}[A-Z]{0,4})", upper)
        if m:
            series = f"Intel Core {m.group(1)}"
            model = m.group(2)
            digits = re.match(r"(\d{4,5})", model)
            if digits:
                model_digits = digits.group(1)
                try:
                    # Intel model families: 10xxx/11xxx/12xxx/etc. are
                    # commonly 10th/11th/12th generation; older 4-digit
                    # models (8xxx/9xxx) map naturally from the first digit.
                    if model_digits.startswith(("10", "11", "12", "13", "14", "15")):
                        gen = int(model_digits[:2])
                    else:
                        gen = int(model_digits[0])
                    generation = f"{gen}th Gen"
                except ValueError:
                    pass
        else:
            # Newer Core Ultra naming: Core Ultra 7 155H
            m = re.search(r"CORE\s+ULTRA\s+([3579])\s+([0-9]{3}[A-Z]{0,2})", upper)
            if m:
                series = f"Intel Core Ultra {m.group(1)}"
                generation = "Core Ultra"
            elif "XEON" in upper:
                series = "Intel Xeon"
                generation = "Xeon"
        return generation, series

    if "AMD" in upper or "RYZEN" in upper:
        m = re.search(r"RYZEN\s+([3579])\s+([0-9]{4,5}[A-Z]{0,3})", upper)
        if m:
            series = f"AMD Ryzen {m.group(1)}"
            model = m.group(2)
            digits = re.match(r"(\d{4,5})", model)
            if digits:
                first = digits.group(1)
                try:
                    generation = f"{int(first[0])}000 Series" if len(first) >= 4 else f"{first} Series"
                except ValueError:
                    pass
        elif "THREADRIPPER" in upper:
            series = "AMD Ryzen Threadripper"
        elif "EPYC" in upper:
            series = "AMD EPYC"
        return generation, series

    if vendor:
        series = vendor
    return generation, series


def _format_clock(mhz: Any) -> str:
    try:
        value = float(mhz)
        return f"{value / 1000:.2f} GHz" if value >= 1000 else f"{value:.0f} MHz"
    except (TypeError, ValueError):
        return "Unknown"



def _read_storage_info() -> dict[str, Any]:
    """Read lightweight storage information for the dashboard."""
    data: dict[str, Any] = {
        "system_drive": "C:",
        "storage_error": "",
    }
    try:
        usage = psutil.disk_usage("C:\\")
        data.update({
            "storage_total_gb": usage.total / (1024 ** 3),
            "storage_used_gb": usage.used / (1024 ** 3),
            "storage_free_gb": usage.free / (1024 ** 3),
            "storage_free_percent": usage.free / usage.total * 100 if usage.total else None,
        })
    except Exception as exc:
        data["storage_error"] = str(exc)

    physical = _powershell_json(
        "Get-PhysicalDisk | Select-Object -First 1 FriendlyName,MediaType,BusType,Size,HealthStatus,OperationalStatus | ConvertTo-Json"
    )
    if isinstance(physical, dict):
        data["storage_device"] = str(physical.get("FriendlyName") or "")
        data["storage_media_type"] = str(physical.get("MediaType") or "")
        data["storage_bus_type"] = str(physical.get("BusType") or "")
        data["storage_health"] = str(physical.get("HealthStatus") or "")
        data["storage_operational_status"] = str(physical.get("OperationalStatus") or "")
    return data

def get_system_info() -> dict[str, Any]:
    """Return informational data only; this function does not run diagnosis."""
    memory = psutil.virtual_memory()
    cpu_rows = _powershell_json(
        "Get-CimInstance Win32_Processor | Select-Object -First 1 Name,Manufacturer,MaxClockSpeed,CurrentClockSpeed,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json"
    )
    if isinstance(cpu_rows, list):
        cpu_rows = cpu_rows[0] if cpu_rows else None
    cpu_rows = cpu_rows if isinstance(cpu_rows, dict) else {}

    ram_rows = _powershell_json(
        "Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum | Select-Object @{n='TotalCapacity';e={$_.Sum}} | ConvertTo-Json"
    )
    ram_speed = _powershell_json(
        "(Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1 Speed) | ConvertTo-Json"
    )
    if isinstance(ram_speed, dict):
        ram_speed_mhz = ram_speed.get("Speed")
    else:
        ram_speed_mhz = None

    windows = _read_windows_info()
    cpu_name = str(cpu_rows.get("Name") or platform.processor() or "Unknown processor")
    vendor = str(cpu_rows.get("Manufacturer") or "Unknown")
    generation, series = _cpu_generation_series(cpu_name, vendor)

    physical = cpu_rows.get("NumberOfCores") or psutil.cpu_count(logical=False)
    logical = cpu_rows.get("NumberOfLogicalProcessors") or psutil.cpu_count(logical=True)
    base_clock = cpu_rows.get("CurrentClockSpeed") or psutil.cpu_freq().current if psutil.cpu_freq() else None
    max_clock = cpu_rows.get("MaxClockSpeed") or (psutil.cpu_freq().max if psutil.cpu_freq() else None)

    total_gb = memory.total / (1024 ** 3)
    used_gb = memory.used / (1024 ** 3)
    available_gb = memory.available / (1024 ** 3)
    storage = _read_storage_info()
    if storage.get("storage_free_gb") is not None:
        storage["storage_summary"] = (
            f"{float(storage['storage_free_gb']):.1f} GB free / "
            f"{float(storage.get('storage_total_gb', 0)):.1f} GB"
        )

    info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "computer_name": socket.gethostname(),
        "windows_display_name": windows.get("windows_display_name", f"Windows {platform.release()}"),
        "windows_version": windows.get("windows_version", platform.version()),
        "windows_build": windows.get("windows_build", "Unknown"),
        "windows_build_full": windows.get("windows_build_full", "Unknown"),
        "windows_ubr": windows.get("windows_ubr", ""),
        "cpu": cpu_name,
        "cpu_name": cpu_name,
        "cpu_vendor": vendor,
        "cpu_generation": generation,
        "cpu_series": series,
        "cpu_current_clock": _format_clock(base_clock),
        "cpu_max_clock": _format_clock(max_clock),
        "cpu_summary": f"{series} • {generation} • {_format_clock(max_clock)}",
        "physical_cores": int(physical) if physical is not None else None,
        "logical_cores": int(logical) if logical is not None else None,
        "cpu_usage_percent": psutil.cpu_percent(interval=0.1),
        "ram_total_gb": total_gb,
        "ram_used_gb": used_gb,
        "ram_available_gb": available_gb,
        "ram_usage_percent": memory.percent,
        "ram_speed_mhz": ram_speed_mhz,
        **storage,
    }
    if isinstance(ram_rows, dict) and ram_rows.get("TotalCapacity"):
        try:
            info["ram_total_gb"] = float(ram_rows["TotalCapacity"]) / (1024 ** 3)
        except (TypeError, ValueError):
            pass
    return info


if __name__ == "__main__":
    print(json.dumps(get_system_info(), indent=2, default=str))
