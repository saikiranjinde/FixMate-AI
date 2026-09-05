import subprocess
import json


def run_powershell(command):
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                command
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode != 0:
            return []

        output = result.stdout.strip()

        if not output:
            return []

        return json.loads(output)

    except Exception:
        return []


def get_temperature_sensors():

    # Windows ACPI thermal zone sensors
    command = """
    Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature |
    Select-Object InstanceName, CurrentTemperature, CriticalTripPoint |
    ConvertTo-Json
    """

    data = run_powershell(command)

    if isinstance(data, dict):
        data = [data]

    sensors = []

    for sensor in data:

        try:
            raw_temperature = sensor.get("CurrentTemperature")

            if raw_temperature is None:
                continue

            # ACPI temperature is usually stored in tenths of Kelvin
            celsius = (float(raw_temperature) / 10) - 273.15

            critical_raw = sensor.get("CriticalTripPoint")

            critical_celsius = None

            if critical_raw:
                critical_celsius = (
                    float(critical_raw) / 10
                ) - 273.15

            sensors.append({
                "sensor": sensor.get(
                    "InstanceName",
                    "Unknown"
                ),
                "temperature_c": round(
                    celsius,
                    1
                ),
                "critical_temperature_c": (
                    round(critical_celsius, 1)
                    if critical_celsius is not None
                    else None
                )
            })

        except (TypeError, ValueError):
            continue

    return sensors


def classify_temperature(temp):

    if temp is None:
        return "UNKNOWN"

    if temp >= 95:
        return "CRITICAL"

    if temp >= 90:
        return "HIGH"

    if temp >= 80:
        return "WARM"

    return "NORMAL"


def run_thermal_diagnostic():

    sensors = get_temperature_sensors()

    results = []

    for sensor in sensors:

        temperature = sensor["temperature_c"]

        status = classify_temperature(
            temperature
        )

        results.append({
            "sensor": sensor["sensor"],
            "temperature_c": temperature,
            "critical_temperature_c": sensor[
                "critical_temperature_c"
            ],
            "status": status
        })

    return results


if __name__ == "__main__":

    print("\n========== FIXMATE THERMAL DIAGNOSTIC ==========\n")

    results = run_thermal_diagnostic()

    if not results:

        print(
            "Temperature sensor data is not available "
            "through Windows ACPI."
        )

        print(
            "\nThis does NOT mean the device has a "
            "temperature problem."
        )

    else:

        for result in results:

            print(
                f"Sensor       : {result['sensor']}"
            )

            print(
                f"Temperature  : "
                f"{result['temperature_c']} °C"
            )

            print(
                f"Critical     : "
                f"{result['critical_temperature_c']} °C"
            )

            print(
                f"Status       : "
                f"{result['status']}"
            )

            print("-" * 50)

    print(
        "\n================================================="
    )