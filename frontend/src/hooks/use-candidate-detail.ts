import { useQuery } from '@tanstack/react-query';
import { fetchGet } from '@/lib/api';
import type { CandidateDetailSchema } from '@/types';

interface UseCandidateDetailParams {
  resumeId: string;
  jdId: string;
}

export function useCandidateDetail({ resumeId, jdId }: UseCandidateDetailParams) {
  return useQuery({
    queryKey: ['candidate-detail', resumeId, jdId],
    queryFn: () =>
      fetchGet<CandidateDetailSchema>(
        `/v1/dashboard/candidates/${resumeId}/job/${jdId}`
      ),
  });
}
