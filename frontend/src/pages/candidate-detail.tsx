import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Brain, ShieldAlert, ShieldCheck, FileText, Mail } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { FastTrackCard } from '@/components/fast-track-card';
import { DeepAnalysisPanel } from '@/components/deep-analysis-panel';
import { ResumeViewer } from '@/components/resume-viewer';
import { useCandidateDetail } from '@/hooks/use-candidate-detail';
import { useDeepAnalysisMutation, useDeepAnalysisPolling } from '@/hooks/use-deep-analysis';
import type { DeepAnalysisResultSchema } from '@/types';

export function CandidateDetail() {
  const { resumeId, jdId } = useParams<{ resumeId: string; jdId: string }>();
  const navigate = useNavigate();

  const { data: detail, isLoading } = useCandidateDetail({
    resumeId: resumeId ?? '',
    jdId: jdId ?? '',
  });

  const deepAnalysisMutation = useDeepAnalysisMutation();

  const [pollId, setPollId] = useState<string | null>(null);
  const [pollInitialStatus, setPollInitialStatus] = useState('pending');

  const pollQuery = useDeepAnalysisPolling(pollId, pollInitialStatus);

  useEffect(() => {
    if (deepAnalysisMutation.data) {
      setPollId(deepAnalysisMutation.data.analysis_id);
      setPollInitialStatus(deepAnalysisMutation.data.status);
    }
  }, [deepAnalysisMutation.data]);

  const existingAnalysisId = detail?.deep_analysis?.analysis_id ?? null;
  const existingAnalysisStatus = detail?.deep_analysis?.status ?? '';

  const hasAnalysisInProgress =
    pollQuery.data?.status === 'pending' ||
    pollQuery.data?.status === 'in_progress' ||
    (existingAnalysisId &&
      !pollId &&
      (existingAnalysisStatus === 'in_progress' || existingAnalysisStatus === 'pending'));

  const handleDeepAnalysis = useCallback(() => {
    if (!resumeId || !jdId) return;
    deepAnalysisMutation.mutate({
      resume_id: resumeId,
      job_description_id: jdId,
    });
  }, [resumeId, jdId, deepAnalysisMutation]);

  const analysisResult: DeepAnalysisResultSchema | undefined =
    pollQuery.data ??
    (detail?.deep_analysis?.status === 'completed' || detail?.deep_analysis?.status === 'failed'
      ? (detail.deep_analysis as DeepAnalysisResultSchema)
      : undefined);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-muted-foreground">Candidate not found.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate(-1)}>
        <ArrowLeft className="h-4 w-4" />
        Back
      </Button>

      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold">
            {detail.candidate_name ?? 'Unknown Candidate'}
          </h1>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            {detail.email && (
              <span className="flex items-center gap-1">
                <Mail className="h-4 w-4" />
                {detail.email}
              </span>
            )}
            <span className="flex items-center gap-1">
              <FileText className="h-4 w-4" />
              {detail.filename}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {detail.injection_scan_passed ? (
            <Badge variant="outline" className="border-green-500/20 bg-green-500/10 text-green-600 dark:text-green-400">
              <ShieldCheck className="mr-1 h-3 w-3" />
              Scan Passed
            </Badge>
          ) : (
            <Badge variant="outline" className="border-red-500/20 bg-red-500/10 text-red-600 dark:text-red-400">
              <ShieldAlert className="mr-1 h-3 w-3" />
              Injection Warning
            </Badge>
          )}
        </div>
      </div>

      <Separator />

      {detail.fast_track && <FastTrackCard fastTrack={detail.fast_track} />}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Brain className="h-5 w-5 text-primary" />
            Deep Analysis
          </CardTitle>
          <Button
            onClick={handleDeepAnalysis}
            disabled={hasAnalysisInProgress || deepAnalysisMutation.isPending}
          >
            {deepAnalysisMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Brain className="h-4 w-4" />
            )}
            {deepAnalysisMutation.isPending ? 'Starting...' : hasAnalysisInProgress ? 'In Progress' : 'Run Deep Analysis'}
          </Button>
        </CardHeader>
        <CardContent>
          <DeepAnalysisPanel
            analysisResult={analysisResult}
            isLoading={deepAnalysisMutation.isPending && !pollQuery.data}
          />
          {!analysisResult && !deepAnalysisMutation.isPending && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No deep analysis yet. Click &quot;Run Deep Analysis&quot; to start.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <FileText className="h-5 w-5 text-primary" />
            Resume
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ResumeViewer
            resumeId={resumeId ?? ''}
            fileType={detail.file_type}
            filename={detail.filename}
          />
        </CardContent>
      </Card>
    </div>
  );
}
