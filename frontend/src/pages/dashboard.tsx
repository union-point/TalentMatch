import { JobReview } from '@/components/job-review';
import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { BriefcaseBusiness } from 'lucide-react';
import { NewJobButton } from '@/components/new-job-button';
import { Card, CardContent } from '@/components/ui/card';
import { JdSelector } from '@/components/jd-selector';
import { useJobDescriptions } from '@/hooks/use-job-descriptions';

export function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedJdId = searchParams.get('jd');
  const setSelectedJdId = useCallback((id: string) => {
    setSearchParams((params) => { params.set('jd', id); return params; });
  }, [setSearchParams]);

  const jobs = useJobDescriptions();
  return (
    <div className="space-y-6">
      <header className="dashboard-cover">
        <div>
          <span className="section-label">Hiring workspace</span>
          <h1>Dashboard</h1>
          <p>Manage job descriptions and review the candidates for each role.</p>
          <NewJobButton onCreated={setSelectedJdId} />
        </div>
      </header>

      <Card>
        <CardContent className="job-context">
          <div className="flex items-center gap-3">
            <span className="document-icon"><BriefcaseBusiness size={20} /></span>
            <div><h2 className="font-heading text-3xl">Job description</h2>
              <p className="text-xs text-muted-foreground">{jobs.isPending ? 'Loading jobs…' : jobs.error ? 'Job list unavailable' : `${jobs.data.total} ${jobs.data.total === 1 ? 'job' : 'jobs'} in your workspace`}</p>
            </div>
          </div>
          {jobs.error ? <div role="alert">{jobs.error.message} <button className="text-link" onClick={() => void jobs.refetch()}>Retry</button></div> :
            <JdSelector loading={jobs.isPending} entries={jobs.data?.items ?? []} value={selectedJdId} onChange={setSelectedJdId} />}
        </CardContent>
      </Card>

      <JobReview key={selectedJdId} jdId={selectedJdId} />
    </div>
  );
}
