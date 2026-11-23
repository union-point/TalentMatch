import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { JdUploadDialog } from '@/components/jd-upload-dialog';
import { useUploadJd } from '@/hooks/use-upload-jd';

export function NewJobButton({ onCreated }: { onCreated: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const upload = useUploadJd();
  const client = useQueryClient();

  return <>
    <Button onClick={() => { upload.reset(); setOpen(true); }}><Plus />New job</Button>
    {open && <JdUploadDialog open={open} onOpenChange={(next) => { if (!upload.isPending) setOpen(next); }}
      onUpload={(draft) => upload.mutate(draft, {
        onSuccess: (job) => {
          void client.invalidateQueries({ queryKey: ['job-descriptions'] });
          setOpen(false);
          onCreated(job.id);
        },
      })}
      isUploading={upload.isPending} error={upload.error?.message}
    />}
  </>;
}
