import { NavLink, Outlet, Link, useNavigate } from 'react-router-dom';
import { Briefcase, LayoutDashboard } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '@/auth/auth-context';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/jobs', label: 'Jobs', icon: Briefcase },
];

export function Layout() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 shrink-0 flex-col border-r bg-sidebar p-4">
        <h1 className="mb-8 text-xl font-bold text-sidebar-primary">
          TalentMatch
        </h1>
        <nav className="space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
                )
              }
              end={to === '/'}
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
          <NavLink
            to="/organization"
            className="block rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent"
          >
            Organization
          </NavLink>
          <Link
            to="/account"
            className="block rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent"
          >
            Account security
          </Link>
        </nav>
        <div className="mt-auto space-y-2 pt-8">
          <p className="truncate text-sm font-medium">
            {auth.session?.organization?.name}
          </p>
          <p className="truncate text-xs text-muted-foreground">
            {auth.session?.user?.email}
          </p>
          {error && (
            <p role="alert" className="text-xs text-destructive">
              {error}
            </p>
          )}
          <Button
            variant="outline"
            onClick={() => {
              void auth
                .logout()
                .then(() => navigate('/login'))
                .catch((cause) => setError(cause.message));
            }}
          >
            Sign out
          </Button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-x-hidden p-8">
        <Outlet />
      </main>
    </div>
  );
}
