import { useState } from 'react';
import { NavLink, Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { BriefcaseBusiness, Building2, ChevronRight, LayoutDashboard, LogOut, Menu, ShieldCheck, Users, X } from 'lucide-react';
import { useAuth } from '@/auth/auth-context';
import { Brand } from '@/components/brand';

const hiring = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/jobs', label: 'Jobs', icon: BriefcaseBusiness },
];
const settings = [
  { to: '/organization', label: 'Organization', icon: Users },
  { to: '/account', label: 'Account security', icon: ShieldCheck },
];

export function Layout() {
  const auth = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const org = auth.session?.organization;
  const hasWorkspace = org && !org.locked;
  const email = auth.session?.user?.email ?? '';
  const groups = hasWorkspace
    ? [{ title: 'Workspace', links: hiring }, { title: 'Settings', links: settings }]
    : [{ title: 'Settings', links: settings.filter((link) => link.to === '/account') }];
  const current = pathname.startsWith('/candidates/') ? 'Candidate review'
    : pathname.startsWith('/jobs/') ? 'Job review'
    : [...hiring, ...settings].find((item) => item.to === pathname)?.label;

  async function signOut() {
    try {
      await auth.logout();
      navigate('/login');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not sign out.');
    }
  }

  return (
    <div className="workspace">
      <a href="#workspace-content" className="skip-link">Skip to content</a>
      <aside className="workspace-sidebar">
        <div className="workspace-brand">
          <Brand />
          <button className="mobile-menu" aria-expanded={open} aria-controls="workspace-menu"
            aria-label={open ? 'Close navigation' : 'Open navigation'} onClick={() => setOpen(!open)}>
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
        <div className="sidebar-body" id="workspace-menu" data-open={open}>
          <nav aria-label="Main navigation">
            {groups.map(({ title, links }) => (
              <div key={title} className="nav-group">
                <div className="section-label">{title}</div>
                {links.map(({ to, label, icon: Icon }) => (
                  <NavLink to={to} key={to} end={to === '/'} onClick={() => setOpen(false)}
                    className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}>
                    <Icon size={17} />{label}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          <div className="profile-block">
            <span className="avatar" aria-hidden="true">{email.slice(0, 1).toUpperCase()}</span>
            <Link to="/account" onClick={() => setOpen(false)} className="min-w-0">
              <span className="block truncate text-sm font-medium">{email}</span>
              <span className="block text-xs capitalize text-muted-foreground">{org?.role ?? 'Account'}</span>
            </Link>
            <button aria-label="Sign out" title="Sign out" className="icon-action" onClick={() => void signOut()}><LogOut size={16} /></button>
            {error && <p role="alert" className="col-span-full text-xs">{error}</p>}
          </div>
        </div>
      </aside>
      <div className="workspace-body">
        <header className="workspace-topline">
          <span className="flex min-w-0 items-center gap-2"><Building2 size={15} /><span className="truncate">{org?.name ?? 'Account'}</span></span>
          <ChevronRight size={13} /><span className="shrink-0 text-foreground">{current}</span>
        </header>
        <main id="workspace-content" tabIndex={-1} className="workspace-content"><Outlet /></main>
      </div>
    </div>
  );
}
