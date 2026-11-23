import { useEffect, useRef, useState } from 'react';
import type { DragEvent, FormEvent, RefObject } from 'react';
import { FileText, Type, Upload } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';

type Mode = 'text' | 'file';

interface JdUploadDialogProps {
  open: boolean;
  companyName: string;
  triggerRef: RefObject<HTMLButtonElement | null>;
  error?: string;
  onClearError: () => void;
  onOpenChange: (open: boolean) => void;
  onUpload: (data: { file: File; title: string; company: string }) => void;
  isUploading: boolean;
}

const FILE_EXTENSIONS = ['.pdf', '.docx', '.html', '.htm', '.txt', '.md', '.markdown'];
const FILE_FORMATS = 'PDF, DOCX, HTML, TXT, and Markdown';

export function JdUploadDialog({
  open,
  companyName,
  triggerRef,
  error,
  onClearError,
  onOpenChange,
  onUpload,
  isUploading,
}: JdUploadDialogProps) {
  const [mode, setMode] = useState<Mode>('text');
  const [title, setTitle] = useState('');
  const [company, setCompany] = useState(companyName);
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState('');
  const [dragging, setDragging] = useState(false);
  const [popup, setPopup] = useState<HTMLDivElement | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const canSubmit = Boolean(title.trim() && company.trim() &&
    (mode === 'text' ? text.trim() : file && !fileError));

  useEffect(() => {
    const viewport = window.visualViewport;
    if (!popup || !viewport) return;

    function fitVisibleViewport() {
      if (!popup || !viewport) return;
      if (viewport.scale !== 1) {
        popup.style.removeProperty('--job-viewport-height');
        popup.style.removeProperty('--job-viewport-center');
        return;
      }
      popup.style.setProperty('--job-viewport-height', viewport.height + 'px');
      popup.style.setProperty('--job-viewport-center', viewport.offsetTop + viewport.height / 2 + 'px');
    }

    fitVisibleViewport();
    viewport.addEventListener('resize', fitVisibleViewport);
    viewport.addEventListener('scroll', fitVisibleViewport);
    return () => {
      viewport.removeEventListener('resize', fitVisibleViewport);
      viewport.removeEventListener('scroll', fitVisibleViewport);
    };
  }, [popup]);

  function selectFile(files: FileList | null) {
    if (isUploading || !files?.length) return;
    onClearError();
    if (files.length !== 1) {
      setFileError('Choose one job description file.');
      return;
    }
    const chosen = files[0];
    const extension = chosen.name.slice(chosen.name.lastIndexOf('.')).toLowerCase();
    if (!FILE_EXTENSIONS.includes(extension)) {
      setFileError('Choose a PDF, DOCX, HTML, TXT, or Markdown file.');
      return;
    }
    if (chosen.size === 0) {
      setFileError('This file is empty. Choose a file with a job description.');
      return;
    }
    setFile(chosen);
    setFileError('');
  }

  function dropFile(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    selectFile(event.dataTransfer.files);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || isUploading) return;
    const description = mode === 'text'
      ? new File([text.trim()], 'job-description.txt', { type: 'text/plain' })
      : file;
    if (description) onUpload({ file: description, title: title.trim(), company: company.trim() });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        ref={setPopup}
        initialFocus={heading}
        finalFocus={triggerRef}
        showCloseButton={!isUploading}
        className="top-[var(--job-viewport-center,50%)] flex h-[calc(var(--job-viewport-height,100dvh)_-_1rem)] max-h-[calc(var(--job-viewport-height,100dvh)_-_1rem)] max-w-[calc(100%-1rem)] flex-col gap-0 overflow-hidden p-0 sm:h-auto sm:max-h-[calc(var(--job-viewport-height,100dvh)_-_3rem)] sm:max-w-[35rem]"
      >
        <DialogHeader className="shrink-0 border-b px-5 py-4 pr-14 sm:px-7 sm:py-5">
          <DialogTitle ref={heading} tabIndex={-1} className="text-4xl focus:outline-none">New job</DialogTitle>
          <DialogDescription>Add a job description to create a vacancy.</DialogDescription>
        </DialogHeader>

        <form className="flex min-h-0 flex-1 flex-col" onSubmit={submit} aria-busy={isUploading}>
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-5 py-4 sm:px-7 sm:py-5">
            <div className="space-y-1.5">
              <label htmlFor="job-title" className="font-medium">Job title</label>
              <Input id="job-title" placeholder="e.g. Senior Frontend Engineer" value={title}
                onChange={(event) => setTitle(event.target.value)} disabled={isUploading} maxLength={255} required />
            </div>

            <Tabs className="[--job-editor-height:clamp(9rem,calc(var(--job-viewport-height,100dvh)*0.38),20rem)] sm:[--job-editor-height:12rem]"
              value={mode} onValueChange={(value) => {
              if (isUploading || (value !== 'text' && value !== 'file')) return;
              setMode(value);
              setDragging(false);
              onClearError();
            }}>
              <TabsList className="w-full group-data-horizontal/tabs:h-11" aria-label="Job description source">
                <TabsTrigger value="text" disabled={isUploading}><Type size={16} />Paste text</TabsTrigger>
                <TabsTrigger value="file" disabled={isUploading}><Upload size={16} />Upload file</TabsTrigger>
              </TabsList>
              <TabsContent value="text">
                <div className="space-y-1.5">
                  <label htmlFor="job-description-text" className="block font-medium">Job description</label>
                  <textarea id="job-description-text" value={text} disabled={isUploading}
                    onChange={(event) => setText(event.target.value)}
                    placeholder="Paste the responsibilities, requirements, and other details here."
                    className="block h-[var(--job-editor-height)] w-full resize-y rounded-lg border border-input bg-card p-3 text-base leading-relaxed placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-60"
                  />
                </div>
              </TabsContent>
              <TabsContent value="file">
                <div className="space-y-1.5">
                  <p id="job-description-file-label" className="font-medium">Job description file</p>
                  <div
                    aria-labelledby="job-description-file-label"
                    role="group"
                    onDragOver={(event) => {
                      event.preventDefault();
                      event.dataTransfer.dropEffect = isUploading ? 'none' : 'copy';
                      if (!isUploading) setDragging(true);
                    }}
                    onDragLeave={(event) => {
                      if (!(event.relatedTarget instanceof Node) || !event.currentTarget.contains(event.relatedTarget)) {
                        setDragging(false);
                      }
                    }}
                    onDrop={dropFile}
                    className={cn(
                      'flex min-h-[var(--job-editor-height)] min-w-0 flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-background px-3 py-4 text-center',
                      dragging ? 'border-foreground bg-muted' : 'border-input',
                    )}
                  >
                    <FileText className="size-5 text-muted-foreground" aria-hidden="true" />
                    <p aria-live="polite" className="max-w-full wrap-anywhere font-medium">
                      {file ? file.name : dragging ? 'Drop your file here' : 'Drag and drop a file here'}
                    </p>
                    <p id="job-formats" className="text-xs text-muted-foreground">{FILE_FORMATS}</p>
                    <input ref={fileInput} type="file" aria-label="Job description file" className="hidden"
                      accept={FILE_EXTENSIONS.join(',')} disabled={isUploading}
                      onChange={(event) => {
                        selectFile(event.currentTarget.files);
                        event.currentTarget.value = '';
                      }}
                    />
                    <Button type="button" variant="outline" aria-describedby="job-formats"
                      disabled={isUploading} onClick={() => fileInput.current?.click()}>
                      Select file
                    </Button>
                  </div>
                  {fileError && <p role="alert">{fileError}</p>}
                </div>
              </TabsContent>
            </Tabs>

            <div className="space-y-1.5">
              <label htmlFor="job-company" className="font-medium">Company</label>
              <Input id="job-company" placeholder="e.g. Acme Corp" value={company}
                onChange={(event) => setCompany(event.target.value)} disabled={isUploading} maxLength={255} required />
            </div>
          </div>

          <DialogFooter className="mx-0 mb-0 shrink-0 flex-col px-5 py-3 sm:flex-col sm:px-7">
            {error && <p role="alert">{error}</p>}
            <Button type="submit" className="min-h-11 w-full sm:w-auto sm:self-end" disabled={!canSubmit || isUploading}>
              {isUploading ? 'Creating vacancy…' : 'Create vacancy'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
