import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useUnscoredResumes } from '@/hooks/use-unscored-resumes';
import { useFastTrack } from '@/hooks/use-fast-track';

export function UnscoredResumes({ jdId }: { jdId: string }) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const { data, isFetching, error } = useUnscoredResumes(jdId, page, search);
  const analysis = useFastTrack();
  const items = data?.items ?? [];
  const selectedIds = selected.filter((id) => items.some((item) => item.id === id));

  useEffect(() => {
    if (data && page > Math.max(1, data.pages)) setPage(Math.max(1, data.pages));
  }, [data, page]);

  function changePage(next: number) {
    setPage(next);
    setSelected([]);
  }

  async function analyze() {
    try {
      const result = await analysis.mutateAsync({ job_description_id: jdId, resume_ids: selectedIds });
      const failed = new Set(result.results.filter((item) => item.error).map((item) => item.resume_id));
      setSelected((ids) => ids.filter((id) => failed.has(id)));
    } catch {
      // Keep the selection available for retry; the mutation error is shown below.
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Unscored resumes</CardTitle>
        <p className="text-sm text-muted-foreground">
          Resumes in your organization with no score for this job. Uploads remain here after refresh.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <Input aria-label="Search unscored resumes" placeholder="Search by filename, name or email..."
          value={search} disabled={analysis.isPending}
          onChange={(event) => { setSearch(event.target.value); changePage(1); }} />
        {[error, analysis.error].filter(Boolean).map((cause, index) => (
          <p key={index} role="alert" className="text-sm text-destructive">{cause?.message}</p>
        ))}
        {analysis.data?.results.filter((item) => item.error).map((item) => (
          <p key={item.resume_id} role="alert" className="text-sm text-destructive">
            {items.find((resume) => resume.id === item.resume_id)?.filename ?? item.resume_id}: {item.error}
          </p>
        ))}
        {isFetching && <p role="status">Loading unscored resumes...</p>}
        {!isFetching && !error && items.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {search ? 'No unscored resumes match your search.' : 'No unscored resumes for this job.'}
          </p>
        )}
        {items.length > 0 && (
          <fieldset disabled={analysis.isPending || isFetching} className="space-y-3">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={selectedIds.length === items.length}
                onChange={(event) => setSelected(event.target.checked ? items.map((item) => item.id) : [])} />
              Select all on this page
            </label>
            {items.map((item) => (
              <label key={item.id} className="flex items-center gap-3 rounded-md border p-3 text-sm">
                <input type="checkbox" checked={selectedIds.includes(item.id)}
                  onChange={(event) => setSelected((ids) => event.target.checked
                    ? [...ids, item.id] : ids.filter((id) => id !== item.id))} />
                <span className="min-w-0 flex-1 truncate">
                  {item.filename}{item.candidate_name ? ` — ${item.candidate_name}` : ''}
                </span>
                {!item.injection_scan_passed && <span className="text-orange-600">Injection warning</span>}
              </label>
            ))}
          </fieldset>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button disabled={selectedIds.length === 0 || analysis.isPending || isFetching}
            onClick={analyze}>
            {analysis.isPending ? 'Analyzing...' : `Analyze selected (${selectedIds.length})`}
          </Button>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground" aria-live="polite">
              {data ? `${data.total} unscored · Page ${page} of ${Math.max(1, data.pages)}` : ''}
            </span>
            <Button variant="outline" aria-label="Previous unscored page"
              disabled={page === 1 || isFetching || analysis.isPending}
              onClick={() => changePage(page - 1)}>Previous</Button>
            <Button variant="outline" aria-label="Next unscored page"
              disabled={!data || page >= data.pages || isFetching || analysis.isPending}
              onClick={() => changePage(page + 1)}>Next</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
