from __future__ import annotations

import subprocess


class Blocker:
    def __init__(self, chain: str, action: str) -> None:
        self.chain = chain
        self.action = action

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
        return True
