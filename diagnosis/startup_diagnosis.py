# ============================================================
# FIXMATE-AI
# STARTUP DIAGNOSIS V2
# ============================================================

import json
import os
import re
import subprocess
from typing import Any, Dict, List


# ============================================================
# POWERSHELL HELPER
# ============================================================

def run_powershell(command: str, timeout: int = 20) -> str:
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
            encoding="utf-8",
            errors="ignore",
            timeout=timeout
        )

        if result.returncode != 0:
            return ""

        return result.stdout.strip()

    except Exception:
        return ""


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def normalize_text(value: Any) -> str:
    return safe_str(value).strip().lower()


# ============================================================
# REGISTRY STARTUP ENTRIES
# ============================================================

def get_registry_startup_apps(
    path: str,
    location_label: str,
    scope: str
) -> List[Dict[str, Any]]:
    """
    Read only real registry value properties.

    This fixes the previous parser issue where Select-Object
    PSObject.Properties could produce a fake Unknown entry.
    """

    command = f"""
$results = @()

try {{
    $key = Get-ItemProperty -Path "{path}" -ErrorAction Stop

    foreach ($property in $key.PSObject.Properties) {{
        if (
            $property.Name -notmatch "^PS"
            -and
            $null -ne $property.Value
            -and
            -not [string]::IsNullOrWhiteSpace([string]$property.Value)
        ) {{
            $results += [PSCustomObject]@{{
                Name = [string]$property.Name
                Command = [string]$property.Value
                Location = "{location_label}"
                Scope = "{scope}"
                Source = "Registry"
                Enabled = $true
            }}
        }}
    }}
}}
catch {{}}

$results | ConvertTo-Json -Depth 3
"""

    output = run_powershell(command, 20)

    if not output:
        return []

    try:
        data = json.loads(output)

        if isinstance(data, dict):
            data = [data]

        return data if isinstance(data, list) else []

    except Exception:
        return []


# ============================================================
# STARTUP FOLDER ENTRIES
# ============================================================

def get_startup_folder_apps() -> List[Dict[str, Any]]:
    command = r"""
$results = @()

$folders = @(
    @{
        Path = [Environment]::GetFolderPath("Startup")
        Scope = "Current User"
    },
    @{
        Path = [Environment]::GetFolderPath("CommonStartup")
        Scope = "All Users"
    }
)

foreach ($folder in $folders) {
    if (Test-Path $folder.Path) {
        try {
            Get-ChildItem -Path $folder.Path -File -ErrorAction SilentlyContinue |
            ForEach-Object {
                $results += [PSCustomObject]@{
                    Name = $_.BaseName
                    Command = $_.FullName
                    Location = $_.DirectoryName
                    Scope = $folder.Scope
                    Source = "Startup Folder"
                    Enabled = $true
                }
            }
        }
        catch {}
    }
}

$results | ConvertTo-Json -Depth 3
"""

    output = run_powershell(command, 20)

    if not output:
        return []

    try:
        data = json.loads(output)

        if isinstance(data, dict):
            data = [data]

        return data if isinstance(data, list) else []

    except Exception:
        return []


# ============================================================
# EXECUTABLE TARGET EXTRACTION
# ============================================================

def resolve_shortcut_target(shortcut_path: str) -> str:
    """
    Resolve a Windows .lnk shortcut to its actual target.
    """

    if not shortcut_path:
        return ""

    if not shortcut_path.lower().endswith(".lnk"):
        return shortcut_path

    escaped = shortcut_path.replace("'", "''")

    command = f"""
try {{
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut('{escaped}')
    if ($shortcut.TargetPath) {{
        [Console]::Write($shortcut.TargetPath)
    }}
}}
catch {{}}
"""

    resolved = run_powershell(
        command,
        timeout=10
    ).strip()

    return resolved or shortcut_path


def extract_command_target(command: str) -> str:
    command = safe_str(command).strip()

    if not command:
        return ""

    quoted = re.search(
        r'"([^"]+\.(?:exe|com|bat|cmd|ps1))"',
        command,
        re.IGNORECASE
    )

    if quoted:
        return quoted.group(1)

    token = re.search(
        r'([A-Za-z]:\\[^"\r\n]*?\.(?:exe|com|bat|cmd|ps1))',
        command,
        re.IGNORECASE
    )

    if token:
        return token.group(1).rstrip(" ")

    lowered = command.lower()

    if lowered.endswith(
        (".exe", ".com", ".bat", ".cmd", ".ps1")
    ):
        return command

    if lowered.endswith(".lnk"):
        return resolve_shortcut_target(command)

    if lowered.endswith(".url"):
        return command

    return ""

# ============================================================
# FILE METADATA / SIGNATURE
# ============================================================

def get_file_metadata(command: str) -> Dict[str, Any]:
    """
    Resolve startup targets and inspect executable signature where possible.
    """

    original = safe_str(command).strip()
    target = extract_command_target(original)

    if not target:
        return {
            "original": original,
            "target": "",
            "exists": False,
            "publisher": "",
            "signed": None
        }

    if target.lower().endswith((".lnk", ".url")):
        return {
            "original": original,
            "target": target,
            "exists": os.path.exists(target),
            "publisher": "",
            "signed": None
        }

    if not os.path.exists(target):
        return {
            "original": original,
            "target": target,
            "exists": False,
            "publisher": "",
            "signed": None
        }

    escaped_target = (
        target
        .replace("`", "``")
        .replace('"', '""')
    )

    command_ps = f"""
$path = "{escaped_target}"

$result = [ordered]@{{
    Target = $path
    Exists = Test-Path -LiteralPath $path
    Publisher = ""
    Signed = $null
}}

try {{
    $sig = Get-AuthenticodeSignature `
        -LiteralPath $path `
        -ErrorAction Stop

    if ($sig.SignerCertificate) {{
        $result.Publisher = [string]$sig.SignerCertificate.Subject
    }}

    if ($sig.Status -eq "Valid") {{
        $result.Signed = $true
    }}
    elseif ($sig.Status -eq "NotSigned") {{
        $result.Signed = $false
    }}
}}
catch {{}}

$result | ConvertTo-Json -Compress
"""

    output = run_powershell(
        command_ps,
        timeout=10
    )

    if not output:
        return {
            "original": original,
            "target": target,
            "exists": True,
            "publisher": "",
            "signed": None
        }

    try:
        data = json.loads(output)

        return {
            "original": original,
            "target": data.get("Target", target),
            "exists": bool(data.get("Exists", True)),
            "publisher": safe_str(data.get("Publisher", "")),
            "signed": data.get("Signed")
        }

    except Exception:
        return {
            "original": original,
            "target": target,
            "exists": True,
            "publisher": "",
            "signed": None
        }


# ============================================================
# STARTUP APP ANALYSIS
# ============================================================

def analyze_startup_command(
    app: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Conservative startup classification using entry, resolved target,
    publisher and signature.

    A startup entry alone is not a fault.
    """

    name = safe_str(
        app.get("Name", app.get("name", ""))
    )

    command = safe_str(
        app.get("Command", app.get("command", ""))
    )

    location = safe_str(
        app.get("Location", app.get("location", ""))
    )

    metadata = get_file_metadata(command)

    publisher = safe_str(
        metadata.get("publisher", "")
    )

    target = safe_str(
        metadata.get("target", "")
    )

    signed = metadata.get("signed")

    combined = normalize_text(
        f"{name} {command} {target} {publisher} {location}"
    )

    publisher_text = normalize_text(publisher)
    target_text = normalize_text(target)

    # --------------------------------------------------------
    # Trusted publishers
    # --------------------------------------------------------


    trusted_publishers = [
        "microsoft",
        "windows",
        "lenovo",
        "nvidia",
        "intel",
        "advanced micro devices",
        "amd",
        "realtek",
        "synaptics"
    ]

    if (
        any(
            item in publisher_text
            for item in trusted_publishers
        )
        and signed is not False
    ):
        return {
            "status": "NORMAL",
            "severity": "NORMAL",
            "risk": "LOW",
            "reason":
                "Startup target has a recognized system or hardware "
                "publisher and no unsigned-file signal."
        }

    # --------------------------------------------------------
    # Trusted installed-program / Windows locations
    # --------------------------------------------------------

    trusted_paths = [
        "\\windows\\system32\\",
        "\\windows\\syswow64\\",
        "\\program files\\",
        "\\program files (x86)\\"
    ]

    if (
        any(
            path in target_text
            for path in trusted_paths
        )
        and signed is not False
    ):
        return {
            "status": "NORMAL",
            "severity": "NORMAL",
            "risk": "LOW",
            "reason":
                "Resolved startup target is located in a standard "
                "Windows or installed-program directory."
        }

    # --------------------------------------------------------
    # Known user applications
    # --------------------------------------------------------
    # Trusted publisher/path checks run first so legitimate signed
    # applications are not downgraded merely because they are optional.

    common_apps = [
        "chrome",
        "msedge",
        "edge",
        "discord",
        "spotify",
        "whatsapp",
        "steam",
        "epicgames",
        "teams",
        "vscode",
        "code.exe",
        "onedrive",
        "dropbox",
        "rainmeter",
        "onenote"
    ]

    if any(
        keyword in combined
        for keyword in common_apps
    ):
        return {
            "status": "ADVISORY",
            "severity": "LOW",
            "risk": "LOW",
            "reason":
                "Startup entry appears to belong to a known user "
                "application and may be optional."
        }

    # --------------------------------------------------------
    # Suspicious locations
    # --------------------------------------------------------

    suspicious_locations = [
        "\\appdata\\local\\temp\\",
        "\\appdata\\roaming\\temp\\",
        "\\windows\\temp\\",
        "\\users\\public\\",
        "\\downloads\\"
    ]

    if any(
        location in target_text
        for location in suspicious_locations
    ):
        return {
            "status": "WARNING",
            "severity": "MODERATE",
            "risk": "MEDIUM",
            "reason":
                "Resolved startup target references a location that "
                "deserves manual security review."
        }

    # --------------------------------------------------------
    # Explicitly unsigned executable
    # --------------------------------------------------------

    if signed is False:
        return {
            "status": "REVIEW",
            "severity": "MODERATE",
            "risk": "MEDIUM",
            "reason":
                "Startup target exists but its executable is not "
                "digitally signed."
        }

    # --------------------------------------------------------
    # Unknown / unresolved
    # --------------------------------------------------------

    return {
        "status": "UNKNOWN",
        "severity": "LOW",
        "risk": "LOW",
        "reason":
            "Startup entry could not be confidently classified. "
            "It is not treated as a confirmed fault."
    }


# ============================================================
# STARTUP TASKS
# ============================================================

def get_startup_tasks() -> List[Dict[str, Any]]:
    command = r"""
$results = @()

try {
    Get-ScheduledTask -ErrorAction Stop |
    ForEach-Object {
        $task = $_

        if ($task.State -ne "Disabled") {

            $hasStartupTrigger = $false

            foreach ($trigger in $task.Triggers) {

                if (
                    $trigger.CimClass.CimClassName -eq "MSFT_TaskLogonTrigger"
                    -or
                    $trigger.CimClass.CimClassName -eq "MSFT_TaskBootTrigger"
                ) {
                    $hasStartupTrigger = $true
                    break
                }
            }

            if ($hasStartupTrigger) {

                $results += [PSCustomObject]@{
                    TaskName = $task.TaskName
                    TaskPath = $task.TaskPath
                    State = [string]$task.State
                }
            }
        }
    }
}
catch {}

$results | ConvertTo-Json -Depth 4
"""

    output = run_powershell(command, 30)

    if not output:
        return []

    try:
        data = json.loads(output)

        if isinstance(data, dict):
            data = [data]

        return data if isinstance(data, list) else []

    except Exception:
        return []


# ============================================================
# STARTUP TASK ANALYSIS
# ============================================================

def analyze_startup_task(
    task: Dict[str, Any]
) -> Dict[str, Any]:

    task_name = safe_str(
        task.get("TaskName")
    )

    task_path = safe_str(
        task.get("TaskPath")
    )

    combined = normalize_text(
        f"{task_name} {task_path}"
    )

    trusted_keywords = [
        "microsoft",
        "windows",
        "defender",
        "security",
        "update",
        "nvidia",
        "intel",
        "lenovo",
        "amd",
        "realtek"
    ]

    if any(
        keyword in combined
        for keyword in trusted_keywords
    ):
        return {
            "status": "NORMAL",
            "severity": "NORMAL",
            "risk": "LOW",
            "reason":
                "Task appears related to Windows, security, "
                "updates, hardware, or a recognized vendor."
        }

    return {
        "status": "ADVISORY",
        "severity": "LOW",
        "risk": "LOW",
        "reason":
            "Enabled startup/logon task should be reviewed "
            "if it is not required."
    }


# ============================================================
# OVERALL STARTUP HEALTH
# ============================================================

def calculate_startup_health(
    apps: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]]
) -> Dict[str, Any]:

    severity_order = {
        "NORMAL": 0,
        "LOW": 1,
        "MODERATE": 2,
        "HIGH": 3,
        "CRITICAL": 4
    }

    overall = "NORMAL"

    for app in apps:
        severity = app.get(
            "analysis",
            {}
        ).get(
            "severity",
            "LOW"
        )

        if severity_order.get(
            severity,
            1
        ) > severity_order.get(
            overall,
            0
        ):
            overall = severity

    for task in tasks:
        severity = task.get(
            "analysis",
            {}
        ).get(
            "severity",
            "LOW"
        )

        if severity_order.get(
            severity,
            1
        ) > severity_order.get(
            overall,
            0
        ):
            overall = severity

    if overall == "NORMAL":
        status = "HEALTHY"

    elif overall in (
        "LOW",
        "MODERATE"
    ):
        status = "ADVISORY"

    else:
        status = "WARNING"

    return {
        "status": status,
        "severity": overall,
        "message":
            (
                "Startup configuration appears normal."
                if status == "HEALTHY"
                else
                "Startup configuration contains entries "
                "that may require review."
            )
    }


# ============================================================
# MAIN STARTUP DIAGNOSIS
# ============================================================

def diagnose_startup() -> Dict[str, Any]:

    raw_apps: List[Dict[str, Any]] = []

    raw_apps.extend(
        get_registry_startup_apps(
            r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
            r"HKCU\...\Run",
            "Current User"
        )
    )

    raw_apps.extend(
        get_registry_startup_apps(
            r"HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
            r"HKLM\...\Run",
            "All Users"
        )
    )

    raw_apps.extend(
        get_registry_startup_apps(
            r"HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
            r"HKLM\WOW6432Node\...\Run",
            "All Users"
        )
    )

    raw_apps.extend(
        get_startup_folder_apps()
    )

    raw_tasks = get_startup_tasks()

    # --------------------------------------------------------
    # Applications
    # --------------------------------------------------------

    apps = []

    seen_apps = set()

    for item in raw_apps:

        name = safe_str(
            item.get("Name")
        ).strip()

        command = safe_str(
            item.get("Command")
        ).strip()

        # Ignore invalid/empty records completely.
        if not name or not command:
            continue

        fingerprint = (
            f"{name.lower()}|"
            f"{command.lower()}"
        )

        if fingerprint in seen_apps:
            continue

        seen_apps.add(
            fingerprint
        )

        metadata = get_file_metadata(
            command
        )

        analysis = analyze_startup_command(
            item
        )

        apps.append({
            "name": name,
            "command": command,
            "location": safe_str(
                item.get(
                    "Location"
                ),
                "Unknown"
            ),
            "scope": safe_str(
                item.get(
                    "Scope"
                ),
                "Unknown"
            ),
            "source": safe_str(
                item.get(
                    "Source"
                ),
                "Unknown"
            ),
            "enabled": bool(
                item.get(
                    "Enabled",
                    True
                )
            ),
            "target": metadata.get(
                "target",
                ""
            ),
            "publisher": metadata.get(
                "publisher",
                ""
            ),
            "signed": metadata.get(
                "signed"
            ),
            "target_exists": metadata.get(
                "exists",
                False
            ),
            "analysis": analysis
        })

    # --------------------------------------------------------
    # Scheduled tasks
    # --------------------------------------------------------

    tasks = []

    seen_tasks = set()

    for item in raw_tasks:

        name = safe_str(
            item.get(
                "TaskName"
            )
        ).strip()

        path = safe_str(
            item.get(
                "TaskPath"
            )
        ).strip()

        fingerprint = (
            f"{name.lower()}|"
            f"{path.lower()}"
        )

        if fingerprint in seen_tasks:
            continue

        seen_tasks.add(
            fingerprint
        )

        tasks.append({
            "name":
                name or "Unknown",
            "path":
                path or "Unknown",
            "state":
                safe_str(
                    item.get(
                        "State"
                    ),
                    "Unknown"
                ),
            "analysis":
                analyze_startup_task(
                    item
                )
        })

    health = calculate_startup_health(
        apps,
        tasks
    )

    return {
        "type": "Startup",
        "startup_apps": apps,
        "startup_tasks": tasks,
        "startup_app_count": len(apps),
        "startup_task_count": len(tasks),
        "status": health["status"],
        "severity": health["severity"],
        "message": health["message"],
        "available": bool(
            apps or tasks
        )
    }


# ============================================================
# PRINT REPORT
# ============================================================

def print_startup_report(
    data: Dict[str, Any]
) -> None:

    print("\n")
    print("=" * 75)
    print("              FIXMATE STARTUP DIAGNOSIS V4")
    print("=" * 75)

    print(
        f"\nOverall Status  : "
        f"{data.get('status', 'UNKNOWN')}"
    )

    print(
        f"Overall Severity: "
        f"{data.get('severity', 'UNKNOWN')}"
    )

    print(
        f"Assessment      : "
        f"{data.get('message', 'N/A')}"
    )

    # --------------------------------------------------------
    # STARTUP APPLICATIONS
    # --------------------------------------------------------

    apps = data.get(
        "startup_apps",
        []
    )

    print(
        "\n[ STARTUP APPLICATIONS ]"
    )

    print(
        "-" * 75
    )

    if not apps:

        print(
            "No startup applications detected."
        )

    else:

        for index, app in enumerate(
            apps,
            start=1
        ):

            analysis = app.get(
                "analysis",
                {}
            )

            print(
                f"\n{index}. "
                f"{app.get('name', 'Unknown')}"
            )

            print(
                f"   Source    : "
                f"{app.get('source', 'Unknown')}"
            )

            print(
                f"   Scope     : "
                f"{app.get('scope', 'Unknown')}"
            )

            print(
                f"   Location  : "
                f"{app.get('location', 'Unknown')}"
            )

            print(
                f"   Command   : "
                f"{app.get('command', 'Unknown')}"
            )

            if app.get("target"):
                print(
                    f"   Target    : "
                    f"{app.get('target')}"
                )

            print(
                f"   Publisher : "
                f"{app.get('publisher') or 'Unknown'}"
            )

            signed = app.get("signed")

            if signed is True:
                signature = "VALID"
            elif signed is False:
                signature = "NOT SIGNED"
            else:
                signature = "UNKNOWN"

            print(
                f"   Signature : "
                f"{signature}"
            )

            print(
                f"   Status    : "
                f"{analysis.get('status', 'UNKNOWN')}"
            )

            print(
                f"   Severity  : "
                f"{analysis.get('severity', 'UNKNOWN')}"
            )

            print(
                f"   Risk      : "
                f"{analysis.get('risk', 'UNKNOWN')}"
            )

            print(
                f"   Reason    : "
                f"{analysis.get('reason', 'N/A')}"
            )

    # --------------------------------------------------------
    # STARTUP TASKS
    # --------------------------------------------------------

    tasks = data.get(
        "startup_tasks",
        []
    )

    print(
        "\n[ STARTUP / LOGON TASKS ]"
    )

    print(
        "-" * 75
    )

    if not tasks:

        print(
            "No enabled startup/logon scheduled tasks detected."
        )

    else:

        for index, task in enumerate(
            tasks,
            start=1
        ):

            analysis = task.get(
                "analysis",
                {}
            )

            print(
                f"\n{index}. "
                f"{task.get('name', 'Unknown')}"
            )

            print(
                f"   Path     : "
                f"{task.get('path', 'Unknown')}"
            )

            print(
                f"   State    : "
                f"{task.get('state', 'Unknown')}"
            )

            print(
                f"   Status   : "
                f"{analysis.get('status', 'UNKNOWN')}"
            )

            print(
                f"   Severity : "
                f"{analysis.get('severity', 'UNKNOWN')}"
            )

            print(
                f"   Risk     : "
                f"{analysis.get('risk', 'UNKNOWN')}"
            )

            print(
                f"   Reason   : "
                f"{analysis.get('reason', 'N/A')}"
            )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    normal_apps = sum(
        1
        for app in apps
        if app.get(
            "analysis",
            {}
        ).get(
            "severity"
        ) == "NORMAL"
    )

    advisory_apps = sum(
        1
        for app in apps
        if app.get(
            "analysis",
            {}
        ).get(
            "severity"
        ) == "LOW"
    )

    review_apps = sum(
        1
        for app in apps
        if app.get(
            "analysis",
            {}
        ).get(
            "severity"
        ) in (
            "MODERATE",
            "HIGH",
            "CRITICAL"
        )
    )

    print(
        "\n[ STARTUP SUMMARY ]"
    )

    print(
        "-" * 75
    )

    print(
        f"Startup Applications : "
        f"{len(apps)}"
    )

    print(
        f"Startup Tasks        : "
        f"{len(tasks)}"
    )

    print(
        f"Normal Applications  : "
        f"{normal_apps}"
    )

    print(
        f"Advisory Applications: "
        f"{advisory_apps}"
    )

    print(
        f"Entries for Review   : "
        f"{review_apps}"
    )

    print(
        "\nImportant:"
    )

    print(
        "A startup entry is not automatically a problem."
    )

    print(
        "Unknown or optional entries should be verified "
        "before disabling."
    )

    print(
        "\n" + "=" * 75
    )

    print(
        "              END OF STARTUP DIAGNOSIS"
    )

    print(
        "=" * 75
    )


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    result = diagnose_startup()

    print_startup_report(
        result
    )
