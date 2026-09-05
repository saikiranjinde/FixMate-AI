import subprocess
import json
import os
import re
from html.parser import HTMLParser


# ============================================================
# FIXMATE-AI
# COMPLETE BATTERY DIAGNOSIS
#
# Single file:
# - Battery information
# - Windows batteryreport generation
# - HTML report parsing
# - Capacity health
# - Wear level
# - Cycle count
# - Recent usage
# - Battery usage / drain
# - Usage history
# - Battery life estimates
# - Diagnosis
# - Confidence
# - Hardware-fault indication
# - Recommendations
# ============================================================


# ============================================================
# POWER STATUS MAP
# Win32_Battery BatteryStatus values
# ============================================================

BATTERY_STATUS_MAP = {
    1: "DISCHARGING",
    2: "AC CONNECTED",
    3: "FULLY CHARGED",
    4: "LOW",
    5: "CRITICAL",
    6: "CHARGING",
    7: "CHARGING / HIGH",
    8: "CHARGING / LOW",
    9: "CHARGING / CRITICAL",
    10: "UNDEFINED",
    11: "PARTIALLY CHARGED",
}


# ============================================================
# SAFE POWER SHELL EXECUTION
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
            return None

        return result.stdout.strip()

    except (
        subprocess.TimeoutExpired,
        subprocess.SubprocessError,
        OSError
    ):
        return None


# ============================================================
# BASIC BATTERY INFORMATION
# ============================================================

def get_battery_info():

    command = r"""
    $battery = Get-CimInstance Win32_Battery |
        Select-Object `
        Name,
        BatteryStatus,
        EstimatedChargeRemaining,
        EstimatedRunTime,
        Status,
        Availability

    if ($null -eq $battery) {
        Write-Output "NO_BATTERY"
    }
    else {
        $battery | ConvertTo-Json -Compress
    }
    """

    output = run_powershell(command)

    if not output or output == "NO_BATTERY":
        return None

    try:

        data = json.loads(output)

        if isinstance(data, list):
            return data[0]

        return data

    except json.JSONDecodeError:
        return None


# ============================================================
# GENERATE WINDOWS BATTERY REPORT
# ============================================================

def generate_battery_report():

    temp_dir = os.environ.get(
        "TEMP",
        os.getcwd()
    )

    report_path = os.path.join(
        temp_dir,
        "fixmate_battery_report.html"
    )

    command = rf'''
    powercfg /batteryreport /output "{report_path}" | Out-Null

    if (Test-Path "{report_path}") {{
        Write-Output "{report_path}"
    }}
    else {{
        Write-Output "REPORT_FAILED"
    }}
    '''

    output = run_powershell(command)

    if not output:
        return None

    if output == "REPORT_FAILED":
        return None

    return output.strip()


# ============================================================
# HTML BATTERY REPORT PARSER
# Tracks headings + tables
# ============================================================

class BatteryReportParser(HTMLParser):

    def __init__(self):

        super().__init__()

        self.current_heading = None

        self.heading_buffer = ""

        self.in_heading = False

        self.in_table = False
        self.in_row = False
        self.in_cell = False

        self.current_cell = ""
        self.current_row = []
        self.current_table = []

        self.tables = []

    # --------------------------------------------------------
    # START TAG
    # --------------------------------------------------------

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()

        # Headings
        if tag in ("h1", "h2", "h3"):

            self.in_heading = True
            self.heading_buffer = ""

        # Table
        elif tag == "table":

            self.in_table = True
            self.current_table = []

        # Row
        elif tag == "tr" and self.in_table:

            self.in_row = True
            self.current_row = []

        # Cell
        elif tag in ("td", "th") and self.in_row:

            self.in_cell = True
            self.current_cell = ""

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    def handle_data(self, data):

        text = data.strip()

        if not text:
            return

        if self.in_heading:

            self.heading_buffer += " " + text

        elif self.in_cell:

            self.current_cell += " " + text

    # --------------------------------------------------------
    # END TAG
    # --------------------------------------------------------

    def handle_endtag(self, tag):

        tag = tag.lower()

        # Heading finished
        if tag in ("h1", "h2", "h3"):

            heading = " ".join(
                self.heading_buffer.split()
            )

            if heading:
                self.current_heading = heading

            self.heading_buffer = ""
            self.in_heading = False

        # Cell finished
        elif tag in ("td", "th") and self.in_cell:

            text = " ".join(
                self.current_cell.split()
            )

            self.current_row.append(text)

            self.current_cell = ""
            self.in_cell = False

        # Row finished
        elif tag == "tr" and self.in_row:

            if self.current_row:

                self.current_table.append(
                    self.current_row
                )

            self.current_row = []
            self.in_row = False

        # Table finished
        elif tag == "table" and self.in_table:

            if self.current_table:

                self.tables.append({
                    "heading": self.current_heading,
                    "rows": self.current_table
                })

            self.current_table = []
            self.in_table = False


# ============================================================
# LOAD HTML
# ============================================================

def load_report_html(path):

    if not path:
        return None

    if not os.path.exists(path):
        return None

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            return file.read()

    except OSError:
        return None


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize(text):

    if text is None:
        return ""

    return " ".join(
        str(text).lower().split()
    )


def clean_value(value):

    if value is None:
        return None

    return " ".join(
        str(value).split()
    ).strip()


def parse_number(value):

    if not value:
        return None

    match = re.search(
        r"([\d,]+(?:\.\d+)?)",
        str(value)
    )

    if not match:
        return None

    try:

        return float(
            match.group(1).replace(",", "")
        )

    except ValueError:

        return None


# ============================================================
# FIND ROW VALUE
# ============================================================

def find_row_value(rows, label):

    wanted = normalize(label)

    for row in rows:

        if len(row) < 2:
            continue

        first = normalize(row[0])

        if wanted in first:

            return clean_value(
                row[-1]
            )

    return None


# ============================================================
# FIND TABLE
# ============================================================

def find_table(
    tables,
    heading_text
):

    wanted = normalize(
        heading_text
    )

    for table in tables:

        heading = normalize(
            table.get("heading")
        )

        if wanted in heading:

            return table.get(
                "rows",
                []
            )

    return []


# ============================================================
# FIND TABLE USING CONTENT
# Fallback for HTML variations
# ============================================================

def find_table_by_content(
    tables,
    keywords
):

    normalized_keywords = [
        normalize(keyword)
        for keyword in keywords
    ]

    for table in tables:

        rows = table.get(
            "rows",
            []
        )

        text = normalize(
            " ".join(
                " ".join(row)
                for row in rows
            )
        )

        if all(
            keyword in text
            for keyword in normalized_keywords
        ):

            return rows

    return []


# ============================================================
# PARSE BATTERY REPORT
# ============================================================

def parse_battery_report(html):

    parser = BatteryReportParser()

    try:
        parser.feed(html)
    except Exception:
        return {}

    tables = parser.tables

    result = {

        "manufacturer": None,
        "serial_number": None,
        "chemistry": None,

        "design_capacity_mwh": None,
        "full_charge_capacity_mwh": None,
        "cycle_count": None,

        "recent_usage": [],
        "battery_usage": [],
        "usage_history": [],
        "battery_life_estimates": []
    }

    # ========================================================
    # INSTALLED BATTERY
    # ========================================================

    installed = find_table(
        tables,
        "installed batteries"
    )

    if not installed:

        installed = find_table_by_content(
            tables,
            [
                "design capacity",
                "full charge capacity"
            ]
        )

    if installed:

        result["manufacturer"] = (
            find_row_value(
                installed,
                "manufacturer"
            )
        )

        result["serial_number"] = (
            find_row_value(
                installed,
                "serial number"
            )
        )

        result["chemistry"] = (
            find_row_value(
                installed,
                "chemistry"
            )
        )

        design = find_row_value(
            installed,
            "design capacity"
        )

        full = find_row_value(
            installed,
            "full charge capacity"
        )

        cycles = find_row_value(
            installed,
            "cycle count"
        )

        result[
            "design_capacity_mwh"
        ] = parse_number(
            design
        )

        result[
            "full_charge_capacity_mwh"
        ] = parse_number(
            full
        )

        result[
            "cycle_count"
        ] = parse_number(
            cycles
        )

    # ========================================================
    # RECENT USAGE
    # ========================================================

    result[
        "recent_usage"
    ] = find_table(
        tables,
        "recent usage"
    )

    if not result["recent_usage"]:

        result[
            "recent_usage"
        ] = find_table_by_content(
            tables,
            [
                "start time",
                "capacity remaining"
            ]
        )

    # ========================================================
    # BATTERY USAGE
    # ========================================================

    result[
        "battery_usage"
    ] = find_table(
        tables,
        "battery usage"
    )

    if not result["battery_usage"]:

        result[
            "battery_usage"
        ] = find_table_by_content(
            tables,
            [
                "duration",
                "energy drained"
            ]
        )

    # ========================================================
    # USAGE HISTORY
    # ========================================================

    result[
        "usage_history"
    ] = find_table(
        tables,
        "usage history"
    )

    if not result["usage_history"]:

        result[
            "usage_history"
        ] = find_table_by_content(
            tables,
            [
                "battery duration",
                "ac duration"
            ]
        )

    # ========================================================
    # BATTERY LIFE ESTIMATES
    # ========================================================

    result[
        "battery_life_estimates"
    ] = find_table(
        tables,
        "battery life estimates"
    )

    if not result[
        "battery_life_estimates"
    ]:

        result[
            "battery_life_estimates"
        ] = find_table_by_content(
            tables,
            [
                "period"
            ]
        )

    return result


# ============================================================
# HEALTH CALCULATION
# ============================================================

def calculate_health(
    design_capacity,
    full_charge_capacity
):

    if design_capacity is None:
        return None

    if full_charge_capacity is None:
        return None

    if design_capacity <= 0:
        return None

    health = (
        full_charge_capacity
        / design_capacity
    ) * 100

    health = min(
        100,
        max(0, health)
    )

    return round(
        health,
        1
    )


# ============================================================
# HEALTH STATUS
# ============================================================

def classify_health(
    health
):

    if health is None:

        return (
            "UNKNOWN",
            "Battery health could not be calculated."
        )

    if health >= 95:

        return (
            "EXCELLENT",
            "Battery capacity is very close to its design capacity."
        )

    if health >= 85:

        return (
            "GOOD",
            "Battery capacity is within a healthy range."
        )

    if health >= 70:

        return (
            "FAIR",
            "Battery shows noticeable capacity degradation."
        )

    if health >= 50:

        return (
            "POOR",
            "Battery capacity has significantly degraded."
        )

    return (
        "CRITICAL",
        "Battery capacity is severely degraded."
    )


# ============================================================
# CHARGE STATUS
# ============================================================

def classify_charge(
    charge
):

    if charge is None:
        return "UNKNOWN"

    try:
        charge = float(charge)
    except (
        TypeError,
        ValueError
    ):
        return "UNKNOWN"

    if charge <= 10:
        return "CRITICAL"

    if charge <= 20:
        return "LOW"

    if charge <= 30:
        return "MODERATE"

    return "NORMAL"


# ============================================================
# RUNTIME VALIDATION
# ============================================================

def validate_runtime(
    runtime
):

    if runtime is None:
        return None

    try:
        runtime = int(float(runtime))
    except (
        TypeError,
        ValueError
    ):
        return None

    # Windows may return very large sentinel values
    # when a runtime estimate is unavailable.
    #
    # A laptop runtime above 24 hours is treated as
    # unavailable rather than displaying a bogus value.

    if runtime <= 0:
        return None

    if runtime > 1440:
        return None

    return runtime


# ============================================================
# POWER SOURCE / CHARGING STATE
# ============================================================

def get_power_state(
    battery_status
):

    try:
        status = int(
            battery_status
        )
    except (
        TypeError,
        ValueError
    ):
        return {
            "status": "UNKNOWN",
            "charging_confirmed": False
        }

    name = BATTERY_STATUS_MAP.get(
        status,
        "UNKNOWN"
    )

    if status in (
        6,
        7,
        8,
        9
    ):

        return {
            "status": name,
            "charging_confirmed": True
        }

    if status == 2:

        return {
            "status": "AC CONNECTED",
            "charging_confirmed": False
        }

    if status == 3:

        return {
            "status": "FULLY CHARGED",
            "charging_confirmed": False
        }

    if status == 1:

        return {
            "status": "DISCHARGING",
            "charging_confirmed": False
        }

    return {
        "status": name,
        "charging_confirmed": False
    }


# ============================================================
# BATTERY DIAGNOSIS
# ============================================================

def diagnose_battery():

    battery = get_battery_info()

    report_path = (
        generate_battery_report()
    )

    result = {

        "available": False,

        "battery_name": "Unknown",

        "manufacturer": None,
        "serial_number": None,
        "chemistry": None,

        "battery_status_code": None,

        "power_state": "UNKNOWN",
        "charging_confirmed": False,

        "charge_percent": None,
        "charge_status": "UNKNOWN",

        "estimated_runtime_minutes": None,

        "design_capacity_mwh": None,
        "full_charge_capacity_mwh": None,

        "battery_health_percent": None,
        "wear_percent": None,

        "cycle_count": None,

        "health_status": "UNKNOWN",
        "health_message":
            "Battery health could not be determined.",

        "recent_usage": [],
        "battery_usage": [],
        "usage_history": [],
        "battery_life_estimates": [],

        "report_path": report_path,

        "confidence": "LOW",

        "hardware_fault": False,

        "assessment": "",

        "recommendations": []
    }

    # ========================================================
    # NO BATTERY
    # ========================================================

    if not battery:

        result["assessment"] = (
            "No battery information is available "
            "through Windows."
        )

        return result

    result["available"] = True

    result["battery_name"] = battery.get(
        "Name",
        "Unknown"
    )

    result[
        "manufacturer"
    ] = None

    result[
        "battery_status_code"
    ] = battery.get(
        "BatteryStatus"
    )

    power_state = get_power_state(
        battery.get("BatteryStatus")
    )

    result[
        "power_state"
    ] = power_state[
        "status"
    ]

    result[
        "charging_confirmed"
    ] = power_state[
        "charging_confirmed"
    ]

    # --------------------------------------------------------
    # Charge
    # --------------------------------------------------------

    charge = battery.get(
        "EstimatedChargeRemaining"
    )

    try:

        result[
            "charge_percent"
        ] = float(charge)

    except (
        TypeError,
        ValueError
    ):

        result[
            "charge_percent"
        ] = None

    result[
        "charge_status"
    ] = classify_charge(
        result["charge_percent"]
    )

    # --------------------------------------------------------
    # Runtime
    # --------------------------------------------------------

    result[
        "estimated_runtime_minutes"
    ] = validate_runtime(
        battery.get(
            "EstimatedRunTime"
        )
    )

    # ========================================================
    # PARSE BATTERY REPORT
    # ========================================================

    html = load_report_html(
        report_path
    )

    if html:

        parsed = parse_battery_report(
            html
        )

        for key in (
            "manufacturer",
            "serial_number",
            "chemistry",
            "design_capacity_mwh",
            "full_charge_capacity_mwh",
            "cycle_count",
            "recent_usage",
            "battery_usage",
            "usage_history",
            "battery_life_estimates"
        ):

            result[key] = parsed.get(
                key
            )

    # ========================================================
    # CALCULATE HEALTH
    # ========================================================

    health = calculate_health(
        result[
            "design_capacity_mwh"
        ],
        result[
            "full_charge_capacity_mwh"
        ]
    )

    result[
        "battery_health_percent"
    ] = health

    if health is not None:

        result[
            "wear_percent"
        ] = round(
            100 - health,
            1
        )

    (
        result[
            "health_status"
        ],
        result[
            "health_message"
        ]
    ) = classify_health(
        health
    )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    if (
        result[
            "design_capacity_mwh"
        ] is not None
        and result[
            "full_charge_capacity_mwh"
        ] is not None
        and health is not None
    ):

        result[
            "confidence"
        ] = "HIGH"

    elif result["available"]:

        result[
            "confidence"
        ] = "MEDIUM"

    # ========================================================
    # HARDWARE FAULT DECISION
    # ========================================================

    if health is not None:

        if health < 50:

            result[
                "hardware_fault"
            ] = True

            result[
                "assessment"
            ] = (
                "Battery capacity is severely degraded. "
                "Battery replacement should be considered."
            )

            result[
                "recommendations"
            ] = [
                "Back up important data.",
                "Confirm the condition with manufacturer diagnostics.",
                "Consider battery replacement."
            ]

        elif health < 70:

            result[
                "assessment"
            ] = (
                "Battery capacity has significant degradation. "
                "Reduced runtime is expected."
            )

            result[
                "recommendations"
            ] = [
                "Monitor battery runtime.",
                "Check manufacturer battery diagnostics.",
                "Consider replacement if runtime becomes insufficient."
            ]

        elif health < 85:

            result[
                "assessment"
            ] = (
                "Battery capacity shows moderate degradation, "
                "but no immediate hardware fault is indicated."
            )

            result[
                "recommendations"
            ] = [
                "Monitor battery health over time.",
                "Avoid prolonged high-temperature operation.",
                "Consider battery replacement if runtime becomes inadequate."
            ]

        else:

            result[
                "assessment"
            ] = (
                "Battery capacity is within a healthy range. "
                "No direct battery hardware fault is indicated "
                "by the available capacity data."
            )

            result[
                "recommendations"
            ] = [
                "Continue normal battery usage.",
                "Monitor battery capacity over time.",
                "Avoid unnecessary prolonged high-temperature operation."
            ]

    else:

        result[
            "assessment"
        ] = (
            "Basic battery information is available, "
            "but battery health could not be calculated "
            "from the Windows battery report."
        )

        result[
            "recommendations"
        ] = [
            "Open the generated Windows battery report.",
            "Use manufacturer diagnostics for deeper battery testing."
        ]

    return result


# ============================================================
# FORMAT HELPERS
# ============================================================

def format_mwh(value):

    if value is None:
        return "Unavailable"

    return f"{value:,.0f} mWh"


def format_number(value):

    if value is None:
        return "Unavailable"

    if isinstance(
        value,
        float
    ) and value.is_integer():

        return str(
            int(value)
        )

    return str(value)


# ============================================================
# TABLE PRINTER
# ============================================================

def print_report_table(
    rows,
    title
):

    if not rows:
        return

    print("\n" + title)
    print("-" * 90)

    for row in rows:

        if not row:
            continue

        print(
            " | ".join(
                str(cell)
                for cell in row
            )
        )


# ============================================================
# PRINT COMPLETE BATTERY REPORT
# ============================================================

def print_battery_report(
    result
):

    print("\n")
    print("=" * 70)
    print("                 FIXMATE BATTERY DIAGNOSIS")
    print("=" * 70)

    # ========================================================
    # AVAILABILITY
    # ========================================================

    if not result["available"]:

        print(
            "\nBattery information is not available."
        )

        print("=" * 70)

        return

    # ========================================================
    # BATTERY INFORMATION
    # ========================================================

    print("\n[ BATTERY INFORMATION ]")
    print("-" * 70)

    print(
        f"Battery Name            : "
        f"{result['battery_name']}"
    )

    print(
        f"Manufacturer            : "
        f"{result.get('manufacturer') or 'Unavailable'}"
    )

    print(
        f"Serial Number           : "
        f"{result.get('serial_number') or 'Unavailable'}"
    )

    print(
        f"Chemistry               : "
        f"{result.get('chemistry') or 'Unavailable'}"
    )

    print(
        f"Battery Status Code     : "
        f"{result.get('battery_status_code') or 'Unknown'}"
    )

    print(
        f"Power State             : "
        f"{result['power_state']}"
    )

    print(
        f"Charging Confirmed      : "
        f"{'YES' if result['charging_confirmed'] else 'NO'}"
    )

    # ========================================================
    # CURRENT STATE
    # ========================================================

    print("\n[ CURRENT BATTERY STATE ]")
    print("-" * 70)

    if result["charge_percent"] is None:

        print(
            "Charge                  : Unavailable"
        )

    else:

        print(
            f"Charge                  : "
            f"{result['charge_percent']:.0f}%"
        )

    print(
        f"Charge Status           : "
        f"{result['charge_status']}"
    )

    if result[
        "estimated_runtime_minutes"
    ] is None:

        print(
            "Estimated Runtime       : "
            "Unavailable"
        )

    else:

        runtime = result[
            "estimated_runtime_minutes"
        ]

        hours = runtime // 60
        minutes = runtime % 60

        print(
            f"Estimated Runtime       : "
            f"{hours}h {minutes}m "
            f"({runtime} minutes)"
        )

    # ========================================================
    # CAPACITY HEALTH
    # ========================================================

    print("\n[ BATTERY CAPACITY HEALTH ]")
    print("-" * 70)

    print(
        f"Design Capacity         : "
        f"{format_mwh(result['design_capacity_mwh'])}"
    )

    print(
        f"Full Charge Capacity    : "
        f"{format_mwh(result['full_charge_capacity_mwh'])}"
    )

    if result[
        "battery_health_percent"
    ] is None:

        print(
            "Battery Health          : "
            "Unavailable"
        )

        print(
            "Wear Level              : "
            "Unavailable"
        )

    else:

        print(
            f"Battery Health          : "
            f"{result['battery_health_percent']:.1f}%"
        )

        print(
            f"Wear Level              : "
            f"{result['wear_percent']:.1f}%"
        )

    print(
        f"Cycle Count             : "
        f"{format_number(result['cycle_count'])}"
    )

    # ========================================================
    # DIAGNOSIS
    # ========================================================

    print("\n[ BATTERY DIAGNOSIS ]")
    print("-" * 70)

    print(
        f"Health Status           : "
        f"{result['health_status']}"
    )

    print(
        f"Confidence              : "
        f"{result['confidence']}"
    )

    print(
        f"Hardware Fault          : "
        f"{'YES' if result['hardware_fault'] else 'NO'}"
    )

    print(
        f"\nHealth Message:\n"
        f"{result['health_message']}"
    )

    print(
        f"\nAssessment:\n"
        f"{result['assessment']}"
    )

    # ========================================================
    # RECOMMENDATIONS
    # ========================================================

    if result["recommendations"]:

        print(
            "\nRecommendations:"
        )

        for item in result[
            "recommendations"
        ]:

            print(
                f"- {item}"
            )

    # ========================================================
    # RECENT USAGE
    # ========================================================

    print_report_table(
        result["recent_usage"],
        "[ RECENT USAGE ]"
    )

    # ========================================================
    # BATTERY USAGE
    # ========================================================

    print_report_table(
        result["battery_usage"],
        "[ BATTERY USAGE / DRAIN ]"
    )

    # ========================================================
    # USAGE HISTORY
    # ========================================================

    print_report_table(
        result["usage_history"],
        "[ USAGE HISTORY ]"
    )

    # ========================================================
    # LIFE ESTIMATES
    # ========================================================

    print_report_table(
        result["battery_life_estimates"],
        "[ BATTERY LIFE ESTIMATES ]"
    )

    # ========================================================
    # REPORT FILE
    # ========================================================

    if result["report_path"]:

        print(
            "\n[ WINDOWS BATTERY REPORT ]"
        )

        print("-" * 70)

        print(
            result["report_path"]
        )

    print("\n" + "=" * 70)
    print("             END OF BATTERY DIAGNOSIS")
    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    result = diagnose_battery()

    print_battery_report(
        result
    )