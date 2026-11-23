import { Badge } from '@/components/ui/badge';
import type { EvidenceSchema } from '@/types';

interface EvidenceListProps {
  evidence: EvidenceSchema[];
}

export function EvidenceList({ evidence }: EvidenceListProps) {
  return (
    <ul className="space-y-3">
      {evidence.map((item, i) => (
        <li key={i} className="rounded-lg border p-3">
          <p className="text-sm leading-relaxed">{item.text}</p>
          <Badge
            variant="outline"
            className="mt-2 bg-muted text-xs font-medium"
          >
            {item.category}
          </Badge>
        </li>
      ))}
    </ul>
  );
}
