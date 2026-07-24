import { NavLink, Outlet } from 'react-router-dom';
import { Briefcase, LayoutDashboard } from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/jobs', label: 'Jobs', icon: Briefcase },
];

export function Layout() {
  return (
    <div className="flex min-h-screen">
      <aside className="w-64 shrink-0 border-r bg-sidebar p-4">
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
        </nav>
      </aside>
      <main className="min-w-0 flex-1 overflow-x-hidden p-8">
        <Outlet />
      </main>
    </div>
  );
}
