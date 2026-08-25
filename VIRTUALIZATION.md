# Virtualization and CPU compatibility

Universal Fullstack Agent is intended to run well as a headless VM, but the guest must expose a modern enough CPU feature baseline for current scientific Python wheels used by Whisper and TTS.

## x86-64 requirement

On x86-64, current NumPy wheels use the x86-64-v2 baseline. A VM that presents an older compatibility CPU such as a legacy `kvm64` model may allow Codex and the shell to run while failing as soon as the remote voice endpoint imports NumPy.

The repository includes `cpu-preflight.sh`, and both `verify-vm.sh` and `verify-endpoint.sh` run it before loading the voice endpoint.

## Proxmox recommendation

For a single-node installation or a cluster whose nodes have the same CPU model, use the Proxmox VM CPU type:

```text
host
```

This exposes the host CPU flags to the guest and gives Whisper, NumPy, and TTS the best available CPU performance.

If live migration across dissimilar hosts matters, use at least:

```text
x86-64-v2-AES
```

or a newer common CPU model supported by every target node.

Changing the virtual CPU model requires a VM power-off and boot. A reboot from inside the guest is not sufficient if QEMU needs to recreate the VM with a different CPU model.

### Proxmox CLI example

On the Proxmox host, locate the VM ID:

```bash
qm list | grep -i peter
```

After shutting the VM down, set the CPU type:

```bash
qm set <VMID> --cpu host
```

Then start the VM and rerun:

```bash
cd ~/universal-agent
./fullstack-agent/verify-vm.sh
./fullstack-agent/verify-endpoint.sh
```

## Why not pin an old NumPy?

The shell should not trade away performance or carry an indefinitely old numerical stack merely to accommodate an unnecessarily restricted virtual CPU on modern hardware. A source-built compatibility NumPy is possible for genuinely old physical CPUs, but it is treated as a fallback path, not the default VM architecture.

## Hardware capacity

Passing the CPU feature check does not guarantee acceptable latency. `verify-endpoint.sh` performs a synthetic full remote voice round trip and prints elapsed time and memory availability. That runtime measurement is the authoritative capacity test for a particular VM.
