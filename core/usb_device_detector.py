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

        data = json.loads(output)

        if isinstance(data, dict):
            return [data]

        return data

    except Exception:
        return []


def get_usb_devices():

    command = r"""
    Get-PnpDevice |
    Where-Object {
        $_.InstanceId -like 'USB\*' -or
        $_.InstanceId -like 'USBSTOR\*' -or
        $_.FriendlyName -match 'Android|MTP|ADB|NDIS|iPhone|iPad|Apple Mobile'
    } |
    Select-Object Status,
                  Class,
                  FriendlyName,
                  Manufacturer,
                  InstanceId,
                  ProblemCode |
    ConvertTo-Json -Depth 3
    """

    return run_powershell(command)


def classify_device(device):

    name = str(
        device.get("FriendlyName", "")
    ).lower()

    device_class = str(
        device.get("Class", "")
    ).lower()

    manufacturer = str(
        device.get("Manufacturer", "")
    ).lower()

    instance_id = str(
        device.get("InstanceId", "")
    ).lower()

    text = (
        name + " "
        + device_class + " "
        + manufacturer + " "
        + instance_id
    )

    # ==========================================
    # ANDROID / MOBILE
    # ==========================================

    android_keywords = [
        "android",
        "adb",
        "android composite",
        "android adb interface",
        "mtp",
        "portable device",
        "mobile",
        "remote ndis",
        "rndis",
        "internet sharing",
        "usb tethering"
    ]

    if any(
        keyword in text
        for keyword in android_keywords
    ):

        return "ANDROID / MOBILE DEVICE"

    # ==========================================
    # APPLE
    # ==========================================

    apple_keywords = [
        "iphone",
        "ipad",
        "apple mobile",
        "apple inc",
        "apple"
    ]

    if any(
        keyword in text
        for keyword in apple_keywords
    ):

        return "APPLE DEVICE"

    # ==========================================
    # USB STORAGE
    # ==========================================

    storage_keywords = [
        "mass storage",
        "usb storage",
        "flash drive",
        "disk drive",
        "usbstor"
    ]

    if any(
        keyword in text
        for keyword in storage_keywords
    ):

        return "USB STORAGE"

    # ==========================================
    # KEYBOARD
    # ==========================================

    if (
        "keyboard" in text
        or device_class == "hidclass"
        and "input" in name
    ):

        return "KEYBOARD / INPUT DEVICE"

    # ==========================================
    # MOUSE
    # ==========================================

    if "mouse" in text:

        return "MOUSE"

    # ==========================================
    # CAMERA
    # ==========================================

    camera_keywords = [
        "camera",
        "webcam",
        "imaging"
    ]

    if any(
        keyword in text
        for keyword in camera_keywords
    ):

        return "CAMERA"

    # ==========================================
    # AUDIO
    # ==========================================

    audio_keywords = [
        "audio",
        "headset",
        "microphone",
        "speaker"
    ]

    if any(
        keyword in text
        for keyword in audio_keywords
    ):

        return "AUDIO DEVICE"

    # ==========================================
    # NETWORK
    # ==========================================

    network_keywords = [
        "network",
        "ethernet",
        "wireless",
        "wifi"
    ]

    if any(
        keyword in text
        for keyword in network_keywords
    ):

        return "NETWORK DEVICE"

    return "USB DEVICE"


def get_device_status(device):

    status = str(
        device.get("Status", "")
    ).lower()

    problem_code = device.get(
        "ProblemCode"
    )

    if status == "ok":

        return "NORMAL"

    if (
        problem_code is not None
        and str(problem_code) not in [
            "0",
            "None",
            ""
        ]
    ):

        return "PROBLEM DETECTED"

    if status:

        return status.upper()

    return "UNKNOWN"


def analyze_usb_devices():

    devices = get_usb_devices()

    results = []

    for device in devices:

        category = classify_device(
            device
        )

        results.append({

            "name": device.get(
                "FriendlyName",
                "Unknown Device"
            ),

            "manufacturer": device.get(
                "Manufacturer",
                "Unknown"
            ),

            "class": device.get(
                "Class",
                "Unknown"
            ),

            "category": category,

            "status": get_device_status(
                device
            ),

            "problem_code": device.get(
                "ProblemCode"
            ),

            "instance_id": device.get(
                "InstanceId",
                "Unknown"
            )
        })

    return results


def print_usb_report():

    print(
        "\n========== FIXMATE USB DEVICE DETECTOR V2 ==========\n"
    )

    devices = analyze_usb_devices()

    if not devices:

        print(
            "No supported USB devices detected."
        )

        print(
            "\nConnect a USB device and run "
            "the scan again."
        )

        return

    print(
        f"Detected devices: {len(devices)}\n"
    )

    for index, device in enumerate(
        devices,
        start=1
    ):

        print(
            f"Device #{index}"
        )

        print("-" * 55)

        print(
            f"Name         : "
            f"{device['name']}"
        )

        print(
            f"Manufacturer : "
            f"{device['manufacturer']}"
        )

        print(
            f"Class        : "
            f"{device['class']}"
        )

        print(
            f"Category     : "
            f"{device['category']}"
        )

        print(
            f"Status       : "
            f"{device['status']}"
        )

        print(
            f"Problem Code : "
            f"{device['problem_code']}"
        )

        print()


if __name__ == "__main__":

    print_usb_report()

    print(
        "===================================================="
    )