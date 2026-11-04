import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

export function AuthShell({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
      <section className="w-full max-w-md space-y-6 rounded-xl border bg-background p-8 shadow-sm">
        <Link to="/" className="text-sm font-semibold text-primary">
          TalentMatch
        </Link>
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">{title}</h1>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
        {children}
      </section>
    </main>
  );
}
