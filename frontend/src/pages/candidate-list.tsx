import { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ResumeDropzone } from '@/components/resume-dropzone';
import { UploadResults } from '@/components/upload-results';
import { CandidateTable } from '@/components/candidate-table';
import { useJobDescription } from '@/hooks/use-job-description';
import { useBatchUpload } from '@/hooks/use-batch-upload';
import { UnscoredResumes } from '@/components/unscored-resumes';
import type { BatchUploadResponse } from '@/types';

export function CandidateList() {
  const { jdId } = useParams<{ jdId: string }>();
  const navigate = useNavigate();
  const [uploadResult, setUploadResult] = useState<BatchUploadResponse | null>(null);

  const { data: jd, isLoading: jdLoading } = useJobDescription(jdId ?? null);
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

  if (jdLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon-sm" onClick={() => navigate('/jobs')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold">{jd?.title ?? 'Job Description'}</h1>
            {jd && <Badge variant="secondary">{jd.file_type}</Badge>}
          </div>
          {jd && (
            <p className="mt-1 text-muted-foreground">{jd.company}</p>
          )}
        </div>
      </div>

      {batchUpload.error && <p role="alert" className="text-sm text-destructive">{batchUpload.error.message}</p>}
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

      {jdId && <UnscoredResumes key={jdId} jdId={jdId} />}

      <Card>
        <CardHeader>
          <CardTitle>Candidates</CardTitle>
        </CardHeader>
        <CardContent>
          <CandidateTable key={jdId ?? null} jdId={jdId ?? null} />
        </CardContent>
      </Card>
    </div>
  );
}
