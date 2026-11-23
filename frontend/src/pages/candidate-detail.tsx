import { lazy, Suspense, useCallback } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2, Brain, ShieldAlert, ShieldCheck, FileText, Mail } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { FastTrackCard } from '@/components/fast-track-card';
import { DeepAnalysisPanel } from '@/components/deep-analysis-panel';
import { useCandidateDetail } from '@/hooks/use-candidate-detail';
import { useDeepAnalysisMutation, useDeepAnalysisPolling } from '@/hooks/use-deep-analysis';
import type { DeepAnalysisResultSchema } from '@/types';

const ResumeViewer = lazy(() => import('@/components/resume-viewer').then((module) => ({ default: module.ResumeViewer })));

export function CandidateDetail() {
  const { resumeId, jdId } = useParams<{ resumeId: string; jdId: string }>();
  return <CandidateDetailContent key={`${resumeId}:${jdId}`} resumeId={resumeId} jdId={jdId} />;
}

function CandidateDetailContent({ resumeId, jdId }: { resumeId?: string; jdId?: string }) {
  const { state } = useLocation();
  const jobsPath = jdId ? '/jobs/' + jdId : '/jobs';
  const backPath = jdId && state?.fromDashboard ? '/?jd=' + encodeURIComponent(jdId) : jobsPath;
  const backLabel = state?.fromDashboard ? 'Back to dashboard' : 'Back to job';

  const { data: detail, isLoading, error, refetch } = useCandidateDetail({
    resumeId: resumeId ?? '',
    jdId: jdId ?? '',
  });

  const deepAnalysisMutation = useDeepAnalysisMutation();

  const analysis = deepAnalysisMutation.data ?? detail?.deep_analysis;
  const pollId = analysis?.analysis_id ?? null;
  const pollQuery = useDeepAnalysisPolling(pollId, analysis?.status ?? 'pending');
  const currentStatus = pollQuery.data?.status ?? analysis?.status;
  const hasAnalysisInProgress = currentStatus === 'pending' || currentStatus === 'in_progress';

  const handleDeepAnalysis = useCallback(() => {
    if (!resumeId || !jdId) return;
    deepAnalysisMutation.mutate({
      resume_id: resumeId,
      job_description_id: jdId,
    });
  }, [resumeId, jdId, deepAnalysisMutation]);

  const analysisResult: DeepAnalysisResultSchema | undefined = pollQuery.data ?? analysis ?? undefined;

  if (isLoading) {
    return (
      <div role="status" className="flex items-center justify-center gap-2 py-20 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Loading candidate…
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="space-y-4">
        <Link className="back-link" to={backPath}><ArrowLeft size={15} />{backLabel}</Link>
        <div className="flex flex-col items-center justify-center py-20 text-center">
          {error ? <div role="alert">{error.message} <Button variant="outline" onClick={() => void refetch()}>Retry</Button></div> : <p>Candidate not found.</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="min-w-0 max-w-full space-y-6">
      <Link className="back-link" to={backPath}><ArrowLeft size={15} />{backLabel}</Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold">
            {detail.candidate_name ?? 'Unknown Candidate'}
          </h1>
          <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
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
            <Badge variant="outline" className="border-border bg-muted text-foreground">
              <ShieldCheck className="mr-1 h-3 w-3" />
              Scan Passed
            </Badge>
          ) : (
            <Badge variant="outline" className="border-border bg-muted text-foreground">
              <ShieldAlert className="mr-1 h-3 w-3" />
              Injection Warning
            </Badge>
          )}
        </div>
      </div>

      <Separator />

      {detail.fast_track && <FastTrackCard fastTrack={detail.fast_track} />}

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
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
          {deepAnalysisMutation.error && <p role="alert">{deepAnalysisMutation.error.message}</p>}
          {pollQuery.error && <p role="alert">{pollQuery.error.message} <button className="text-link" onClick={() => void pollQuery.refetch()}>Retry</button></p>}
          <DeepAnalysisPanel
            analysisResult={analysisResult}
            isLoading={deepAnalysisMutation.isPending && !pollQuery.data}
          />
          {!analysisResult && !hasAnalysisInProgress && !deepAnalysisMutation.isPending && (
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
          <Suspense fallback={<p role="status">Loading résumé…</p>}>
            <ResumeViewer
              resumeId={resumeId ?? ''}
              fileType={detail.file_type}
              filename={detail.filename}
            />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  );
}
