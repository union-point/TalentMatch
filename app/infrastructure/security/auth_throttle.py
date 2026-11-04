import hashlib
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.services.auth_sessions import AuthError

_RESERVE = """
for i, key in ipairs(KEYS) do
  if tonumber(redis.call('GET', key) or '0') >= tonumber(ARGV[i]) then
    return math.max(redis.call('TTL', key), 1)
  end
end
for i, key in ipairs(KEYS) do
  if redis.call('INCR', key) == 1 then redis.call('EXPIRE', key, ARGV[#KEYS + 1]) end
end
return 0
"""
_RELEASE = """
for _, key in ipairs(KEYS) do
  if tonumber(redis.call('GET', key) or '0') > 0 then redis.call('DECR', key) end
end
return 0
"""


class ThrottleError(AuthError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("rate_limited", "Too many attempts. Try again later.", 429)
        self.retry_after = retry_after


@dataclass
class AuthThrottle:
    redis: Redis

    async def reserve(
        self, operation: str, account: str, ip: str, account_limit: int, ip_limit: int, seconds: int
    ) -> tuple[str, str]:
        digest = hashlib.sha256(account.encode()).hexdigest()
        keys = (f"auth:{operation}:account:{digest}", f"auth:{operation}:ip:{ip}")
        try:
            retry = int(
                await cast(
                    Awaitable[str],
                    self.redis.eval(
                        _RESERVE, 2, *keys, str(account_limit), str(ip_limit), str(seconds)
                    ),
                )
            )
        except RedisError as exc:
            raise AuthError(
                "auth_unavailable", "Authentication is temporarily unavailable.", 503
            ) from exc
        if retry:
            raise ThrottleError(retry)
        return keys

    async def release(self, keys: tuple[str, str]) -> None:
        try:
            await cast(Awaitable[str], self.redis.eval(_RELEASE, 2, *keys))
        except RedisError as exc:
            raise AuthError(
                "auth_unavailable", "Authentication is temporarily unavailable.", 503
            ) from exc
