import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, LockKeyhole } from 'lucide-react';
import { Brand } from '@/components/brand';
import { withReturnTo } from '@/lib/auth-navigation';

export function AuthShell({ title, description, children, accountLink, focusTitle, returnTo = '/' }: {
  accountLink?: 'login' | 'signup';
  title: string;
  description?: string;
  children: ReactNode;
  focusTitle?: boolean;
  returnTo?: string;
}) {
  const isSignup = accountLink === 'login';
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (focusTitle) heading.current?.focus();
  }, [focusTitle, title]);

  return (
    <div className="access-page" data-entry={accountLink != null}>
      <header className="access-bar">
        <Brand />
        {accountLink && <div className="flex items-center gap-4 text-sm">
          <span className="hidden text-muted-foreground sm:inline">{isSignup ? 'Already have an account?' : 'New to TalentMatch?'}</span>
          <Link className="access-link" to={withReturnTo(isSignup ? '/login' : '/signup', returnTo)}>
            {isSignup ? 'Sign in' : 'Create account'} <ArrowUpRight size={15} />
          </Link>
        </div>}
      </header>
      <main className="access-main">
        <section className="access-form">
          <div className="access-form-inner">
            <div className="section-label flex items-center gap-2"><span className="access-rule" /> Workspace access</div>
            <h1 ref={heading} tabIndex={focusTitle ? -1 : undefined} className="display-title">{title}</h1>
            {description && <p className="access-description">{description}</p>}
            <div className="access-fields">{children}</div>
          </div>
        </section>
        <aside className="access-art" aria-label="About TalentMatch">
          <img className="paper-study" src="/images/paper-study.webp" alt="" fetchPriority="high" />
          <div className="art-frame" aria-hidden="true"><i /><i /><i /><i /></div>
          <div className="art-caption">
            <div className="section-label">TalentMatch workspace</div>
            <h2>Candidate <em>review.</em></h2>
            <p>Compare résumés with the requirements of each role.</p>
          </div>
        </aside>
      </main>
      <footer className="access-bar access-footer">
        <span>© {new Date().getFullYear()} TalentMatch</span>
        <span className="flex items-center gap-2"><LockKeyhole size={13} /> Private workspace</span>
      </footer>
    </div>
  );
}
