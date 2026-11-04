import { useQuery } from '@tanstack/react-query';
import { fetchGet } from '@/lib/api';
import type { UnscoredResumesResponse } from '@/types';

export function useUnscoredResumes(jdId: string, page: number, search: string) {
  return useQuery({
    queryKey: ['unscored-resumes', jdId, page, search],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), page_size: '20', q: search });
      return fetchGet<UnscoredResumesResponse>(`/v1/dashboard/jobs/${jdId}/unscored-resumes?${params}`);
    },
  });
}
