import psutil


def get_top_processes(limit=10):
    processes = []

    # Start CPU measurement
    for process in psutil.process_iter(["pid", "name"]):
        try:
            process.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Wait for measurement interval
    psutil.cpu_percent(interval=0.5)

    logical_cpus = psutil.cpu_count(logical=True) or 1

    for process in psutil.process_iter(
        ["pid", "name", "memory_percent", "memory_info"]
    ):
        try:
            pid = process.info["pid"]
            name = process.info["name"] or "Unknown"

            # Don't include FixMate's own Python process
            if pid == psutil.Process().pid:
                continue

            raw_cpu = process.cpu_percent(interval=None)

            # Normalize CPU usage to total system capacity
            cpu = raw_cpu / logical_cpus

            memory = process.info["memory_percent"] or 0

            memory_mb = 0

            if process.info["memory_info"]:
                memory_mb = (
                    process.info["memory_info"].rss
                    / (1024 ** 2)
                )

            processes.append({
                "pid": pid,
                "name": name,
                "cpu_percent": round(cpu, 1),
                "memory_percent": round(memory, 2),
                "memory_mb": round(memory_mb, 1)
            })

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess
        ):
            continue

    top_cpu = sorted(
        processes,
        key=lambda x: x["cpu_percent"],
        reverse=True
    )[:limit]

    top_memory = sorted(
        processes,
        key=lambda x: x["memory_percent"],
        reverse=True
    )[:limit]

    return top_cpu, top_memory


if __name__ == "__main__":

    top_cpu, top_memory = get_top_processes()

    print("\n========== TOP CPU PROCESSES ==========\n")

    for process in top_cpu:
        print(
            f"{process['name']:<35} "
            f"CPU: {process['cpu_percent']:>5}%  "
            f"RAM: {process['memory_mb']:>7.1f} MB"
        )

    print("\n========== TOP MEMORY PROCESSES ==========\n")

    for process in top_memory:
        print(
            f"{process['name']:<35} "
            f"RAM: {process['memory_mb']:>7.1f} MB  "
            f"({process['memory_percent']:>5}%)"
        )

    print("\n========================================")