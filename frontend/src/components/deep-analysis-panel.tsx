import { useState } from 'react';
import {
  Sparkles,
  AlertTriangle,
  Lightbulb,
  Target,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Brain,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { ScoreBadge } from '@/components/score-badge';
import { DeepAnalysisStatus } from '@/components/deep-analysis-status';
import { EvidenceList } from '@/components/evidence-list';
import { cn } from '@/lib/utils';
import type { DeepAnalysisResultSchema } from '@/types';

interface DeepAnalysisPanelProps {
  analysisResult: DeepAnalysisResultSchema | undefined;
  isLoading: boolean;
}

function SectionList({
  icon: Icon,
  title,
  items,
  color,
}: {
  icon: React.ElementType;
  title: string;
  items: string[];
  color: string;
}) {
  const [open, setOpen] = useState(true);
  if (!items || items.length === 0) return null;

  return (
    <div className="space-y-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between text-sm font-medium"
      >
        <span className="flex items-center gap-2">
          <Icon className={cn('h-4 w-4', color)} />
          {title} ({items.length})
        </span>
        {open ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {open && (
        <ul className="space-y-1.5 pl-6">
          {items.map((item, i) => (
            <li key={i} className="text-sm text-muted-foreground list-disc">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function DeepAnalysisPanel({
  analysisResult,
  isLoading,
}: DeepAnalysisPanelProps) {
  if (isLoading) {
    return <div className="flex items-center justify-center py-12"><Brain className="h-8 w-8 animate-pulse text-muted-foreground" /></div>;
  }

  if (!analysisResult) return null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Brain className="h-5 w-5 text-primary" />
          Deep Analysis
        </CardTitle>
        <DeepAnalysisStatus status={analysisResult.status} />
      </CardHeader>
      <CardContent className="space-y-4">
        {analysisResult.status === 'failed' && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-600 dark:text-red-400">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {analysisResult.error_message || 'Analysis failed'}
          </div>
        )}

        {analysisResult.status === 'completed' && (
          <>
            {analysisResult.overall_score != null && (
              <div className="flex items-center gap-3">
                <span className="text-sm text-muted-foreground">
                  Overall Score
                </span>
                <ScoreBadge score={analysisResult.overall_score} />
              </div>
            )}

            {analysisResult.strengths && analysisResult.strengths.length > 0 && (
              <SectionList
                icon={Sparkles}
                title="Strengths"
                items={analysisResult.strengths}
                color="text-green-600 dark:text-green-400"
              />
            )}

            {analysisResult.weaknesses && analysisResult.weaknesses.length > 0 && (
              <SectionList
                icon={AlertTriangle}
                title="Weaknesses"
                items={analysisResult.weaknesses}
                color="text-amber-600 dark:text-amber-400"
              />
            )}

            {analysisResult.risks && analysisResult.risks.length > 0 && (
              <SectionList
                icon={Target}
                title="Risks"
                items={analysisResult.risks}
                color="text-red-600 dark:text-red-400"
              />
            )}

            {analysisResult.detailed_reasoning && (
              <div className="space-y-2">
                <Separator />
                <h4 className="flex items-center gap-2 text-sm font-medium">
                  <MessageSquare className="h-4 w-4 text-muted-foreground" />
                  Detailed Reasoning
                </h4>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {analysisResult.detailed_reasoning}
                </p>
              </div>
            )}

            {analysisResult.evidence && analysisResult.evidence.length > 0 && (
              <div className="space-y-2">
                <Separator />
                <h4 className="flex items-center gap-2 text-sm font-medium">
                  <Lightbulb className="h-4 w-4 text-muted-foreground" />
                  Evidence ({analysisResult.evidence.length})
                </h4>
                <EvidenceList evidence={analysisResult.evidence} />
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
