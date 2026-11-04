import asyncio
import base64
import hashlib
import io
import secrets
import time

import pyotp
import qrcode
from cryptography.fernet import Fernet, MultiFernet
from pwdlib import PasswordHash


class ArgonPasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(32))

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._hasher.hash, password)

    async def verify(self, password: str, password_hash: str) -> bool:
        return await asyncio.to_thread(self._hasher.verify, password, password_hash)

    async def dummy_verify(self, password: str) -> None:
        await self.verify(password, self._dummy_hash)


class EncryptedIdentitySecrets:
    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError("AUTH_ENCRYPTION_KEYS must contain at least one Fernet key")
        self._cipher = MultiFernet([Fernet(key.encode()) for key in keys])

    def token(self) -> str:
        return secrets.token_urlsafe(32)

    def digest(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def encrypt(self, value: str) -> str:
        return self._cipher.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self._cipher.decrypt(value.encode()).decode()

    def totp_secret(self) -> str:
        return pyotp.random_base32()

    def totp_step(self, secret: str, code: str, last_step: int) -> int | None:
        if len(code) != 6 or not code.isascii() or not code.isdigit():
            return None
        current = int(time.time()) // 30
        totp = pyotp.TOTP(secret)
        for step in (current, current - 1, current + 1):
            if step > last_step and secrets.compare_digest(totp.at(step * 30), code):
                return step
        return None

    def provisioning(self, secret: str, email: str) -> tuple[str, str]:
        uri = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="TalentMatch")
        output = io.BytesIO()
        qrcode.make(uri).save(output, format="PNG")
        return uri, "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()
