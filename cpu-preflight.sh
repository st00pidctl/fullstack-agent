#!/usr/bin/env bash
# Check CPU features required by current scientific Python wheels.
# SPDX-License-Identifier: AGPL-3.0-or-later
set -euo pipefail

arch="$(uname -m)"
if [ "$arch" != "x86_64" ]; then
  echo "CPU_OK arch=$arch (x86-64-v2 check not applicable)"
  exit 0
fi

flags=" $(awk -F: '/^flags[[:space:]]*:/{print $2; exit}' /proc/cpuinfo 2>/dev/null || true) "
if [ "$flags" = "  " ]; then
  echo "CPU_WARN could not read /proc/cpuinfo; skipping x86-64-v2 feature check" >&2
  exit 0
fi

missing=()
# Linux commonly reports SSE3 as pni. Accept either spelling.
if [[ "$flags" != *" pni "* && "$flags" != *" sse3 "* ]]; then
  missing+=(sse3)
fi
for feature in ssse3 sse4_1 sse4_2 popcnt cx16 lahf_lm; do
  if [[ "$flags" != *" $feature "* ]]; then
    missing+=("$feature")
  fi
done

if [ "${#missing[@]}" -gt 0 ]; then
  echo "CPU_FAIL x86-64-v2 is not exposed to this VM." >&2
  echo "Missing guest CPU flags: ${missing[*]}" >&2
  echo "Current NumPy x86-64 wheels require the x86-64-v2 baseline." >&2
  echo "For Proxmox on a single node or homogeneous cluster, set the VM CPU type to 'host'." >&2
  echo "For migration compatibility, use at least 'x86-64-v2-AES'." >&2
  echo "Power the VM off before changing its CPU model, then boot it and rerun verification." >&2
  exit 1
fi

echo "CPU_OK x86-64-v2 feature baseline exposed"
