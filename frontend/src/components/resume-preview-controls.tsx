import { Download, Loader2, AlertCircle, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import { Button, buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export const MIN_SCALE = 0.5;
export const MAX_SCALE = 2.5;
export const DEFAULT_SCALE = 1;

export function ResumeDownload({ fileUrl, filename, label = 'Download' }: {
  fileUrl: string;
  filename: string;
  label?: string;
}) {
  return <a href={fileUrl} download={filename} className={buttonVariants({ variant: 'outline', size: 'sm' })}>
    <Download aria-hidden="true" />{label}
  </a>;
}

export function PdfSkeleton() {
  return (
    <div className="flex h-[min(60vh,520px)] flex-col items-center justify-center gap-3">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      <p className="text-sm text-muted-foreground">Loading PDF…</p>
    </div>
  );
}

export function PdfError({ fileUrl, filename }: { fileUrl: string; filename: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <AlertCircle className="h-8 w-8 text-destructive" />
      <div className="space-y-1">
        <p className="text-sm font-medium">Could not load PDF preview</p>
        <p className="text-xs text-muted-foreground">
          The file may be unavailable or corrupted.
        </p>
      </div>
      <ResumeDownload fileUrl={fileUrl} filename={filename} label="Download PDF" />
    </div>
  );
}

export function ZoomControls({
  scale,
  onZoomIn,
  onZoomOut,
  onReset,
}: {
  scale: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
}) {
  const percent = Math.round(scale * 100);

  return (
    <div className="flex shrink-0 items-center gap-0.5 rounded-md border bg-background p-0.5">
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        onClick={onZoomOut}
        disabled={scale <= MIN_SCALE}
        aria-label="Zoom out"
      >
        <ZoomOut />
      </Button>
      <button
        type="button"
        onClick={onReset}
        className={cn(
          'min-w-12 rounded-md px-1 py-0.5 text-center text-xs font-medium tabular-nums',
          'text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
          'disabled:pointer-events-none disabled:opacity-50',
        )}
        disabled={scale === DEFAULT_SCALE}
        aria-label="Reset zoom"
        title="Reset zoom"
      >
        {percent}%
      </button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        onClick={onZoomIn}
        disabled={scale >= MAX_SCALE}
        aria-label="Zoom in"
      >
        <ZoomIn />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        onClick={onReset}
        disabled={scale === DEFAULT_SCALE}
        aria-label="Fit to width"
        title="Fit to width"
      >
        <Maximize2 />
      </Button>
    </div>
  );
}

