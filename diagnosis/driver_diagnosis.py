# ============================================================
# FIXMATE-AI
# DRIVER DIAGNOSTICS V1.1
# ============================================================
#
# Improvements over V1:
# - No false HIGH fault just because PNPClass is missing
# - Problem Code is the primary fault signal
# - Duplicate device entries are removed
# - WMI driver dates are parsed correctly
# - Healthy OK devices remain NORMAL
# - Driver information unavailable != automatic fault
# ============================================================

import json
import re
import subprocess
from datetime import datetime


# ============================================================
# POWERSHELL EXECUTION
# ============================================================

def run_powershell(command):

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return {
                "success": False,
                "output": "",
                "error": result.stderr.strip()
            }

        return {
            "success": True,
            "output": result.stdout.strip(),
            "error": ""
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": "PowerShell command timed out."
        }

    except Exception as exc:
        return {
            "success": False,
            "output": "",
            "error": str(exc)
        }


# ============================================================
# JSON PARSER
# ============================================================

def parse_json_output(output):

    if not output:
        return []

    try:
        data = json.loads(output)

        if isinstance(data, list):
            return data

        return [data]

    except json.JSONDecodeError:
        return []


# ============================================================
# CLEAN VALUE
# ============================================================

def clean_value(value):

    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


# ============================================================
# DRIVER DATE PARSER
# ============================================================

def parse_driver_date(value):

    value = clean_value(value)

    if not value:
        return None

    # --------------------------------------------------------
    # WMI / PowerShell format:
    # /Date(1751328000000)/
    # --------------------------------------------------------

    match = re.search(
        r"/Date\((\d+)",
        value
    )

    if match:

        try:

            milliseconds = int(
                match.group(1)
            )

            date = datetime.fromtimestamp(
                milliseconds / 1000
            )

            return date.strftime(
                "%Y-%m-%d"
            )

        except (
            ValueError,
            OSError,
            OverflowError
        ):
            pass

    # --------------------------------------------------------
    # Already readable date
    # --------------------------------------------------------

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                value,
                fmt
            ).strftime("%Y-%m-%d")

        except ValueError:
            continue

    # --------------------------------------------------------
    # Raw WMI timestamp:
    # 20250101000000.000000+000
    # --------------------------------------------------------

    match = re.match(
        r"(\d{8})\d{6}",
        value
    )

    if match:
        raw = match.group(1)

        try:

            return datetime.strptime(
                raw,
                "%Y%m%d"
            ).strftime("%Y-%m-%d")

        except ValueError:
            pass

    return None


# ============================================================
# PNP DEVICE COLLECTION
# ============================================================

def collect_pnp_devices():

    command = r"""
$ErrorActionPreference = "SilentlyContinue"

Get-CimInstance Win32_PnPEntity |
    Select-Object `
        Name,
        DeviceID,
        PNPClass,
        Manufacturer,
        Status,
        ConfigManagerErrorCode,
        Present |
    ConvertTo-Json -Depth 4
"""

    result = run_powershell(
        command
    )

    if not result["success"]:

        return {
            "success": False,
            "devices": [],
            "error": result["error"]
        }

    devices = parse_json_output(
        result["output"]
    )

    normalized = []

    for device in devices:

        normalized.append({

            "name":
                clean_value(
                    device.get("Name")
                ),

            "device_id":
                clean_value(
                    device.get("DeviceID")
                ),

            "pnp_class":
                clean_value(
                    device.get("PNPClass")
                ),

            "manufacturer":
                clean_value(
                    device.get("Manufacturer")
                ),

            "status":
                clean_value(
                    device.get("Status")
                ),

            "problem_code":
                device.get(
                    "ConfigManagerErrorCode"
                ),

            "present":
                device.get(
                    "Present"
                ),
        })

    return {
        "success": True,
        "devices": normalized,
        "error": ""
    }


# ============================================================
# SIGNED DRIVER COLLECTION
# ============================================================

def collect_signed_drivers():

    command = r"""
$ErrorActionPreference = "SilentlyContinue"

Get-CimInstance Win32_PnPSignedDriver |
    Select-Object `
        DeviceName,
        DeviceID,
        DriverProviderName,
        DriverVersion,
        DriverDate,
        InfName,
        IsSigned,
        Signer |
    ConvertTo-Json -Depth 4
"""

    result = run_powershell(
        command
    )

    if not result["success"]:

        return {
            "success": False,
            "drivers": [],
            "error": result["error"]
        }

    drivers = parse_json_output(
        result["output"]
    )

    normalized = []

    for driver in drivers:

        device_id = clean_value(
            driver.get("DeviceID")
        )

        normalized.append({

            "device_name":
                clean_value(
                    driver.get("DeviceName")
                ),

            "device_id":
                device_id,

            "provider":
                clean_value(
                    driver.get(
                        "DriverProviderName"
                    )
                ),

            "version":
                clean_value(
                    driver.get(
                        "DriverVersion"
                    )
                ),

            "driver_date":
                parse_driver_date(
                    driver.get(
                        "DriverDate"
                    )
                ),

            "inf_name":
                clean_value(
                    driver.get(
                        "InfName"
                    )
                ),

            "signed":
                driver.get(
                    "IsSigned"
                ),

            "signer":
                clean_value(
                    driver.get(
                        "Signer"
                    )
                ),
        })

    return {
        "success": True,
        "drivers": normalized,
        "error": ""
    }


# ============================================================
# DRIVER MAP
# ============================================================

def build_driver_map(drivers):

    driver_map = {}

    for driver in drivers:

        device_id = driver.get(
            "device_id"
        )

        if not device_id:
            continue

        key = device_id.upper()

        # Keep first valid entry.
        if key not in driver_map:
            driver_map[key] = driver

    return driver_map


# ============================================================
# DEDUPLICATE PNP DEVICES
# ============================================================

def deduplicate_devices(devices):

    unique = {}

    for device in devices:

        device_id = device.get(
            "device_id"
        )

        name = (
            device.get("name")
            or "Unknown Device"
        )

        manufacturer = (
            device.get("manufacturer")
            or ""
        )

        status = (
            device.get("status")
            or ""
        )

        problem_code = device.get(
            "problem_code"
        )

        # ----------------------------------------------------
        # Normalize problem code
        # ----------------------------------------------------

        try:
            problem_code = int(
                problem_code
            )
        except (
            TypeError,
            ValueError
        ):
            problem_code = 0

        # ----------------------------------------------------
        # Actual device problems
        #
        # Keep separate instances when Windows gives a
        # non-zero Problem Code.
        # ----------------------------------------------------

        if problem_code != 0:

            if device_id:

                key = (
                    "PROBLEM",
                    device_id.upper()
                )

            else:

                key = (
                    "PROBLEM",
                    name.upper(),
                    manufacturer.upper(),
                    status.upper(),
                    problem_code
                )

        # ----------------------------------------------------
        # Warning/degraded/metadata duplicates
        #
        # Different PNP instance IDs can still describe the
        # same underlying driver/component.
        #
        # Group them using diagnostic fingerprint.
        # ----------------------------------------------------

        elif status.upper() not in (
            "OK",
            "UNKNOWN",
            ""
        ):

            key = (
                "WARNING",
                name.upper(),
                manufacturer.upper()
            )

        # ----------------------------------------------------
        # Healthy devices
        #
        # Keep DeviceID-based identity.
        # ----------------------------------------------------

        else:

            if device_id:

                key = (
                    "HEALTHY",
                    device_id.upper()
                )

            else:

                key = (
                    "HEALTHY",
                    name.upper(),
                    manufacturer.upper()
                )

        # ----------------------------------------------------
        # Store first occurrence
        # ----------------------------------------------------

        if key not in unique:

            entry = dict(device)

            entry["_occurrences"] = 1

            unique[key] = entry

        else:

            # Count duplicates so FixMate knows that multiple
            # Windows records pointed to the same diagnostic
            # component.

            unique[key]["_occurrences"] = (
                unique[key].get(
                    "_occurrences",
                    1
                ) + 1
            )

    return list(
        unique.values()
    )
# ============================================================
# DEVICE DIAGNOSIS
# ============================================================

def diagnose_device(
    device,
    driver=None
):

    name = (
        device.get("name")
        or "Unknown Device"
    )

    status = (
        str(
            device.get(
                "status"
            ) or ""
        )
        .strip()
        .upper()
    )

    problem_code = device.get(
        "problem_code"
    )

    # Normalize problem code.
    try:
        problem_code = int(
            problem_code
        )

    except (
        TypeError,
        ValueError
    ):
        problem_code = 0

    present = device.get(
        "present"
    )

    # ========================================================
    # PRIMARY FAULT SIGNAL:
    # CONFIGURATION MANAGER ERROR CODE
    # ========================================================

    if problem_code != 0:

        return {
            "name": name,
            "status":
                "DRIVER_OR_DEVICE_PROBLEM",
            "severity": "HIGH",
            "problem_code":
                problem_code,
            "problem": (
                "Windows reports a non-zero "
                "device configuration problem code."
            ),
            "driver": driver,
        }

    # ========================================================
    # DEVICE NOT PRESENT
    # ========================================================

    if present is False:

        return {
            "name": name,
            "status": "NOT_PRESENT",
            "severity": "LOW",
            "problem_code": 0,
            "problem": (
                "The device is currently not present."
            ),
            "driver": driver,
        }

    # ========================================================
    # SPECIAL MICROSOFT / BLUETOOTH / SOFTWARE DEVICES
    #
    # Missing PNPClass or missing signed-driver record alone
    # is NOT considered a hardware/driver fault.
    # ========================================================

    if status in (
        "OK",
        "UNKNOWN",
        ""
    ):

        # ----------------------------------------------------
        # Driver metadata unavailable
        # ----------------------------------------------------

        if driver is None:

            return {
                "name": name,
                "status":
                    "DRIVER_INFO_UNAVAILABLE",
                "severity": "NORMAL",
                "problem_code": 0,
                "problem": (
                    "No matching signed-driver "
                    "metadata was found, but Windows "
                    "reports no device configuration error."
                ),
                "driver": None,
            }

        # ----------------------------------------------------
        # Unsigned driver
        # ----------------------------------------------------

        signed = driver.get(
            "signed"
        )

        if signed is False:

            return {
                "name": name,
                "status": "UNSIGNED_DRIVER",
                "severity": "HIGH",
                "problem_code": 0,
                "problem": (
                    "The installed driver is "
                    "reported as unsigned."
                ),
                "driver": driver,
            }

        # ----------------------------------------------------
        # Healthy
        # ----------------------------------------------------

        return {
            "name": name,
            "status": "HEALTHY",
            "severity": "NORMAL",
            "problem_code": 0,
            "problem": (
                "Device and driver information "
                "appear normal."
            ),
            "driver": driver,
        }

    # ========================================================
    # NON-OK STATUS
    # ========================================================

    # Device status is meaningful even when the problem code
    # is zero. Do not label it as hardware failure automatically.

    if status in (
        "DEGRADED",
        "WARNING"
    ):

        return {
            "name": name,
            "status": "DEVICE_WARNING",
            "severity": "MODERATE",
            "problem_code": 0,
            "problem": (
                f"Windows reports device status: {status}."
            ),
            "driver": driver,
        }

    # ========================================================
    # OTHER NON-OK STATE
    # ========================================================

    return {
        "name": name,
        "status": "DEVICE_WARNING",
        "severity": "MODERATE",
        "problem_code": 0,
        "problem": (
            f"Windows reports device status: {status}."
        ),
        "driver": driver,
    }


# ============================================================
# COMPLETE DRIVER DIAGNOSIS
# ============================================================

def diagnose_drivers():

    pnp_result = collect_pnp_devices()

    if not pnp_result["success"]:

        return {
            "available": False,
            "devices": [],
            "summary": {},
            "error":
                pnp_result["error"]
        }

    driver_result = collect_signed_drivers()

    devices = deduplicate_devices(
        pnp_result["devices"]
    )

    drivers = driver_result.get(
        "drivers",
        []
    )

    driver_map = build_driver_map(
        drivers
    )

    diagnosed_devices = []

    for device in devices:

        device_id = device.get(
            "device_id"
        )

        driver = None

        if device_id:

            driver = driver_map.get(
                device_id.upper()
            )

        diagnosis = diagnose_device(
            device,
            driver
        )

        # Attach extra device information.
        diagnosis["device_id"] = device_id
        diagnosis["pnp_class"] = device.get(
            "pnp_class"
        )
        diagnosis["manufacturer"] = device.get(
            "manufacturer"
        )
        diagnosis["present"] = device.get(
            "present"
        )
        diagnosis["occurrences"] = device.get(
            "_occurrences",
            1
        )
        diagnosed_devices.append(
            diagnosis
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    summary = {

        "total_devices":
            len(diagnosed_devices),

        "healthy":
            0,

        "low":
            0,

        "moderate":
            0,

        "high":
            0,

        "problem_devices":
            0,
    }

    for item in diagnosed_devices:

        severity = str(
            item.get(
                "severity",
                "NORMAL"
            )
        ).lower()

        status = item.get(
            "status"
        )

        if severity == "normal":
            summary["healthy"] += 1

        elif severity == "low":
            summary["low"] += 1

        elif severity == "moderate":
            summary["moderate"] += 1

        elif severity == "high":
            summary["high"] += 1

        # Only actual warning/problem states count.
        if status in (
            "DRIVER_OR_DEVICE_PROBLEM",
            "UNSIGNED_DRIVER",
            "DEVICE_WARNING",
        ):

            summary[
                "problem_devices"
            ] += 1

    return {

        "available": True,

        "devices":
            diagnosed_devices,

        "summary":
            summary,

        "driver_collection_available":
            driver_result["success"],

        "error":
            driver_result.get(
                "error",
                ""
            ),
    }


# ============================================================
# PRINT DRIVER REPORT
# ============================================================

def print_driver_report(
    result
):

    print("\n")
    print("=" * 70)
    print("                 FIXMATE DRIVER DIAGNOSIS")
    print("=" * 70)

    if not result.get(
        "available",
        False
    ):

        print(
            "\nDriver diagnostics unavailable."
        )

        print(
            "Reason:",
            result.get(
                "error",
                "Unknown error"
            )
        )

        print(
            "\n" + "=" * 70
        )

        return

    summary = result.get(
        "summary",
        {}
    )

    print("\n[ DRIVER SUMMARY ]")
    print("-" * 70)

    print(
        f"Total Devices       : "
        f"{summary.get('total_devices', 0)}"
    )

    print(
        f"Healthy             : "
        f"{summary.get('healthy', 0)}"
    )

    print(
        f"Low                 : "
        f"{summary.get('low', 0)}"
    )

    print(
        f"Moderate            : "
        f"{summary.get('moderate', 0)}"
    )

    print(
        f"High                : "
        f"{summary.get('high', 0)}"
    )

    print(
        f"Problem Devices     : "
        f"{summary.get('problem_devices', 0)}"
    )

    print("\n[ NON-NORMAL DEVICES ]")
    print("-" * 70)

    non_normal = [
        item
        for item in result.get(
            "devices",
            []
        )
        if item.get(
            "severity"
        ) != "NORMAL"
    ]

    if not non_normal:

        print(
            "No driver/device problems detected."
        )

    else:

        for item in non_normal:

            print(
                f"\nDevice               : "
                f"{item.get('name', 'Unknown')}"
            )

            print(
                f"Status               : "
                f"{item.get('status', 'UNKNOWN')}"
            )

            print(
                f"Severity             : "
                f"{item.get('severity', 'UNKNOWN')}"
            )
            
            print(
                f"Occurrences          : "
                f"{item.get('occurrences', 1)}"
            )

            print(
                f"Problem Code         : "
                f"{item.get('problem_code', 0)}"
            )

            print(
                f"Problem              : "
                f"{item.get('problem', 'N/A')}"
            )

            driver = item.get(
                "driver"
            )

            if driver:

                print(
                    f"Driver Provider      : "
                    f"{driver.get('provider', 'N/A')}"
                )

                print(
                    f"Driver Version       : "
                    f"{driver.get('version', 'N/A')}"
                )

                print(
                    f"Driver Date          : "
                    f"{driver.get('driver_date', 'N/A')}"
                )

                print(
                    f"INF File             : "
                    f"{driver.get('inf_name', 'N/A')}"
                )

                print(
                    f"Signed               : "
                    f"{driver.get('signed', 'N/A')}"
                )

                print(
                    f"Signer               : "
                    f"{driver.get('signer', 'N/A')}"
                )

    print("\n")
    print("=" * 70)
    print("              END OF DRIVER DIAGNOSIS")
    print("=" * 70)


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    print(
        "\n========== FIXMATE DRIVER DIAGNOSTICS V1.1 ==========\n"
    )

    result = diagnose_drivers()

    print_driver_report(
        result
    )