import subprocess
from unittest.mock import patch

import pytest

from memento.secrets import KeychainSecretError, read_keychain_secret


def test_read_keychain_secret_returns_stripped_stdout():
    completed = subprocess.CompletedProcess([], 0, stdout="s3cr3t-token\n", stderr="")
    with patch("subprocess.run", return_value=completed) as run:
        value = read_keychain_secret("memento-atlassian-api-token", "ian@lvt.com")

    assert value == "s3cr3t-token"
    command = run.call_args.args[0]
    assert command == [
        "security", "find-generic-password", "-s", "memento-atlassian-api-token", "-a", "ian@lvt.com", "-w",
    ]


def test_read_keychain_secret_raises_when_item_missing():
    error = subprocess.CalledProcessError(returncode=44, cmd=["security"])
    with patch("subprocess.run", side_effect=error):
        with pytest.raises(KeychainSecretError, match="no Keychain item found"):
            read_keychain_secret("memento-atlassian-api-token", "ian@lvt.com")


def test_read_keychain_secret_raises_when_security_unavailable():
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        with pytest.raises(KeychainSecretError, match="unavailable"):
            read_keychain_secret("memento-atlassian-api-token", "ian@lvt.com")
