import psutil
from collections import defaultdict


FRIENDLY_NAMES = {
    "code.exe": "Visual Studio Code",
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "msedgewebview2.exe": "Microsoft Edge WebView2",
    "explorer.exe": "Windows Explorer",
    "powershell.exe": "PowerShell",
    "cmd.exe": "Command Prompt",
    "python.exe": "Python",
    "msmpeng.exe": "Microsoft Defender",
    "nvdisplay.container.exe": "NVIDIA Container",
    "mspcmanager.exe": "Microsoft PC Manager",
    "mspcmanagercore.exe": "Microsoft PC Manager Core",
    "mspcmanagerservice.exe": "Microsoft PC Manager Service",
}


SYSTEM_PROCESSES = {
    "svchost.exe",
    "system",
    "csrss.exe",
    "lsass.exe",
    "services.exe",
    "wininit.exe",
    "winlogon.exe",
    "smss.exe",
    "runtimebroker.exe",
    "wudfhost.exe",
}


def friendly_name(name):
    return FRIENDLY_NAMES.get(name.lower(), name)


def get_severity(memory_percent, cpu_percent, process_name):

    name = process_name.lower()

    # Windows host processes need different treatment
    if name in SYSTEM_PROCESSES:
        return "SYSTEM"

    if memory_percent >= 20 or cpu_percent >= 50:
        return "CRITICAL"

    if memory_percent >= 10 or cpu_percent >= 25:
        return "HIGH"

    if memory_percent >= 5 or cpu_percent >= 10:
        return "MODERATE"

    return "NORMAL"


def analyze_processes(limit=15):

    processes = []

    current_pid = psutil.Process().pid
    logical_cpus = psutil.cpu_count(logical=True) or 1

    # Initialize CPU measurement
    for process in psutil.process_iter(["pid", "name"]):
        try:
            process.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    psutil.cpu_percent(interval=0.5)

    for process in psutil.process_iter(
        ["pid", "name", "memory_percent", "memory_info"]
    ):
        try:

            pid = process.info["pid"]
            name = process.info["name"] or "Unknown"

            if pid == current_pid:
                continue

            if name.lower() in [
                "system idle process",
                "idle"
            ]:
                continue

            raw_cpu = process.cpu_percent(interval=None)
            cpu_percent = raw_cpu / logical_cpus

            memory_percent = process.info["memory_percent"] or 0

            memory_mb = 0

            if process.info["memory_info"]:
                memory_mb = (
                    process.info["memory_info"].rss
                    / (1024 ** 2)
                )

            processes.append({
                "pid": pid,
                "name": name,
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_mb": memory_mb
            })

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess
        ):
            continue

    grouped = defaultdict(
        lambda: {
            "cpu_percent": 0,
            "memory_percent": 0,
            "memory_mb": 0,
            "process_count": 0
        }
    )

    for process in processes:

        name = process["name"]

        grouped[name]["cpu_percent"] += process["cpu_percent"]
        grouped[name]["memory_percent"] += process["memory_percent"]
        grouped[name]["memory_mb"] += process["memory_mb"]
        grouped[name]["process_count"] += 1

    applications = []

    for name, data in grouped.items():

        severity = get_severity(
            data["memory_percent"],
            data["cpu_percent"],
            name
        )

        applications.append({
            "process_name": name,
            "display_name": friendly_name(name),
            "cpu_percent": round(data["cpu_percent"], 1),
            "memory_percent": round(data["memory_percent"], 2),
            "memory_mb": round(data["memory_mb"], 1),
            "process_count": data["process_count"],
            "severity": severity
        })

    top_memory = sorted(
        applications,
        key=lambda x: x["memory_mb"],
        reverse=True
    )[:limit]

    top_cpu = sorted(
        applications,
        key=lambda x: x["cpu_percent"],
        reverse=True
    )[:limit]

    return top_cpu, top_memory


def print_report():

    top_cpu, top_memory = analyze_processes()

    print("\n========== FIXMATE PROCESS ANALYSIS ==========\n")

    print("TOP APPLICATIONS BY MEMORY\n")
    print("-" * 75)

    for app in top_memory:

        print(
            f"{app['display_name']:<30} "
            f"RAM: {app['memory_mb']:>8.1f} MB  "
            f"CPU: {app['cpu_percent']:>5}%  "
            f"Processes: {app['process_count']:>3}  "
            f"Status: {app['severity']}"
        )

    print("\n\nTOP APPLICATIONS BY CPU\n")
    print("-" * 75)

    for app in top_cpu:

        print(
            f"{app['display_name']:<30} "
            f"CPU: {app['cpu_percent']:>5}%  "
            f"RAM: {app['memory_mb']:>8.1f} MB  "
            f"Processes: {app['process_count']:>3}  "
            f"Status: {app['severity']}"
        )

    print("\n==============================================")


if __name__ == "__main__":
    print_report()