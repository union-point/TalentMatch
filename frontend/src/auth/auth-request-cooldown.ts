import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { ApiError } from '@/lib/api';

export function useCooldown(retryAt: number): number {
  const [now, setNow] = useState(Date.now);

  useEffect(() => {
    const started = Date.now();
    setNow(started);
    if (retryAt <= started) return;
    const timer = window.setInterval(() => {
      const time = Date.now();
      setNow(time);
      if (time >= retryAt) window.clearInterval(timer);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [retryAt]);

  return Math.max(0, Math.ceil((retryAt - now) / 1000));
}

function retryDeadline(error: ApiError): number {
  const seconds = error.retryAfter;
  return Date.now() + (Number.isSafeInteger(seconds) && seconds > 0 ? seconds * 1000 : 60_000);
}

export function useAuthRequestRetry() {
  const { state, pathname, search, hash } = useLocation();
  const navigate = useNavigate();
  const retryState = state as { authRetryAt?: number; verificationRetryAt?: number; address?: string } | null;

  function rememberRateLimit(error: ApiError, address?: string) {
    navigate(pathname + search + hash, {
      replace: true,
      state: { ...retryState, address, authRetryAt: retryDeadline(error) },
    });
  }

  return {
    rateLimitedUntil: retryState?.authRetryAt ?? retryState?.verificationRetryAt ?? 0,
    address: retryState?.address ?? '',
    rememberRateLimit,
  };
}
