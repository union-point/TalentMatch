import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { BriefcaseBusiness, Users } from 'lucide-react';
import { NewJobButton } from '@/components/new-job-button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { JdSelector } from '@/components/jd-selector';
import { ResumeDropzone } from '@/components/resume-dropzone';
import { UploadResults } from '@/components/upload-results';
import { CandidateTable } from '@/components/candidate-table';
import { useBatchUpload } from '@/hooks/use-batch-upload';
import { UnscoredResumes } from '@/components/unscored-resumes';
import { useJobDescriptions } from '@/hooks/use-job-descriptions';
import type { BatchUploadResponse } from '@/types';

export function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedJdId = searchParams.get('jd');
  const setSelectedJdId = useCallback((id: string) => {
    setSearchParams((params) => { params.set('jd', id); return params; });
  }, [setSearchParams]);
  const [uploadResult, setUploadResult] = useState<BatchUploadResponse | null>(null);

  const jobs = useJobDescriptions();
  const batchUpload = useBatchUpload();

  const handleBatchUpload = useCallback(
    async (files: File[]) => {
      try {
        const result = await batchUpload.mutateAsync(files);
        setUploadResult(result);
      } catch {
        // The mutation error is rendered below.
      }
    },
    [batchUpload]
  );

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
            <JdSelector entries={jobs.data?.items ?? []} value={selectedJdId} onChange={setSelectedJdId} />}
        </CardContent>
      </Card>

      {batchUpload.error && <p role="alert">{batchUpload.error.message}</p>}
      {selectedJdId && (
        <Card>
          <CardHeader>
            <CardTitle>Upload Resumes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ResumeDropzone
              onUpload={handleBatchUpload}
              isUploading={batchUpload.isPending}
            />
            <UploadResults result={uploadResult} />
          </CardContent>
        </Card>
      )}

      {selectedJdId && <UnscoredResumes key={selectedJdId} jdId={selectedJdId} />}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Users size={20} />Candidates</CardTitle>
        </CardHeader>
        <CardContent>
          <CandidateTable key={selectedJdId} jdId={selectedJdId} />
        </CardContent>
      </Card>
    </div>
  );
}
