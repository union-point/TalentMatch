import { Link, useNavigate } from 'react-router-dom';
import { ArrowUpRight, BriefcaseBusiness, FileText, ShieldAlert, ShieldCheck } from 'lucide-react';
import { useJobDescriptions } from '@/hooks/use-job-descriptions';
import { NewJobButton } from '@/components/new-job-button';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export function JobsList() {
  const navigate = useNavigate();
  const jobs = useJobDescriptions();
  return (
    <div className="space-y-6">
      <header className="page-heading flex flex-wrap items-end justify-between gap-4">
        <div><h1>Job descriptions</h1><p>Select a role to upload résumés and review candidates.</p></div>
        <NewJobButton onCreated={(id) => navigate('/jobs/' + id)} />
      </header>
      {jobs.isPending && <p role="status">Loading jobs…</p>}
      {jobs.error && <div role="alert">{jobs.error.message} <Button variant="outline" onClick={() => void jobs.refetch()}>Retry</Button></div>}
      {jobs.data && (
        <section className="job-list">
          <h2 className="section-label border-b px-5 py-4">Jobs in your workspace · {jobs.data.total}</h2>
          {jobs.data.items.length === 0 && <div className="grid justify-items-center gap-3 px-5 py-14 text-center">
            <span className="document-icon"><BriefcaseBusiness size={21} /></span>
            <h3 className="font-heading text-3xl">No jobs yet</h3>
            <p className="text-sm text-muted-foreground">Choose New job to upload your first job description.</p>
          </div>}
          {jobs.data.items.map((job) => (
            <Link key={job.id} to={'/jobs/' + job.id} className="job-row">
              <span className="document-icon"><FileText size={21} /></span>
              <div className="min-w-0 flex-1"><h3 className="font-medium">{job.title}</h3>
                <p className="text-sm text-muted-foreground">{job.company} · <span className="uppercase">{job.file_type}</span></p>
              </div>
              <Badge variant={job.injection_scan_passed ? 'outline' : 'secondary'}>
                {job.injection_scan_passed ? <ShieldCheck /> : <ShieldAlert />}
                {job.injection_scan_passed ? 'Safe' : 'Flagged'}
              </Badge>
              <ArrowUpRight size={17} />
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}
