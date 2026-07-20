import { Target } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { ScoreBadge } from '@/components/score-badge';
import { StatusBadge } from '@/components/status-badge';
import type { FastTrackSummarySchema } from '@/types';

interface FastTrackCardProps {
  fastTrack: FastTrackSummarySchema;
}

export function FastTrackCard({ fastTrack }: FastTrackCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Target className="h-5 w-5 text-primary" />
          Fast-Track Analysis
        </CardTitle>
        <StatusBadge pass={fastTrack.pass_fail} />
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-center">
            <span className="text-sm text-muted-foreground">Score</span>
            <ScoreBadge score={fastTrack.score} />
          </div>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {fastTrack.explanation}
        </p>
      </CardContent>
    </Card>
  );
}
