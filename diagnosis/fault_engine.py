from typing import Any, Dict, List, Optional


# ============================================================
# FIXMATE FAULT ENGINE V7
# ============================================================
#
# V7 additions:
# - Battery diagnosis integration
# - Driver diagnosis integration
# - Windows Health diagnosis integration
# - System resource vs application issue separation
# - Hardware-fault distinction
# - Confidence
# - Assessment
# - Structured evidence, causes and recommendations
# ============================================================


# ============================================================
# FAULT CREATOR
# ============================================================

def create_fault(
    component: str,
    severity: str,
    problem: str,
    evidence: str,
    causes: Optional[List[str]] = None,
    recommendations: Optional[List[str]] = None,
    fault_type: str = "resource_pressure",
    confidence: str = "MEDIUM",
    hardware_fault: bool = False,
    assessment: str = "",
) -> Dict[str, Any]:

    return {
        "component": component,
        "severity": severity,
        "fault_type": fault_type,
        "problem": problem,
        "evidence": evidence,
        "causes": causes or [],
        "recommendations": recommendations or [],
        "confidence": confidence,
        "hardware_fault": hardware_fault,
        "assessment": assessment,
    }


# ============================================================
# SAFE CONVERSION
# ============================================================

def safe_float(value, default=0.0):

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# PROCESS HELPERS
# ============================================================

def get_top_memory_consumers(
    processes: Optional[List[Dict[str, Any]]],
    limit: int = 3
) -> List[Dict[str, Any]]:

    if not processes:
        return []

    valid = []

    for process in processes:

        if not isinstance(process, dict):
            continue

        memory_mb = safe_float(
            process.get("memory_mb", 0)
        )

        if memory_mb <= 0:
            continue

        valid.append({
            "display_name": process.get(
                "display_name",
                process.get("process_name", "Unknown")
            ),
            "memory_mb": memory_mb,
            "memory_percent": safe_float(
                process.get("memory_percent", 0)
            ),
            "process_count": process.get(
                "process_count",
                1
            ),
            "severity": str(
                process.get("severity", "NORMAL")
            ).upper(),
        })

    valid.sort(
        key=lambda item: item["memory_mb"],
        reverse=True
    )

    return valid[:limit]


# ============================================================
# SYSTEM MEMORY
# ============================================================

def analyze_memory(
    memory: Optional[Dict[str, Any]],
    processes: Optional[List[Dict[str, Any]]] = None
) -> Optional[Dict[str, Any]]:

    if not memory:
        return None

    usage = safe_float(
        memory.get("usage_percent", 0)
    )

    if usage < 70:
        return None

    contributors = get_top_memory_consumers(
        processes,
        limit=3
    )

    evidence = (
        f"System RAM usage is {usage:.1f}%."
    )

    if contributors:

        text = ", ".join(
            f"{item['display_name']} "
            f"({item['memory_mb']:.1f} MB)"
            for item in contributors
        )

        evidence += (
            f" Major memory contributors: {text}."
        )

    if usage >= 95:

        return create_fault(
            component="Memory",
            severity="CRITICAL",
            fault_type="resource_pressure",
            confidence="HIGH",
            hardware_fault=False,
            problem="Very high system memory usage detected.",
            evidence=evidence,
            causes=[
                "Multiple applications are consuming large amounts of RAM.",
                "Memory-heavy applications may be active.",
                "Background processes may be consuming available memory.",
            ],
            recommendations=[
                "Close unnecessary applications immediately.",
                "Check the top memory-consuming applications.",
                "Reduce unnecessary browser tabs and background applications.",
                "Consider additional RAM if this condition occurs frequently.",
            ],
            assessment=(
                "System-wide memory pressure is significant. "
                "This indicates resource pressure, not direct proof "
                "of a defective RAM module."
            ),
        )

    if usage >= 85:

        return create_fault(
            component="Memory",
            severity="HIGH",
            fault_type="resource_pressure",
            confidence="HIGH",
            hardware_fault=False,
            problem="High system memory usage detected.",
            evidence=evidence,
            causes=[
                "Memory-heavy applications may be active.",
                "Several applications may be running simultaneously.",
                "Background processes may be consuming RAM.",
            ],
            recommendations=[
                "Check applications using the most RAM.",
                "Close applications that are not required.",
                "Reduce unnecessary browser tabs.",
                "Monitor RAM usage for repeated high usage.",
            ],
            assessment=(
                "System memory pressure is high. "
                "No hardware fault is confirmed by memory usage alone."
            ),
        )

    return create_fault(
        component="Memory",
        severity="MODERATE",
        fault_type="resource_pressure",
        confidence="MEDIUM",
        hardware_fault=False,
        problem="Moderate system memory pressure detected.",
        evidence=evidence,
        causes=[
            "Several applications are running.",
            "Memory-heavy applications may be active.",
            "Background processes are using available RAM.",
        ],
        recommendations=[
            "Check applications using the most RAM.",
            "Close applications that are not required.",
            "Reduce unnecessary browser tabs or background applications.",
            "Monitor memory usage if system slowdown occurs.",
        ],
        assessment=(
            "Moderate memory pressure is present, but this does "
            "not indicate a confirmed RAM hardware fault."
        ),
    )


# ============================================================
# APPLICATION MEMORY
# ============================================================

def analyze_application_memory(
    processes: Optional[List[Dict[str, Any]]],
    system_memory: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:

    faults = []

    if not processes:
        return faults

    system_ram_usage = safe_float(
        (system_memory or {}).get(
            "usage_percent",
            0
        )
    )

    for process in processes:

        if not isinstance(process, dict):
            continue

        display_name = process.get(
            "display_name",
            process.get(
                "process_name",
                "Unknown"
            )
        )

        memory_mb = safe_float(
            process.get(
                "memory_mb",
                0
            )
        )

        memory_percent = safe_float(
            process.get(
                "memory_percent",
                0
            )
        )

        process_count = process.get(
            "process_count",
            1
        )

        process_severity = str(
            process.get(
                "severity",
                "NORMAL"
            )
        ).upper()

        if process_severity == "SYSTEM":
            continue

        if process_severity == "CRITICAL":
            issue_severity = "HIGH"

        elif process_severity == "HIGH":
            issue_severity = "LOW"

        else:
            continue

        causes = []

        if process_count >= 10:
            causes.append(
                "Multiple application processes are active."
            )

        if memory_percent >= 15:
            causes.append(
                "The application is consuming a significant "
                "share of system memory."
            )

        if memory_percent >= 10:
            causes.append(
                "The application may have a large workspace, "
                "project, cache, or background service load."
            )

        if not causes:
            causes.append(
                "The application is using comparatively high memory."
            )

        if memory_percent >= 15 and process_count >= 10:
            confidence = "HIGH"

        elif memory_percent >= 10:
            confidence = "MEDIUM"

        else:
            confidence = "LOW"

        if system_ram_usage < 70:

            assessment = (
                f"{display_name} has high application-level "
                f"memory consumption, but the system as a whole "
                f"is not currently under memory pressure. "
                f"No hardware fault is indicated."
            )

        elif system_ram_usage < 85:

            assessment = (
                f"{display_name} is contributing to overall "
                f"memory pressure. The current evidence points "
                f"toward application resource usage rather than "
                f"a confirmed hardware fault."
            )

        else:

            assessment = (
                f"{display_name} is contributing to significant "
                f"system-wide memory pressure. Application resource "
                f"usage is a likely contributor."
            )

        evidence = (
            f"{display_name} is using "
            f"{memory_mb:.1f} MB of RAM "
            f"({memory_percent:.1f}% of system memory) "
            f"across {process_count} process(es). "
            f"Overall system RAM usage is "
            f"{system_ram_usage:.1f}%."
        )

        faults.append(
            create_fault(
                component=f"Application: {display_name}",
                severity=issue_severity,
                fault_type="application_resource_usage",
                confidence=confidence,
                hardware_fault=False,
                problem=(
                    "Application is consuming a high amount "
                    "of system memory."
                ),
                evidence=evidence,
                causes=causes,
                recommendations=[
                    f"Close unused {display_name} windows or sessions.",
                    f"Review unnecessary extensions or plugins used by {display_name}.",
                    f"Restart {display_name} if memory usage continues to grow.",
                    "Monitor memory usage after optimization.",
                ],
                assessment=assessment,
            )
        )

    return faults


# ============================================================
# CPU
# ============================================================

def analyze_cpu(
    cpu: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:

    if not cpu:
        return None

    usage = safe_float(
        cpu.get("usage_percent", 0)
    )

    if usage >= 95:

        return create_fault(
            component="CPU",
            severity="HIGH",
            fault_type="resource_pressure",
            confidence="HIGH",
            hardware_fault=False,
            problem="Very high CPU usage detected.",
            evidence=f"CPU usage is {usage:.1f}%.",
            causes=[
                "A CPU-intensive application may be running.",
                "Background processes may be consuming CPU resources.",
            ],
            recommendations=[
                "Check top CPU-consuming applications.",
                "Close unnecessary CPU-intensive applications.",
                "Monitor CPU usage for repeated spikes.",
            ],
            assessment=(
                "High CPU utilization has been detected. "
                "This alone does not confirm a CPU hardware fault."
            ),
        )

    if usage >= 80:

        return create_fault(
            component="CPU",
            severity="MODERATE",
            fault_type="resource_pressure",
            confidence="HIGH",
            hardware_fault=False,
            problem="High CPU usage detected.",
            evidence=f"CPU usage is {usage:.1f}%.",
            causes=[
                "One or more applications may be under heavy load.",
                "Background processes may be active.",
            ],
            recommendations=[
                "Check top CPU-consuming applications.",
                "Close unnecessary applications.",
                "Monitor CPU usage if performance problems continue.",
            ],
            assessment=(
                "CPU resource usage is elevated, but there is "
                "no direct evidence of a CPU hardware fault."
            ),
        )

    return None


# ============================================================
# GPU
# ============================================================

def analyze_gpu(
    gpu: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:

    if not gpu:
        return None

    temperature = gpu.get(
        "temperature_c"
    )

    if temperature is None:
        return None

    temperature = safe_float(
        temperature,
        -1
    )

    if temperature < 0:
        return None

    if temperature >= 90:

        return create_fault(
            component="GPU",
            severity="CRITICAL",
            fault_type="thermal",
            confidence="HIGH",
            hardware_fault=False,
            problem="GPU temperature is critically high.",
            evidence=(
                f"GPU temperature is "
                f"{temperature:.1f} °C."
            ),
            causes=[
                "Heavy GPU workload may be active.",
                "Cooling or airflow may be insufficient.",
                "Dust buildup or thermal issues may contribute.",
            ],
            recommendations=[
                "Stop heavy GPU workloads temporarily.",
                "Check cooling and ventilation.",
                "Inspect fans and airflow.",
                "Monitor GPU temperature under load.",
            ],
            assessment=(
                "Critical GPU thermal conditions are detected. "
                "This does not by itself prove a permanent GPU hardware defect."
            ),
        )

    if temperature >= 80:

        return create_fault(
            component="GPU",
            severity="HIGH",
            fault_type="thermal",
            confidence="HIGH",
            hardware_fault=False,
            problem="GPU temperature is high.",
            evidence=(
                f"GPU temperature is "
                f"{temperature:.1f} °C."
            ),
            causes=[
                "Heavy GPU workload may be active.",
                "Cooling may be insufficient.",
            ],
            recommendations=[
                "Check GPU workload.",
                "Improve airflow and cooling.",
                "Monitor GPU temperature during heavy workloads.",
            ],
            assessment=(
                "GPU temperature is elevated and should be monitored."
            ),
        )

    if temperature >= 70:

        return create_fault(
            component="GPU",
            severity="MODERATE",
            fault_type="thermal",
            confidence="MEDIUM",
            hardware_fault=False,
            problem="GPU temperature is elevated.",
            evidence=(
                f"GPU temperature is "
                f"{temperature:.1f} °C."
            ),
            causes=[
                "GPU may be under moderate or heavy load.",
            ],
            recommendations=[
                "Monitor GPU temperature.",
                "Check cooling if elevated temperatures persist.",
            ],
            assessment=(
                "GPU temperature is somewhat elevated, "
                "but no hardware fault is confirmed."
            ),
        )

    return None


# ============================================================
# STORAGE
# ============================================================

def analyze_storage(
    storage_devices: Optional[List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:

    faults = []

    if not storage_devices:
        return faults

    for disk in storage_devices:

        if not isinstance(disk, dict):
            continue

        health = str(
            disk.get(
                "HealthStatus",
                disk.get(
                    "health_status",
                    disk.get("health", "")
                )
            )
        ).lower()

        operational = str(
            disk.get(
                "OperationalStatus",
                disk.get(
                    "operational_status",
                    disk.get("operational", "")
                )
            )
        ).lower()

        name = disk.get(
            "FriendlyName",
            disk.get(
                "name",
                "Unknown Storage Device"
            )
        )

        if (
            health in (
                "warning",
                "degraded",
                "unhealthy",
                "failed"
            )
            or operational in (
                "failed",
                "offline"
            )
        ):

            faults.append(
                create_fault(
                    component="Storage",
                    severity="HIGH",
                    fault_type="hardware_fault",
                    confidence="HIGH",
                    hardware_fault=True,
                    problem="Storage health problem detected.",
                    evidence=(
                        f"{name}: "
                        f"Health={health or 'Unknown'}, "
                        f"Operational={operational or 'Unknown'}."
                    ),
                    causes=[
                        "The storage device may be experiencing a hardware or communication problem.",
                        "Drive health information indicates an abnormal state.",
                    ],
                    recommendations=[
                        "Back up important data immediately.",
                        "Check storage health using manufacturer diagnostics.",
                        "Inspect drive connections and firmware.",
                    ],
                    assessment=(
                        "The storage health data indicates a potential "
                        "hardware or device-level problem."
                    ),
                )
            )

    return faults


# ============================================================
# THERMAL
# ============================================================

def analyze_thermal(
    thermal: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:

    if not thermal:
        return None

    temperature = thermal.get(
        "temperature"
    )

    if temperature is None:
        return None

    temperature = safe_float(
        temperature,
        -1
    )

    if temperature < 0:
        return None

    if temperature >= 95:

        return create_fault(
            component="CPU Thermal",
            severity="CRITICAL",
            fault_type="thermal",
            confidence="HIGH",
            hardware_fault=False,
            problem="CPU temperature is critically high.",
            evidence=(
                f"CPU temperature is "
                f"{temperature:.1f} °C."
            ),
            causes=[
                "CPU may be under heavy load.",
                "Cooling performance may be insufficient.",
                "Fan or thermal interface issues may be present.",
            ],
            recommendations=[
                "Stop heavy workloads temporarily.",
                "Check cooling fans and airflow.",
                "Inspect the cooling system.",
            ],
            assessment=(
                "Critical CPU thermal conditions are present. "
                "Further cooling diagnostics are recommended."
            ),
        )

    if temperature >= 90:

        return create_fault(
            component="CPU Thermal",
            severity="HIGH",
            fault_type="thermal",
            confidence="HIGH",
            hardware_fault=False,
            problem="CPU temperature is very high.",
            evidence=(
                f"CPU temperature is "
                f"{temperature:.1f} °C."
            ),
            causes=[
                "Heavy CPU load.",
                "Reduced cooling efficiency.",
            ],
            recommendations=[
                "Check CPU-heavy processes.",
                "Improve airflow and cooling.",
                "Monitor CPU temperature under load.",
            ],
            assessment=(
                "CPU temperature is very high and should be investigated."
            ),
        )

    if temperature >= 80:

        return create_fault(
            component="CPU Thermal",
            severity="MODERATE",
            fault_type="thermal",
            confidence="MEDIUM",
            hardware_fault=False,
            problem="CPU temperature is elevated.",
            evidence=(
                f"CPU temperature is "
                f"{temperature:.1f} °C."
            ),
            causes=[
                "CPU may be under sustained workload.",
            ],
            recommendations=[
                "Monitor CPU temperature.",
                "Check cooling if elevated temperatures persist.",
            ],
            assessment=(
                "CPU temperature is elevated, but this alone "
                "does not confirm a hardware fault."
            ),
        )

    return None


# ============================================================
# BATTERY
# ============================================================

def analyze_battery(
    battery: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    faults = []

    if not battery:
        return faults

    if not battery.get(
        "available",
        False
    ):
        return faults

    health = battery.get(
        "battery_health_percent"
    )

    health = (
        safe_float(
            health,
            -1
        )
        if health is not None
        else None
    )

    wear = battery.get(
        "wear_percent"
    )

    wear = (
        safe_float(
            wear,
            -1
        )
        if wear is not None
        else None
    )

    health_status = str(
        battery.get(
            "health_status",
            "UNKNOWN"
        )
    ).upper()

    confidence = str(
        battery.get(
            "confidence",
            "LOW"
        )
    ).upper()

    if (
        health is not None
        and health >= 0
        and health < 50
    ):

        faults.append(
            create_fault(
                component="Battery",
                severity="HIGH",
                fault_type="hardware_fault",
                confidence=confidence,
                hardware_fault=True,
                problem=(
                    "Battery capacity is severely degraded."
                ),
                evidence=(
                    f"Battery health is {health:.1f}%. "
                    f"Wear level is "
                    f"{wear:.1f}%."
                    if wear is not None
                    else
                    f"Battery health is {health:.1f}%."
                ),
                causes=[
                    "Battery capacity has significantly degraded.",
                    "The battery may be near the end of its useful service life.",
                ],
                recommendations=[
                    "Back up important data.",
                    "Confirm the condition using manufacturer diagnostics.",
                    "Consider battery replacement.",
                ],
                assessment=(
                    "Battery capacity is severely degraded and "
                    "may require replacement."
                ),
            )
        )

    elif (
        health is not None
        and health >= 50
        and health < 70
    ):

        faults.append(
            create_fault(
                component="Battery",
                severity="MODERATE",
                fault_type="battery_degradation",
                confidence=confidence,
                hardware_fault=False,
                problem=(
                    "Battery capacity has significant degradation."
                ),
                evidence=(
                    f"Battery health is {health:.1f}%. "
                    f"Wear level is "
                    f"{wear:.1f}%."
                    if wear is not None
                    else
                    f"Battery health is {health:.1f}%."
                ),
                causes=[
                    "Battery capacity has degraded over time.",
                    "A reduced battery runtime is expected.",
                ],
                recommendations=[
                    "Monitor battery runtime.",
                    "Use manufacturer diagnostics for confirmation.",
                    "Consider replacement if runtime becomes insufficient.",
                ],
                assessment=(
                    "Significant battery degradation is present, "
                    "but this is not classified as a confirmed hardware fault."
                ),
            )
        )

    elif (
        health is not None
        and health >= 70
        and health < 85
    ):

        faults.append(
            create_fault(
                component="Battery",
                severity="LOW",
                fault_type="battery_degradation",
                confidence=confidence,
                hardware_fault=False,
                problem=(
                    "Battery capacity shows moderate degradation."
                ),
                evidence=(
                    f"Battery health is {health:.1f}%. "
                    f"Wear level is "
                    f"{wear:.1f}%."
                    if wear is not None
                    else
                    f"Battery health is {health:.1f}%."
                ),
                causes=[
                    "Battery capacity has degraded from its original capacity.",
                ],
                recommendations=[
                    "Monitor battery health over time.",
                    "Avoid prolonged high-temperature operation.",
                    "Consider replacement if battery runtime becomes inadequate.",
                ],
                assessment=(
                    "Moderate battery degradation is present, "
                    "but no immediate hardware fault is indicated."
                ),
            )
        )

    charge = battery.get(
        "charge_percent"
    )

    charge = (
        safe_float(
            charge,
            -1
        )
        if charge is not None
        else None
    )

    power_state = battery.get(
        "power_state",
        "UNKNOWN"
    )

    if (
        charge is not None
        and 0 <= charge <= 10
    ):

        faults.append(
            create_fault(
                component="Battery Charge",
                severity="LOW",
                fault_type="low_charge",
                confidence="HIGH",
                hardware_fault=False,
                problem=(
                    "Battery charge level is critically low."
                ),
                evidence=(
                    f"Current battery charge is "
                    f"{charge:.0f}%. "
                    f"Power state: {power_state}."
                ),
                causes=[
                    "The laptop is operating with a low remaining charge.",
                ],
                recommendations=[
                    "Connect the AC adapter.",
                    "Save important work.",
                    "Avoid heavy workloads until sufficient charge is restored.",
                ],
                assessment=(
                    "Current battery charge is low. "
                    "This does not indicate battery hardware failure."
                ),
            )
        )

    elif (
        charge is not None
        and 10 < charge <= 20
    ):

        faults.append(
            create_fault(
                component="Battery Charge",
                severity="LOW",
                fault_type="low_charge",
                confidence="HIGH",
                hardware_fault=False,
                problem="Battery charge level is low.",
                evidence=(
                    f"Current battery charge is "
                    f"{charge:.0f}%. "
                    f"Power state: {power_state}."
                ),
                causes=[
                    "The laptop is operating with reduced remaining charge.",
                ],
                recommendations=[
                    "Connect the AC adapter when convenient.",
                    "Save important work if operating away from AC power.",
                ],
                assessment=(
                    "Battery charge is low, but battery health "
                    "does not necessarily indicate a hardware fault."
                ),
            )
        )

    return faults


# ============================================================
# DRIVER DIAGNOSIS
# ============================================================

def analyze_drivers(
    driver_diagnostics: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    faults = []

    if not driver_diagnostics:
        return faults

    if not driver_diagnostics.get(
        "available",
        False
    ):
        return faults

    devices = driver_diagnostics.get(
        "devices",
        []
    )

    for device in devices:

        if not isinstance(device, dict):
            continue

        status = str(
            device.get(
                "status",
                ""
            )
        ).upper()

        severity = str(
            device.get(
                "severity",
                "NORMAL"
            )
        ).upper()

        if severity == "NORMAL":
            continue

        name = (
            device.get("name")
            or "Unknown Device"
        )

        problem_code = device.get(
            "problem_code",
            0
        )

        occurrences = device.get(
            "occurrences",
            1
        )

        driver = device.get(
            "driver"
        ) or {}

        provider = driver.get(
            "provider"
        )

        version = driver.get(
            "version"
        )

        driver_date = driver.get(
            "driver_date"
        )

        signed = driver.get(
            "signed"
        )

        signer = driver.get(
            "signer"
        )

        if status == "DRIVER_OR_DEVICE_PROBLEM":

            fault_type = "driver_problem"
            confidence = "HIGH"
            hardware_fault = False

            problem = (
                f"Windows reports a device/driver "
                f"configuration problem for {name}."
            )

            evidence = (
                f"Windows Problem Code: {problem_code}. "
                f"Driver Provider: {provider or 'Unknown'}. "
                f"Driver Version: {version or 'Unknown'}."
            )

            causes = [
                "The device driver may have failed to initialize correctly.",
                "The device may have a configuration or compatibility problem.",
                "The connected or paired device may currently be unavailable.",
            ]

            recommendations = [
                f"Check Device Manager for {name}.",
                "Disable and re-enable the affected device.",
                "Update or reinstall the affected driver if the problem persists.",
                "Reconnect or re-pair the associated device when applicable.",
            ]

            assessment = (
                f"{name} has a Windows-reported "
                f"Problem Code {problem_code}. "
                f"This indicates a device/driver configuration "
                f"problem, but does not by itself prove a permanent "
                f"hardware failure."
            )

        elif status == "DEVICE_WARNING":

            fault_type = "driver_warning"
            confidence = "MEDIUM"
            hardware_fault = False

            problem = (
                f"Windows reports a warning/degraded state "
                f"for {name}."
            )

            evidence = (
                f"Device status: {status}. "
                f"Problem Code: {problem_code}. "
                f"Driver Provider: {provider or 'Unknown'}. "
                f"Driver Version: {version or 'Unknown'}. "
                f"Observed occurrences: {occurrences}."
            )

            causes = [
                "The device may be reporting a degraded operating state.",
                "A vendor utility or device component may be reporting a non-critical condition.",
                "The condition may be temporary or software-related.",
            ]

            recommendations = [
                f"Monitor {name} for functional problems.",
                "Check Device Manager for additional details.",
                "Update the associated driver or vendor software if problems are observed.",
            ]

            assessment = (
                f"{name} is reporting a degraded/warning "
                f"state, but there is no non-zero Windows "
                f"Problem Code confirming a device configuration failure."
            )

        elif status == "UNSIGNED_DRIVER":

            fault_type = "driver_problem"
            confidence = "HIGH"
            hardware_fault = False

            problem = (
                f"{name} is using an unsigned driver."
            )

            evidence = (
                f"Driver Provider: {provider or 'Unknown'}. "
                f"Driver Version: {version or 'Unknown'}. "
                f"Signed: {signed}."
            )

            causes = [
                "The installed driver may not have a valid digital signature.",
                "A third-party or manually installed driver may be in use.",
            ]

            recommendations = [
                "Check the driver in Device Manager.",
                "Install a properly signed driver from the device manufacturer or Windows Update.",
                "Avoid untrusted driver packages.",
            ]

            assessment = (
                f"{name} has an unsigned driver according "
                f"to Windows driver information."
            )

        else:
            continue

        if driver_date:
            evidence += (
                f" Driver Date: {driver_date}."
            )

        if signer:
            evidence += (
                f" Signer: {signer}."
            )

        faults.append(
            create_fault(
                component=f"Driver: {name}",
                severity=severity,
                fault_type=fault_type,
                confidence=confidence,
                hardware_fault=hardware_fault,
                problem=problem,
                evidence=evidence,
                causes=causes,
                recommendations=recommendations,
                assessment=assessment,
            )
        )

    return faults


# ============================================================
# WINDOWS HEALTH
# ============================================================

def analyze_windows_health(
    windows_health: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    faults = []

    if not windows_health:
        return faults

    if not windows_health.get(
        "available",
        False
    ):
        return faults

    checks = windows_health.get(
        "checks",
        []
    )

    for check in checks:

        if not isinstance(
            check,
            dict
        ):
            continue

        check_name = check.get(
            "check",
            "Windows Health"
        )

        status = str(
            check.get(
                "status",
                "UNKNOWN"
            )
        ).upper()

        severity = str(
            check.get(
                "severity",
                "NORMAL"
            )
        ).upper()

        message = check.get(
            "message",
            "Windows health condition detected."
        )

        # Healthy and unknown results are not faults.
        if severity == "NORMAL":
            continue

        if status == "UNKNOWN":
            continue

        # ----------------------------------------------------
        # DISM
        # ----------------------------------------------------

        if check_name == "DISM Component Store":

            fault_type = "windows_system_issue"
            confidence = "HIGH"
            hardware_fault = False

            problem = (
                "Windows component-store corruption "
                "or a repairable component-store condition "
                "was detected."
            )

            evidence = (
                f"DISM Status: {status}. "
                f"{message}"
            )

            causes = [
                "Windows component-store files may be corrupted.",
                "A previous update or system change may have affected Windows components.",
                "Incomplete servicing operations may have left repairable component corruption.",
            ]

            recommendations = [
                "Restart Windows if a reboot is pending.",
                "Run an elevated DISM repair after confirming the issue.",
                "Run SFC again after DISM repair.",
                "Back up important data before performing system repair operations.",
            ]

            assessment = (
                "Windows reports a component-store condition "
                "that may be repairable. This is a Windows "
                "software/system-integrity issue, not direct evidence "
                "of a hardware fault."
            )

        # ----------------------------------------------------
        # SFC
        # ----------------------------------------------------

        elif check_name == "System File Checker":

            fault_type = "windows_system_issue"
            confidence = "HIGH"
            hardware_fault = False

            problem = (
                "Windows system-file integrity problems "
                "were detected."
            )

            evidence = (
                f"SFC Status: {status}. "
                f"{message}"
            )

            causes = [
                "Windows system files may be corrupted.",
                "System changes or failed updates may have affected system files.",
            ]

            recommendations = [
                "Restart Windows if a reboot is pending.",
                "Run DISM repair if system-file corruption persists.",
                "Run SFC again after completing DISM repair.",
            ]

            assessment = (
                "System File Checker reported a Windows "
                "system-file integrity issue."
            )

        # ----------------------------------------------------
        # PENDING REBOOT
        # ----------------------------------------------------

        elif check_name == "Pending Reboot":

            fault_type = "windows_configuration"
            confidence = "HIGH"
            hardware_fault = False

            problem = (
                "Windows reports that a system reboot "
                "may be required."
            )

            indicators = check.get(
                "indicators",
                []
            )

            evidence = (
                "Windows reports a pending reboot."
            )

            if indicators:

                evidence += (
                    " Indicators: "
                    + ", ".join(
                        str(item)
                        for item in indicators
                    )
                    + "."
                )

            causes = [
                "Windows or an installed application may have pending system changes.",
                "A previous update or file operation may require a restart.",
            ]

            recommendations = [
                "Restart the computer when convenient.",
                "Run FixMate again after restarting to confirm the condition is cleared.",
            ]

            assessment = (
                "A pending reboot is a configuration condition "
                "and does not indicate hardware failure."
            )

        # ----------------------------------------------------
        # WINDOWS UPDATE SERVICE
        # ----------------------------------------------------

        elif check_name == "Windows Update Service":

            fault_type = "windows_configuration"
            confidence = "MEDIUM"
            hardware_fault = False

            problem = (
                "Windows Update service is not currently running."
            )

            evidence = (
                f"Windows Update Status: {status}. "
                f"{message}"
            )

            causes = [
                "The Windows Update service may have been stopped manually.",
                "Windows may have temporarily stopped the service.",
                "An update-management tool or configuration may control the service state.",
            ]

            recommendations = [
                "Check Windows Update settings.",
                "Start the Windows Update service if updates are required.",
                "Run FixMate again after confirming Windows Update configuration.",
            ]

            assessment = (
                "The Windows Update service is stopped, "
                "but this alone does not indicate a Windows "
                "system integrity failure or hardware fault."
            )

        else:
            continue

        faults.append(
            create_fault(
                component=f"Windows: {check_name}",
                severity=severity,
                fault_type=fault_type,
                confidence=confidence,
                hardware_fault=hardware_fault,
                problem=problem,
                evidence=evidence,
                causes=causes,
                recommendations=recommendations,
                assessment=assessment,
            )
        )

    return faults


# ============================================================
# NETWORK
# ============================================================

def analyze_network(
    network: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    faults = []

    if not network:
        return faults

    # --------------------------------------------------------
    # LOCAL NETWORK
    # --------------------------------------------------------

    local = network.get("local_network", {})

    local_status = str(
        local.get("status", "UNKNOWN")
    ).upper()

    local_severity = str(
        local.get("severity", "UNKNOWN")
    ).upper()

    if local_status in ("PROBLEM", "WARNING"):

        severity = local_severity

        if severity not in (
            "LOW", "MODERATE", "HIGH", "CRITICAL"
        ):
            severity = "MODERATE"

        faults.append(
            create_fault(
                component="Network",
                severity=severity,
                fault_type="network_configuration",
                confidence="HIGH",
                hardware_fault=False,
                problem="Local network configuration problem detected.",
                evidence=local.get(
                    "message",
                    "Local network configuration is abnormal."
                ),
                causes=[
                    "The network adapter may not have a valid network configuration.",
                    "Default gateway or IPv4 configuration may be missing.",
                    "DHCP or network configuration may be unavailable.",
                ],
                recommendations=[
                    "Check Wi-Fi or Ethernet connection.",
                    "Verify IPv4 and default gateway settings.",
                    "Reconnect to the network.",
                    "Restart the network adapter if the problem persists.",
                ],
                assessment=(
                    "The system's local network configuration is abnormal. "
                    "This does not by itself confirm a network hardware failure."
                ),
            )
        )

    # --------------------------------------------------------
    # INTERNET CONNECTIVITY
    # --------------------------------------------------------

    internet = network.get("internet_connectivity", {})

    internet_status = str(
        internet.get("status", "UNKNOWN")
    ).upper()

    internet_severity = str(
        internet.get("severity", "UNKNOWN")
    ).upper()

    if internet_status in ("PROBLEM", "WARNING"):

        severity = internet_severity

        if severity not in (
            "LOW", "MODERATE", "HIGH", "CRITICAL"
        ):
            severity = "MODERATE"

        evidence = internet.get(
            "message",
            "Internet connectivity is abnormal."
        )

        packet_loss = internet.get("packet_loss_percent")
        latency = internet.get("latency_ms")

        if packet_loss is not None:
            evidence += f" Packet loss: {packet_loss}%."

        if latency is not None:
            evidence += f" Latency: {latency} ms."

        faults.append(
            create_fault(
                component="Internet Connectivity",
                severity=severity,
                fault_type="network_connectivity",
                confidence="HIGH",
                hardware_fault=False,
                problem="Internet connectivity problem detected.",
                evidence=evidence,
                causes=[
                    "Internet connection may be unstable.",
                    "Network congestion may be present.",
                    "Router, ISP, or Wi-Fi conditions may affect connectivity.",
                ],
                recommendations=[
                    "Check the router or hotspot connection.",
                    "Reconnect to the network.",
                    "Test connectivity again after a few minutes.",
                    "Check for packet loss or unstable Wi-Fi conditions.",
                ],
                assessment=(
                    "Internet connectivity is degraded. This does not directly "
                    "confirm a faulty network adapter or other hardware component."
                ),
            )
        )

    # --------------------------------------------------------
    # DNS
    # --------------------------------------------------------

    dns = network.get("dns", {})

    dns_status = str(
        dns.get("status", "UNKNOWN")
    ).upper()

    dns_severity = str(
        dns.get("severity", "UNKNOWN")
    ).upper()

    if dns_status in ("PROBLEM", "WARNING"):

        severity = dns_severity

        if severity not in (
            "LOW", "MODERATE", "HIGH", "CRITICAL"
        ):
            severity = "MODERATE"

        faults.append(
            create_fault(
                component="DNS",
                severity=severity,
                fault_type="dns_resolution",
                confidence="HIGH",
                hardware_fault=False,
                problem="DNS resolution problem detected.",
                evidence=dns.get(
                    "message",
                    "DNS resolution is abnormal."
                ),
                causes=[
                    "DNS server may be unavailable.",
                    "Network DNS configuration may be incorrect.",
                    "The current network may have temporary DNS problems.",
                ],
                recommendations=[
                    "Check DNS configuration.",
                    "Reconnect to the current network.",
                    "Try another DNS server if the problem persists.",
                    "Test DNS resolution again.",
                ],
                assessment=(
                    "DNS resolution is degraded. This is a software or network "
                    "configuration issue unless additional evidence indicates otherwise."
                ),
            )
        )

    return faults



# ============================================================
# STARTUP DIAGNOSTICS
# ============================================================

def analyze_startup(
    startup: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    faults = []

    if not startup:
        return faults

    apps = startup.get(
        "startup_apps",
        []
    )

    tasks = startup.get(
        "startup_tasks",
        []
    )

    # --------------------------------------------------------
    # Startup applications
    # --------------------------------------------------------

    for app in apps:

        if not isinstance(app, dict):
            continue

        analysis = app.get(
            "analysis",
            {}
        )

        if not isinstance(analysis, dict):
            continue

        status = str(
            analysis.get(
                "status",
                "UNKNOWN"
            )
        ).upper()

        severity = str(
            analysis.get(
                "severity",
                "LOW"
            )
        ).upper()

        # Normal startup entries are intentionally ignored.
        if status == "NORMAL":
            continue

        # LOW/UNKNOWN entries are informational unless the
        # startup module explicitly marks them for review.
        if severity not in (
            "LOW",
            "MODERATE",
            "HIGH",
            "CRITICAL"
        ):
            severity = "LOW"

        name = str(
            app.get(
                "name",
                "Unknown"
            )
        )

        command = str(
            app.get(
                "command",
                "Unknown"
            )
        )

        target = str(
            analysis.get(
                "target",
                ""
            )
        )

        risk = str(
            analysis.get(
                "risk",
                "LOW"
            )
        )

        reason = str(
            analysis.get(
                "reason",
                "Startup entry requires review."
            )
        )

        # ----------------------------------------------------
        # Advisory optional startup entry
        # ----------------------------------------------------

        if severity == "LOW":

            fault_type = "startup_configuration"
            confidence = "MEDIUM"

        # ----------------------------------------------------
        # Explicit review / warning
        # ----------------------------------------------------

        else:

            fault_type = "startup_problem"
            confidence = "HIGH"

        evidence = (
            f"Startup entry: {name}. "
            f"Source: {app.get('source', 'Unknown')}. "
            f"Scope: {app.get('scope', 'Unknown')}. "
            f"Risk: {risk}. "
            f"Status: {status}."
        )

        if command:
            evidence += (
                f" Command: {command}."
            )

        if target:
            evidence += (
                f" Resolved target: {target}."
            )

        faults.append(
            create_fault(
                component=f"Startup: {name}",
                severity=severity,
                fault_type=fault_type,
                confidence=confidence,
                hardware_fault=False,
                problem=(
                    "Startup configuration entry may require review."
                ),
                evidence=evidence,
                causes=[
                    reason,
                    "The entry may be optional or may affect startup behavior.",
                ],
                recommendations=[
                    "Verify whether the startup entry is required.",
                    "Check the resolved target and publisher before disabling it.",
                    "Disable optional startup items only when their purpose is understood.",
                ],
                assessment=(
                    "This is a startup configuration finding, not evidence "
                    "of a hardware fault."
                ),
            )
        )

    # --------------------------------------------------------
    # Startup/logon scheduled tasks
    # --------------------------------------------------------

    for task in tasks:

        if not isinstance(task, dict):
            continue

        analysis = task.get(
            "analysis",
            {}
        )

        if not isinstance(analysis, dict):
            continue

        status = str(
            analysis.get(
                "status",
                "UNKNOWN"
            )
        ).upper()

        severity = str(
            analysis.get(
                "severity",
                "LOW"
            )
        ).upper()

        if status == "NORMAL":
            continue

        if severity not in (
            "LOW",
            "MODERATE",
            "HIGH",
            "CRITICAL"
        ):
            severity = "LOW"

        task_name = str(
            task.get(
                "name",
                "Unknown Task"
            )
        )

        task_path = str(
            task.get(
                "path",
                "Unknown"
            )
        )

        reason = str(
            analysis.get(
                "reason",
                "Startup/logon task requires review."
            )
        )

        if severity == "LOW":

            fault_type = "startup_configuration"
            confidence = "MEDIUM"

        else:

            fault_type = "startup_problem"
            confidence = "HIGH"

        faults.append(
            create_fault(
                component=f"Startup Task: {task_name}",
                severity=severity,
                fault_type=fault_type,
                confidence=confidence,
                hardware_fault=False,
                problem=(
                    "Enabled startup/logon task may require review."
                ),
                evidence=(
                    f"Task: {task_name}. "
                    f"Path: {task_path}. "
                    f"State: {task.get('state', 'Unknown')}. "
                    f"Status: {status}."
                ),
                causes=[
                    reason,
                    "The task may be optional or may affect Windows startup/logon behavior.",
                ],
                recommendations=[
                    "Verify whether the scheduled task is required.",
                    "Check the task action and publisher before disabling it.",
                    "Disable only tasks that are clearly unnecessary or suspicious.",
                ],
                assessment=(
                    "This is a startup/task configuration finding, "
                    "not evidence of hardware failure."
                ),
            )
        )

    return faults


# ============================================================
# MAIN FAULT ANALYZER
# ============================================================

def analyze_faults(
    diagnostics: Optional[Dict[str, Any]] = None,
    gpu: Optional[Dict[str, Any]] = None,
    thermal: Optional[Dict[str, Any]] = None,
    storage: Optional[List[Dict[str, Any]]] = None,
    processes: Optional[List[Dict[str, Any]]] = None,
    battery: Optional[Dict[str, Any]] = None,
    driver_diagnostics: Optional[Dict[str, Any]] = None,
    windows_health: Optional[Dict[str, Any]] = None,
    network: Optional[Dict[str, Any]] = None,
    startup: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:

    faults = []

    diagnostics = diagnostics or {}

    # --------------------------------------------------------
    # System memory
    # --------------------------------------------------------

    memory_fault = analyze_memory(
        diagnostics.get("memory"),
        processes
    )

    if memory_fault:
        faults.append(memory_fault)

    # --------------------------------------------------------
    # CPU
    # --------------------------------------------------------

    cpu_fault = analyze_cpu(
        diagnostics.get("cpu")
    )

    if cpu_fault:
        faults.append(cpu_fault)

    # --------------------------------------------------------
    # Applications
    # --------------------------------------------------------

    faults.extend(
        analyze_application_memory(
            processes,
            diagnostics.get("memory")
        )
    )

    # --------------------------------------------------------
    # GPU
    # --------------------------------------------------------

    gpu_fault = analyze_gpu(
        gpu
    )

    if gpu_fault:
        faults.append(gpu_fault)

    # --------------------------------------------------------
    # Thermal
    # --------------------------------------------------------

    thermal_fault = analyze_thermal(
        thermal
    )

    if thermal_fault:
        faults.append(thermal_fault)

    # --------------------------------------------------------
    # Storage
    # --------------------------------------------------------

    faults.extend(
        analyze_storage(
            storage
        )
    )

    # --------------------------------------------------------
    # Battery
    # --------------------------------------------------------

    faults.extend(
        analyze_battery(
            battery
        )
    )

    # --------------------------------------------------------
    # Drivers
    # --------------------------------------------------------

    faults.extend(
        analyze_drivers(
            driver_diagnostics
        )
    )

    # --------------------------------------------------------
    # Windows Health
    # --------------------------------------------------------

    faults.extend(
        analyze_windows_health(
            windows_health
        )
    )

    # --------------------------------------------------------
    # Network
    # --------------------------------------------------------

    faults.extend(
        analyze_network(
            network
        )
    )

    # --------------------------------------------------------
    # Startup
    # --------------------------------------------------------

    faults.extend(
        analyze_startup(
            startup
        )
    )

    return faults


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    test_diagnostics = {

        "memory": {
            "type": "Memory",
            "usage_percent": 74.6,
            "status": "MODERATE",
        },

        "cpu": {
            "type": "CPU",
            "usage_percent": 8.2,
            "status": "NORMAL",
        }
    }


    test_processes = [

        {
            "process_name": "code.exe",
            "display_name": "Visual Studio Code",
            "cpu_percent": 0.2,
            "memory_percent": 22.3,
            "memory_mb": 3586.7,
            "process_count": 16,
            "severity": "CRITICAL",
        },

        {
            "process_name": "svchost.exe",
            "display_name": "svchost.exe",
            "cpu_percent": 0.1,
            "memory_percent": 11.2,
            "memory_mb": 1956.7,
            "process_count": 98,
            "severity": "SYSTEM",
        },

        {
            "process_name": "chrome.exe",
            "display_name": "Google Chrome",
            "cpu_percent": 0.2,
            "memory_percent": 10.1,
            "memory_mb": 1595.8,
            "process_count": 13,
            "severity": "MODERATE",
        },
    ]


    test_battery = {

        "available": True,

        "charge_percent": 34,

        "charge_status": "NORMAL",

        "power_state": "AC CONNECTED",

        "battery_health_percent": 100.0,

        "wear_percent": 0.0,

        "health_status": "EXCELLENT",

        "confidence": "HIGH",

    }


    test_drivers = {

        "available": True,

        "devices": [

            {
                "name":
                    "NARZO 70 Pro 5G Hands-Free HF",

                "status":
                    "DRIVER_OR_DEVICE_PROBLEM",

                "severity":
                    "HIGH",

                "problem_code":
                    10,

                "occurrences":
                    1,

                "driver": {

                    "provider":
                        "Microsoft",

                    "version":
                        "10.0.26100.1",

                    "driver_date":
                        "2024-03-31",

                    "signed":
                        True,

                    "signer":
                        "Microsoft Windows",
                },
            },

            {
                "name":
                    "Intel(R) XTU Component Device",

                "status":
                    "DEVICE_WARNING",

                "severity":
                    "MODERATE",

                "problem_code":
                    0,

                "occurrences":
                    20,

                "driver": {

                    "provider":
                        "Intel",

                    "version":
                        "7.14.2.14",

                    "driver_date":
                        "2024-06-21",

                    "signed":
                        True,

                    "signer":
                        "Microsoft Windows Hardware Compatibility Publisher",
                },
            },
        ],
    }


    test_windows_health = {

        "available": True,

        "checks": [

            {
                "check":
                    "DISM Component Store",

                "status":
                    "REPAIRABLE",

                "severity":
                    "HIGH",

                "message":
                    "DISM reports corruption or a repairable component store.",

                "returncode":
                    0,
            },

            {
                "check":
                    "System File Checker",

                "status":
                    "HEALTHY",

                "severity":
                    "NORMAL",

                "message":
                    "SFC found no Windows system-file integrity violations.",

                "returncode":
                    0,
            },

            {
                "check":
                    "Pending Reboot",

                "status":
                    "REBOOT_PENDING",

                "severity":
                    "LOW",

                "message":
                    "Windows reports that a system reboot may be required.",

                "indicators":
                    [
                        "Pending file rename operations"
                    ],
            },

            {
                "check":
                    "Windows Update Service",

                "status":
                    "STOPPED",

                "severity":
                    "LOW",

                "message":
                    "Windows Update service is currently stopped.",
            },
        ],
    }


    print(
        "\n========== FIXMATE FAULT ENGINE V7 ==========\n"
    )


    faults = analyze_faults(

        diagnostics=test_diagnostics,

        processes=test_processes,

        battery=test_battery,

        driver_diagnostics=test_drivers,

        windows_health=test_windows_health,

        network={
            "local_network": {
                "status": "HEALTHY",
                "severity": "NORMAL",
                "message": "Local network configuration is working."
            },
            "internet_connectivity": {
                "status": "HEALTHY",
                "severity": "NORMAL",
                "message": "Network connectivity is working normally.",
                "latency_ms": 84,
                "packet_loss_percent": 0
            },
            "dns": {
                "status": "HEALTHY",
                "severity": "NORMAL",
                "message": "DNS resolution is working normally."
            }
        },
    )


    if not faults:

        print(
            "No faults detected."
        )

    else:

        for fault in faults:

            print(
                f"[{fault['severity']}] "
                f"{fault['component']}"
            )

            print(
                f"Type       : "
                f"{fault['fault_type']}"
            )

            print(
                f"Confidence : "
                f"{fault['confidence']}"
            )

            print(
                f"Hardware   : "
                f"{'YES' if fault['hardware_fault'] else 'NO'}"
            )

            print(
                f"Problem    : "
                f"{fault['problem']}"
            )

            print(
                f"Evidence   : "
                f"{fault['evidence']}"
            )

            print(
                f"Assessment : "
                f"{fault['assessment']}"
            )

            if fault["causes"]:

                print(
                    "\nPossible Causes:"
                )

                for cause in fault[
                    "causes"
                ]:

                    print(
                        f"- {cause}"
                    )

            if fault["recommendations"]:

                print(
                    "\nRecommendations:"
                )

                for recommendation in fault[
                    "recommendations"
                ]:

                    print(
                        f"- {recommendation}"
                    )

            print(
                "\n" + "-" * 55
            )

    print()
