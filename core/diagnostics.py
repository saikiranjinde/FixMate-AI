import psutil


def check_memory():
    memory = psutil.virtual_memory()

    result = {
        "type": "Memory",
        "total_gb": round(memory.total / (1024 ** 3), 2),
        "used_gb": round(memory.used / (1024 ** 3), 2),
        "available_gb": round(memory.available / (1024 ** 3), 2),
        "usage_percent": memory.percent,
        "status": "NORMAL",
        "message": ""
    }

    if memory.percent >= 95:
        result["status"] = "CRITICAL"
        result["message"] = (
            "Very high memory usage detected. "
            "The system may experience severe slowdown."
        )

    elif memory.percent >= 85:
        result["status"] = "HIGH"
        result["message"] = (
            "High memory usage detected. "
            "Check applications and background processes."
        )

    elif memory.percent >= 70:
        result["status"] = "MODERATE"
        result["message"] = (
            "Memory usage is moderately high."
        )

    else:
        result["message"] = (
            "Memory usage is within the normal range."
        )

    return result


def check_cpu():
    usage = psutil.cpu_percent(interval=1)

    result = {
        "type": "CPU",
        "usage_percent": usage,
        "status": "NORMAL",
        "message": ""
    }

    if usage >= 95:
        result["status"] = "HIGH"
        result["message"] = (
            "Very high CPU usage detected."
        )

    elif usage >= 80:
        result["status"] = "MODERATE"
        result["message"] = (
            "High CPU usage detected."
        )

    else:
        result["message"] = (
            "CPU usage is within the normal range."
        )

    return result


def run_diagnostics():
    return {
        "memory": check_memory(),
        "cpu": check_cpu()
    }


if __name__ == "__main__":

    results = run_diagnostics()

    print("\n========== FIXMATE DIAGNOSTICS ==========\n")

    for name, result in results.items():

        print(f"{result['type']}")
        print("-" * 30)

        for key, value in result.items():
            print(f"{key}: {value}")

        print()

    print("=========================================")