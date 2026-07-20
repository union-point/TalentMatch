import { useMutation } from '@tanstack/react-query';
import { fetchPostMultipart } from '@/lib/api';
import type { BatchUploadResponse } from '@/types';

export function useBatchUpload() {
  return useMutation({
    mutationFn: (files: File[]) => {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));
      return fetchPostMultipart<BatchUploadResponse>(
        '/v1/resumes/batch-upload',
        formData
      );
    },
  });
}
