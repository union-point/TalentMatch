import { useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Plus, Play, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { JdUploadDialog } from '@/components/jd-upload-dialog';
import { JdSelector } from '@/components/jd-selector';
import { ResumeDropzone } from '@/components/resume-dropzone';
import { UploadResults } from '@/components/upload-results';
import { CandidateTable } from '@/components/candidate-table';
import { useUploadJd } from '@/hooks/use-upload-jd';
import { useBatchUpload } from '@/hooks/use-batch-upload';
import { useFastTrack } from '@/hooks/use-fast-track';
import { useJobDescriptions } from '@/hooks/use-job-descriptions';
import type { BatchUploadResponse } from '@/types';

export function Dashboard() {
  const queryClient = useQueryClient();
  const [selectedJdId, setSelectedJdId] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [uploadResult, setUploadResult] = useState<BatchUploadResponse | null>(null);

  const { data: jdData } = useJobDescriptions();
  const uploadJd = useUploadJd();
  const batchUpload = useBatchUpload();
  const fastTrack = useFastTrack();


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
    [uploadJd, queryClient]
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

  const handleRunAnalysis = useCallback(() => {
    if (!selectedJdId || !uploadResult || uploadResult.resumes.length === 0) return;
    const resumeIds = uploadResult.resumes.map((r) => r.id);
    fastTrack.mutate({ job_description_id: selectedJdId, resume_ids: resumeIds });
  }, [selectedJdId, uploadResult, fastTrack]);


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

      {[uploadJd.error, batchUpload.error, fastTrack.error].filter(Boolean).map((error, index) => (
        <p key={index} role="alert" className="text-sm text-destructive">
          {error?.message}
        </p>
      ))}
      {fastTrack.data?.results.filter((result) => result.error).map((result) => (
        <p key={result.resume_id} role="alert" className="text-sm text-destructive">
          {uploadResult?.resumes.find((resume) => resume.id === result.resume_id)?.filename ?? result.resume_id}: {result.error}
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

      {uploadResult && uploadResult.total > 0 && (
        <div className="flex items-center justify-center">
          <Button
            size="lg"
            onClick={handleRunAnalysis}
            disabled={fastTrack.isPending}
          >
            {fastTrack.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {fastTrack.isPending ? 'Analyzing...' : 'Run Analysis'}
          </Button>
        </div>
      )}

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
