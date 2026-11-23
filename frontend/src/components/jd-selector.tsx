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
  loading: boolean;
  onChange: (id: string) => void;
}

export function JdSelector({ entries, value, loading, onChange }: JdSelectorProps) {
  return (
    <Select
      disabled={loading || entries.length === 0}
      items={entries.map((entry) => ({ value: entry.id, label: `${entry.title} — ${entry.company}` }))}
      value={value}
      onValueChange={(v) => onChange(v ?? '')}
    >
      <SelectTrigger aria-label="Job description" className="w-full min-w-0">
        <SelectValue placeholder={loading ? 'Loading jobs…' : entries.length ? 'Select a job description…' : 'Create a job to get started'} />
      </SelectTrigger>
      <SelectContent>
        {entries.map((entry) => (
          <SelectItem key={entry.id} value={entry.id}>
            {entry.title} — {entry.company}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
