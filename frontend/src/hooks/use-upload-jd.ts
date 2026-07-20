import { useMutation } from '@tanstack/react-query';
import { fetchPostMultipart } from '@/lib/api';
import type { JobDescriptionUploadResponse } from '@/types';

interface UploadJdParams {
  file: File;
  title: string;
  company: string;
}

export function useUploadJd() {
  return useMutation({
    mutationFn: ({ file, title, company }: UploadJdParams) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', title);
      formData.append('company', company);
      return fetchPostMultipart<JobDescriptionUploadResponse>(
        '/v1/job-descriptions/upload',
        formData
      );
    },
  });
}
