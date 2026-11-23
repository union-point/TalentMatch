import { useState } from 'react';
import { FileUp, Users } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ResumeDropzone } from '@/components/resume-dropzone';
import { UploadResults } from '@/components/upload-results';
import { CandidateTable } from '@/components/candidate-table';
import { UnscoredResumes } from '@/components/unscored-resumes';
import { useBatchUpload } from '@/hooks/use-batch-upload';
import type { BatchUploadResponse } from '@/types';

export function JobReview({ jdId }: { jdId: string | null }) {
  const upload = useBatchUpload();
  const [result, setResult] = useState<BatchUploadResponse | null>(null);

  return <div className="space-y-6">
    {jdId && <div className="review-intake">
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><FileUp size={20} />Upload résumés</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <ResumeDropzone isUploading={upload.isPending} onUpload={(files) => {
            setResult(null);
            upload.mutate(files, { onSuccess: setResult });
          }} />
          {upload.error && <p role="alert">{upload.error.message}</p>}
          <UploadResults result={result} />
        </CardContent>
      </Card>
      <UnscoredResumes jdId={jdId} />
    </div>}
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Users size={20} />Candidates</CardTitle></CardHeader>
      <CardContent><CandidateTable jdId={jdId} /></CardContent>
    </Card>
  </div>;
}
