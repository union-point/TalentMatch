import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  pass: boolean;
}

export function StatusBadge({ pass }: StatusBadgeProps) {
  return (
    <Badge
      className={cn(
        pass
          ? 'bg-green-500/10 text-green-600 dark:bg-green-500/20 dark:text-green-400'
          : 'bg-red-500/10 text-red-600 dark:bg-red-500/20 dark:text-red-400'
      )}
    >
      {pass ? 'Pass' : 'Fail'}
    </Badge>
  );
}
