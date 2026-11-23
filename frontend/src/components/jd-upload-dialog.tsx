import { useState } from 'react';
import { Upload } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface JdUploadDialogProps {
  open: boolean;
  error?: string;
  onOpenChange: (open: boolean) => void;
  onUpload: (data: { file: File; title: string; company: string }) => void;
  isUploading: boolean;
}

export function JdUploadDialog({ open, onOpenChange, onUpload, isUploading, error }: JdUploadDialogProps) {
  const [title, setTitle] = useState('');
  const [company, setCompany] = useState('');
  const [file, setFile] = useState<File | null>(null);


  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !title.trim() || !company.trim()) return;
    onUpload({ file, title: title.trim(), company: company.trim() });

  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-md" showCloseButton={!isUploading}>
        <DialogHeader>
          <DialogTitle className="text-4xl">New job</DialogTitle>
          <DialogDescription>
            Add the role and its job description to your workspace.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="job-title" className="text-sm font-medium">Job title</label>
            <Input
              id="job-title" disabled={isUploading}
              placeholder="e.g. Senior Frontend Engineer"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="job-company" className="text-sm font-medium">Company</label>
            <Input
              id="job-company" disabled={isUploading}
              placeholder="e.g. Acme Corp"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="job-file" className="text-sm font-medium">Job description file</label>
            <Input
              id="job-file" disabled={isUploading}
              type="file"
              accept=".pdf,.docx,.html,.htm"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
            <p className="text-xs text-muted-foreground">
              Supported formats: PDF, DOCX, HTML
            </p>
          </div>
          {error && <p role="alert">{error}</p>}
          <DialogFooter>
            <Button type="button" disabled={isUploading} variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!file || !title.trim() || !company.trim() || isUploading}>
              <Upload className="h-4 w-4" />
              {isUploading ? 'Uploading...' : 'Upload'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
