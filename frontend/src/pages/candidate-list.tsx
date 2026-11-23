import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { JobReview } from '@/components/job-review';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useJobDescription } from '@/hooks/use-job-description';

export function CandidateList() {
  const { jdId } = useParams<{ jdId: string }>();
  const job = useJobDescription(jdId ?? null);

  return <div className="space-y-6">
    <Link className="back-link" to="/jobs"><ArrowLeft size={15} />All jobs</Link>
    {job.isPending && <p role="status">Loading job description…</p>}
    {job.error && <div role="alert">{job.error.message} <Button variant="outline" onClick={() => void job.refetch()}>Retry</Button></div>}
    {job.data && jdId && <>
      <header className="page-heading">
        <h1>{job.data.title}</h1>
        <div className="mt-3 flex items-center gap-3 text-muted-foreground">
          {job.data.company}<Badge variant="outline" className="uppercase">{job.data.file_type}</Badge>
        </div>
      </header>
      <JobReview key={jdId} jdId={jdId} />
    </>}
  </div>;
}
