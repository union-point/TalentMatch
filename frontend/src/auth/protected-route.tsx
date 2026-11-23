import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/auth/auth-context';
import { sessionDestination } from '@/lib/auth-navigation';
import { AuthShell } from '@/auth/auth-shell';
import { AuthForm } from '@/pages/auth-forms';
import { Button } from '@/components/ui/button';

export function ProtectedRoute({
  organization = true,
}: {
  organization?: boolean;
}) {
  const { session, loading, error, refresh } = useAuth();
  const location = useLocation();
  if (loading)
    return (
      <p className="p-8" role="status">
        Checking your session…
      </p>
    );
  if (error && !session) return <AuthForm mode="login" destination={location.pathname + location.search} />;
  if (error)
    return (
      <AuthShell title="Reconnect to your workspace" description="Your session could not be checked. Try again to continue.">
        <p role="alert">{error}</p>
        <Button onClick={() => void refresh()}>Retry</Button>
      </AuthShell>
    );
  const destination = sessionDestination(
    session,
    location.pathname + location.search
  );
  if (
    session?.state !== 'authenticated' ||
    (organization && (!session.organization || session.organization.locked))
  ) {
    return <Navigate to={destination} replace
      state={session?.state === 'email_verification_required' ? { email: session.user?.email } : undefined} />;
  }
  return <Outlet />;
}
