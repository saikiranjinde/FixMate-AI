import socket
import subprocess
import re
from typing import Dict, Any, List


def run_command(command: List[str]) -> str:
    """
    Run a Windows command safely and return stdout.
    """
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=15
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_network_adapters() -> List[Dict[str, Any]]:
    """
    Collect active network adapters using PowerShell.
    """
    output = run_command([
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Get-NetAdapter | "
            "Select-Object Name, InterfaceDescription, Status, LinkSpeed, MacAddress | "
            "ConvertTo-Json -Compress"
        )
    ])

    if not output:
        return []

    try:
        import json

        data = json.loads(output)

        if isinstance(data, dict):
            data = [data]

        adapters = []

        for item in data:
            adapters.append({
                "name": item.get("Name"),
                "description": item.get("InterfaceDescription"),
                "status": item.get("Status"),
                "link_speed": item.get("LinkSpeed"),
                "mac_address": item.get("MacAddress"),
            })

        return adapters

    except Exception:
        return []


def get_ip_configuration() -> Dict[str, Any]:
    """
    Collect IP, gateway and DNS information.
    """
    output = run_command([
        "ipconfig",
        "/all"
    ])

    if not output:
        return {
            "ipv4": [],
            "gateway": [],
            "dns": []
        }

    ipv4_addresses = []
    gateways = []
    dns_servers = []

    for line in output.splitlines():
        line = line.strip()

        # IPv4
        if "IPv4 Address" in line:
            match = re.search(r":\s*([\d.]+)", line)

            if match:
                ipv4 = match.group(1)

                if not ipv4.startswith("169.254."):
                    ipv4_addresses.append(ipv4)

        # Default Gateway
        elif "Default Gateway" in line:
            match = re.search(r":\s*([\d.]+)", line)

            if match:
                gateways.append(match.group(1))

        # DNS Servers
        elif "DNS Servers" in line:
            match = re.search(r":\s*([\d.]+)", line)

            if match:
                dns_servers.append(match.group(1))

    return {
        "ipv4": list(dict.fromkeys(ipv4_addresses)),
        "gateway": list(dict.fromkeys(gateways)),
        "dns": list(dict.fromkeys(dns_servers)),
    }


def check_local_network() -> Dict[str, Any]:
    """
    Check whether the PC has working local network configuration.
    """
    config = get_ip_configuration()

    has_ip = len(config["ipv4"]) > 0
    has_gateway = len(config["gateway"]) > 0

    if has_ip and has_gateway:
        return {
            "status": "HEALTHY",
            "severity": "NORMAL",
            "message": "Local network configuration is working."
        }

    if has_ip and not has_gateway:
        return {
            "status": "WARNING",
            "severity": "MODERATE",
            "message": "IPv4 address exists but default gateway was not detected."
        }

    return {
        "status": "PROBLEM",
        "severity": "HIGH",
        "message": "No usable IPv4 address was detected."
    }


def ping_host(host: str = "8.8.8.8", timeout: int = 3) -> Dict[str, Any]:
    """
    Test connectivity and latency.
    """
    output = run_command([
        "ping",
        "-n",
        "4",
        "-w",
        str(timeout * 1000),
        host
    ])

    if not output:
        return {
            "status": "UNKNOWN",
            "severity": "LOW",
            "host": host,
            "latency_ms": None,
            "packet_loss_percent": None,
            "message": "Ping command did not return usable output."
        }

    loss_match = re.search(
        r"(\d+)%\s*loss",
        output,
        re.IGNORECASE
    )

    packet_loss = int(loss_match.group(1)) if loss_match else None

    latency = None

    avg_match = re.search(
        r"Average\s*=\s*(\d+)ms",
        output,
        re.IGNORECASE
    )

    if avg_match:
        latency = int(avg_match.group(1))

    if packet_loss == 100:
        return {
            "status": "PROBLEM",
            "severity": "HIGH",
            "host": host,
            "latency_ms": latency,
            "packet_loss_percent": packet_loss,
            "message": "Host is unreachable."
        }

    if packet_loss is not None and packet_loss > 10:
        return {
            "status": "WARNING",
            "severity": "HIGH",
            "host": host,
            "latency_ms": latency,
            "packet_loss_percent": packet_loss,
            "message": "High packet loss detected."
        }

    if latency is not None and latency > 150:
        return {
            "status": "WARNING",
            "severity": "MODERATE",
            "host": host,
            "latency_ms": latency,
            "packet_loss_percent": packet_loss,
            "message": "High network latency detected."
        }

    return {
        "status": "HEALTHY",
        "severity": "NORMAL",
        "host": host,
        "latency_ms": latency,
        "packet_loss_percent": packet_loss,
        "message": "Network connectivity is working normally."
    }


def check_dns() -> Dict[str, Any]:
    """
    Check DNS resolution.
    """
    test_domains = [
        "google.com",
        "microsoft.com"
    ]

    resolved = []

    for domain in test_domains:
        try:
            ip = socket.gethostbyname(domain)
            resolved.append({
                "domain": domain,
                "ip": ip
            })
        except Exception:
            pass

    if len(resolved) == len(test_domains):
        return {
            "status": "HEALTHY",
            "severity": "NORMAL",
            "resolved": resolved,
            "message": "DNS resolution is working normally."
        }

    if len(resolved) > 0:
        return {
            "status": "WARNING",
            "severity": "MODERATE",
            "resolved": resolved,
            "message": "DNS resolution is partially working."
        }

    return {
        "status": "PROBLEM",
        "severity": "HIGH",
        "resolved": [],
        "message": "DNS resolution failed."
    }


def diagnose_network() -> Dict[str, Any]:
    """
    Main Network Diagnosis V1.
    """
    adapters = get_network_adapters()
    ip_config = get_ip_configuration()
    local_network = check_local_network()
    internet = ping_host()
    dns = check_dns()

    active_adapters = [
        adapter for adapter in adapters
        if str(adapter.get("status", "")).upper() == "UP"
    ]

    return {
        "type": "Network",
        "adapters": adapters,
        "active_adapters": active_adapters,
        "ip_configuration": ip_config,
        "local_network": local_network,
        "internet_connectivity": internet,
        "dns": dns,
    }


def print_network_report(data: Dict[str, Any]) -> None:
    """
    Print a readable standalone report.
    """
    print("\n" + "=" * 65)
    print("              FIXMATE NETWORK DIAGNOSIS V1")
    print("=" * 65)

    print(f"\nTotal Adapters : {len(data['adapters'])}")
    print(f"Active Adapters: {len(data['active_adapters'])}")

    if data["active_adapters"]:
        print("\nActive Adapters:")
        for adapter in data["active_adapters"]:
            print(f"  - {adapter['name']}")
            print(f"    Description : {adapter['description']}")
            print(f"    Status      : {adapter['status']}")
            print(f"    Link Speed  : {adapter['link_speed']}")
            print(f"    MAC Address : {adapter['mac_address']}")

    ip = data["ip_configuration"]

    print("\nIP Configuration:")
    print(f"  IPv4   : {', '.join(ip['ipv4']) if ip['ipv4'] else 'Unavailable'}")
    print(f"  Gateway: {', '.join(ip['gateway']) if ip['gateway'] else 'Unavailable'}")
    print(f"  DNS    : {', '.join(ip['dns']) if ip['dns'] else 'Unavailable'}")

    local = data["local_network"]

    print("\nLocal Network:")
    print(f"  Status  : {local['status']}")
    print(f"  Severity: {local['severity']}")
    print(f"  Message : {local['message']}")

    internet = data["internet_connectivity"]

    print("\nInternet Connectivity:")
    print(f"  Status        : {internet['status']}")
    print(f"  Severity      : {internet['severity']}")
    print(f"  Host          : {internet['host']}")
    print(f"  Latency       : {internet['latency_ms']} ms")
    print(f"  Packet Loss   : {internet['packet_loss_percent']}%")
    print(f"  Message       : {internet['message']}")

    dns = data["dns"]

    print("\nDNS:")
    print(f"  Status  : {dns['status']}")
    print(f"  Severity: {dns['severity']}")
    print(f"  Message : {dns['message']}")

    print("\n" + "=" * 65)


if __name__ == "__main__":
    result = diagnose_network()
    print_network_report(result)