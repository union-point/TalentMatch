import { AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import type { BatchUploadResponse } from '@/types';

interface UploadResultsProps {
  result: BatchUploadResponse | null;
}

export function UploadResults({ result }: UploadResultsProps) {
  if (!result) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-sm">
        <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
          <CheckCircle className="h-4 w-4" />
          {result.succeeded} succeeded
        </span>
        {result.failed > 0 && (
          <span className="flex items-center gap-1 text-red-600 dark:text-red-400">
            <XCircle className="h-4 w-4" />
            {result.failed} failed
          </span>
        )}
      </div>
      <div className="max-h-48 space-y-1 overflow-y-auto">
        {result.resumes.map((resume, i) => {
          const scan = resume.injection_scan;
          const hasWarning = scan && !scan.passed;
          return (
            <div
              key={`${resume.id}-${i}`}
              className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm"
            >
              <span className="flex-1 truncate">{resume.filename}</span>
              <span className="text-xs text-muted-foreground">{resume.file_type}</span>
              {hasWarning && (
                <span className="inline-flex items-center gap-1 text-xs text-orange-600 dark:text-orange-400">
                  <AlertTriangle className="h-3 w-3" />
                  Injection {scan.suspicion_score != null ? `(${scan.suspicion_score})` : 'warning'}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
