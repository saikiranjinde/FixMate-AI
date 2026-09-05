import subprocess
import shutil


def check_nvidia_smi():
    return shutil.which("nvidia-smi") is not None


def safe_float(value):
    """
    Convert NVIDIA SMI value to float.
    Returns None when NVIDIA reports N/A.
    """
    if value is None:
        return None

    value = str(value).strip()

    if value.upper() in ["N/A", "[N/A]", "NA", "[NOT SUPPORTED]"]:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def safe_string(value):
    if value is None:
        return "N/A"

    value = str(value).strip()

    if value.upper() in ["[N/A]", "N/A", "NA", "[NOT SUPPORTED]"]:
        return "N/A"

    return value


def get_gpu_info():

    if not check_nvidia_smi():

        return {
            "available": False,
            "error": "nvidia-smi is not available."
        }

    command = [
        "nvidia-smi",

        "--query-gpu="
        "name,"
        "temperature.gpu,"
        "utilization.gpu,"
        "memory.total,"
        "memory.used,"
        "memory.free,"
        "power.draw,"
        "power.limit,"
        "clocks.current.graphics,"
        "clocks.current.memory,"
        "driver_version",

        "--format=csv,noheader,nounits"
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:

            return {
                "available": False,
                "error": result.stderr.strip()
            }

        output = result.stdout.strip()

        if not output:

            return {
                "available": False,
                "error": "No GPU data returned."
            }

        # Only use the first GPU for now
        line = output.splitlines()[0]

        values = [
            value.strip()
            for value in line.split(",")
        ]

        if len(values) < 11:

            return {
                "available": False,
                "error": "Incomplete GPU information."
            }

        return {

            "available": True,

            "name": safe_string(values[0]),

            "temperature_c": safe_float(values[1]),

            "utilization_percent": safe_float(values[2]),

            "memory_total_mb": safe_float(values[3]),

            "memory_used_mb": safe_float(values[4]),

            "memory_free_mb": safe_float(values[5]),

            "power_draw_w": safe_float(values[6]),

            "power_limit_w": safe_float(values[7]),

            "graphics_clock_mhz": safe_float(values[8]),

            "memory_clock_mhz": safe_float(values[9]),

            "driver_version": safe_string(values[10])
        }

    except FileNotFoundError:

        return {
            "available": False,
            "error": "nvidia-smi command not found."
        }

    except subprocess.TimeoutExpired:

        return {
            "available": False,
            "error": "GPU query timed out."
        }

    except Exception as e:

        return {
            "available": False,
            "error": str(e)
        }


def classify_gpu_temperature(temp):

    if temp is None:
        return "UNKNOWN"

    if temp >= 90:
        return "CRITICAL"

    if temp >= 80:
        return "HIGH"

    if temp >= 70:
        return "WARM"

    return "NORMAL"


def run_gpu_diagnostic():

    gpu = get_gpu_info()

    if not gpu["available"]:
        return gpu

    gpu["temperature_status"] = classify_gpu_temperature(
        gpu["temperature_c"]
    )

    power_draw = gpu["power_draw_w"]
    power_limit = gpu["power_limit_w"]

    if (
        power_draw is not None
        and power_limit is not None
        and power_limit > 0
    ):

        gpu["power_usage_percent"] = round(
            (power_draw / power_limit) * 100,
            1
        )

    else:

        gpu["power_usage_percent"] = None

    return gpu


def display_value(value, unit=""):

    if value is None:
        return "N/A"

    return f"{value}{unit}"


if __name__ == "__main__":

    print("\n========== FIXMATE GPU DIAGNOSTIC ==========\n")

    gpu = run_gpu_diagnostic()

    if not gpu["available"]:

        print("NVIDIA GPU telemetry unavailable.")
        print(f"Reason: {gpu['error']}")

    else:

        print(
            f"GPU              : "
            f"{gpu['name']}"
        )

        print(
            f"Driver           : "
            f"{gpu['driver_version']}"
        )

        print(
            f"Temperature      : "
            f"{display_value(gpu['temperature_c'], ' °C')}"
        )

        print(
            f"Temperature Status: "
            f"{gpu['temperature_status']}"
        )

        print(
            f"GPU Usage        : "
            f"{display_value(gpu['utilization_percent'], ' %')}"
        )

        print(
            f"VRAM             : "
            f"{display_value(gpu['memory_used_mb'], ' MB')} / "
            f"{display_value(gpu['memory_total_mb'], ' MB')}"
        )

        print(
            f"Power            : "
            f"{display_value(gpu['power_draw_w'], ' W')} / "
            f"{display_value(gpu['power_limit_w'], ' W')}"
        )

        print(
            f"Power Usage      : "
            f"{display_value(gpu['power_usage_percent'], ' %')}"
        )

        print(
            f"Graphics Clock   : "
            f"{display_value(gpu['graphics_clock_mhz'], ' MHz')}"
        )

        print(
            f"Memory Clock     : "
            f"{display_value(gpu['memory_clock_mhz'], ' MHz')}"
        )

    print("\n============================================")