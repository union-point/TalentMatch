import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUpDown, Search, Eye } from 'lucide-react';
import type { RankedCandidateSchema } from '@/types';
import { useCandidates } from '@/hooks/use-candidates';
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
  jdId: string | null;
}

type SortKey = 'score' | 'candidate_name' | 'pass_fail';
type SortDir = 'asc' | 'desc';
type FilterValue = 'all' | 'pass' | 'fail';

export function CandidateTable({ jdId }: CandidateTableProps) {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterValue>('all');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const [page, setPage] = useState(1);
  const { data, isLoading, isFetching, error } = useCandidates({
    jdId, page, pageSize: 20, q: search, status: filter,
    sortBy: sortKey, sortDirection: sortDir,
  });
  const candidates = data?.items ?? [];

  function toggleSort(key: SortKey) {
    setPage(1);
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
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            aria-label="Search candidates"
            className="pl-8"
          />
        </div>
        <Select value={filter} onValueChange={(v) => { setFilter(v ?? 'all'); setPage(1); }}>
          <SelectTrigger className="w-32" aria-label="Candidate status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="pass">Pass only</SelectItem>
            <SelectItem value="fail">Fail only</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {error && <p role="alert" className="text-sm text-destructive">{error.message}</p>}
      {isFetching && <p role="status" className="text-sm text-muted-foreground">Loading candidates...</p>}
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
          {!isLoading && !error && candidates.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                {search || filter !== 'all'
                  ? 'No candidates match your search.'
                  : 'No candidates yet. Upload resumes and run analysis.'}
              </TableCell>
            </TableRow>
          )}
          {candidates.map((candidate) => (
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
                  aria-label={`View ${candidate.candidate_name ?? 'candidate'}`}
                >
                  <Eye className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {data ? `${data.total} candidates · Page ${page} of ${Math.max(1, data.pages)}` : ''}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" disabled={page === 1 || isFetching}
            onClick={() => setPage((value) => value - 1)}>Previous</Button>
          <Button variant="outline" disabled={!data || page >= data.pages || isFetching}
            onClick={() => setPage((value) => value + 1)}>Next</Button>
        </div>
      </div>
    </div>
  );
}
