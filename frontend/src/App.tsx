import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from '@/components/layout';
import { Dashboard } from '@/pages/dashboard';
import { JobsList } from '@/pages/jobs-list';
import { CandidateList } from '@/pages/candidate-list';
import { CandidateDetail } from '@/pages/candidate-detail';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/jobs" element={<JobsList />} />
            <Route path="/jobs/:jdId" element={<CandidateList />} />
            <Route
              path="/candidates/:resumeId/job/:jdId"
              element={<CandidateDetail />}
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
