import { useQuery } from '@tanstack/react-query';
import { fetchGet } from '@/lib/api';
import type { PaginatedResponse } from '@/types';

interface UseCandidatesParams {
  jdId: string | null;
  page?: number;
  pageSize?: number;
  minScore?: number;
  passFailOnly?: boolean;
  q?: string;
  sortBy?: 'score' | 'candidate_name' | 'pass_fail';
  sortDirection?: 'asc' | 'desc';
  status?: 'all' | 'pass' | 'fail';
}

export function useCandidates(params: UseCandidatesParams) {
  const { jdId, page = 1, pageSize = 20, minScore, passFailOnly, q, sortBy = 'score', sortDirection = 'desc', status = 'all' } = params;

  return useQuery({
    queryKey: ['candidates', jdId, page, pageSize, minScore, passFailOnly, q, sortBy, sortDirection, status],
    queryFn: () => {
      const searchParams = new URLSearchParams();
      searchParams.set('page', page.toString());
      searchParams.set('page_size', pageSize.toString());
      if (minScore !== undefined) searchParams.set('min_score', minScore.toString());
      if (passFailOnly !== undefined) searchParams.set('pass_fail_only', passFailOnly.toString());
      if (q) searchParams.set('q', q);
      searchParams.set('sort_by', sortBy);
      searchParams.set('sort_direction', sortDirection);
      searchParams.set('status', status);
      return fetchGet<PaginatedResponse>(
        `/v1/dashboard/jobs/${jdId}/candidates?${searchParams.toString()}`
      );
    },
    enabled: !!jdId,
  });
}
