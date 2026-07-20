import { FileText, Download, File } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ResumeViewerProps {
  resumeId: string;
  fileType: string;
  filename: string;
}

const BASE_URL = '/api';

export function ResumeViewer({ resumeId, fileType, filename }: ResumeViewerProps) {
  const fileUrl = `${BASE_URL}/v1/dashboard/candidates/${resumeId}/resume-file`;

  if (fileType === 'pdf') {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <FileText className="h-4 w-4" />
            {filename}
          </div>
          <Button variant="outline" size="sm" render={<a href={fileUrl} download={filename} />}>
            <Download className="h-4 w-4" />
            Download
          </Button>
        </div>
        <div className="overflow-hidden rounded-lg border">
          <object
            data={fileUrl}
            type="application/pdf"
            className="h-[600px] w-full"
            aria-label="Resume PDF"
          >
            <div className="flex flex-col items-center justify-center gap-3 py-12 text-center text-sm text-muted-foreground">
              <File className="h-8 w-8" />
              <p>PDF preview not available.</p>
              <Button variant="outline" size="sm" render={<a href={fileUrl} download={filename} />}>
                <Download className="h-4 w-4" />
                Download PDF
              </Button>
            </div>
          </object>
        </div>
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
