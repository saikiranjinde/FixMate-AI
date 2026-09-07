import sys
import os
from pathlib import Path


# ============================================================
# PATH SETUP
# ============================================================

CORE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_ROOT = os.path.dirname(
    CORE_DIR
)

if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


# ============================================================
# CORE MODULES
# ============================================================

from core.system_info import get_system_info
from core.hardware import get_hardware_info
from core.diagnostics import run_diagnostics
from core.process_analyzer_v3 import analyze_processes
from core.gpu_diagnostics import run_gpu_diagnostic
from core.thermal import run_thermal_diagnostic
from core.storage_diagnostics import get_storage_diagnostic

from core.battery_diagnosis import (
    diagnose_battery,
    print_battery_report
)

# ============================================================
# DRIVER DIAGNOSTICS
# ============================================================

from diagnosis.driver_diagnosis import (
    diagnose_drivers,
    print_driver_report
)

# ============================================================
# NETWORK DIAGNOSTICS
# ============================================================

from diagnosis.network_diagnosis import (
    diagnose_network,
    print_network_report
)

from diagnosis.windows_health import (
    diagnose_windows_health,
    print_windows_health_report
)

from diagnosis.startup_diagnosis import (
    diagnose_startup,
    print_startup_report
)


# ============================================================
# DIAGNOSIS ENGINE
# ============================================================

from diagnosis.fault_engine import (
    analyze_faults
)

from diagnosis.severity_engine import (
    calculate_overall_severity
)

from diagnosis.recommendation_engine import (
    generate_recommendations
)

from diagnosis.diagnosis_report import (
    generate_diagnosis_report,
    print_diagnosis_report
)

from diagnosis.report_ui import (
    save_html_report
)


# ============================================================
# SECTION PRINTER
# ============================================================

def print_section(title):

    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


# ============================================================
# SAFE VALUE HELPERS
# ============================================================

def safe_number(
    value,
    default=0.0
):

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return default


def format_optional(
    value,
    suffix=""
):

    if value is None:
        return "N/A"

    return f"{value}{suffix}"


# ============================================================
# STORAGE VALUE HELPERS
# ============================================================

def get_storage_value(
    device,
    *keys,
    default="N/A"
):

    for key in keys:

        value = device.get(
            key
        )

        if value is not None:

            return value

    return default


# ============================================================
# FULL SCAN
# ============================================================

def run_full_scan():

    print("\n")
    print("=" * 60)
    print("              FIXMATE FULL SCAN")
    print("=" * 60)


    # ========================================================
    # STEP 1
    # SYSTEM INFORMATION
    # ========================================================

    print_section(
        "SYSTEM INFORMATION"
    )

    try:

        system = get_system_info()

    except Exception as exc:

        system = {}

        print(
            f"System information unavailable: {exc}"
        )

    for key, value in system.items():

        print(
            f"{key:<25}: {value}"
        )


    # ========================================================
    # STEP 2
    # HARDWARE INFORMATION
    # ========================================================

    print_section(
        "HARDWARE INFORMATION"
    )

    try:

        hardware = get_hardware_info()

    except Exception as exc:

        hardware = {}

        print(
            f"Hardware information unavailable: {exc}"
        )

    for category, devices in hardware.items():

        print(
            f"\n{category}:"
        )

        if not devices:

            print(
                "  No information available"
            )

            continue

        if not isinstance(
            devices,
            list
        ):

            devices = [devices]

        for device in devices:

            if isinstance(
                device,
                dict
            ):

                for key, value in device.items():

                    if (
                        key.lower() == "size"
                        and isinstance(
                            value,
                            (int, float)
                        )
                    ):

                        value = (
                            f"{value / (1024 ** 3):.2f} GB"
                        )

                    print(
                        f"  {key}: {value}"
                    )

            else:

                print(
                    f"  {device}"
                )


    # ========================================================
    # STEP 3
    # SYSTEM DIAGNOSTICS
    # ========================================================

    print_section(
        "SYSTEM DIAGNOSTICS"
    )

    try:

        diagnostics = run_diagnostics()

    except Exception as exc:

        diagnostics = {}

        print(
            f"System diagnostics unavailable: {exc}"
        )

    for category, result in diagnostics.items():

        if not isinstance(
            result,
            dict
        ):
            continue

        result_type = result.get(
            "type",
            category
        )

        print(
            f"\n{result_type}"
        )

        print(
            f"Status : "
            f"{result.get('status', 'UNKNOWN')}"
        )

        print(
            f"Message: "
            f"{result.get('message', 'N/A')}"
        )

        # ----------------------------------------------------
        # MEMORY
        # ----------------------------------------------------

        if str(
            result_type
        ).lower() == "memory":

            print(
                f"Usage     : "
                f"{format_optional(result.get('usage_percent'), '%')}"
            )

            print(
                f"Used      : "
                f"{format_optional(result.get('used_gb'), ' GB')}"
            )

            print(
                f"Available : "
                f"{format_optional(result.get('available_gb'), ' GB')}"
            )

        # ----------------------------------------------------
        # CPU
        # ----------------------------------------------------

        elif str(
            result_type
        ).lower() == "cpu":

            print(
                f"Usage     : "
                f"{format_optional(result.get('usage_percent'), '%')}"
            )


    # ========================================================
    # STEP 4
    # PROCESS ANALYSIS
    # ========================================================

    print_section(
        "PROCESS ANALYSIS"
    )

    try:

        top_cpu, top_memory = (
            analyze_processes()
        )

    except Exception as exc:

        top_cpu = []
        top_memory = []

        print(
            f"Process analysis unavailable: {exc}"
        )


    print(
        "\nTop Applications by Memory:\n"
    )

    for app in top_memory[:10]:

        print(
            f"{app.get('display_name', 'Unknown'):<30} "
            f"RAM: {safe_number(app.get('memory_mb')):>8.1f} MB  "
            f"Processes: {app.get('process_count', 1):>3}  "
            f"Status: {app.get('severity', 'NORMAL')}"
        )


    print(
        "\nTop Applications by CPU:\n"
    )

    for app in top_cpu[:10]:

        print(
            f"{app.get('display_name', 'Unknown'):<30} "
            f"CPU: {safe_number(app.get('cpu_percent')):>5.1f}%  "
            f"Processes: {app.get('process_count', 1):>3}  "
            f"Status: {app.get('severity', 'NORMAL')}"
        )


    # ========================================================
    # STEP 5
    # GPU DIAGNOSTICS
    # ========================================================

    print_section(
        "GPU DIAGNOSTICS"
    )

    try:

        gpu = run_gpu_diagnostic()

    except Exception as exc:

        gpu = {
            "available": False,
            "error": str(exc)
        }

    if not gpu.get(
        "available",
        False
    ):

        print(
            "NVIDIA GPU telemetry unavailable."
        )

        print(
            f"Reason: "
            f"{gpu.get('error', 'Unknown error')}"
        )

    else:

        print(
            f"GPU               : "
            f"{gpu.get('name', 'Unknown GPU')}"
        )

        print(
            f"Driver            : "
            f"{gpu.get('driver_version', 'N/A')}"
        )

        print(
            f"Temperature       : "
            f"{format_optional(gpu.get('temperature_c'), ' °C')}"
        )

        print(
            f"Temperature Status: "
            f"{gpu.get('temperature_status', 'UNKNOWN')}"
        )

        print(
            f"GPU Usage         : "
            f"{format_optional(gpu.get('utilization_percent'), '%')}"
        )

        print(
            f"VRAM              : "
            f"{format_optional(gpu.get('memory_used_mb'), ' MB')} / "
            f"{format_optional(gpu.get('memory_total_mb'), ' MB')}"
        )

        print(
            f"Power             : "
            f"{format_optional(gpu.get('power_draw_w'), ' W')} / "
            f"{format_optional(gpu.get('power_limit_w'), ' W')}"
        )

        print(
            f"Power Usage       : "
            f"{format_optional(gpu.get('power_usage_percent'), '%')}"
        )

        print(
            f"Graphics Clock    : "
            f"{format_optional(gpu.get('graphics_clock_mhz'), ' MHz')}"
        )

        print(
            f"Memory Clock      : "
            f"{format_optional(gpu.get('memory_clock_mhz'), ' MHz')}"
        )


    # ========================================================
    # STEP 6
    # THERMAL DIAGNOSTICS
    # ========================================================

    print_section(
        "THERMAL DIAGNOSTICS"
    )

    try:

        thermal = run_thermal_diagnostic()

    except Exception as exc:

        thermal = None

        print(
            f"Thermal diagnostics unavailable: {exc}"
        )

    if not thermal:

        print(
            "CPU temperature sensor data is not available "
            "through Windows ACPI."
        )

        print(
            "This does NOT indicate a hardware fault."
        )

    else:

        # Support either list or dict return.
        if isinstance(
            thermal,
            dict
        ):

            thermal_items = [thermal]

        else:

            thermal_items = thermal

        for sensor in thermal_items:

            if not isinstance(
                sensor,
                dict
            ):
                continue

            print(
                f"Sensor     : "
                f"{sensor.get('name', 'Unknown')}"
            )

            print(
                f"Temperature: "
                f"{format_optional(sensor.get('temperature'), ' °C')}"
            )

            print(
                f"Status     : "
                f"{sensor.get('status', 'UNKNOWN')}"
            )

            print()


    # ========================================================
    # STEP 7
    # STORAGE DIAGNOSTICS
    # ========================================================

    print_section(
        "STORAGE DIAGNOSTICS"
    )

    try:

        storage_data = get_storage_diagnostic()

    except Exception as exc:

        storage_data = []

        print(
            f"Storage diagnostics unavailable: {exc}"
        )

    # --------------------------------------------------------
    # Storage module compatibility
    # --------------------------------------------------------
    # Newer storage_diagnostics returns a dictionary containing
    # physical disk data and volume/system-drive information.
    # Older versions may return a list of physical devices.
    #
    # Keep the original storage_data unchanged for Fault Engine,
    # but normalize only the display list here.

    if isinstance(
        storage_data,
        dict
    ):

        storage_devices = (
            storage_data.get(
                "physical_disks"
            )
            or storage_data.get(
                "disks"
            )
            or storage_data.get(
                "devices"
            )
            or []
        )

        if isinstance(
            storage_devices,
            dict
        ):

            storage_devices = [
                storage_devices
            ]

        volumes = (
            storage_data.get(
                "volumes"
            )
            or []
        )

        if isinstance(
            volumes,
            dict
        ):

            volumes = [
                volumes
            ]

        system_drive = (
            storage_data.get(
                "system_drive"
            )
            or {}
        )

    elif isinstance(
        storage_data,
        list
    ):

        storage_devices = storage_data
        volumes = []
        system_drive = {}

    else:

        storage_devices = []
        volumes = []
        system_drive = {}


    if not storage_devices:

        print(
            "No physical storage device information available."
        )

    else:

        for index, device in enumerate(
            storage_devices,
            start=1
        ):

            if not isinstance(
                device,
                dict
            ):

                print(
                    f"\nStorage Device #{index}"
                )

                print(
                    "-" * 50
                )

                print(
                    f"Name       : {device}"
                )

                continue

            print(
                f"\nStorage Device #{index}"
            )

            print(
                "-" * 50
            )

            name = get_storage_value(
                device,
                "name",
                "Name",
                "FriendlyName",
                default="Unknown Storage Device"
            )

            media_type = get_storage_value(
                device,
                "media_type",
                "MediaType",
                default="N/A"
            )

            size_gb = get_storage_value(
                device,
                "size_gb",
                "SizeGB",
                default=None
            )

            if size_gb is None:

                raw_size = get_storage_value(
                    device,
                    "Size",
                    "size",
                    default=None
                )

                if isinstance(
                    raw_size,
                    (int, float)
                ):

                    size_gb = (
                        raw_size / (1024 ** 3)
                    )

            if size_gb is not None:

                try:

                    size_text = (
                        f"{float(size_gb):.2f} GB"
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    size_text = str(
                        size_gb
                    )

            else:

                size_text = "N/A"


            health = get_storage_value(
                device,
                "health_status",
                "HealthStatus",
                "health",
                default="N/A"
            )

            operational = get_storage_value(
                device,
                "operational_status",
                "OperationalStatus",
                "operational",
                default="N/A"
            )

            bus_type = get_storage_value(
                device,
                "bus_type",
                "BusType",
                default="N/A"
            )

            firmware = get_storage_value(
                device,
                "firmware",
                "Firmware",
                "FirmwareVersion",
                default="N/A"
            )

            status = get_storage_value(
                device,
                "status",
                "Status",
                default="UNKNOWN"
            )


            print(
                f"Name       : "
                f"{name}"
            )

            print(
                f"Media Type : "
                f"{media_type}"
            )

            print(
                f"Size       : "
                f"{size_text}"
            )

            print(
                f"Health     : "
                f"{health}"
            )

            print(
                f"Operational: "
                f"{operational}"
            )

            print(
                f"Bus Type   : "
                f"{bus_type}"
            )

            print(
                f"Firmware   : "
                f"{firmware}"
            )

            print(
                f"Status     : "
                f"{status}"
            )


            status_upper = str(
                status
            ).upper()


            if status_upper == "NORMAL":

                print(
                    "Verdict    : "
                    "No storage fault detected."
                )

            elif status_upper == "WARNING":

                print(
                    "Verdict    : "
                    "Storage health warning detected."
                )

                print(
                    "Recommendation: "
                    "Back up important files and "
                    "consider professional inspection."
                )

            elif status_upper in (
                "CRITICAL",
                "FAILED",
                "UNHEALTHY"
            ):

                print(
                    "Verdict    : "
                    "Potential storage fault detected."
                )

            else:

                print(
                    "Verdict    : "
                    "Storage health status is "
                    f"{status}."
                )


    # --------------------------------------------------------
    # Volume information
    # --------------------------------------------------------

    if volumes:

        print(
            "\nVolumes:"
        )

        for volume in volumes:

            if not isinstance(
                volume,
                dict
            ):
                continue

            drive = get_storage_value(
                volume,
                "drive",
                "DriveLetter",
                "drive_letter",
                default="N/A"
            )

            label = get_storage_value(
                volume,
                "label",
                "FileSystemLabel",
                default=""
            )

            filesystem = get_storage_value(
                volume,
                "filesystem",
                "FileSystem",
                default="N/A"
            )

            free_percent = get_storage_value(
                volume,
                "free_percent",
                "FreePercent",
                default=None
            )

            free_gb = get_storage_value(
                volume,
                "free_gb",
                "FreeGB",
                default=None
            )

            volume_health = get_storage_value(
                volume,
                "health",
                "HealthStatus",
                default="N/A"
            )

            print(
                f"  {drive}: "
                f"Label={label or 'N/A'}, "
                f"FileSystem={filesystem}, "
                f"Free={format_optional(free_gb, ' GB')}, "
                f"Free%={format_optional(free_percent, '%')}, "
                f"Health={volume_health}"
            )


    # --------------------------------------------------------
    # System drive summary
    # --------------------------------------------------------

    if isinstance(
        system_drive,
        dict
    ) and system_drive:

        drive = get_storage_value(
            system_drive,
            "drive",
            "DriveLetter",
            "drive_letter",
            default="N/A"
        )

        free_percent = get_storage_value(
            system_drive,
            "free_percent",
            "FreePercent",
            default=None
        )

        free_gb = get_storage_value(
            system_drive,
            "free_gb",
            "FreeGB",
            default=None
        )

        system_status = get_storage_value(
            system_drive,
            "status",
            "Status",
            default="UNKNOWN"
        )

        print(
            "\nSystem Drive:"
        )

        print(
            f"  Drive      : {drive}"
        )

        print(
            f"  Free Space : {format_optional(free_gb, ' GB')}"
        )

        print(
            f"  Free %     : {format_optional(free_percent, '%')}"
        )

        print(
            f"  Status     : {system_status}"
        )

    # ========================================================
    # STEP 8
    # BATTERY DIAGNOSTICS
    # ========================================================

    print_section(
        "BATTERY DIAGNOSTICS"
    )

    try:

        battery = diagnose_battery()

    except Exception as exc:

        battery = {
            "available": False,
            "error": str(exc)
        }

        print(
            f"Battery diagnostics unavailable: {exc}"
        )

    print_battery_report(
        battery
    )


    # ========================================================
    # STEP 9
    # DRIVER DIAGNOSTICS
    # ========================================================

    print_section(
        "DRIVER DIAGNOSTICS"
    )

    try:

        driver_diagnostics = (
            diagnose_drivers()
        )

    except Exception as exc:

        driver_diagnostics = {
            "available": False,
            "devices": [],
            "summary": {},
            "error": str(exc)
        }

        print(
            f"Driver diagnostics unavailable: {exc}"
        )

    print_driver_report(
        driver_diagnostics
    )


    # ========================================================
    # STEP 10

    # ========================================================
    # STEP 10
    # NETWORK DIAGNOSTICS
    # ========================================================

    print_section(
        "NETWORK DIAGNOSTICS"
    )

    try:

        network = diagnose_network()

    except Exception as exc:

        network = {}

        print(
            f"Network diagnostics unavailable: {exc}"
        )

    if network:

        print_network_report(
            network
        )

    else:

        print(
            "Network diagnostics returned no data."
        )


    # ========================================================
    # STEP 11
    # WINDOWS HEALTH DIAGNOSTICS
    # ========================================================

    print_section(
        "WINDOWS HEALTH DIAGNOSTICS"
    )

    try:

        windows_health = diagnose_windows_health()

    except Exception as exc:

        windows_health = {}

        print(
            f"Windows health diagnostics unavailable: {exc}"
        )

    if windows_health:

        print_windows_health_report(
            windows_health
        )

    else:

        print(
            "Windows health diagnostics returned no data."
        )


    # ========================================================
    # STEP 12
    # STARTUP DIAGNOSTICS
    # ========================================================

    print_section(
        "STARTUP DIAGNOSTICS"
    )

    try:

        startup = diagnose_startup()

    except Exception as exc:

        startup = {
            "available": False,
            "startup_apps": [],
            "startup_tasks": [],
            "startup_app_count": 0,
            "startup_task_count": 0,
            "status": "UNKNOWN",
            "severity": "UNKNOWN",
            "error": str(exc)
        }

        print(
            f"Startup diagnostics unavailable: {exc}"
        )

    print_startup_report(
        startup
    )


    # ========================================================
    # STEP 13
    # FIXMATE DIAGNOSIS ENGINE
    # ========================================================

    print_section(
        "FIXMATE DIAGNOSIS ENGINE"
    )


    # --------------------------------------------------------
    # STEP 12.1
    # DETECT FAULTS
    # --------------------------------------------------------

    try:

        faults = analyze_faults(

            diagnostics=diagnostics,

            gpu=gpu,

            thermal=thermal,

            storage=storage_data,

            processes=top_memory,

            battery=battery,

            driver_diagnostics=driver_diagnostics,

            windows_health=windows_health,

            network=network,

            startup=startup
        )

    except Exception as exc:

        faults = []

        print(
            f"\nFault analysis failed: {exc}"
        )


    # --------------------------------------------------------
    # STEP 12.2
    # CALCULATE OVERALL SEVERITY
    # --------------------------------------------------------

    try:

        severity_result = (
            calculate_overall_severity(
                faults
            )
        )

    except Exception as exc:

        severity_result = {

            "overall_severity": "UNKNOWN",

            "fault_count": len(
                faults
            ),

            "message":
                f"Severity calculation failed: {exc}"
        }


    # --------------------------------------------------------
    # STEP 12.3
    # GENERATE RECOMMENDATIONS
    # --------------------------------------------------------

    try:

        recommendations = (
            generate_recommendations(
                faults
            )
        )

    except Exception as exc:

        recommendations = []

        print(
            f"\nRecommendation generation failed: {exc}"
        )


    # --------------------------------------------------------
    # STEP 12.4
    # GENERATE FINAL REPORT
    # --------------------------------------------------------

    try:

        diagnosis_report = (
            generate_diagnosis_report(
                faults,
                severity_result,
                recommendations
            )
        )

    except Exception as exc:

        diagnosis_report = {

            "overall_severity":
                severity_result.get(
                    "overall_severity",
                    "UNKNOWN"
                ),

            "fault_count":
                len(faults),

            "assessment":
                f"Report generation failed: {exc}",

            "faults":
                faults,

            "recommendations":
                recommendations
        }


    # --------------------------------------------------------
    # STEP 12.5
    # PRINT FINAL REPORT
    # --------------------------------------------------------

    try:

        print_diagnosis_report(
            diagnosis_report
        )

    except Exception as exc:

        print(
            "\nDiagnosis report printing failed:"
        )

        print(
            exc
        )

    # --------------------------------------------------------
    # HTML REPORT
    # --------------------------------------------------------

    try:

        reports_dir = (
            Path(PROJECT_ROOT)
            / "reports"
        )

        reports_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        html_report_path = (
            reports_dir
            / "FixMate_Diagnostic_Report.html"
        )

        from datetime import datetime

        # ----------------------------------------------------
        # Build friendly live status values for Report UI V2.
        # ----------------------------------------------------

        cpu_status = str(
            diagnostics.get(
                "cpu",
                {}
            ).get(
                "status",
                "UNKNOWN"
            )
        ).upper()

        memory_status = str(
            diagnostics.get(
                "memory",
                {}
            ).get(
                "status",
                "UNKNOWN"
            )
        ).upper()

        if gpu.get(
            "available",
            False
        ):

            gpu_status = str(
                gpu.get(
                    "temperature_status",
                    "UNKNOWN"
                )
            ).upper()

        else:

            gpu_status = "UNAVAILABLE"

        # Storage status is derived from the physical-device
        # statuses already collected.
        storage_statuses = []

        for device in storage_devices:

            if not isinstance(
                device,
                dict
            ):
                continue

            storage_statuses.append(
                str(
                    device.get(
                        "status",
                        device.get(
                            "Status",
                            "UNKNOWN"
                        )
                    )
                ).upper()
            )

        if storage_statuses and all(
            item == "NORMAL"
            for item in storage_statuses
        ):

            storage_status = "NORMAL"

        elif any(
            item in (
                "CRITICAL",
                "FAILED",
                "UNHEALTHY"
            )
            for item in storage_statuses
        ):

            storage_status = "CRITICAL"

        elif any(
            item == "WARNING"
            for item in storage_statuses
        ):

            storage_status = "WARNING"

        else:

            storage_status = "UNKNOWN"

        # Battery.
        battery_status = str(
            battery.get(
                "health_status",
                "UNKNOWN"
            )
        ).upper()

        # Driver status.
        if driver_diagnostics.get(
            "available",
            False
        ):

            driver_summary = driver_diagnostics.get(
                "summary",
                {}
            )

            driver_high = int(
                driver_summary.get(
                    "high",
                    0
                )
                or 0
            )

            driver_moderate = int(
                driver_summary.get(
                    "moderate",
                    0
                )
                or 0
            )

            if driver_high > 0:

                driver_status = (
                    f"{driver_high} High Problems"
                )

            elif driver_moderate > 0:

                driver_status = (
                    f"{driver_moderate} Moderate Warnings"
                )

            else:

                driver_status = "Normal"

        else:

            driver_status = "Unavailable"

        # Network.
        if network:

            local_network = network.get(
                "local_network",
                {}
            )

            internet = network.get(
                "internet_connectivity",
                {}
            )

            dns = network.get(
                "dns",
                {}
            )

            network_statuses = [
                str(
                    local_network.get(
                        "status",
                        "UNKNOWN"
                    )
                ).upper(),

                str(
                    internet.get(
                        "status",
                        "UNKNOWN"
                    )
                ).upper(),

                str(
                    dns.get(
                        "status",
                        "UNKNOWN"
                    )
                ).upper()
            ]

            if all(
                item == "HEALTHY"
                for item in network_statuses
            ):

                network_status = "Normal"

            elif any(
                item == "PROBLEM"
                for item in network_statuses
            ):

                network_status = "Problem"

            elif any(
                item in (
                    "WARNING",
                    "DEGRADED"
                )
                for item in network_statuses
            ):

                network_status = "Warning"

            else:

                network_status = "Unknown"

        else:

            network_status = "Unavailable"

        # Windows.
        if windows_health.get(
            "available",
            False
        ):

            windows_status = str(
                windows_health.get(
                    "overall_status",
                    "UNKNOWN"
                )
            ).upper()

            windows_severity = str(
                windows_health.get(
                    "overall_severity",
                    "UNKNOWN"
                )
            ).upper()

            windows_status_display = (
                f"{windows_status.title()} "
                f"({windows_severity.title()})"
            )

        else:

            windows_status_display = "Unavailable"

        # Startup.
        if startup.get(
            "available",
            False
        ):

            startup_status_value = str(
                startup.get(
                    "status",
                    "UNKNOWN"
                )
            ).upper()

            startup_severity_value = str(
                startup.get(
                    "severity",
                    "UNKNOWN"
                )
            ).upper()

            startup_status_display = (
                f"{startup_status_value.title()} "
                f"({startup_severity_value.title()})"
            )

        else:

            startup_status_display = "Unavailable"

        status_overview = {
            "cpu":
                cpu_status.title(),

            "memory":
                memory_status.title(),

            "gpu":
                gpu_status.title(),

            "storage":
                storage_status.title(),

            "battery":
                battery_status.title(),

            "drivers":
                driver_status,

            "network":
                network_status,

            "windows":
                windows_status_display,

            "startup":
                startup_status_display,
        }

        save_html_report(
            report=diagnosis_report,
            output_path=html_report_path,
            system=system,
            scan_metadata={
                "generated_at":
                    datetime.now()
                    .astimezone()
                    .strftime(
                        "%Y-%m-%d %H:%M:%S %Z"
                    )
            },
            status_overview=status_overview
        )

        print(
            "\nHTML Report:"
        )

        print(
            f"Report saved to: {html_report_path}"
        )

    except Exception as exc:

        print(
            "\nHTML report generation failed:"
        )

        print(
            exc
        )


    # ========================================================
    # STEP 14
    # SCAN SUMMARY
    # ========================================================

    print_section(
        "SCAN SUMMARY"
    )


    memory_info = diagnostics.get(
        "memory",
        {}
    )

    cpu_info = diagnostics.get(
        "cpu",
        {}
    )


    memory_status = memory_info.get(
        "status",
        "UNKNOWN"
    )

    cpu_status = cpu_info.get(
        "status",
        "UNKNOWN"
    )


    print(
        f"CPU Status    : "
        f"{cpu_status}"
    )

    print(
        f"Memory Status : "
        f"{memory_status}"
    )


    # --------------------------------------------------------
    # GPU SUMMARY
    # --------------------------------------------------------

    if gpu.get(
        "available",
        False
    ):

        print(
            f"GPU Status    : "
            f"{gpu.get('temperature_status', 'UNKNOWN')}"
        )

    else:

        print(
            "GPU Status    : "
            "Telemetry unavailable"
        )


    # --------------------------------------------------------
    # THERMAL SUMMARY
    # --------------------------------------------------------

    if thermal:

        if isinstance(
            thermal,
            dict
        ):

            thermal_items = [
                thermal
            ]

        else:

            thermal_items = thermal


        thermal_statuses = []

        for item in thermal_items:

            if isinstance(
                item,
                dict
            ):

                thermal_statuses.append(
                    str(
                        item.get(
                            "status",
                            "UNKNOWN"
                        )
                    )
                )


        if thermal_statuses:

            print(
                f"Thermal Status: "
                f"{', '.join(thermal_statuses)}"
            )

        else:

            print(
                "Thermal Status: "
                "Sensor unavailable"
            )

    else:

        print(
            "Thermal Status: "
            "Sensor unavailable"
        )


    # --------------------------------------------------------
    # STORAGE SUMMARY
    # --------------------------------------------------------

    if storage_devices:

        storage_statuses = []

        for device in storage_devices:

            status = get_storage_value(
                device,
                "status",
                "Status",
                default="UNKNOWN"
            )

            storage_statuses.append(
                str(status)
            )


        print(
            f"Storage Status: "
            f"{', '.join(storage_statuses)}"
        )

    else:

        print(
            "Storage Status: "
            "No device detected"
        )


    # --------------------------------------------------------
    # BATTERY SUMMARY
    # --------------------------------------------------------

    if battery.get(
        "available",
        False
    ):

        battery_health = battery.get(
            "battery_health_percent"
        )

        battery_status = battery.get(
            "health_status",
            "UNKNOWN"
        )


        if battery_health is not None:

            try:

                health_text = (
                    f"{float(battery_health):.1f}%"
                )

            except (
                TypeError,
                ValueError
            ):

                health_text = str(
                    battery_health
                )


            print(
                f"Battery Status: "
                f"{battery_status} "
                f"({health_text})"
            )

        else:

            print(
                f"Battery Status: "
                f"{battery_status}"
            )

    else:

        print(
            "Battery Status: "
            "Unavailable"
        )


# --------------------------------------------------------
# WINDOWS HEALTH SUMMARY
# --------------------------------------------------------

    if windows_health.get(
        "available",
        False
    ):

        windows_status = str(
            windows_health.get(
                "overall_status",
                "UNKNOWN"
            )
        ).upper()

        windows_severity = str(
            windows_health.get(
                "overall_severity",
                "UNKNOWN"
            )
        ).upper()

        print(
            f"Windows Health: "
            f"{windows_status} "
            f"({windows_severity})"
        )

    else:

        print(
            "Windows Health: "
            "Unavailable"
        )

    # --------------------------------------------------------

        # NETWORK SUMMARY
    # --------------------------------------------------------

    if network:

        local_network = network.get(
            "local_network",
            {}
        )

        internet = network.get(
            "internet_connectivity",
            {}
        )

        dns = network.get(
            "dns",
            {}
        )

        network_statuses = [
            str(local_network.get("status", "UNKNOWN")).upper(),
            str(internet.get("status", "UNKNOWN")).upper(),
            str(dns.get("status", "UNKNOWN")).upper()
        ]

        if all(
            status == "HEALTHY"
            for status in network_statuses
        ):
            network_summary = "NORMAL"

        elif any(
            status == "PROBLEM"
            for status in network_statuses
        ):
            network_summary = "PROBLEM"

        elif any(
            status == "WARNING"
            for status in network_statuses
        ):
            network_summary = "WARNING"

        else:
            network_summary = "UNKNOWN"

        print(
            f"Network Status : "
            f"{network_summary}"
        )

    else:

        print(
            "Network Status : "
            "Unavailable"
        )


    # --------------------------------------------------------
    # STARTUP SUMMARY
    # --------------------------------------------------------

    if startup.get(
        "available",
        False
    ):

        startup_status = str(
            startup.get(
                "status",
                "UNKNOWN"
            )
        ).upper()

        startup_severity = str(
            startup.get(
                "severity",
                "UNKNOWN"
            )
        ).upper()

        startup_app_count = startup.get(
            "startup_app_count",
            len(
                startup.get(
                    "startup_apps",
                    []
                )
            )
        )

        startup_task_count = startup.get(
            "startup_task_count",
            len(
                startup.get(
                    "startup_tasks",
                    []
                )
            )
        )

        print(
            f"Startup Status : "
            f"{startup_status} "
            f"({startup_severity})"
        )

        print(
            f"Startup Entries: "
            f"{startup_app_count} app(s), "
            f"{startup_task_count} task(s)"
        )

    else:

        print(
            "Startup Status : "
            "Unavailable"
        )


    # DRIVER SUMMARY
    # --------------------------------------------------------

    if driver_diagnostics.get(
        "available",
        False
    ):

        driver_summary = (
            driver_diagnostics.get(
                "summary",
                {}
            )
        )

        driver_problem_count = (
            driver_summary.get(
                "problem_devices",
                0
            )
        )

        driver_high = (
            driver_summary.get(
                "high",
                0
            )
        )

        driver_moderate = (
            driver_summary.get(
                "moderate",
                0
            )
        )


        if driver_high > 0:

            driver_status = (
                f"{driver_high} HIGH "
                f"problem(s)"
            )

        elif driver_moderate > 0:

            driver_status = (
                f"{driver_moderate} MODERATE "
                f"warning(s)"
            )

        elif driver_problem_count > 0:

            driver_status = (
                f"{driver_problem_count} "
                f"problem device(s)"
            )

        else:

            driver_status = "NORMAL"


        print(
            f"Driver Status : "
            f"{driver_status}"
        )

    else:

        print(
            "Driver Status : "
            "Unavailable"
        )


    # ========================================================
    # STEP 14
    # GENERAL WARNINGS
    # ========================================================

    if memory_status == "CRITICAL":

        print(
            "\n🔴 Critical memory pressure detected."
        )

    elif memory_status == "HIGH":

        print(
            "\n🟠 High memory usage detected."
        )

    elif memory_status == "MODERATE":

        print(
            "\n🟡 Moderate memory usage detected."
        )

    else:

        print(
            "\n🟢 CPU and memory usage are normal."
        )


    # --------------------------------------------------------
    # GPU WARNING
    # --------------------------------------------------------

    if gpu.get(
        "available",
        False
    ):

        gpu_temp_status = str(
            gpu.get(
                "temperature_status",
                "UNKNOWN"
            )
        ).upper()


        if gpu_temp_status == "CRITICAL":

            print(
                "🔴 GPU temperature is critically high."
            )

        elif gpu_temp_status == "HIGH":

            print(
                "🟠 GPU temperature is high."
            )

        elif gpu_temp_status in (
            "WARM",
            "ELEVATED"
        ):

            print(
                "🟡 GPU temperature is elevated."
            )

        else:

            print(
                "🟢 GPU temperature is normal."
            )


    # --------------------------------------------------------
    # STORAGE WARNING
    # --------------------------------------------------------

    warning_storage = []

    for device in storage_devices:

        status = str(
            get_storage_value(
                device,
                "status",
                "Status",
                default="UNKNOWN"
            )
        ).upper()

        if status in (
            "WARNING",
            "CRITICAL",
            "FAILED",
            "UNHEALTHY"
        ):

            warning_storage.append(
                device
            )


    if warning_storage:

        print(
            "🔴 Storage health warning detected."
        )

    elif storage_devices:

        print(
            "🟢 Storage health appears normal."
        )


    # --------------------------------------------------------

    # --------------------------------------------------------
    # WINDOWS HEALTH WARNING
    # --------------------------------------------------------

    if windows_health.get(
        "available",
        False
    ):

        windows_severity = str(
            windows_health.get(
                "overall_severity",
                "UNKNOWN"
            )
        ).upper()

        if windows_severity == "CRITICAL":

            print(
                "🔴 Critical Windows health issue detected."
            )

        elif windows_severity == "HIGH":

            print(
                "🔴 Significant Windows health issue detected."
            )

        elif windows_severity == "MODERATE":

            print(
                "🟡 Moderate Windows health issue detected."
            )

        elif windows_severity == "LOW":

            print(
                "🟡 Minor Windows health/configuration warning detected."
            )

        else:

            print(
                "🟢 Windows health appears normal."
            )


    # --------------------------------------------------------
    # NETWORK WARNING
    # --------------------------------------------------------

    if network:

        local_network = network.get(
            "local_network",
            {}
        )

        internet = network.get(
            "internet_connectivity",
            {}
        )

        dns = network.get(
            "dns",
            {}
        )

        network_statuses = [
            str(local_network.get("status", "UNKNOWN")).upper(),
            str(internet.get("status", "UNKNOWN")).upper(),
            str(dns.get("status", "UNKNOWN")).upper()
        ]

        if any(
            status == "PROBLEM"
            for status in network_statuses
        ):

            print(
                "🔴 Network connectivity/configuration problem detected."
            )

        elif any(
            status == "WARNING"
            for status in network_statuses
        ):

            print(
                "🟡 Network connectivity warning detected."
            )

        elif all(
            status == "HEALTHY"
            for status in network_statuses
        ):

            print(
                "🟢 Network connectivity is normal."
            )

        else:

            print(
                "🟡 Network status could not be fully determined."
            )


    # DRIVER WARNING
    # --------------------------------------------------------

    if driver_diagnostics.get(
        "available",
        False
    ):

        driver_summary = (
            driver_diagnostics.get(
                "summary",
                {}
            )
        )

        driver_high = (
            driver_summary.get(
                "high",
                0
            )
        )

        driver_moderate = (
            driver_summary.get(
                "moderate",
                0
            )
        )


        if driver_high > 0:

            print(
                f"🔴 {driver_high} "
                f"driver/device problem(s) detected."
            )

        elif driver_moderate > 0:

            print(
                f"🟡 {driver_moderate} "
                f"driver/device warning(s) detected."
            )

        else:

            print(
                "🟢 Driver/device status appears normal."
            )


    # ========================================================
    # BATTERY WARNING
    # ========================================================

    if battery.get(
        "available",
        False
    ):

        battery_health = safe_number(
            battery.get(
                "battery_health_percent"
            ),
            -1
        )

        battery_charge = safe_number(
            battery.get(
                "charge_percent"
            ),
            -1
        )


        if 0 <= battery_health < 50:

            print(
                "🔴 Severe battery degradation detected."
            )

        elif 50 <= battery_health < 70:

            print(
                "🟠 Significant battery degradation detected."
            )

        elif 70 <= battery_health < 85:

            print(
                "🟡 Moderate battery degradation detected."
            )

        elif 0 <= battery_charge <= 10:

            print(
                "🟡 Battery charge is critically low."
            )

        else:

            print(
                "🟢 Battery health appears normal."
            )


    # ========================================================
    # STEP 15
    # IMPORTANT MESSAGE
    # ========================================================

    print(
        "\nIMPORTANT:"
    )

    print(
        "A warning does not automatically mean "
        "hardware failure."
    )

    print(
        "FixMate requires multiple diagnostic signals "
        "before recommending hardware repair."
    )


    # ========================================================
    # END
    # ========================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "              SCAN COMPLETE"
    )

    print(
        "=" * 60
    )

    # Return the complete structured result used by the desktop UI,
    # History/Reports, and optional FixMate AI analysis.
    return {
        "system": system,
        "hardware": hardware,
        "diagnostics": diagnostics,
        "top_cpu": top_cpu,
        "top_memory": top_memory,
        "gpu": gpu,
        "thermal": thermal,
        "storage": storage_data,
        "battery": battery,
        "drivers": driver_diagnostics,
        "network": network,
        "windows_health": windows_health,
        "startup": startup,
        "faults": faults,
        "severity": severity_result,
        "recommendations": recommendations,
        "diagnosis_report": diagnosis_report,
        "html_report_path": str(html_report_path) if 'html_report_path' in locals() else "",
    }


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_full_scan()