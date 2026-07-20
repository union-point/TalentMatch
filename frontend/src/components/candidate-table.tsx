import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUpDown, Search, Eye } from 'lucide-react';
import type { RankedCandidateSchema } from '@/types';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ScoreBadge } from '@/components/score-badge';
import { StatusBadge } from '@/components/status-badge';

interface CandidateTableProps {
  candidates: RankedCandidateSchema[];
  jdId: string | null;
}

type SortKey = 'score' | 'candidate_name' | 'pass_fail';
type SortDir = 'asc' | 'desc';
type FilterValue = 'all' | 'pass' | 'fail';

export function CandidateTable({ candidates, jdId }: CandidateTableProps) {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterValue>('all');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const filtered = useMemo(() => {
    let items = candidates;

    if (search) {
      const q = search.toLowerCase();
      items = items.filter(
        (c) =>
          (c.candidate_name ?? '').toLowerCase().includes(q) ||
          (c.email ?? '').toLowerCase().includes(q)
      );
    }

    if (filter === 'pass') {
      items = items.filter((c) => c.pass_fail);
    } else if (filter === 'fail') {
      items = items.filter((c) => !c.pass_fail);
    }

    items = [...items].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'score') {
        cmp = a.score - b.score;
      } else if (sortKey === 'candidate_name') {
        cmp = (a.candidate_name ?? '').localeCompare(b.candidate_name ?? '');
      } else {
        cmp = Number(a.pass_fail) - Number(b.pass_fail);
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });

    return items;
  }, [candidates, search, filter, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }

  function handleView(candidate: RankedCandidateSchema) {
    if (!jdId) return;
    navigate(`/candidates/${candidate.resume_id}/job/${jdId}`);
  }

  if (!jdId) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-sm text-muted-foreground">
          Select a job description to view candidates
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search candidates..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
        <Select value={filter} onValueChange={(v) => setFilter(v ?? 'all')}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="pass">Pass only</SelectItem>
            <SelectItem value="fail">Fail only</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>
              <button
                onClick={() => toggleSort('candidate_name')}
                className="inline-flex items-center gap-1 font-medium"
              >
                Name
                <ArrowUpDown className="h-3 w-3" />
              </button>
            </TableHead>
            <TableHead>
              <button
                onClick={() => toggleSort('score')}
                className="inline-flex items-center gap-1 font-medium"
              >
                Score
                <ArrowUpDown className="h-3 w-3" />
              </button>
            </TableHead>
            <TableHead>
              <button
                onClick={() => toggleSort('pass_fail')}
                className="inline-flex items-center gap-1 font-medium"
              >
                Status
                <ArrowUpDown className="h-3 w-3" />
              </button>
            </TableHead>
            <TableHead className="hidden md:table-cell">Explanation</TableHead>
            <TableHead className="w-16" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                {candidates.length === 0
                  ? 'No candidates yet. Upload resumes and run analysis.'
                  : 'No candidates match your search.'}
              </TableCell>
            </TableRow>
          )}
          {filtered.map((candidate) => (
            <TableRow key={candidate.resume_id}>
              <TableCell className="font-medium">
                {candidate.candidate_name ?? 'Unknown'}
              </TableCell>
              <TableCell>
                <ScoreBadge score={candidate.score} />
              </TableCell>
              <TableCell>
                <StatusBadge pass={candidate.pass_fail} />
              </TableCell>
              <TableCell className="hidden max-w-xs truncate md:table-cell">
                {candidate.explanation}
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => handleView(candidate)}
                >
                  <Eye className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
