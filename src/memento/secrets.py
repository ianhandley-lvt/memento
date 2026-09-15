from __future__ import annotations

import subprocess


class KeychainSecretError(RuntimeError):
    """A configured Keychain item could not be read."""


def read_keychain_secret(service: str, account: str) -> str:
    """Read a generic-password item from the macOS Keychain via the `security`
    CLI. Never accepts a secret as a Python value from a caller — the token
    itself is only ever handled by `security`, never passed through argv from
    application code, so it can't end up in a process listing or shell history
    this tool controls."""

    try:
        completed = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True, text=True, check=True,
        )
    except FileNotFoundError as error:
        raise KeychainSecretError("the `security` command is unavailable (not macOS?)") from error
    except subprocess.CalledProcessError as error:
        raise KeychainSecretError(
            f"no Keychain item found for service={service!r} account={account!r}"
        ) from error
    return completed.stdout.strip()
