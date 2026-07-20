import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { EvidenceSchema } from '@/types';

interface EvidenceListProps {
  evidence: EvidenceSchema[];
}

const categoryColors: Record<string, string> = {
  skills: 'bg-blue-500/10 text-blue-600 border-blue-500/20 dark:bg-blue-500/20 dark:text-blue-400',
  experience:
    'bg-purple-500/10 text-purple-600 border-purple-500/20 dark:bg-purple-500/20 dark:text-purple-400',
  education:
    'bg-green-500/10 text-green-600 border-green-500/20 dark:bg-green-500/20 dark:text-green-400',
  achievement:
    'bg-amber-500/10 text-amber-600 border-amber-500/20 dark:bg-amber-500/20 dark:text-amber-400',
};

export function EvidenceList({ evidence }: EvidenceListProps) {
  return (
    <ul className="space-y-3">
      {evidence.map((item, i) => (
        <li key={i} className="rounded-lg border p-3">
          <p className="text-sm leading-relaxed">{item.text}</p>
          <Badge
            variant="outline"
            className={cn(
              'mt-2 text-xs font-medium',
              categoryColors[item.category] ||
                'bg-gray-500/10 text-gray-600 border-gray-500/20 dark:bg-gray-500/20 dark:text-gray-400'
            )}
          >
            {item.category}
          </Badge>
        </li>
      ))}
    </ul>
  );
}
