# ============================================================
# FIXMATE-AI
# Recommendation Engine V2
# ============================================================

from typing import Any, Dict, List


SEVERITY_ORDER = {
    "NORMAL": 0,
    "LOW": 1,
    "MODERATE": 2,
    "HIGH": 3,
    "CRITICAL": 4
}


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _severity(fault: Dict[str, Any]) -> str:
    return _text(
        fault.get(
            "severity",
            "LOW"
        )
    ).upper()


def _fault_type(fault: Dict[str, Any]) -> str:
    return _text(
        fault.get(
            "fault_type",
            "unknown"
        )
    ).lower()


def _component(fault: Dict[str, Any]) -> str:
    return _text(
        fault.get(
            "component",
            "Unknown"
        )
    )


def _add(
    results: List[Dict[str, str]],
    component: str,
    recommendation: str,
    priority: str
) -> None:

    results.append({
        "component": component,
        "recommendation": recommendation,
        "priority": priority
    })


def _generic(
    fault: Dict[str, Any]
) -> List[str]:

    severity = _severity(fault)

    if severity == "CRITICAL":
        return [
            "Address the detected condition as soon as possible.",
            "Save important work and verify whether the problem persists after corrective action.",
            "Run FixMate again after remediation to confirm the condition is cleared."
        ]

    if severity == "HIGH":
        return [
            "Address the detected condition and verify whether the problem persists.",
            "Run FixMate again after corrective action to confirm the condition is cleared."
        ]

    if severity == "MODERATE":
        return [
            "Review the detected condition and monitor whether it recurs.",
            "Run FixMate again after making relevant changes."
        ]

    return [
        "Monitor the condition and verify it is still relevant before making changes."
    ]


def generate_recommendations(
    faults: List[Dict[str, Any]]
) -> List[Dict[str, str]]:

    results: List[Dict[str, str]] = []

    for fault in faults or []:

        if not isinstance(fault, dict):
            continue

        component = _component(fault)
        fault_type = _fault_type(fault)
        severity = _severity(fault)

        # ----------------------------------------------------
        # Hardware fault
        # ----------------------------------------------------

        if fault.get("hardware_fault", False):

            recommendations = [
                "Back up important data before performing hardware service.",
                "Check the affected component for physical, thermal, power, or connection issues.",
                "Run a second diagnostic pass after corrective action.",
            ]

            for rec in recommendations:
                _add(
                    results,
                    component,
                    rec,
                    severity
                )

            continue

        # ----------------------------------------------------
        # System memory pressure
        # ----------------------------------------------------

        if fault_type == "resource_pressure":

            if component.lower() == "memory":

                recommendations = [
                    "Close applications that are not required.",
                    "Reduce unnecessary browser tabs and background applications.",
                    "Check the top memory-consuming processes in FixMate.",
                    "Restart the highest-memory application if its usage continues to grow.",
                    "Monitor system RAM usage after optimization.",
                ]

                if severity in ("HIGH", "CRITICAL"):
                    recommendations.append(
                        "Consider reducing startup/background software or increasing RAM only if high usage is frequent."
                    )

                for rec in recommendations:
                    _add(
                        results,
                        component,
                        rec,
                        severity
                    )

                continue

        # ----------------------------------------------------
        # Application resource usage
        # ----------------------------------------------------

        if fault_type == "application_resource_usage":

            recommendations = [
                f"Close unused {component.replace('Application: ', '')} windows or sessions.",
                f"Review unnecessary extensions, plugins, tabs, or background activity in {component.replace('Application: ', '')}.",
                f"Restart {component.replace('Application: ', '')} if memory usage continues to grow.",
                "Monitor memory usage after optimization.",
            ]

            # For applications with genuinely high severity, make the
            # first corrective action more prominent.
            if severity in ("HIGH", "CRITICAL"):
                recommendations.insert(
                    0,
                    "Close the application temporarily if system responsiveness is affected."
                )

            for rec in recommendations:
                _add(
                    results,
                    component,
                    rec,
                    severity
                )

            continue

        # ----------------------------------------------------
        # Driver problem
        # ----------------------------------------------------

        if fault_type == "driver_problem":

            recommendations = [
                "Open Device Manager and inspect the affected device.",
                "Disable and re-enable the affected device.",
                "Install the latest compatible driver or reinstall the current driver if the problem persists.",
            ]

            # Bluetooth / phone-device problems need device-side checks.
            component_lower = component.lower()

            if (
                "narzo" in component_lower
                or "bluetooth" in component_lower
                or "hands-free" in component_lower
                or "avrcp" in component_lower
            ):
                recommendations.extend([
                    "Reconnect or re-pair the associated Bluetooth device.",
                    "Verify that the phone/device is powered on and Bluetooth is enabled.",
                    "Remove and re-add the Bluetooth device only if the problem continues."
                ])

            if severity == "CRITICAL":
                recommendations.insert(
                    0,
                    "Avoid unnecessary hardware replacement until the driver/device configuration has been checked."
                )

            for rec in recommendations:
                _add(
                    results,
                    component,
                    rec,
                    severity
                )

            continue

        # ----------------------------------------------------
        # Driver warning
        # ----------------------------------------------------

        if fault_type == "driver_warning":

            recommendations = [
                "Check Device Manager for additional status details.",
                "Monitor the device for actual functional problems.",
                "Update the associated vendor driver or software if the warning persists.",
            ]

            # Intel XTU Component Device is commonly tied to
            # Intel XTU/vendor software rather than a confirmed
            # physical hardware failure.
            if "xtu" in component.lower():
                recommendations = [
                    "Check whether Intel XTU or related Intel utility software is installed and actively used.",
                    "Update Intel XTU and its associated components if a newer compatible version is available.",
                    "Check Device Manager for any additional warning details.",
                    "Do not treat Problem Code 0 by itself as proof of hardware failure.",
                ]

            for rec in recommendations:
                _add(
                    results,
                    component,
                    rec,
                    severity
                )

            continue

        # ----------------------------------------------------
        # Windows system integrity
        # ----------------------------------------------------

        if fault_type == "windows_system_issue":

            recommendations = [
                "Restart Windows first when a reboot is pending.",
                "Run an elevated DISM repair for the component store.",
                "Run System File Checker again after DISM completes.",
                "Run FixMate again after repair to verify Windows health.",
                "Back up important data before significant system repair operations.",
            ]

            for rec in recommendations:
                _add(
                    results,
                    component,
                    rec,
                    severity
                )

            continue

        # ----------------------------------------------------
        # Windows configuration
        # ----------------------------------------------------

        if fault_type == "windows_configuration":

            component_lower = component.lower()

            if "pending reboot" in component_lower:

                recommendations = [
                    "Restart the computer when convenient.",
                    "Run FixMate again after restarting to confirm the pending reboot is cleared."
                ]

            elif "windows update" in component_lower:

                recommendations = [
                    "Check Windows Update settings and recent update activity.",
                    "Start the Windows Update service if updates are required.",
                    "Avoid disabling Windows Update permanently unless there is a specific administrative reason.",
                    "Run FixMate again after confirming the service configuration."
                ]

            else:

                recommendations = _generic(
                    fault
                )

            for rec in recommendations:
                _add(
                    results,
                    component,
                    rec,
                    severity
                )

            continue

        # ----------------------------------------------------
        # Network diagnostics
        # ----------------------------------------------------

        if fault_type in (
            "network_configuration",
            "network_connectivity",
            "dns_resolution"
        ):

            component_lower = component.lower()

            if fault_type == "network_connectivity":

                recommendations = [
                    "Reconnect to the current Wi-Fi or wired network.",
                    "Check router or hotspot conditions if high latency continues.",
                    "Repeat the connectivity test after a few minutes.",
                    "Compare results with another network to determine whether the issue is local or upstream."
                ]

            elif fault_type == "dns_resolution":

                recommendations = [
                    "Check the configured DNS server.",
                    "Reconnect to the network and retry DNS resolution.",
                    "Test DNS resolution against another known domain.",
                    "Check whether the problem affects multiple devices on the same network."
                ]

            else:

                recommendations = [
                    "Verify the active network adapter, IP address, gateway, and DNS configuration.",
                    "Reconnect to the network and run FixMate again.",
                    "Check the router or access point if the problem persists."
                ]

            # Congestion / latency-specific guidance.
            evidence = _text(
                fault.get(
                    "evidence",
                    ""
                )
            ).lower()

            if (
                fault_type == "network_connectivity"
                and "latency" in evidence
            ):
                recommendations.insert(
                    0,
                    "Retest latency at another time or on another network before changing adapter settings."
                )

            for rec in recommendations:
                _add(
                    results,
                    component,
                    rec,
                    severity
                )

            continue

        # ----------------------------------------------------
        # Startup diagnostics
        # ----------------------------------------------------

        if fault_type in (
            "startup_configuration",
            "startup_problem"
        ):

            if fault_type == "startup_problem":

                recommendations = [
                    "Verify the startup entry's resolved target and publisher.",
                    "Check whether the target is digitally signed.",
                    "Disable the startup entry only after confirming it is unnecessary or suspicious.",
                    "Run FixMate again after making a startup change."
                ]

            else:

                recommendations = [
                    "Verify whether the startup entry is actually needed.",
                    "Keep trusted, signed startup applications unless they cause a measurable problem.",
                    "Disable optional startup entries only when their purpose is understood."
                ]

            for rec in recommendations:
                _add(
                    results,
                    component,
                    rec,
                    severity
                )

            continue

        # ----------------------------------------------------
        # Fallback
        # ----------------------------------------------------

        for rec in _generic(
            fault
        ):
            _add(
                results,
                component,
                rec,
                severity
            )

    return results


# ============================================================
# Standalone Test
# ============================================================

if __name__ == "__main__":

    sample_faults = [
        {
            "component": "Memory",
            "severity": "MODERATE",
            "fault_type": "resource_pressure",
            "hardware_fault": False
        },
        {
            "component": "Driver: NARZO 70 Pro 5G Hands-Free HF",
            "severity": "HIGH",
            "fault_type": "driver_problem",
            "hardware_fault": False
        },
        {
            "component": "Windows: DISM Component Store",
            "severity": "HIGH",
            "fault_type": "windows_system_issue",
            "hardware_fault": False
        },
        {
            "component": "Startup: Example",
            "severity": "LOW",
            "fault_type": "startup_configuration",
            "hardware_fault": False
        }
    ]

    result = generate_recommendations(
        sample_faults
    )

    for item in result:
        print(
            f"{item['component']} | "
            f"{item['priority']} | "
            f"{item['recommendation']}"
        )
