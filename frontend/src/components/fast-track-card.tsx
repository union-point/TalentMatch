import { Target } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
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
      <CardContent className="grid items-center gap-5 sm:grid-cols-[auto_minmax(0,1fr)]">
        <div className="rounded-md bg-primary px-6 py-4 text-primary-foreground">
          <span className="block text-xs">Match score</span>
          <span className="font-heading text-5xl">{fastTrack.score}</span><span className="ml-1 text-xs">/ 100</span>
        </div>
        <p className="max-w-prose text-sm leading-relaxed">{fastTrack.explanation}</p>
      </CardContent>
    </Card>
  );
}
