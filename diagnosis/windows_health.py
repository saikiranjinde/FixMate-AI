# ============================================================
# FIXMATE-AI
# WINDOWS HEALTH DIAGNOSIS V1.1
# ============================================================

import re
import subprocess
import winreg


# ============================================================
# COMMAND EXECUTION
# ============================================================

def run_command(command, timeout=300):

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False
        )

        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    except subprocess.TimeoutExpired:

        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "Command timed out.",
        }

    except Exception as exc:

        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
        }


# ============================================================
# COMBINE OUTPUT
# ============================================================

def combine_output(result):

    parts = []

    stdout = result.get("stdout", "")
    stderr = result.get("stderr", "")

    if stdout:
        parts.append(stdout)

    if stderr:
        parts.append(stderr)

    return "\n".join(parts).strip()


# ============================================================
# DISM HEALTH
# ============================================================

def check_dism_health():

    result = run_command(
        [
            "DISM.exe",
            "/Online",
            "/Cleanup-Image",
            "/CheckHealth"
        ],
        timeout=180
    )

    output = combine_output(
        result
    )

    text = output.lower()

    # --------------------------------------------------------
    # IMPORTANT:
    # DISM may localize output. Therefore use several
    # recognizable English phrases plus return code.
    # --------------------------------------------------------

    if (
        "no component store corruption detected"
        in text
        or
        "component store is not corrupt"
        in text
    ):

        return {
            "available": True,
            "check": "DISM Component Store",
            "status": "HEALTHY",
            "severity": "NORMAL",
            "message": (
                "DISM reports that the Windows "
                "component store is healthy."
            ),
            "returncode":
                result["returncode"],
            "raw_output":
                output,
        }

    if (
        "component store is repairable"
        in text
        or
        "component store corruption"
        in text
    ):

        return {
            "available": True,
            "check": "DISM Component Store",
            "status": "REPAIRABLE",
            "severity": "HIGH",
            "message": (
                "DISM reports corruption or a "
                "repairable component store."
            ),
            "returncode":
                result["returncode"],
            "raw_output":
                output,
        }

    # --------------------------------------------------------
    # Successful execution with no recognized corruption
    # --------------------------------------------------------

    if result["returncode"] == 0:

        return {
            "available": True,
            "check": "DISM Component Store",
            "status": "HEALTHY",
            "severity": "NORMAL",
            "message": (
                "DISM completed successfully without "
                "reporting a component-store corruption condition."
            ),
            "returncode":
                result["returncode"],
            "raw_output":
                output,
        }

    return {
        "available": True,
        "check": "DISM Component Store",
        "status": "UNKNOWN",
        "severity": "LOW",
        "message": (
            "DISM completed but its health state "
            "could not be determined confidently."
        ),
        "returncode":
            result["returncode"],
        "raw_output":
            output,
    }


# ============================================================
# SFC
# ============================================================

def check_sfc():

    result = run_command(
        [
            "sfc.exe",
            "/verifyonly"
        ],
        timeout=300
    )

    output = combine_output(
        result
    )

    text = output.lower()

    # --------------------------------------------------------
    # Healthy
    # --------------------------------------------------------

    if (
        "did not find any integrity violations"
        in text
        or
        "windows resource protection did not find"
        in text
    ):

        return {
            "available": True,
            "check": "System File Checker",
            "status": "HEALTHY",
            "severity": "NORMAL",
            "message": (
                "SFC found no Windows system-file "
                "integrity violations."
            ),
            "returncode":
                result["returncode"],
            "raw_output":
                output,
        }

    # --------------------------------------------------------
    # Corruption
    # --------------------------------------------------------

    if (
        "found integrity violations"
        in text
        or
        "found corrupt files"
        in text
        or
        "corrupt files"
        in text
    ):

        if (
            "could not repair"
            in text
            or
            "unable to fix"
            in text
        ):

            severity = "HIGH"

            status = (
                "CORRUPTION_NOT_REPAIRED"
            )

            message = (
                "SFC detected corrupted system "
                "files that could not be repaired."
            )

        else:

            severity = "MODERATE"

            status = (
                "CORRUPTION_DETECTED"
            )

            message = (
                "SFC detected Windows system-file "
                "integrity violations."
            )

        return {
            "available": True,
            "check": "System File Checker",
            "status": status,
            "severity": severity,
            "message": message,
            "returncode":
                result["returncode"],
            "raw_output":
                output,
        }

    # --------------------------------------------------------
    # Successful execution fallback
    # --------------------------------------------------------

    if result["returncode"] == 0:

        return {
            "available": True,
            "check": "System File Checker",
            "status": "HEALTHY",
            "severity": "NORMAL",
            "message": (
                "SFC verification completed successfully "
                "without reporting a recognized integrity problem."
            ),
            "returncode":
                result["returncode"],
            "raw_output":
                output,
        }

    return {
        "available": True,
        "check": "System File Checker",
        "status": "UNKNOWN",
        "severity": "LOW",
        "message": (
            "SFC completed but its integrity state "
            "could not be determined confidently."
        ),
        "returncode":
            result["returncode"],
        "raw_output":
            output,
    }


# ============================================================
# PENDING REBOOT
# ============================================================

def check_pending_reboot():

    indicators = []

    registry_paths = [

        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"
        ),

        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
        ),

        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager"
        ),
    ]

    for root, path in registry_paths:

        try:

            key = winreg.OpenKey(
                root,
                path,
                0,
                winreg.KEY_READ
            )

            if path.endswith(
                r"Session Manager"
            ):

                try:

                    value = winreg.QueryValueEx(
                        key,
                        "PendingFileRenameOperations"
                    )

                    if value:

                        indicators.append(
                            "Pending file rename operations"
                        )

                except FileNotFoundError:
                    pass

            else:

                indicators.append(
                    path
                )

            winreg.CloseKey(
                key
            )

        except FileNotFoundError:

            continue

        except OSError:

            continue

    if indicators:

        return {

            "available": True,

            "check":
                "Pending Reboot",

            "status":
                "REBOOT_PENDING",

            "severity":
                "LOW",

            "message":
                "Windows reports that a system reboot may be required.",

            "indicators":
                indicators,
        }

    return {

        "available": True,

        "check":
            "Pending Reboot",

        "status":
            "NO_REBOOT_REQUIRED",

        "severity":
            "NORMAL",

        "message":
            "No common pending-reboot indicators were detected.",

        "indicators":
            [],
    }


# ============================================================
# WINDOWS UPDATE SERVICE
# ============================================================

def check_update_service():

    result = run_command(
        [
            "sc.exe",
            "query",
            "wuauserv"
        ],
        timeout=30
    )

    output = combine_output(
        result
    )

    match = re.search(
        r"STATE\s*:\s*(\d+)\s+([A-Z]+)",
        output,
        re.IGNORECASE
    )

    if match:

        state = match.group(
            2
        ).upper()

    else:

        state = "UNKNOWN"

    if state == "RUNNING":

        return {

            "available": True,

            "check":
                "Windows Update Service",

            "status":
                "RUNNING",

            "severity":
                "NORMAL",

            "message":
                "Windows Update service is running.",
        }

    if state == "STOPPED":

        return {

            "available": True,

            "check":
                "Windows Update Service",

            "status":
                "STOPPED",

            "severity":
                "LOW",

            "message":
                "Windows Update service is currently stopped.",
        }

    return {

        "available": True,

        "check":
            "Windows Update Service",

        "status":
            state,

        "severity":
            "LOW",

        "message":
            "Windows Update service state could not be fully interpreted.",
    }


# ============================================================
# WINDOWS HEALTH
# ============================================================

def diagnose_windows_health():

    checks = []

    try:
        checks.append(
            check_dism_health()
        )
    except Exception as exc:

        checks.append({

            "available": False,
            "check": "DISM Component Store",
            "status": "UNAVAILABLE",
            "severity": "LOW",
            "message": f"DISM check failed: {exc}",
        })


    try:
        checks.append(
            check_sfc()
        )
    except Exception as exc:

        checks.append({

            "available": False,
            "check": "System File Checker",
            "status": "UNAVAILABLE",
            "severity": "LOW",
            "message": f"SFC check failed: {exc}",
        })


    try:
        checks.append(
            check_pending_reboot()
        )
    except Exception as exc:

        checks.append({

            "available": False,
            "check": "Pending Reboot",
            "status": "UNKNOWN",
            "severity": "LOW",
            "message": f"Reboot check failed: {exc}",
        })


    try:
        checks.append(
            check_update_service()
        )
    except Exception as exc:

        checks.append({

            "available": False,
            "check": "Windows Update Service",
            "status": "UNKNOWN",
            "severity": "LOW",
            "message":
                f"Windows Update check failed: {exc}",
        })


    # ========================================================
    # OVERALL SEVERITY
    # ========================================================

    weights = {
        "NORMAL": 0,
        "LOW": 1,
        "MODERATE": 2,
        "HIGH": 3,
        "CRITICAL": 4,
    }

    highest_weight = 0

    for check in checks:

        severity = str(
            check.get(
                "severity",
                "NORMAL"
            )
        ).upper()

        weight = weights.get(
            severity,
            0
        )

        highest_weight = max(
            highest_weight,
            weight
        )

    if highest_weight == 0:

        overall_severity = "NORMAL"
        overall_status = "HEALTHY"

        message = (
            "Windows health checks did not "
            "detect a significant system integrity problem."
        )

    elif highest_weight == 1:

        overall_severity = "LOW"
        overall_status = "MINOR"

        message = (
            "Windows health checks detected "
            "minor system conditions that may require attention."
        )

    elif highest_weight == 2:

        overall_severity = "MODERATE"
        overall_status = "MODERATE"

        message = (
            "Windows health checks detected "
            "a moderate system issue."
        )

    elif highest_weight == 3:

        overall_severity = "HIGH"
        overall_status = "HIGH"

        message = (
            "Windows health checks detected "
            "a significant system integrity issue."
        )

    else:

        overall_severity = "CRITICAL"
        overall_status = "CRITICAL"

        message = (
            "Windows health checks detected "
            "a critical system integrity issue."
        )

    return {

        "available": True,

        "overall_status":
            overall_status,

        "overall_severity":
            overall_severity,

        "message":
            message,

        "checks":
            checks,
    }


# ============================================================
# PRINT REPORT
# ============================================================

def print_windows_health_report(
    result
):

    print("\n")
    print("=" * 70)
    print("              FIXMATE WINDOWS HEALTH")
    print("=" * 70)

    if not result.get(
        "available",
        False
    ):

        print(
            "\nWindows health diagnostics unavailable."
        )

        print(
            "=" * 70
        )

        return


    print(
        "\n[ OVERALL WINDOWS HEALTH ]"
    )

    print(
        "-" * 70
    )

    print(
        f"Status               : "
        f"{result.get('overall_status', 'UNKNOWN')}"
    )

    print(
        f"Severity             : "
        f"{result.get('overall_severity', 'UNKNOWN')}"
    )

    print(
        f"Assessment           : "
        f"{result.get('message', 'N/A')}"
    )


    print(
        "\n[ HEALTH CHECKS ]"
    )

    print(
        "-" * 70
    )


    for check in result.get(
        "checks",
        []
    ):

        print(
            f"\nCheck                : "
            f"{check.get('check', 'Unknown')}"
        )

        print(
            f"Status               : "
            f"{check.get('status', 'UNKNOWN')}"
        )

        print(
            f"Severity             : "
            f"{check.get('severity', 'UNKNOWN')}"
        )

        print(
            f"Message              : "
            f"{check.get('message', 'N/A')}"
        )

        if check.get(
            "returncode"
        ) is not None:

            print(
                f"Return Code          : "
                f"{check.get('returncode')}"
            )

        if check.get(
            "indicators"
        ):

            print(
                "Indicators           :"
            )

            for indicator in check[
                "indicators"
            ]:

                print(
                    f"  - {indicator}"
                )


    print("\n")
    print("=" * 70)
    print("           END OF WINDOWS HEALTH")
    print("=" * 70)


# ============================================================
# STANDALONE
# ============================================================

if __name__ == "__main__":

    print(
        "\n========== FIXMATE WINDOWS HEALTH V1.1 ==========\n"
    )

    result = diagnose_windows_health()

    print_windows_health_report(
        result
    )