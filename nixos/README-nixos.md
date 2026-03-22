# NovaX AI OS — NixOS Build Guide

## Overview

This directory contains the complete NixOS configuration to build NovaX as a
bootable AI operating system. It packages 97 NovaLang microservices, 4 Python
services, the Rust-based NovaLang VM, and all infrastructure (Redis,
Meilisearch, Ollama) into a single bootable system.

**Target hardware:** x86_64 with NVIDIA GPU (RTX 4060 or similar)
**Boot time target:** Under 5 seconds to NovaX dashboard

---

## File Structure

```
nixos/
  flake.nix            — Flake entry point, pins nixpkgs + rust-overlay
  configuration.nix    — System config: boot, GPU, networking, user, kiosk
  novax-services.nix   — All 97+ NovaX systemd service definitions
  novax-overlay.nix    — Custom Nix packages (novalang-vm, novax-files)
  boot-splash.nix      — Plymouth boot splash with NovaX branding
  README-nixos.md      — This file
```

---

## Prerequisites

1. **Nix with flakes enabled** (on any Linux or WSL2):
   ```bash
   sh <(curl -L https://nixos.org/nix/install) --daemon
   # Enable flakes:
   mkdir -p ~/.config/nix
   echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf
   ```

2. **NovaX source tree** at `C:\NovaX` (Windows) or `/opt/novax` (Linux)

3. **NVIDIA GPU** with proprietary driver support

---

## Quick Start

### 1. Build a QEMU Virtual Machine (for testing)

```bash
cd /path/to/NovaX/nixos

# Build the VM (first build takes 30-60 minutes)
nix build .#nixosConfigurations.novax.config.system.build.vm

# Run it (QEMU)
./result/bin/run-novax-vm

# Or with GPU passthrough (requires IOMMU):
QEMU_OPTS="-m 8G -smp 4" ./result/bin/run-novax-vm
```

The VM will boot directly to the NovaX dashboard at `http://127.0.0.1:8888`.

### 2. Build a Bootable ISO

```bash
cd /path/to/NovaX/nixos

# Build the ISO image
nix build .#nixosConfigurations.novax.config.system.build.isoImage

# The ISO will be at:
ls result/iso/nixos-*.iso

# Write to USB drive (replace /dev/sdX):
sudo dd if=result/iso/nixos-*.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

### 3. Install to Real Hardware

Boot from the ISO, then:

```bash
# Partition the disk (example: /dev/nvme0n1)
parted /dev/nvme0n1 -- mklabel gpt
parted /dev/nvme0n1 -- mkpart ESP fat32 1MiB 512MiB
parted /dev/nvme0n1 -- set 1 esp on
parted /dev/nvme0n1 -- mkpart primary ext4 512MiB 100%

mkfs.fat -F 32 /dev/nvme0n1p1
mkfs.ext4 /dev/nvme0n1p2

mount /dev/nvme0n1p2 /mnt
mkdir -p /mnt/boot
mount /dev/nvme0n1p1 /mnt/boot

# Copy NovaX files
mkdir -p /mnt/opt/novax
cp -r /path/to/novax/files/* /mnt/opt/novax/

# Generate hardware config
nixos-generate-config --root /mnt

# Copy our flake config
cp -r /path/to/nixos/* /mnt/etc/nixos/

# Install
nixos-install --flake /mnt/etc/nixos#novax --no-root-passwd

# Reboot
reboot
```

### 4. Rebuild After Changes

On a running NovaX system:

```bash
# Edit configuration
sudo nano /etc/nixos/configuration.nix

# Rebuild and switch (no reboot needed for most changes)
sudo nixos-rebuild switch --flake /etc/nixos

# Rebuild and reboot (for kernel/boot changes)
sudo nixos-rebuild boot --flake /etc/nixos
sudo reboot
```

---

## Architecture

### Boot Sequence

```
UEFI → systemd-boot (0s timeout) → kernel+initrd → Plymouth splash
  → systemd targets:
      1. redis-novax.service        (port 6379)
      2. meilisearch.service        (port 7700)
      3. ollama.service             (port 11434)
      4. novax-infra-ready.target   ← gates all NovaX services
      5. novax-static.service       (port 8888) ← dashboard available
      6. novax-fleet.target         ← 97 microservices start in parallel
      7. novax-orchestrator.service (port 9999)
      8. novax-ready.target         ← system fully operational
  → lightdm auto-login → openbox → chromium kiosk → dashboard
```

### Service Management

```bash
# View all NovaX services
systemctl list-units 'novax-*'

# Check a specific service
systemctl status novax-hivemind

# View service logs
journalctl -u novax-orchestrator -f

# Restart a service
sudo systemctl restart novax-hivemind

# View fleet health
curl http://127.0.0.1:9999/health

# View all service ports
ss -tlnp | grep -E '9[0-9]{3}'
```

### Key Ports

| Port  | Service           | Type     |
|-------|-------------------|----------|
| 6379  | Redis             | Infra    |
| 7700  | Meilisearch       | Infra    |
| 8888  | Dashboard (static)| NovaLang |
| 9800  | NovaX LLM         | NovaLang |
| 9801  | Voice Server      | Python   |
| 9878  | Cloud Router      | NovaLang |
| 9881  | Hivemind          | NovaLang |
| 9999  | Orchestrator      | Python   |
| 11434 | Ollama            | Infra    |

---

## Customization

### Adding a New NovaLang Service

In `novax-services.nix`, add:

```nix
systemd.services.novax-myservice = mkNovaService {
  name = "myservice";
  file = "nova_myservice.nova";
  port = 9xxx;
};
```

### Adding a New Python Service

```nix
systemd.services.novax-mypy = mkPythonService {
  name = "mypy";
  file = "nova_mypy.py";
  port = 9xxx;
};
```

### Changing the Kiosk Browser

In `configuration.nix`, modify the `environment.etc."xdg/openbox/autostart"`
section. Replace `chromium` with `firefox` and adjust flags:

```nix
firefox --kiosk http://127.0.0.1:8888/nova_desktop.html &
```

### Disabling the Splash Screen

Remove `./boot-splash.nix` from the modules list in `flake.nix`.

---

## Troubleshooting

### Services not starting

```bash
# Check the infra target
systemctl status novax-infra-ready.target

# Check Redis
systemctl status redis-novax
redis-cli -h 127.0.0.1 ping

# Check all failed services
systemctl list-units --failed 'novax-*'
```

### NVIDIA driver issues

```bash
# Verify GPU is detected
nvidia-smi

# Check kernel module
lsmod | grep nvidia

# Check Xorg logs
journalctl -u display-manager -b
```

### Path issues (Windows paths in .nova files)

The `novax-path-patcher` service runs once on first boot to convert all
`C:\NovaX` paths to `/opt/novax`. If it fails:

```bash
# Re-run manually
sudo systemctl restart novax-path-patcher

# Check status
systemctl status novax-path-patcher

# Verify paths are patched
grep -r 'C:\\' /opt/novax/*.nova | head -5
```

### Boot is slow

```bash
# Analyze boot time
systemd-analyze
systemd-analyze blame
systemd-analyze critical-chain novax-ready.target
```

---

## Performance Tuning

The configuration includes aggressive tuning for a single-user AI workstation:

- **Kernel:** `mitigations=off` (security tradeoff for performance)
- **Swap:** `vm.swappiness=10` (minimize swapping)
- **File limits:** 65536 per process, 2M system-wide
- **TCP:** Fast Open enabled, large backlog
- **Boot:** zstd-compressed initrd, no GRUB timeout
- **GPU:** NVIDIA proprietary with modesetting

---

## Building from Windows (WSL2)

If building on Windows with WSL2:

```bash
# In WSL2
cd /mnt/c/NovaX/nixos
nix build .#nixosConfigurations.novax.config.system.build.isoImage

# The ISO will be accessible from Windows at:
# \\wsl$\Ubuntu\mnt\c\NovaX\nixos\result\iso\
```

Note: NVIDIA GPU passthrough in QEMU from WSL2 is not supported.
Use bare-metal Linux or a full Linux VM with GPU passthrough for testing.
