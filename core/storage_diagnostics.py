import subprocess
import json
import os


# ============================================================
# POWERSHELL HELPER
# ============================================================

def run_powershell(command, timeout=20):

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
            encoding="utf-8",
            errors="ignore",
            timeout=timeout
        )

        if result.returncode != 0:
            return []

        output = result.stdout.strip()

        if not output:
            return []

        data = json.loads(output)

        if isinstance(data, dict):
            return [data]

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []


# ============================================================
# STORAGE DEVICES
# ============================================================

def get_storage_devices():

    command = """
    Get-PhysicalDisk |
    Select-Object FriendlyName,
                  MediaType,
                  Size,
                  HealthStatus,
                  OperationalStatus,
                  BusType,
                  FirmwareVersion,
                  SerialNumber,
                  DeviceId,
                  PhysicalSectorSize,
                  LogicalSectorSize |
    ConvertTo-Json -Depth 3
    """

    return run_powershell(command)


# ============================================================
# STORAGE VOLUMES
# ============================================================

def get_storage_volumes():

    command = """
    Get-Volume |
    Where-Object {
        $_.DriveLetter -ne $null
    } |
    Select-Object DriveLetter,
                  FileSystemLabel,
                  FileSystem,
                  HealthStatus,
                  Size,
                  SizeRemaining,
                  DriveType |
    ConvertTo-Json -Depth 3
    """

    return run_powershell(command)


# ============================================================
# SYSTEM DRIVE
# ============================================================

def get_system_drive():

    return (
        os.environ.get(
            "SystemDrive",
            "C:"
        )
        .upper()
        .rstrip("\\")
    )


# ============================================================
# FREE SPACE ANALYSIS
# ============================================================

def analyze_free_space(
    free_percent,
    free_gb
):

    if free_percent is None:

        return {
            "status": "UNKNOWN",
            "severity": "LOW",
            "message":
                "Free-space information is unavailable.",
            "hardware_fault": False
        }

    if free_percent < 5:

        return {
            "status": "CRITICAL",
            "severity": "HIGH",
            "message":
                f"Critically low free space: "
                f"{free_percent:.1f}% "
                f"({free_gb:.2f} GB) remaining.",
            "hardware_fault": False
        }

    if free_percent < 10:

        return {
            "status": "WARNING",
            "severity": "MODERATE",
            "message":
                f"Low free space: "
                f"{free_percent:.1f}% "
                f"({free_gb:.2f} GB) remaining.",
            "hardware_fault": False
        }

    if free_percent < 15:

        return {
            "status": "ADVISORY",
            "severity": "LOW",
            "message":
                f"Free space is getting low: "
                f"{free_percent:.1f}% remaining.",
            "hardware_fault": False
        }

    return {
        "status": "HEALTHY",
        "severity": "NORMAL",
        "message":
            f"Free space is healthy: "
            f"{free_percent:.1f}% available.",
        "hardware_fault": False
    }


# ============================================================
# PHYSICAL DISK HEALTH ANALYSIS
# ============================================================

def analyze_disk_health(
    health,
    operational
):

    health_text = str(
        health
    ).lower()

    operational_text = str(
        operational
    ).lower()

    # Healthy disk
    if (
        health_text == "healthy"
        and (
            "ok" in operational_text
            or "online" in operational_text
        )
    ):

        return {
            "status": "NORMAL",
            "severity": "NORMAL",
            "message":
                "No storage hardware health problem detected.",
            "hardware_fault": False
        }

    # Confirmed unhealthy/failed state
    if (
        "unhealthy" in health_text
        or "failed" in health_text
    ):

        return {
            "status": "CRITICAL",
            "severity": "CRITICAL",
            "message":
                "Windows reports the physical storage "
                "device as unhealthy or failed.",
            "hardware_fault": True
        }

    # Warning/degraded state
    if (
        "warning" in health_text
        or "degraded" in health_text
    ):

        return {
            "status": "WARNING",
            "severity": "HIGH",
            "message":
                "Windows reports a degraded or warning "
                "storage health state.",
            "hardware_fault": False
        }

    # Operational problem
    if operational_text not in (
        "ok",
        "online",
        "normal",
        "operational"
    ):

        return {
            "status": "WARNING",
            "severity": "HIGH",
            "message":
                f"Storage operational status is "
                f"{operational}.",
            "hardware_fault": False
        }

    return {
        "status": "UNKNOWN",
        "severity": "LOW",
        "message":
            "Storage health could not be fully determined.",
        "hardware_fault": False
    }


# ============================================================
# MAIN STORAGE DIAGNOSIS
# ============================================================

def get_storage_diagnostic():

    devices = get_storage_devices()

    volumes = get_storage_volumes()

    system_drive = get_system_drive()

    results = []

    # --------------------------------------------------------
    # Physical disks
    # --------------------------------------------------------

    for device in devices:

        size_bytes = device.get(
            "Size"
        )

        if isinstance(
            size_bytes,
            (int, float)
        ):

            size_gb = round(
                size_bytes / (1024 ** 3),
                2
            )

        else:

            size_gb = None


        health = device.get(
            "HealthStatus",
            "Unknown"
        )

        operational = device.get(
            "OperationalStatus",
            "Unknown"
        )


        # PowerShell may return arrays
        if isinstance(
            operational,
            list
        ):

            operational = ", ".join(
                str(item)
                for item in operational
            )


        if isinstance(
            health,
            list
        ):

            health = ", ".join(
                str(item)
                for item in health
            )


        analysis = analyze_disk_health(
            health,
            operational
        )


        results.append({

            "name":
                device.get(
                    "FriendlyName",
                    "Unknown"
                ),

            "media_type":
                device.get(
                    "MediaType",
                    "Unknown"
                ),

            "size_gb":
                size_gb,

            "size_bytes":
                size_bytes,

            "health":
                health,

            "operational_status":
                operational,

            "bus_type":
                device.get(
                    "BusType",
                    "Unknown"
                ),

            "firmware":
                device.get(
                    "FirmwareVersion",
                    "Unknown"
                ),

            "serial":
                device.get(
                    "SerialNumber",
                    "Unknown"
                ),

            "device_id":
                device.get(
                    "DeviceId",
                    "Unknown"
                ),

            "physical_sector_size":
                device.get(
                    "PhysicalSectorSize"
                ),

            "logical_sector_size":
                device.get(
                    "LogicalSectorSize"
                ),

            "status":
                (
                    "NORMAL"
                    if analysis["status"] == "NORMAL"
                    else
                    "WARNING"
                    if analysis["status"] == "WARNING"
                    else
                    "CRITICAL"
                    if analysis["status"] == "CRITICAL"
                    else
                    "UNKNOWN"
                ),

            "health_analysis":
                analysis
        })


    # --------------------------------------------------------
    # Volumes
    # --------------------------------------------------------

    volume_results = []

    for volume in volumes:

        size_bytes = volume.get(
            "Size"
        )

        remaining_bytes = volume.get(
            "SizeRemaining"
        )


        if isinstance(
            size_bytes,
            (int, float)
        ):

            size_gb = (
                size_bytes /
                (1024 ** 3)
            )

        else:

            size_gb = None


        if isinstance(
            remaining_bytes,
            (int, float)
        ):

            free_gb = (
                remaining_bytes /
                (1024 ** 3)
            )

        else:

            free_gb = None


        used_gb = None

        if (
            size_gb is not None
            and free_gb is not None
        ):

            used_gb = max(
                size_gb - free_gb,
                0
            )


        free_percent = None

        if (
            isinstance(
                size_bytes,
                (int, float)
            )
            and size_bytes > 0
            and isinstance(
                remaining_bytes,
                (int, float)
            )
            and remaining_bytes >= 0
        ):

            free_percent = (
                remaining_bytes /
                size_bytes
            ) * 100


        free_analysis = analyze_free_space(
            free_percent,
            free_gb
            if free_gb is not None
            else 0
        )


        drive = volume.get(
            "DriveLetter"
        )


        volume_results.append({

            "drive":
                drive,

            "label":
                volume.get(
                    "FileSystemLabel"
                ),

            "filesystem":
                volume.get(
                    "FileSystem"
                ),

            "health_status":
                volume.get(
                    "HealthStatus",
                    "Unknown"
                ),

            "drive_type":
                volume.get(
                    "DriveType"
                ),

            "size_gb":
                round(
                    size_gb,
                    2
                )
                if size_gb is not None
                else None,

            "used_gb":
                round(
                    used_gb,
                    2
                )
                if used_gb is not None
                else None,

            "free_gb":
                round(
                    free_gb,
                    2
                )
                if free_gb is not None
                else None,

            "free_percent":
                round(
                    free_percent,
                    2
                )
                if free_percent is not None
                else None,

            "free_space_analysis":
                free_analysis
        })


    # --------------------------------------------------------
    # Overall physical-device status
    # --------------------------------------------------------

    if not results:

        overall_status = "UNKNOWN"
        overall_severity = "LOW"

    elif any(
        item["health_analysis"].get(
            "severity"
        ) == "CRITICAL"
        for item in results
    ):

        overall_status = "CRITICAL"
        overall_severity = "CRITICAL"

    elif any(
        item["health_analysis"].get(
            "severity"
        ) == "HIGH"
        for item in results
    ):

        overall_status = "WARNING"
        overall_severity = "HIGH"

    elif any(
        item["health_analysis"].get(
            "severity"
        ) == "MODERATE"
        for item in results
    ):

        overall_status = "WARNING"
        overall_severity = "MODERATE"

    else:

        overall_status = "NORMAL"
        overall_severity = "NORMAL"


    # --------------------------------------------------------
    # Add volume free-space impact
    # --------------------------------------------------------

    volume_severity_order = {
        "NORMAL": 0,
        "LOW": 1,
        "MODERATE": 2,
        "HIGH": 3,
        "CRITICAL": 4
    }

    for volume in volume_results:

        severity = volume[
            "free_space_analysis"
        ].get(
            "severity",
            "LOW"
        )

        if (
            volume_severity_order.get(
                severity,
                1
            )
            >
            volume_severity_order.get(
                overall_severity,
                0
            )
        ):

            overall_severity = severity

            if severity in (
                "CRITICAL",
                "HIGH"
            ):

                overall_status = "WARNING"

            elif severity in (
                "MODERATE",
                "LOW"
            ):

                if overall_status == "NORMAL":
                    overall_status = "WARNING"


    # --------------------------------------------------------
    # Find system volume
    # --------------------------------------------------------

    system_volume = None

    for volume in volume_results:

        drive = str(
            volume.get(
                "drive",
                ""
            )
        ).upper().rstrip(":")

        system_drive_normalized = str(
            system_drive
        ).upper().rstrip(":")

        if drive == system_drive_normalized:

            system_volume = volume
            break


    return {

        "type":
            "Storage",

        "devices":
            results,

        "volumes":
            volume_results,

        "system_drive":
            system_drive,

        "system_volume":
            system_volume,

        "overall_status":
            overall_status,

        "overall_severity":
            overall_severity,

        "available":
            bool(
                results
                or volume_results
            )
    }


# ============================================================
# PRINT STORAGE REPORT
# ============================================================

def print_storage_report():

    print(
        "\n========== FIXMATE STORAGE DIAGNOSTIC ==========\n"
    )

    data = get_storage_diagnostic()

    devices = data.get(
        "devices",
        []
    )

    volumes = data.get(
        "volumes",
        []
    )


    if not devices:

        print(
            "No physical storage devices detected."
        )

        print(
            "\nThis does NOT automatically indicate "
            "a storage failure."
        )

    else:

        print(
            f"Overall Status : "
            f"{data.get('overall_status', 'UNKNOWN')}"
        )

        print(
            f"Overall Severity: "
            f"{data.get('overall_severity', 'UNKNOWN')}"
        )

        print()


    # --------------------------------------------------------
    # Physical devices
    # --------------------------------------------------------

    for index, device in enumerate(
        devices,
        start=1
    ):

        print(
            f"Storage Device #{index}"
        )

        print(
            "-" * 50
        )

        print(
            f"Name       : "
            f"{device['name']}"
        )

        print(
            f"Media Type : "
            f"{device['media_type']}"
        )


        if device["size_gb"] is not None:

            print(
                f"Size       : "
                f"{device['size_gb']} GB"
            )

        else:

            print(
                "Size       : N/A"
            )


        print(
            f"Health     : "
            f"{device['health']}"
        )

        print(
            f"Operational: "
            f"{device['operational_status']}"
        )

        print(
            f"Bus Type   : "
            f"{device['bus_type']}"
        )

        print(
            f"Firmware   : "
            f"{device['firmware']}"
        )

        print(
            f"Serial     : "
            f"{device['serial']}"
        )

        print(
            f"Status     : "
            f"{device['status']}"
        )


        analysis = device.get(
            "health_analysis",
            {}
        )

        print(
            f"Severity   : "
            f"{analysis.get('severity', 'UNKNOWN')}"
        )

        print(
            f"Assessment : "
            f"{analysis.get('message', 'N/A')}"
        )

        print(
            f"Hardware Fault: "
            f"{'YES' if analysis.get('hardware_fault', False) else 'NO'}"
        )

        print()


        if device["status"] == "NORMAL":

            print(
                "Verdict    : "
                "No storage fault detected."
            )

        elif device["status"] == "WARNING":

            print(
                "Verdict    : "
                "Storage health warning detected."
            )

            print(
                "Recommendation: "
                "Back up important files and "
                "investigate the storage device."
            )

        elif device["status"] == "CRITICAL":

            print(
                "Verdict    : "
                "Potential storage hardware failure detected."
            )

            print(
                "Recommendation: "
                "Back up important files immediately "
                "and arrange professional inspection."
            )

        else:

            print(
                "Verdict    : "
                "Storage health could not be determined."
            )

        print("\n")


    # --------------------------------------------------------
    # Volumes / free space
    # --------------------------------------------------------

    print(
        "[ STORAGE VOLUMES / FREE SPACE ]"
    )

    print(
        "-" * 50
    )


    if not volumes:

        print(
            "No mounted storage volumes detected."
        )

    else:

        for volume in volumes:

            drive = volume.get(
                "drive",
                "Unknown"
            )

            print(
                f"\nDrive       : "
                f"{drive}:"
            )

            print(
                f"Label       : "
                f"{volume.get('label') or 'N/A'}"
            )

            print(
                f"File System : "
                f"{volume.get('filesystem') or 'N/A'}"
            )

            if volume.get(
                "size_gb"
            ) is not None:

                print(
                    f"Total Size  : "
                    f"{volume['size_gb']:.2f} GB"
                )

            if volume.get(
                "used_gb"
            ) is not None:

                print(
                    f"Used        : "
                    f"{volume['used_gb']:.2f} GB"
                )

            if volume.get(
                "free_gb"
            ) is not None:

                print(
                    f"Free        : "
                    f"{volume['free_gb']:.2f} GB"
                )

            if volume.get(
                "free_percent"
            ) is not None:

                print(
                    f"Free Space  : "
                    f"{volume['free_percent']:.1f}%"
                )


            analysis = volume.get(
                "free_space_analysis",
                {}
            )

            print(
                f"Risk Status : "
                f"{analysis.get('status', 'UNKNOWN')}"
            )

            print(
                f"Severity    : "
                f"{analysis.get('severity', 'UNKNOWN')}"
            )

            print(
                f"Assessment  : "
                f"{analysis.get('message', 'N/A')}"
            )

            # Explicitly avoid treating free space as hardware failure.
            print(
                "Hardware Fault: NO"
            )

            if analysis.get(
                "severity"
            ) in (
                "MODERATE",
                "HIGH"
            ):

                print(
                    "Recommendation: "
                    "Free additional disk space "
                    "to maintain healthy system operation."
                )


    # --------------------------------------------------------
    # System drive
    # --------------------------------------------------------

    system_volume = data.get(
        "system_volume"
    )

    print(
        "\n[ SYSTEM DRIVE ]"
    )

    print(
        "-" * 50
    )

    if system_volume:

        print(
            f"System Drive: "
            f"{system_volume.get('drive', 'UNKNOWN')}:"
        )

        print(
            f"Free Space  : "
            f"{system_volume.get('free_percent', 'N/A')}%"
        )

        print(
            f"Free        : "
            f"{system_volume.get('free_gb', 'N/A')} GB"
        )

        risk = system_volume.get(
            "free_space_analysis",
            {}
        )

        print(
            f"Risk        : "
            f"{risk.get('status', 'UNKNOWN')}"
        )

        print(
            f"Severity    : "
            f"{risk.get('severity', 'UNKNOWN')}"
        )

    else:

        print(
            "System drive information unavailable."
        )


    print(
        "\n================================================"
    )


if __name__ == "__main__":

    print_storage_report()
