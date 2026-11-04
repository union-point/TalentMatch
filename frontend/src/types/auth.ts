export type SessionState =
  | 'anonymous'
  | 'email_verification_required'
  | 'mfa_enrollment_required'
  | 'mfa_challenge_required'
  | 'authenticated';

export interface AuthSession {
  state: SessionState;
  csrf_token: string;
  user: { id: string; email: string; verified: boolean } | null;
  organization: {
    id: string;
    name: string;
    role: 'owner' | 'member';
    locked: boolean;
  } | null;
  mfa_enabled: boolean;
}

export interface RecoverySession extends AuthSession {
  recovery_codes: string[];
}
