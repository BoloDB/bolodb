"""Tests for recent-connection URL encryption.

The key comes only from RECENT_CONNECTIONS_KEY — nothing is read from or written
to disk. A stored URL must round-trip under that key, legacy rows written when
JWT_SECRET was the key must still decrypt, and a missing key must fail loudly
rather than silently dropping the save.
"""

import base64
import hashlib

import pytest
from cryptography.fernet import Fernet

import backend.app.pgdatabase.connections as conns
from backend.app.pgdatabase.connections import ConnectionKeyError


def _fernet_for(secret: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


@pytest.fixture(autouse=True)
def _clear_cipher_cache(monkeypatch):
    monkeypatch.setattr(conns, "_RECENT_CIPHER", None)
    for var in ("RECENT_CONNECTIONS_KEY", "JWT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    yield
    conns._RECENT_CIPHER = None


def test_roundtrip_with_env_key(monkeypatch):
    monkeypatch.setenv("RECENT_CONNECTIONS_KEY", "a-direct-key")
    token = conns._encrypt_connection_url("postgresql://u:p@host/db")
    assert token != "postgresql://u:p@host/db"
    assert conns._decrypt_connection_url(token) == "postgresql://u:p@host/db"


def test_missing_key_raises_connection_key_error(monkeypatch):
    """No key set is a server misconfiguration, surfaced as a distinct type."""
    with pytest.raises(ConnectionKeyError, match="RECENT_CONNECTIONS_KEY"):
        conns._build_recent_connection_cipher()


def test_encrypt_without_key_raises_connection_key_error(monkeypatch):
    with pytest.raises(ConnectionKeyError):
        conns._encrypt_connection_url("postgresql://u:p@host/db")


def test_falls_back_to_jwt_secret_for_legacy_rows(monkeypatch):
    """Rows written when JWT_SECRET was the key must still decrypt.

    The current key is set to something else, so only the legacy fallback can
    read these — the point being that old saved connections survive the move to
    an env-only key.
    """
    monkeypatch.setenv("RECENT_CONNECTIONS_KEY", "the-new-key")
    monkeypatch.setenv("JWT_SECRET", "the-old-secret")
    legacy = _fernet_for("the-old-secret").encrypt(b"mysql://u:p@host/db").decode()

    assert conns._decrypt_connection_url(legacy) == "mysql://u:p@host/db"


def test_missing_key_does_not_block_the_legacy_path(monkeypatch):
    """Even with no current key, a legacy JWT_SECRET row must still decrypt.

    Building the cipher raises ConnectionKeyError; that must be caught so the
    fallback still runs rather than the whole read failing.
    """
    monkeypatch.setenv("JWT_SECRET", "the-old-secret")
    legacy = _fernet_for("the-old-secret").encrypt(b"mysql://u:p@host/db").decode()

    assert conns._decrypt_connection_url(legacy) == "mysql://u:p@host/db"


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
