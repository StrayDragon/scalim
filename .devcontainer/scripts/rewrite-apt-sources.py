#!/usr/bin/env python3
"""Rewrite Debian APT sources to use a mirror, skipping security repos."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def rewrite_deb822_sources(path: Path, mirror: str, skip_hosts: tuple[str, ...]) -> None:
    """Rewrite DEB822 format sources file to use mirror."""
    mirror = mirror.strip()
    if not mirror:
        return
    mirror = mirror.rstrip("/")
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        # Skip security repositories (they use different mirror paths)
        if line.startswith("URIs:") and not any(host in line for host in skip_hosts) and "security" not in line.lower():
            out.append(f"URIs: {mirror}\n")
        else:
            out.append(line)
    path.write_text("".join(out), encoding="utf-8")


def main() -> None:
    """Main entry point."""
    debian_sources = Path("/etc/apt/sources.list.d/debian.sources")

    if debian_sources.exists():
        mirror = os.environ.get("SCALIM_APT_DEBIAN_MIRROR", "")
        rewrite_deb822_sources(
            debian_sources,
            mirror,
            skip_hosts=("security.debian.org",),
        )
        sys.stdout.write("APT sources rewritten to use mirror: {}\n".format(mirror))
    else:
        sys.stdout.write("Debian sources file not found, skipping mirror configuration\n")


if __name__ == "__main__":
    main()
