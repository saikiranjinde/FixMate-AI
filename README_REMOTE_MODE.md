# FixMate-AI Remote Diagnostic Mode (Add-on)

This add-on is deliberately **additive**: it does not overwrite or edit the existing FixMate-AI `core`, `ui`, `ai`, `storage`, or `diagnosis` files.

## What it does

It lets one Windows PC act as the **controller** and another trusted Windows PC act as the **target**.

```text
Controller PC
    │
    │ IP + Port + 6-digit Pair PIN
    ▼
Target PC — FixMate-AI Remote Agent
    │
    ├── Fetch target system information
    └── Run the existing FixMate-AI full diagnosis on the target
```

The target result is returned as structured JSON to the controller. The existing FixMate-AI AI analyzer can later be wired to that returned scan result without changing the diagnostic engine.

## Target PC setup

The target must currently have the FixMate-AI project files, because the agent imports the existing `system_info.py` and `core/full_scan.py`.

Run:

```powershell
python remote_agent.py
```

The agent prints:

- Target IP
- Port
- A fresh 6-digit pairing PIN

Keep the agent window open.

## Controller PC setup

Run:

```powershell
python remote_diagnostic.py
```

Enter the target PC's IP address, port, and pairing PIN.

Then use:

1. **Test Connection**
2. **Fetch System Info**
3. **Run Remote Diagnosis**

## Windows Firewall

The first time the target agent listens on TCP port `47821`, Windows Firewall may ask for permission. Allow it only on a **Private/trusted network**.

## Safety

This prototype is intended for a trusted local network only. Do not expose the agent's port directly to the internet. The pairing PIN is an application-level pairing control, not a replacement for VPN/TLS or enterprise authentication.

## Why no original files were changed

The add-on consists only of:

```text
remote/
remote_agent.py
remote_diagnostic.py
README_REMOTE_MODE.md
```

No existing FixMate-AI files are replaced by this package.
