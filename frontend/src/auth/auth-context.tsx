import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  fetchGet,
  fetchPost,
  onSessionExpired,
  resetSessionToken,
} from '@/lib/api';
import type { AuthSession } from '@/types/auth';

interface AuthContextValue {
  session: AuthSession | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  update: (session: AuthSession | null) => void;
  logout: (everywhere?: boolean) => Promise<void>;
  invitationToken: string;
  rememberInvitation: (token: string) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [invitationToken, rememberInvitation] = useState('');
  const [error, setError] = useState<string | null>(null);
  const identity = useRef('');
  const generation = useRef(0);
  const client = useQueryClient();
  const update = useCallback(
    (next: AuthSession | null) => {
      const nextIdentity = `${next?.user?.id ?? ''}:${next?.organization?.id ?? ''}:${next?.state ?? ''}`;
      if (identity.current !== nextIdentity) {
        void client.cancelQueries();
        client.clear();
        identity.current = nextIdentity;
      }
      generation.current += 1;
      setSession(next);
      setError(null);
    },
    [client]
  );

  const refresh = useCallback(async () => {
    const current = ++generation.current;
    try {
      const next = await fetchGet<AuthSession>('/v1/auth/session');
      if (current === generation.current) update(next);
    } catch (cause) {
      if (current === generation.current)
        setError(
          cause instanceof Error
            ? cause.message
            : 'Could not check your session.'
        );
    } finally {
      setLoading(false);
    }
  }, [update]);

  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => onSessionExpired(() => update(null)), [update]);
  useEffect(() => {
    const onFocus = () => {
      void refresh();
    };
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [refresh]);

  const logout = useCallback(
    async (everywhere = false) => {
      await fetchPost(`/v1/auth/${everywhere ? 'logout-all' : 'logout'}`);
      resetSessionToken();
      update(null);
    },
    [update]
  );

  return (
    <AuthContext.Provider
      value={{
        session,
        loading,
        error,
        refresh,
        update,
        logout,
        invitationToken,
        rememberInvitation,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth requires AuthProvider');
  return context;
}
