import { lazy, Suspense, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useAuth } from '@/auth/auth-context';
import { Button } from '@/components/ui/button';
import { useUploadJd } from '@/hooks/use-upload-jd';

const JdUploadDialog = lazy(() =>
  import('@/components/jd-upload-dialog').then((module) => ({ default: module.JdUploadDialog }))
);

export function NewJobButton({ onCreated }: { onCreated: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const { session } = useAuth();
  const upload = useUploadJd();
  const client = useQueryClient();

  return (
    <>
      <Button ref={triggerRef} onClick={() => {
        upload.reset();
        setOpen(true);
      }}>
        <Plus />New job
      </Button>
      {open && (
        <Suspense fallback={<span role="status" className="sr-only">Opening new job…</span>}>
          <JdUploadDialog
            open={open}
            companyName={session?.organization?.name ?? ''}
            triggerRef={triggerRef}
            onClearError={() => { if (upload.isError) upload.reset(); }}
            onOpenChange={(next) => { if (!upload.isPending) setOpen(next); }}
            onUpload={(draft) => upload.mutate(draft, {
              onSuccess: (job) => {
                void client.invalidateQueries({ queryKey: ['job-descriptions'] });
                setOpen(false);
                onCreated(job.id);
              },
            })}
            isUploading={upload.isPending}
            error={upload.error?.message}
          />
        </Suspense>
      )}
    </>
  );
}
