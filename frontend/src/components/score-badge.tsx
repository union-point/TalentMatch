export function ScoreBadge({ score }: { score: number }) {
  return <span className="inline-flex items-center gap-2 font-medium tabular-nums">
    {score}
    <span aria-hidden="true" className="block h-1 w-9 overflow-hidden rounded-full bg-secondary">
      <span className="block h-full bg-primary" style={{ width: Math.max(0, Math.min(100, score)) + '%' }} />
    </span>
  </span>;
}
