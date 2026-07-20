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
import { useCandidates } from '@/hooks/use-candidates';
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
  const { data: candidatesData, isLoading: candidatesLoading } = useCandidates({
    jdId: selectedJdId,
    pageSize: 50,
  });

  const handleJdUpload = useCallback(
    async (data: { file: File; title: string; company: string }) => {
      try {
        const result = await uploadJd.mutateAsync(data);
        queryClient.invalidateQueries({ queryKey: ['job-descriptions'] });
        setSelectedJdId(result.id);
        setDialogOpen(false);
      } catch {
        // Error handling via toast in M4
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
        // Error handling via toast in M4
      }
    },
    [batchUpload]
  );

  const handleRunAnalysis = useCallback(() => {
    if (!selectedJdId || !uploadResult || uploadResult.resumes.length === 0) return;
    const resumeIds = uploadResult.resumes.map((r) => r.id);
    fastTrack.mutate({ job_description_id: selectedJdId, resume_ids: resumeIds });
  }, [selectedJdId, uploadResult, fastTrack]);

  const candidates = candidatesData?.items ?? [];

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

      {uploadResult && uploadResult.succeeded > 0 && (
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
          {candidatesLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <CandidateTable candidates={candidates} jdId={selectedJdId} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
