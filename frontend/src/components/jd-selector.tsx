import type { JobDescriptionListItem } from '@/types';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface JdSelectorProps {
  entries: JobDescriptionListItem[];
  value: string | null;
  onChange: (id: string) => void;
}

export function JdSelector({ entries, value, onChange }: JdSelectorProps) {
  return (
    <Select
      items={entries.map((entry) => ({ value: entry.id, label: `${entry.title} — ${entry.company}` }))}
      value={value}
      onValueChange={(v) => onChange(v ?? '')}
    >
      <SelectTrigger aria-label="Job description" className="w-full min-w-0">
        <SelectValue placeholder="Select a job description…" />
      </SelectTrigger>
      <SelectContent>
        {entries.length === 0 && (
          <div className="px-2 py-4 text-center text-sm text-muted-foreground">
            No job descriptions uploaded yet
          </div>
        )}
        {entries.map((entry) => (
          <SelectItem key={entry.id} value={entry.id}>
            {entry.title} — {entry.company}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
