from unittest.mock import patch

import pyotp
import pytest
from cryptography.fernet import Fernet

from app.infrastructure.security.identity import ArgonPasswordHasher, EncryptedIdentitySecrets


def test_tokens_encryption_and_key_rotation() -> None:
    key, previous = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    old = EncryptedIdentitySecrets([previous])
    current = EncryptedIdentitySecrets([key, previous])
    secret = old.token()
    assert len(secret) >= 40
    assert old.digest(secret) != secret
    assert current.decrypt(old.encrypt(secret)) == secret
    assert current.decrypt(current.encrypt(secret)) == secret
    with pytest.raises(ValueError):
        EncryptedIdentitySecrets([])


def test_totp_window_rejects_replay_and_invalid_codes() -> None:
    crypto = EncryptedIdentitySecrets([Fernet.generate_key().decode()])
    secret = crypto.totp_secret()
    with patch("app.infrastructure.security.identity.time.time", return_value=3000):
        code = pyotp.TOTP(secret).at(3000)
        assert crypto.totp_step(secret, code, -1) == 100
        assert crypto.totp_step(secret, code, 100) is None
        assert crypto.totp_step(secret, pyotp.TOTP(secret).at(2970), -1) == 99
        assert crypto.totp_step(secret, pyotp.TOTP(secret).at(2940), -1) is None
        assert crypto.totp_step(secret, "１２３４５６", -1) is None
        assert crypto.totp_step(secret, "invalid", -1) is None
    uri, image = crypto.provisioning(secret, "person@example.com")
    assert uri.startswith("otpauth://totp/")
    assert image.startswith("data:image/png;base64,")


async def test_argon_hashes_passwords_without_losing_unicode_or_spaces() -> None:
    hasher = ArgonPasswordHasher()
    password = "a long գաղտնաբառ with spaces"
    hashed = await hasher.hash(password)
    assert hashed.startswith("$argon2id$")
    assert await hasher.verify(password, hashed)
    assert not await hasher.verify(password + "!", hashed)
