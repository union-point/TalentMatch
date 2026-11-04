import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { JdUploadDialog } from '@/components/jd-upload-dialog';
import { JdSelector } from '@/components/jd-selector';
import { ResumeDropzone } from '@/components/resume-dropzone';
import { UploadResults } from '@/components/upload-results';
import { CandidateTable } from '@/components/candidate-table';
import { useUploadJd } from '@/hooks/use-upload-jd';
import { useBatchUpload } from '@/hooks/use-batch-upload';
import { UnscoredResumes } from '@/components/unscored-resumes';
import { useJobDescriptions } from '@/hooks/use-job-descriptions';
import type { BatchUploadResponse } from '@/types';

export function Dashboard() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedJdId = searchParams.get('jd');
  const setSelectedJdId = useCallback((id: string) => {
    setSearchParams((params) => { params.set('jd', id); return params; });
  }, [setSearchParams]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [uploadResult, setUploadResult] = useState<BatchUploadResponse | null>(null);

  const { data: jdData } = useJobDescriptions();
  const uploadJd = useUploadJd();
  const batchUpload = useBatchUpload();

  const handleJdUpload = useCallback(
    async (data: { file: File; title: string; company: string }) => {
      try {
        const result = await uploadJd.mutateAsync(data);
        queryClient.invalidateQueries({ queryKey: ['job-descriptions'] });
        setSelectedJdId(result.id);
        setDialogOpen(false);
      } catch {
        // The mutation error is rendered below.
      }
    },
    [uploadJd, queryClient, setSelectedJdId]
  );

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
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="mt-1 text-muted-foreground">
            Upload job descriptions and manage candidates.
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="h-4 w-4" />
          New JD
        </Button>
      </div>

      {[uploadJd.error, batchUpload.error].filter(Boolean).map((error, index) => (
        <p key={index} role="alert" className="text-sm text-destructive">
          {error?.message}
        </p>
      ))}

      <JdUploadDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onUpload={handleJdUpload}
        isUploading={uploadJd.isPending}
      />

      <Card>
        <CardHeader>
          <CardTitle>Job Description</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <JdSelector
            entries={jdData?.items ?? []}
            value={selectedJdId}
            onChange={setSelectedJdId}
          />
        </CardContent>
      </Card>

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
          <CardTitle>Candidates</CardTitle>
        </CardHeader>
        <CardContent>
          <CandidateTable key={selectedJdId} jdId={selectedJdId} />
        </CardContent>
      </Card>
    </div>
  );
}
