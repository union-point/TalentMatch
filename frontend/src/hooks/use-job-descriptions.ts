import { useQuery } from '@tanstack/react-query';
import { fetchGet } from '@/lib/api';
import type { JobDescriptionListResponse } from '@/types';

export function useJobDescriptions() {
  return useQuery({
    queryKey: ['job-descriptions'],
    queryFn: () => fetchGet<JobDescriptionListResponse>('/v1/job-descriptions'),
  });
}
