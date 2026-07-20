import { useQuery } from '@tanstack/react-query';
import { fetchGet } from '@/lib/api';
import type { JobDescriptionDetailResponse } from '@/types';

export function useJobDescription(jdId: string | null) {
  return useQuery({
    queryKey: ['job-description', jdId],
    queryFn: () => fetchGet<JobDescriptionDetailResponse>(`/v1/job-descriptions/${jdId}`),
    enabled: !!jdId,
  });
}
