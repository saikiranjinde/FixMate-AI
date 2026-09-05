# ============================================================
# FIXMATE-AI
# Diagnosis Report Engine V6
# ============================================================


def generate_diagnosis_report(
    faults,
    severity_result,
    recommendations
):
    """
    Combine faults, overall severity and recommendations
    into one structured diagnosis report.

    V5 additions:
    - fault_type
    - confidence
    - hardware_fault
    - assessment
    - causes
    - category summary
    - network / Windows Health issue tracking
    """

    report = {
        "overall_severity": severity_result.get(
            "overall_severity",
            "UNKNOWN"
        ),

        "fault_count": severity_result.get(
            "fault_count",
            len(faults)
        ),

        "assessment": severity_result.get(
            "message",
            "No assessment available."
        ),

        "summary": {
            "hardware_faults": 0,
            "application_issues": 0,
            "system_resource_issues": 0,
            "driver_problems": 0,
            "driver_warnings": 0,
            "windows_system_issues": 0,
            "windows_configuration_issues": 0,
            "network_issues": 0,
            "startup_issues": 0,
            "other_issues": 0,
        },

        "faults": []
    }

    for fault in faults:

        component = fault.get(
            "component",
            "Unknown"
        )

        fault_recommendations = []

        # ----------------------------------------------------
        # Match recommendations from recommendation engine
        # ----------------------------------------------------

        for recommendation in recommendations or []:

            if recommendation.get("component") == component:

                recommendation_text = recommendation.get(
                    "recommendation",
                    "No recommendation available."
                )

                if recommendation_text not in fault_recommendations:
                    fault_recommendations.append(
                        recommendation_text
                    )

        # ----------------------------------------------------
        # Fallback: use recommendations already attached
        # to the fault when recommendation engine has none.
        # ----------------------------------------------------

        if not fault_recommendations:

            existing_recommendations = fault.get(
                "recommendations",
                []
            )

            if isinstance(
                existing_recommendations,
                list
            ):

                fault_recommendations = list(
                    existing_recommendations
                )

        # ----------------------------------------------------
        # V5 fault data
        # ----------------------------------------------------

        causes = fault.get(
            "causes",
            fault.get(
                "possible_causes",
                []
            )
        )

        # ----------------------------------------------------
        # Update issue category summary
        # ----------------------------------------------------

        fault_type = str(
            fault.get(
                "fault_type",
                "unknown"
            )
        ).lower()

        if fault.get("hardware_fault", False):

            report["summary"]["hardware_faults"] += 1

        if fault_type == "application_resource_usage":

            report["summary"]["application_issues"] += 1

        elif fault_type == "resource_pressure":

            report["summary"]["system_resource_issues"] += 1

        elif fault_type == "driver_problem":

            report["summary"]["driver_problems"] += 1

        elif fault_type == "driver_warning":

            report["summary"]["driver_warnings"] += 1

        elif fault_type == "windows_system_issue":

            report["summary"]["windows_system_issues"] += 1

        elif fault_type == "windows_configuration":

            report["summary"]["windows_configuration_issues"] += 1

        elif fault_type in (
            "startup_configuration",
            "startup_problem"
        ):

            report["summary"]["startup_issues"] += 1

        elif fault_type in (
            "network_configuration",
            "network_connectivity",
            "dns_resolution"
        ):

            report["summary"]["network_issues"] += 1

        elif (
            not fault.get("hardware_fault", False)
            and fault_type not in (
                "resource_pressure",
                "application_resource_usage",
                "driver_problem",
                "driver_warning",
                "windows_system_issue",
                "windows_configuration",
                "startup_configuration",
                "startup_problem",
                "network_configuration",
                "network_connectivity",
                "dns_resolution"
            )
        ):

            report["summary"]["other_issues"] += 1

        report["faults"].append({

            "component": component,

            "severity": fault.get(
                "severity",
                "UNKNOWN"
            ),

            "fault_type": fault.get(
                "fault_type",
                "unknown"
            ),

            "confidence": fault.get(
                "confidence",
                "UNKNOWN"
            ),

            "hardware_fault": fault.get(
                "hardware_fault",
                False
            ),

            "problem": fault.get(
                "problem",
                "Unknown problem."
            ),

            "evidence": fault.get(
                "evidence",
                "No evidence available."
            ),

            "assessment": fault.get(
                "assessment",
                ""
            ),

            "possible_causes": causes,

            "recommendations": fault_recommendations
        })

    return report


# ============================================================
# PRINT DIAGNOSIS REPORT
# ============================================================

def print_diagnosis_report(report):

    print("\n")
    print("=" * 50)
    print("             FIXMATE DIAGNOSIS")
    print("=" * 50)

    print(
        f"\nOverall Severity : "
        f"{report['overall_severity']}"
    )

    print(
        f"Issues Found     : "
        f"{report['fault_count']}"
    )

    print(
        f"Assessment       : "
        f"{report['assessment']}"
    )

    # --------------------------------------------------------
    # No issues
    # --------------------------------------------------------

    if not report["faults"]:

        print(
            "\nNo significant problems detected."
        )

        print("\n" + "=" * 50)

        return

    # --------------------------------------------------------
    # Issue details
    # --------------------------------------------------------

    for index, fault in enumerate(
        report["faults"],
        start=1
    ):

        print("\n" + "-" * 50)

        print(
            f"Issue {index}: "
            f"{fault['component']}"
        )

        print(
            f"Severity   : "
            f"{fault['severity']}"
        )

        print(
            f"Issue Type : "
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
            f"\nProblem:\n"
            f"{fault['problem']}"
        )

        print(
            f"\nEvidence:\n"
            f"{fault['evidence']}"
        )

        # ----------------------------------------------------
        # Assessment
        # ----------------------------------------------------

        assessment = fault.get(
            "assessment",
            ""
        )

        if assessment:

            print(
                f"\nAssessment:\n"
                f"{assessment}"
            )

        # ----------------------------------------------------
        # Possible Causes
        # ----------------------------------------------------

        causes = fault.get(
            "possible_causes",
            []
        )

        if causes:

            print(
                "\nPossible Causes:"
            )

            for cause in causes:
                print(
                    f"- {cause}"
                )

        # ----------------------------------------------------
        # Recommendations
        # ----------------------------------------------------

        recommendations = fault.get(
            "recommendations",
            []
        )

        if recommendations:

            print(
                "\nRecommendations:"
            )

            for recommendation in recommendations:
                print(
                    f"- {recommendation}"
                )

    # --------------------------------------------------------
    # Diagnosis category summary
    # --------------------------------------------------------

    summary = report.get(
        "summary",
        {}
    )

    print("\n" + "-" * 50)
    print("DIAGNOSIS SUMMARY")

    print(
        f"Hardware Faults        : "
        f"{summary.get('hardware_faults', 0)}"
    )

    print(
        f"Application Issues     : "
        f"{summary.get('application_issues', 0)}"
    )

    print(
        f"System Resource Issues : "
        f"{summary.get('system_resource_issues', 0)}"
    )

    print(
        f"Driver Problems        : "
        f"{summary.get('driver_problems', 0)}"
    )

    print(
        f"Driver Warnings        : "
        f"{summary.get('driver_warnings', 0)}"
    )

    print(
        f"Windows System Issues  : "
        f"{summary.get('windows_system_issues', 0)}"
    )

    print(
        f"Windows Configuration  : "
        f"{summary.get('windows_configuration_issues', 0)}"
    )

    print(
        f"Network Issues         : "
        f"{summary.get('network_issues', 0)}"
    )

    print(
        f"Startup Issues         : "
        f"{summary.get('startup_issues', 0)}"
    )

    print(
        f"Other Issues           : "
        f"{summary.get('other_issues', 0)}"
    )

    # --------------------------------------------------------
    # Hardware fault summary
    # --------------------------------------------------------

    hardware_fault_count = sum(
        1
        for fault in report["faults"]
        if fault.get("hardware_fault", False)
    )

    application_issue_count = sum(
        1
        for fault in report["faults"]
        if fault.get("fault_type")
        == "application_resource_usage"
    )

    print("\n" + "-" * 50)

    print(
        f"Hardware Faults Detected : "
        f"{hardware_fault_count}"
    )

    print(
        f"Application Issues       : "
        f"{application_issue_count}"
    )

    print("\n" + "=" * 50)
    print("          END OF DIAGNOSIS")
    print("=" * 50)


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    sample_faults = [

        {
            "component":
                "Application: Visual Studio Code",

            "severity":
                "LOW",

            "fault_type":
                "application_resource_usage",

            "confidence":
                "HIGH",

            "hardware_fault":
                False,

            "problem":
                "Application is consuming a high amount "
                "of system memory.",

            "evidence":
                "Visual Studio Code is using 3042.4 MB "
                "of RAM (18.9% of system memory) across "
                "15 process(es). Overall system RAM usage "
                "is 69.1%.",

            "assessment":
                "Visual Studio Code has high application-level "
                "memory consumption, but the system as a whole "
                "is not currently under memory pressure. "
                "No hardware fault is indicated.",

            "causes": [
                "Multiple application processes are active.",
                "The application is consuming a significant "
                "share of system memory.",
                "The application may have a large workspace, "
                "project, cache, or background service load."
            ]
        }

    ]

    sample_severity = {

        "overall_severity":
            "LOW",

        "fault_count":
            1,

        "message":
            "Minor issue detected. "
            "No immediate action required."
    }

    sample_recommendations = [

        {
            "component":
                "Application: Visual Studio Code",

            "severity":
                "LOW",

            "problem":
                "Application is consuming a high amount "
                "of system memory.",

            "recommendation":
                "Close unused Visual Studio Code "
                "windows or sessions."
        },

        {
            "component":
                "Application: Visual Studio Code",

            "severity":
                "LOW",

            "problem":
                "Application is consuming a high amount "
                "of system memory.",

            "recommendation":
                "Review unnecessary extensions or plugins "
                "used by Visual Studio Code."
        }

    ]

    report = generate_diagnosis_report(
        sample_faults,
        sample_severity,
        sample_recommendations
    )

    print_diagnosis_report(
        report
    )