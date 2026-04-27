from __future__ import annotations

import subprocess
from pathlib import Path
from threading import Lock


class IptablesSnapshotWriter:
    def __init__(self, file_path: str, chain: str) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.chain = chain
        self.lock = Lock()

    def write_snapshot(self, action: str, ip_address: str) -> None:
        result = subprocess.run(
            ["iptables", "-L", self.chain, "-n", "--line-numbers"],
            check=False,
            capture_output=True,
            text=True,
        )
        snapshot = result.stdout.strip()
        lines = [
            f"ACTION={action} IP={ip_address}",
            snapshot,
            "",
        ]
        with self.lock:
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(lines))


class Blocker:
    def __init__(self, chain: str, action: str, snapshot_writer: IptablesSnapshotWriter | None = None) -> None:
        self.chain = chain
        self.action = action
        self.snapshot_writer = snapshot_writer

    def is_blocked(self, ip_address: str) -> bool:
        result = subprocess.run(
            ["iptables", "-C", self.chain, "-s", ip_address, "-j", self.action],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def block_ip(self, ip_address: str) -> bool:
        if self.is_blocked(ip_address):
            return False
        result = subprocess.run(
            ["iptables", "-I", self.chain, "-s", ip_address, "-j", self.action],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"failed to block {ip_address}")
        if self.snapshot_writer is not None:
            self.snapshot_writer.write_snapshot("BAN", ip_address)
        return True

    def unblock_ip(self, ip_address: str) -> bool:
        if not self.is_blocked(ip_address):
            return False
        result = subprocess.run(
            ["iptables", "-D", self.chain, "-s", ip_address, "-j", self.action],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"failed to unblock {ip_address}")
        if self.snapshot_writer is not None:
            self.snapshot_writer.write_snapshot("UNBAN", ip_address)
        return True
