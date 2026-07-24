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
  const originRef = useRef({ x: 0, y: 0 });
  const pendingScrollRef = useRef<{ left: number; top: number } | null>(null);
  const prevRenderScaleRef = useRef(DEFAULT_SCALE);

  const [baseWidth, setBaseWidth] = useState(0);
  const [numPages, setNumPages] = useState(0);
  const [scale, setScale] = useState(DEFAULT_SCALE);
  const [renderScale, setRenderScale] = useState(DEFAULT_SCALE);

  useEffect(() => {
    const timer = setTimeout(() => setRenderScale(scale), 120);
    return () => clearTimeout(timer);
  }, [scale]);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const prev = prevRenderScaleRef.current;
    if (prev !== renderScale) {
      if (pendingScrollRef.current) {
        el.scrollLeft = pendingScrollRef.current.left;
        el.scrollTop = pendingScrollRef.current.top;
        pendingScrollRef.current = null;
      } else {
        const ratio = renderScale / prev;
        el.scrollLeft *= ratio;
        el.scrollTop *= ratio;
      }
    }
    prevRenderScaleRef.current = renderScale;
  }, [renderScale]);

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

  function applyZoom(el: HTMLElement, prev: number, next: number, focalX: number, focalY: number) {
    const ratio = next / prev;
    pendingScrollRef.current = {
      left: (el.scrollLeft + focalX) * ratio - focalX,
      top: (el.scrollTop + focalY) * ratio - focalY,
    };
    originRef.current = {
      x: el.scrollLeft + focalX,
      y: el.scrollTop + focalY,
    };
  }

  const zoomIn = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    setScale((prev) => {
      const next = clampScale(prev + SCALE_STEP);
      if (next !== prev) {
        applyZoom(el, prev, next, el.clientWidth / 2, el.clientHeight / 2);
      }
      return next;
    });
  }, []);

  const zoomOut = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    setScale((prev) => {
      const next = clampScale(prev - SCALE_STEP);
      if (next !== prev) {
        applyZoom(el, prev, next, el.clientWidth / 2, el.clientHeight / 2);
      }
      return next;
    });
  }, []);

  const resetZoom = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    setScale((prev) => {
      if (prev !== DEFAULT_SCALE) {
        applyZoom(el, prev, DEFAULT_SCALE, el.clientWidth / 2, el.clientHeight / 2);
      }
      return DEFAULT_SCALE;
    });
  }, []);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const onWheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();

      const rect = el.getBoundingClientRect();
      const mouseX = event.clientX - rect.left;
      const mouseY = event.clientY - rect.top;
      const delta = -event.deltaY * 0.0015;

      setScale((prev) => {
        const next = clampScale(prev + delta);
        if (next !== prev) {
          const ratio = next / prev;
          pendingScrollRef.current = {
            left: (el.scrollLeft + mouseX) * ratio - mouseX,
            top: (el.scrollTop + mouseY) * ratio - mouseY,
          };
          originRef.current = {
            x: el.scrollLeft + mouseX,
            y: el.scrollTop + mouseY,
          };
        }
        return next;
      });
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  const onLoadSuccess = useCallback(({ numPages: pages }: { numPages: number }) => {
    setNumPages(pages);
  }, []);

  const pageWidth = baseWidth > 0 ? Math.floor(baseWidth * renderScale) : 0;
  const previewRatio = scale / renderScale;
  const showPreview = pageWidth > 0 && numPages > 0 && Math.abs(previewRatio - 1) > 0.001;
  const visualWidth = pageWidth > 0 ? Math.floor(pageWidth * previewRatio) : 0;

  function renderPages() {
    const pageElements =
      pageWidth > 0 &&
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
      ));

    if (!showPreview || !pageElements) return pageElements;

    const { x: ox, y: oy } = originRef.current;
    const invRatio = 1 / previewRatio;
    const tx = ox * (invRatio - 1);
    const ty = oy * (invRatio - 1);

    const estimatedPageHeight = pageWidth * 1.3;
    const totalHeight = numPages * estimatedPageHeight + (numPages - 1) * 16;
    const sizerHeight = Math.floor(totalHeight * previewRatio);

    return (
      <div
        className="relative"
        style={{ width: `${visualWidth}px`, height: `${sizerHeight}px` }}
      >
        <div
          className="flex flex-col items-center gap-4"
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            transformOrigin: '0 0',
            transform: `scale(${previewRatio}) translate(${tx}px, ${ty}px)`,
          }}
        >
          {pageElements}
        </div>
      </div>
    );
  }

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
          {renderPages()}
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