"""Tests for recent-connection URL encryption and its migration fallbacks.

A stored connection URL must stay readable across key-scheme changes — an
unreadable URL means the user can no longer reopen a database they already
connected, which is exactly the failure these fallbacks exist to prevent.
"""

import base64
import hashlib

import pytest
from cryptography.fernet import Fernet

import backend.app.pgdatabase.connections as conns


def _fernet_for(secret: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


@pytest.fixture(autouse=True)
def _clear_cipher_cache(monkeypatch):
    monkeypatch.setattr(conns, "_RECENT_CIPHER", None)
    for var in (
        "RECENT_CONNECTIONS_KEY",
        "RECENT_CONNECTIONS_MASTER_KEY",
        "JWT_SECRET",
    ):
        monkeypatch.delenv(var, raising=False)
    yield
    conns._RECENT_CIPHER = None


def test_roundtrip_with_direct_key(monkeypatch):
    monkeypatch.setenv("RECENT_CONNECTIONS_KEY", "a-direct-key")
    token = conns._encrypt_connection_url("postgresql://u:p@host/db")
    assert token != "postgresql://u:p@host/db"
    assert conns._decrypt_connection_url(token) == "postgresql://u:p@host/db"


def test_falls_back_to_jwt_secret_when_no_connections_key(monkeypatch, tmp_path):
    """Rows written when JWT_SECRET was the key must still decrypt.

    With no RECENT_CONNECTIONS_* var set, building the cipher raises — that
    must not stop the legacy path from being tried.
    """
    monkeypatch.setattr(conns, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(conns, "_CONNECTIONS_KEY_FILE", tmp_path / "connections.key")
    monkeypatch.setenv("JWT_SECRET", "the-old-secret")
    legacy = _fernet_for("the-old-secret").encrypt(b"mysql://u:p@host/db").decode()

    assert conns._decrypt_connection_url(legacy) == "mysql://u:p@host/db"


def test_falls_back_to_jwt_secret_when_key_file_needs_absent_master(
    monkeypatch, tmp_path
):
    """A v1: key file with no master key set must not derive a garbage key.

    This is the regression: treating the ciphertext as a raw secret produced a
    wrong cipher, and the resulting RuntimeError skipped the legacy path.
    """
    key_file = tmp_path / "connections.key"
    key_file.write_text("v1:" + _fernet_for("master").encrypt(b"inner").decode())
    monkeypatch.setattr(conns, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(conns, "_CONNECTIONS_KEY_FILE", key_file)
    monkeypatch.setenv("JWT_SECRET", "the-old-secret")
    legacy = _fernet_for("the-old-secret").encrypt(b"mysql://u:p@host/db").decode()

    assert conns._decrypt_connection_url(legacy) == "mysql://u:p@host/db"


def test_encrypted_key_file_without_master_key_is_a_clear_error(monkeypatch, tmp_path):
    key_file = tmp_path / "connections.key"
    key_file.write_text("v1:" + _fernet_for("master").encrypt(b"inner").decode())
    monkeypatch.setattr(conns, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(conns, "_CONNECTIONS_KEY_FILE", key_file)

    with pytest.raises(RuntimeError, match="RECENT_CONNECTIONS_MASTER_KEY"):
        conns._build_recent_connection_cipher()


def test_master_key_reads_back_its_own_key_file(monkeypatch, tmp_path):
    key_file = tmp_path / "connections.key"
    monkeypatch.setattr(conns, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(conns, "_CONNECTIONS_KEY_FILE", key_file)
    monkeypatch.setenv("RECENT_CONNECTIONS_MASTER_KEY", "master")

    token = conns._build_recent_connection_cipher().encrypt(b"sqlite:///x.db").decode()
    conns._RECENT_CIPHER = None  # force a rebuild from the persisted file
    assert conns._decrypt_connection_url(token) == "sqlite:///x.db"


def test_plaintext_url_passes_through(monkeypatch):
    monkeypatch.setenv("RECENT_CONNECTIONS_KEY", "a-direct-key")
    assert (
        conns._decrypt_connection_url("postgresql://u:p@host/db")
        == "postgresql://u:p@host/db"
    )


def test_undecryptable_value_raises(monkeypatch):
    monkeypatch.setenv("RECENT_CONNECTIONS_KEY", "a-direct-key")
    with pytest.raises(RuntimeError, match="Failed to decrypt"):
        conns._decrypt_connection_url("not-a-token-and-not-a-url")
