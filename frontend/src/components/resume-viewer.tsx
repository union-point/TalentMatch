import { useCallback, useEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import {
  FileText,
  Download,
  Loader2,
  AlertCircle,
  ZoomIn,
  ZoomOut,
  Maximize2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

interface ResumeViewerProps {
  resumeId: string;
  fileType: string;
  filename: string;
}

const BASE_URL = '/api';
const PAGE_PADDING = 32;
const MIN_SCALE = 0.5;
const MAX_SCALE = 2.5;
const SCALE_STEP = 0.25;
const DEFAULT_SCALE = 1;

function clampScale(value: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.round(value * 100) / 100));
}

function PdfSkeleton() {
  return (
    <div className="flex h-[min(60vh,520px)] flex-col items-center justify-center gap-3">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      <p className="text-sm text-muted-foreground">Loading PDF…</p>
    </div>
  );
}

function PdfError({ fileUrl, filename }: { fileUrl: string; filename: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <AlertCircle className="h-8 w-8 text-destructive" />
      <div className="space-y-1">
        <p className="text-sm font-medium">Could not load PDF preview</p>
        <p className="text-xs text-muted-foreground">
          The file may be unavailable or corrupted.
        </p>
      </div>
      <Button variant="outline" size="sm" render={<a href={fileUrl} download={filename} />}>
        <Download className="h-4 w-4" />
        Download PDF
      </Button>
    </div>
  );
}

function ZoomControls({
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

function PdfDocument({ fileUrl, filename }: { fileUrl: string; filename: string }) {
  const shellRef = useRef<HTMLDivElement>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [baseWidth, setBaseWidth] = useState(0);
  const [numPages, setNumPages] = useState(0);
  const [scale, setScale] = useState(DEFAULT_SCALE);

  useEffect(() => {
    const el = shellRef.current;
    if (!el) return;

    const updateWidth = () => {
      const next = Math.max(0, Math.floor(el.clientWidth) - PAGE_PADDING);
      setBaseWidth((prev) => (prev === next ? prev : next));
    };

    updateWidth();

    const observer = new ResizeObserver(updateWidth);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const zoomIn = useCallback(() => {
    setScale((prev) => clampScale(prev + SCALE_STEP));
  }, []);

  const zoomOut = useCallback(() => {
    setScale((prev) => clampScale(prev - SCALE_STEP));
  }, []);

  const resetZoom = useCallback(() => {
    setScale(DEFAULT_SCALE);
  }, []);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;

    const onWheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      const direction = event.deltaY > 0 ? -1 : 1;
      setScale((prev) => clampScale(prev + direction * SCALE_STEP));
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  const onLoadSuccess = useCallback(({ numPages: pages }: { numPages: number }) => {
    setNumPages(pages);
  }, []);

  const pageWidth = baseWidth > 0 ? Math.floor(baseWidth * scale) : 0;

  return (
    <div ref={shellRef} className="w-full min-w-0 max-w-full space-y-2">
      <div className="flex min-w-0 items-center gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-2 text-sm text-muted-foreground">
          <FileText className="h-4 w-4 shrink-0" />
          <span className="truncate">{filename}</span>
        </div>
        <ZoomControls
          scale={scale}
          onZoomIn={zoomIn}
          onZoomOut={zoomOut}
          onReset={resetZoom}
        />
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          render={<a href={fileUrl} download={filename} />}
        >
          <Download className="h-4 w-4" />
          Download
        </Button>
      </div>
      <div
        ref={scrollerRef}
        className="max-h-[min(70vh,800px)] w-full min-w-0 overflow-auto overscroll-contain rounded-lg border bg-muted/40"
      >
        <Document
          file={fileUrl}
          onLoadSuccess={onLoadSuccess}
          loading={<PdfSkeleton />}
          error={<PdfError fileUrl={fileUrl} filename={filename} />}
          externalLinkTarget="_blank"
          externalLinkRel="noopener noreferrer"
          className="flex w-max min-w-full flex-col items-center gap-4 p-4"
        >
          {pageWidth > 0 &&
            Array.from({ length: numPages }, (_, index) => (
              <Page
                key={`page-${index + 1}`}
                pageNumber={index + 1}
                width={pageWidth}
                renderTextLayer={false}
                renderAnnotationLayer
                className="react-pdf-page max-w-none shrink-0 rounded-md bg-white shadow-sm ring-1 ring-foreground/10"
                loading={
                  <div
                    className="animate-pulse rounded-md bg-muted"
                    style={{ width: pageWidth, height: pageWidth * 1.3 }}
                  />
                }
              />
            ))}
        </Document>
      </div>
    </div>
  );
}

export function ResumeViewer({ resumeId, fileType, filename }: ResumeViewerProps) {
  const fileUrl = `${BASE_URL}/v1/dashboard/candidates/${resumeId}/resume-file`;

  if (fileType === 'pdf') {
    return (
      <div className="w-full min-w-0 max-w-full">
        <PdfDocument fileUrl={fileUrl} filename={filename} />
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between rounded-lg border p-4">
      <div className="flex items-center gap-3">
        <FileText className="h-5 w-5 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">{filename}</p>
          <p className="text-xs text-muted-foreground">{fileType}</p>
        </div>
      </div>
      <Button variant="outline" size="sm" render={<a href={fileUrl} download={filename} />}>
        <Download className="h-4 w-4" />
        Download
      </Button>
    </div>
  );
}
