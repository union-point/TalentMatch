import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@/auth/auth-context';
import { ProtectedRoute } from '@/auth/protected-route';
import { Layout } from '@/components/layout';
import { Dashboard } from '@/pages/dashboard';
import { JobsList } from '@/pages/jobs-list';
import { CandidateList } from '@/pages/candidate-list';
import { AuthForm } from '@/pages/auth-forms';
import { MfaPage } from '@/pages/mfa';
import { Account } from '@/pages/account';
import { OrganizationPage } from '@/pages/organization';

const queryClient = new QueryClient();
const CandidateDetail = lazy(() =>
  import('@/pages/candidate-detail').then((module) => ({ default: module.CandidateDetail }))
);

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route
              path="/login"
              element={<AuthForm key="login" mode="login" />}
            />
            <Route
              path="/signup"
              element={<AuthForm key="signup" mode="signup" />}
            />
            <Route
              path="/verify-email"
              element={<AuthForm key="verify" mode="verify-email" />}
            />
            <Route
              path="/forgot-password"
              element={<AuthForm key="forgot" mode="forgot-password" />}
            />
            <Route
              path="/reset-password"
              element={<AuthForm key="reset" mode="reset-password" />}
            />
            <Route
              path="/accept-invitation"
              element={<AuthForm key="invite" mode="accept-invitation" />}
            />
            <Route path="/mfa" element={<MfaPage />} />
            <Route element={<ProtectedRoute organization={false} />}>
              <Route element={<Layout />}>
                <Route path="/account" element={<Account />} />
              </Route>
            </Route>
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<Dashboard />} />
                <Route path="/jobs" element={<JobsList />} />
                <Route path="/jobs/:jdId" element={<CandidateList />} />
                <Route
                  path="/candidates/:resumeId/job/:jdId"
                  element={
                    <Suspense fallback={<p role="status">Loading candidate…</p>}>
                      <CandidateDetail />
                    </Suspense>
                  }
                />
                <Route path="/organization" element={<OrganizationPage />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
