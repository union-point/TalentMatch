import { cn } from '@/lib/utils';

interface ScoreBadgeProps {
  score: number;
}

export function ScoreBadge({ score }: ScoreBadgeProps) {
  const color =
    score >= 70
      ? 'bg-green-500/10 text-green-600 border-green-500/20 dark:bg-green-500/20 dark:text-green-400'
      : score >= 40
        ? 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20 dark:bg-yellow-500/20 dark:text-yellow-400'
        : 'bg-red-500/10 text-red-600 border-red-500/20 dark:bg-red-500/20 dark:text-red-400';

  return (
    <span
      className={cn(
        'inline-flex h-6 w-12 items-center justify-center rounded-md border text-xs font-medium tabular-nums',
        color
      )}
    >
      {score}
    </span>
  );
}
