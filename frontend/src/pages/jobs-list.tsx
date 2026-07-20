import { useNavigate } from 'react-router-dom';
import { Briefcase, Loader2 } from 'lucide-react';
import { useJobDescriptions } from '@/hooks/use-job-descriptions';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export function JobsList() {
  const navigate = useNavigate();
  const { data, isLoading } = useJobDescriptions();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Job Descriptions</h1>
        <p className="mt-1 text-muted-foreground">
          Select a job description to view and analyze candidates.
        </p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (data?.items.length ?? 0) === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Briefcase className="mb-4 h-12 w-12 text-muted-foreground/50" />
          <p className="text-sm text-muted-foreground">
            No job descriptions uploaded yet.
          </p>
          <p className="text-xs text-muted-foreground">
            Go to the Dashboard to upload one.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data?.items.map((jd) => (
            <Card
              key={jd.id}
              className="cursor-pointer transition-colors hover:bg-muted/50"
              onClick={() => navigate(`/jobs/${jd.id}`)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') navigate(`/jobs/${jd.id}`);
              }}
            >
              <CardHeader>
                <CardTitle>{jd.title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="text-sm text-muted-foreground">{jd.company}</p>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{jd.file_type}</Badge>
                  {jd.injection_scan_passed ? (
                    <Badge variant="default">Safe</Badge>
                  ) : (
                    <Badge variant="destructive">Flagged</Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
