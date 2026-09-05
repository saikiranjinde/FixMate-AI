# ============================================================
# FIXMATE-AI
# SEVERITY ENGINE V2.1
# ============================================================
#
# V2.1
# - Hardware faults have highest priority
# - System resource pressure is strongly weighted
# - Driver problems are explicitly recognized
# - Driver warnings are separated from actual problems
# - Application issues cannot automatically make system HIGH
# - Battery degradation is handled independently
# ============================================================


SEVERITY_WEIGHT = {
    "NORMAL": 0,
    "LOW": 1,
    "MODERATE": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


# ============================================================
# FAULT TYPE WEIGHTS
# ============================================================

FAULT_TYPE_WEIGHT = {

    "hardware_fault": 4,

    "resource_pressure": 3,

    "thermal": 3,

    "driver_problem": 3,

    "driver_warning": 2,

    "battery_degradation": 2,

    "low_charge": 1,

    "application_resource_usage": 1,

    "unknown": 1,
}


# ============================================================
# FAULT TYPE
# ============================================================

def get_fault_type(
    fault
):

    return str(
        fault.get(
            "fault_type",
            "unknown"
        )
    ).lower()


# ============================================================
# SEVERITY
# ============================================================

def get_fault_severity(
    fault
):

    return str(
        fault.get(
            "severity",
            "NORMAL"
        )
    ).upper()


# ============================================================
# EFFECTIVE WEIGHT
# ============================================================

def get_effective_severity(
    fault
):

    severity = get_fault_severity(
        fault
    )

    fault_type = get_fault_type(
        fault
    )

    hardware_fault = bool(
        fault.get(
            "hardware_fault",
            False
        )
    )

    base_weight = SEVERITY_WEIGHT.get(
        severity,
        0
    )

    # --------------------------------------------------------
    # CONFIRMED HARDWARE FAULT
    # --------------------------------------------------------

    if hardware_fault:

        return base_weight


    # --------------------------------------------------------
    # APPLICATION RESOURCE USAGE
    #
    # Application issues do not automatically become
    # system-wide HIGH.
    # --------------------------------------------------------

    if fault_type == (
        "application_resource_usage"
    ):

        if severity == "CRITICAL":
            return 2

        if severity == "HIGH":
            return 2

        if severity == "MODERATE":
            return 1

        return 1


    # --------------------------------------------------------
    # DRIVER PROBLEM
    #
    # A non-zero Windows Problem Code indicates an actual
    # device/driver configuration problem.
    # --------------------------------------------------------

    if fault_type == "driver_problem":

        confidence = str(
            fault.get(
                "confidence",
                "LOW"
            )
        ).upper()

        if confidence == "HIGH":

            if severity == "CRITICAL":
                return 4

            if severity == "HIGH":
                return 3

            if severity == "MODERATE":
                return 2

            return 1

        # Lower confidence driver problems
        # are slightly reduced.

        if severity == "CRITICAL":
            return 3

        if severity == "HIGH":
            return 2

        if severity == "MODERATE":
            return 1

        return 1


    # --------------------------------------------------------
    # DRIVER WARNING
    # --------------------------------------------------------

    if fault_type == "driver_warning":

        if severity == "CRITICAL":
            return 3

        if severity == "HIGH":
            return 2

        if severity == "MODERATE":
            return 2

        return 1


    # --------------------------------------------------------
    # LOW BATTERY CHARGE
    # --------------------------------------------------------

    if fault_type == "low_charge":

        return 1


    # --------------------------------------------------------
    # BATTERY DEGRADATION
    # --------------------------------------------------------

    if fault_type == "battery_degradation":

        if severity == "HIGH":
            return 3

        if severity == "MODERATE":
            return 2

        if severity == "LOW":
            return 1

        return 0


    # --------------------------------------------------------
    # SYSTEM RESOURCE PRESSURE
    # --------------------------------------------------------

    if fault_type == "resource_pressure":

        return base_weight


    # --------------------------------------------------------
    # THERMAL
    # --------------------------------------------------------

    if fault_type == "thermal":

        return base_weight


    # --------------------------------------------------------
    # DEFAULT
    # --------------------------------------------------------

    return base_weight


# ============================================================
# CALCULATE OVERALL SEVERITY
# ============================================================

def calculate_overall_severity(
    faults
):

    if not faults:

        return {
            "overall_severity":
                "NORMAL",

            "fault_count":
                0,

            "message":
                "No significant problems detected.",

            "hardware_fault_count":
                0,

            "resource_issue_count":
                0,

            "application_issue_count":
                0,

            "driver_problem_count":
                0,

            "driver_warning_count":
                0,

            "battery_issue_count":
                0,

        }


    # ========================================================
    # CATEGORIES
    # ========================================================

    hardware_faults = []

    resource_faults = []

    thermal_faults = []

    application_faults = []

    driver_problems = []

    driver_warnings = []

    battery_faults = []

    other_faults = []


    # ========================================================
    # CLASSIFY
    # ========================================================

    for fault in faults:

        fault_type = get_fault_type(
            fault
        )

        if fault.get(
            "hardware_fault",
            False
        ):

            hardware_faults.append(
                fault
            )

        elif fault_type == (
            "resource_pressure"
        ):

            resource_faults.append(
                fault
            )

        elif fault_type == "thermal":

            thermal_faults.append(
                fault
            )

        elif fault_type == (
            "application_resource_usage"
        ):

            application_faults.append(
                fault
            )

        elif fault_type == "driver_problem":

            driver_problems.append(
                fault
            )

        elif fault_type == "driver_warning":

            driver_warnings.append(
                fault
            )

        elif fault_type in (
            "battery_degradation",
            "low_charge"
        ):

            battery_faults.append(
                fault
            )

        else:

            other_faults.append(
                fault
            )


    # ========================================================
    # MAX EFFECTIVE WEIGHTS
    # ========================================================

    hardware_weight = max(
        (
            get_effective_severity(
                fault
            )
            for fault in hardware_faults
        ),
        default=0
    )


    resource_weight = max(
        (
            get_effective_severity(
                fault
            )
            for fault in resource_faults
        ),
        default=0
    )


    thermal_weight = max(
        (
            get_effective_severity(
                fault
            )
            for fault in thermal_faults
        ),
        default=0
    )


    driver_problem_weight = max(
        (
            get_effective_severity(
                fault
            )
            for fault in driver_problems
        ),
        default=0
    )


    driver_warning_weight = max(
        (
            get_effective_severity(
                fault
            )
            for fault in driver_warnings
        ),
        default=0
    )


    battery_weight = max(
        (
            get_effective_severity(
                fault
            )
            for fault in battery_faults
            if get_fault_type(
                fault
            ) != "low_charge"
        ),
        default=0
    )


    application_weight = max(
        (
            get_effective_severity(
                fault
            )
            for fault in application_faults
        ),
        default=0
    )


    # ========================================================
    # 1. HARDWARE FAULT
    # ========================================================

    if hardware_weight >= 4:

        overall = "CRITICAL"

        message = (
            "A critical hardware-level problem "
            "has been detected. Immediate attention "
            "is recommended."
        )

    elif hardware_weight >= 3:

        overall = "HIGH"

        message = (
            "A high-severity hardware problem "
            "has been detected. Further inspection "
            "is recommended."
        )

    elif hardware_weight >= 2:

        overall = "MODERATE"

        message = (
            "A moderate hardware-related issue "
            "has been detected."
        )


    # ========================================================
    # 2. THERMAL
    # ========================================================

    elif thermal_weight >= 4:

        overall = "CRITICAL"

        message = (
            "Critical thermal conditions detected. "
            "Immediate attention is recommended."
        )

    elif thermal_weight >= 3:

        overall = "HIGH"

        message = (
            "High thermal conditions detected. "
            "Cooling and workload should be investigated."
        )

    elif thermal_weight >= 2:

        overall = "MODERATE"

        message = (
            "Elevated thermal conditions detected."
        )


    # ========================================================
    # 3. DRIVER PROBLEMS
    # ========================================================

    elif driver_problem_weight >= 4:

        overall = "CRITICAL"

        message = (
            "Critical device/driver configuration "
            "problems were detected."
        )

    elif driver_problem_weight >= 3:

        overall = "HIGH"

        message = (
            "Windows reports one or more high-severity "
            "device/driver configuration problems."
        )

    elif driver_problem_weight >= 2:

        overall = "MODERATE"

        message = (
            "Device/driver configuration problems "
            "were detected and should be investigated."
        )


    # ========================================================
    # 4. SYSTEM RESOURCE
    # ========================================================

    elif resource_weight >= 4:

        overall = "CRITICAL"

        message = (
            "Critical system resource pressure detected. "
            "Immediate action is recommended."
        )

    elif resource_weight >= 3:

        overall = "HIGH"

        message = (
            "High system-level resource pressure detected. "
            "Action is recommended soon."
        )

    elif resource_weight >= 2:

        overall = "MODERATE"

        if (
            application_faults
            or driver_warnings
        ):

            message = (
                "Moderate system resource pressure detected, "
                "with additional software-level contributors."
            )

        else:

            message = (
                "Moderate system resource pressure detected. "
                "Optimization or monitoring is recommended."
            )


    # ========================================================
    # 5. DRIVER WARNINGS
    # ========================================================

    elif driver_warning_weight >= 2:

        overall = "MODERATE"

        message = (
            "Device/driver warnings were detected. "
            "Monitoring and further inspection are recommended."
        )


    # ========================================================
    # 6. BATTERY
    # ========================================================

    elif battery_weight >= 3:

        overall = "HIGH"

        message = (
            "Significant battery degradation detected. "
            "Battery inspection is recommended."
        )

    elif battery_weight >= 2:

        overall = "MODERATE"

        message = (
            "Battery degradation is present. "
            "Monitoring or replacement planning may be appropriate."
        )


    # ========================================================
    # 7. APPLICATION ISSUES
    # ========================================================

    elif application_weight >= 2:

        overall = "MODERATE"

        message = (
            "Application-level resource issues were detected. "
            "The available evidence does not directly indicate "
            "a hardware fault."
        )

    elif application_faults:

        overall = "LOW"

        message = (
            "Minor application-level resource issues detected. "
            "No immediate action is required."
        )


    # ========================================================
    # 8. OTHER
    # ========================================================

    elif other_faults:

        highest = max(
            (
                get_effective_severity(
                    fault
                )
                for fault in other_faults
            ),
            default=0
        )

        overall = weight_to_severity(
            highest
        )

        message = (
            get_severity_message(
                overall
            )
        )


    # ========================================================
    # 9. NOTHING SERIOUS
    # ========================================================

    else:

        overall = "NORMAL"

        message = (
            "No significant problems detected."
        )


    # ========================================================
    # BUILD RESULT
    # ========================================================

    return {

        "overall_severity":
            overall,

        "fault_count":
            len(faults),

        "message":
            message,

        "hardware_fault_count":
            len(hardware_faults),

        "resource_issue_count":
            len(resource_faults),

        "application_issue_count":
            len(application_faults),

        "driver_problem_count":
            len(driver_problems),

        "driver_warning_count":
            len(driver_warnings),

        "battery_issue_count":
            len(battery_faults),
    }


# ============================================================
# WEIGHT → SEVERITY
# ============================================================

def weight_to_severity(
    weight
):

    if weight >= 4:
        return "CRITICAL"

    if weight >= 3:
        return "HIGH"

    if weight >= 2:
        return "MODERATE"

    if weight >= 1:
        return "LOW"

    return "NORMAL"


# ============================================================
# HUMAN MESSAGE
# ============================================================

def get_severity_message(
    severity
):

    severity = str(
        severity
    ).upper()

    messages = {

        "NORMAL":
            "No significant problems detected.",

        "LOW":
            "Minor issue detected. "
            "No immediate action required.",

        "MODERATE":
            "Moderate issue detected. "
            "Optimization or monitoring is recommended.",

        "HIGH":
            "High-severity issue detected. "
            "Action is recommended soon.",

        "CRITICAL":
            "Critical issue detected. "
            "Immediate attention is recommended.",
    }

    return messages.get(
        severity,
        "Assessment unavailable."
    )


# ============================================================
# PRINT REPORT
# ============================================================

def print_severity_report(
    result
):

    print("\n")
    print("=" * 50)
    print("          OVERALL SEVERITY")
    print("=" * 50)

    print(
        f"\nSeverity               : "
        f"{result.get('overall_severity', 'UNKNOWN')}"
    )

    print(
        f"Total Issues           : "
        f"{result.get('fault_count', 0)}"
    )

    print(
        f"Hardware Faults        : "
        f"{result.get('hardware_fault_count', 0)}"
    )

    print(
        f"System Resource Issues : "
        f"{result.get('resource_issue_count', 0)}"
    )

    print(
        f"Application Issues     : "
        f"{result.get('application_issue_count', 0)}"
    )

    print(
        f"Driver Problems        : "
        f"{result.get('driver_problem_count', 0)}"
    )

    print(
        f"Driver Warnings        : "
        f"{result.get('driver_warning_count', 0)}"
    )

    print(
        f"Battery Issues         : "
        f"{result.get('battery_issue_count', 0)}"
    )

    print(
        f"\nAssessment             : "
        f"{result.get('message', 'N/A')}"
    )

    print(
        "\n" + "=" * 50
    )


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    sample_faults = [

        {
            "component": "Memory",
            "severity": "MODERATE",
            "fault_type":
                "resource_pressure",
            "hardware_fault": False,
            "confidence": "MEDIUM",
        },

        {
            "component":
                "Application: Visual Studio Code",
            "severity": "HIGH",
            "fault_type":
                "application_resource_usage",
            "hardware_fault": False,
            "confidence": "HIGH",
        },

        {
            "component":
                "Intel(R) XTU Component Device",
            "severity": "MODERATE",
            "fault_type":
                "driver_warning",
            "hardware_fault": False,
            "confidence": "MEDIUM",
        },

        {
            "component":
                "Driver: NARZO 70 Pro 5G Hands-Free HF",
            "severity": "HIGH",
            "fault_type":
                "driver_problem",
            "hardware_fault": False,
            "confidence": "HIGH",
        },

        {
            "component":
                "Driver: NARZO 70 Pro 5G Avrcp Transport",
            "severity": "HIGH",
            "fault_type":
                "driver_problem",
            "hardware_fault": False,
            "confidence": "HIGH",
        },
    ]


    print(
        "\n========== "
        "FIXMATE SEVERITY ENGINE V2.1 "
        "==========\n"
    )


    result = calculate_overall_severity(
        sample_faults
    )


    print_severity_report(
        result
    )