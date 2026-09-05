import subprocess
import json


def run_powershell(command):
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
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

    except Exception as e:
        return {"error": str(e)}


def get_gpu_info():
    command = """
    Get-CimInstance Win32_VideoController |
    Select-Object Name, AdapterRAM, DriverVersion, VideoProcessor |
    ConvertTo-Json
    """

    data = run_powershell(command)

    if isinstance(data, dict):
        data = [data]

    return data


def get_motherboard_info():
    command = """
    Get-CimInstance Win32_BaseBoard |
    Select-Object Manufacturer, Product, Version, SerialNumber |
    ConvertTo-Json
    """

    data = run_powershell(command)

    if isinstance(data, dict):
        data = [data]

    return data


def get_storage_info():
    command = """
    Get-PhysicalDisk |
    Select-Object FriendlyName, MediaType, Size, HealthStatus, OperationalStatus |
    ConvertTo-Json
    """

    data = run_powershell(command)

    if isinstance(data, dict):
        data = [data]

    return data


def get_battery_info():
    command = """
    Get-CimInstance Win32_Battery |
    Select-Object Name, BatteryStatus, EstimatedChargeRemaining, EstimatedRunTime |
    ConvertTo-Json
    """

    data = run_powershell(command)

    if isinstance(data, dict):
        data = [data]

    return data


def get_hardware_info():
    return {
        "GPU": get_gpu_info(),
        "Motherboard": get_motherboard_info(),
        "Storage": get_storage_info(),
        "Battery": get_battery_info()
    }


if __name__ == "__main__":

    hardware = get_hardware_info()

    print("\n========== FIXMATE HARDWARE INFORMATION ==========\n")

    print("GPU:")
    print(json.dumps(hardware["GPU"], indent=4))

    print("\nMotherboard:")
    print(json.dumps(hardware["Motherboard"], indent=4))

    print("\nStorage:")
    print(json.dumps(hardware["Storage"], indent=4))

    print("\nBattery:")
    print(json.dumps(hardware["Battery"], indent=4))

    print("\n==================================================")