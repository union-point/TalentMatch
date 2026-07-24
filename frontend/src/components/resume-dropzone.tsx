import { useState, useRef, useCallback, type DragEvent } from 'react';
import { Upload, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface ResumeDropzoneProps {
  onUpload: (files: File[]) => void;
  isUploading: boolean;
}

const SUPPORTED_EXTENSIONS = new Set(['.pdf', '.docx', '.html', '.htm']);

function isSupportedFile(name: string): boolean {
  const ext = name.toLowerCase().slice(name.lastIndexOf('.'));
  return SUPPORTED_EXTENSIONS.has(ext);
}

function readDirectoryEntries(
  reader: FileSystemDirectoryReader,
): Promise<FileSystemEntry[]> {
  return new Promise((resolve, reject) => {
    reader.readEntries((entries) => resolve(entries), reject);
  });
}

async function traverseEntry(
  entry: FileSystemEntry,
): Promise<File[]> {
  if (entry.isFile) {
    const file = await new Promise<File>((resolve, reject) =>
      (entry as FileSystemFileEntry).file(resolve, reject),
    );
    return isSupportedFile(file.name) ? [file] : [];
  }

  if (entry.isDirectory) {
    const reader = (entry as FileSystemDirectoryEntry).createReader();
    const files: File[] = [];
    let batch: FileSystemEntry[];
    do {
      batch = await readDirectoryEntries(reader);
      for (const child of batch) {
        files.push(...await traverseEntry(child));
      }
    } while (batch.length > 0);
    return files;
  }

  return [];
}

export function ResumeDropzone({ onUpload, isUploading }: ResumeDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }

  function handleDragLeave(e: DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }

  const handleDrop = useCallback(
    async (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const items = Array.from(e.dataTransfer.items);
      if (items.length > 0 && items[0].webkitGetAsEntry !== undefined) {
        const files: File[] = [];
        for (const item of items) {
          const entry = item.webkitGetAsEntry();
          if (entry) files.push(...await traverseEntry(entry));
        }
        if (files.length > 0) onUpload(files);
      } else {
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) onUpload(files);
      }
    },
    [onUpload],
  );

  function handleFileSelect() {
    fileRef.current?.click();
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) onUpload(files);
    e.target.value = '';
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        'flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors',
        isDragging
          ? 'border-primary bg-primary/5'
          : 'border-muted-foreground/25 hover:border-muted-foreground/50',
        isUploading && 'pointer-events-none opacity-50'
      )}
      onClick={handleFileSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') handleFileSelect();
      }}
    >
      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".pdf,.docx,.html,.htm"
        className="hidden"
        onChange={handleInputChange}
      />
      <div className="mb-4 rounded-full bg-muted p-3">
        {isDragging ? (
          <FileText className="h-6 w-6 text-primary" />
        ) : (
          <Upload className="h-6 w-6 text-muted-foreground" />
        )}
      </div>
      <p className="mb-1 text-sm font-medium">
        {isDragging ? 'Drop files or folders here' : 'Drag & drop resumes or folders here'}
      </p>
      <p className="mb-4 text-xs text-muted-foreground">
        or click to browse — PDF, DOCX, HTML
      </p>
      <Button type="button" variant="secondary" size="sm" disabled={isUploading}>
        {isUploading ? 'Uploading...' : 'Select Files'}
      </Button>
    </div>
  );
}
