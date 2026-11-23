import { useState } from 'react';
import type { FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/auth/auth-context';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { fetchDelete, fetchGet, fetchPost } from '@/lib/api';

interface Member {
  id: string;
  email: string;
  role: 'owner' | 'member';
}
interface Invitation {
  id: string;
  email: string;
  expires_at: string;
}

export function OrganizationPage() {
  const { session } = useAuth();
  const client = useQueryClient();
  const owner = session?.organization?.role === 'owner';
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const members = useQuery({
    queryKey: ['organization-members'],
    queryFn: () => fetchGet<Member[]>('/v1/organization/members'),
  });
  const invitations = useQuery({
    queryKey: ['organization-invitations'],
    queryFn: () => fetchGet<Invitation[]>('/v1/organization/invitations'),
    enabled: owner,
  });

  async function invite(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await fetchPost<{ detail: string }>(
        '/v1/organization/invitations',
        { email }
      );
      setMessage(result.detail);
      setEmail('');
      await client.invalidateQueries({
        queryKey: ['organization-invitations'],
      });
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Could not send invitation.'
      );
    } finally {
      setBusy(false);
    }
  }
  async function remove(path: string, question: string) {
    if (!window.confirm(question)) return;
    setBusy(true);
    setError('');
    try {
      await fetchDelete(path);
      await client.invalidateQueries({ queryKey: ['organization-members'] });
      await client.invalidateQueries({
        queryKey: ['organization-invitations'],
      });
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Could not update organization.'
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-8">
      <div className="page-heading">
        <h1 className="text-2xl font-semibold">
          {session?.organization?.name}
        </h1>
        <p className="text-sm text-muted-foreground">
          Team members share this organization’s jobs, resumes, and analyses.
        </p>
      </div>
      {message && <p role="status">{message}</p>}
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      <section className="settings-section space-y-4">
        <h2 className="font-semibold">Members</h2>
        {members.isPending && <p role="status">Loading members…</p>}
        {members.error && <p role="alert">{members.error.message}</p>}
        <ul className="divide-y rounded-lg border">
          {members.data?.map((member) => (
            <li
              key={member.id}
              className="flex items-center justify-between gap-3 p-4"
            >
              <div>
                <p className="text-sm">{member.email}</p>
                <p className="text-xs capitalize text-muted-foreground">
                  {member.role}
                </p>
              </div>
              {owner && member.role !== 'owner' && (
                <Button
                  variant="destructive"
                  disabled={busy}
                  onClick={() =>
                    void remove(
                      `/v1/organization/members/${member.id}`,
                      `Remove ${member.email} and revoke their access?`
                    )
                  }
                >
                  Remove
                </Button>
              )}
            </li>
          ))}
        </ul>
      </section>
      {owner && (
        <>
          <section className="settings-section space-y-4">
            <h2 className="font-semibold">Invite a teammate</h2>
            <form onSubmit={invite} className="flex flex-col gap-2 sm:flex-row">
              <Input
                type="email"
                aria-label="Teammate email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="teammate@company.com"
                required
              />
              <Button type="submit" disabled={busy}>
                Send invitation
              </Button>
            </form>
            <p className="text-xs text-muted-foreground">
              Invitations expire after 72 hours. Accounts can belong to one
              organization.
            </p>
          </section>
          <section className="settings-section space-y-4">
            <h2 className="font-semibold">Pending invitations</h2>
            {invitations.isPending && <p role="status">Loading invitations…</p>}
            {invitations.error && (
              <p role="alert">{invitations.error.message}</p>
            )}
            {invitations.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No pending invitations.
              </p>
            )}
            <ul className="divide-y">
              {invitations.data?.map((invitation) => (
                <li
                  key={invitation.id}
                  className="flex items-center justify-between gap-3 py-3"
                >
                  <div>
                    <p className="text-sm">{invitation.email}</p>
                    <p className="text-xs text-muted-foreground">
                      Expires {new Date(invitation.expires_at).toLocaleString()}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() =>
                      void remove(
                        `/v1/organization/invitations/${invitation.id}`,
                        `Revoke the invitation for ${invitation.email}?`
                      )
                    }
                  >
                    Revoke
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
