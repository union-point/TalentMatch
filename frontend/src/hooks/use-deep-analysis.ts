import { useMutation, useQuery } from '@tanstack/react-query';
import { fetchPost, fetchGet } from '@/lib/api';
import type { DeepAnalysisRequest, DeepAnalysisResponse, DeepAnalysisResultSchema } from '@/types';

export function useDeepAnalysisMutation() {
  return useMutation({
    mutationFn: (data: DeepAnalysisRequest) =>
      fetchPost<DeepAnalysisResponse>('/v1/analysis/deep', data),
  });
}

export function useDeepAnalysisPolling(analysisId: string | null, initialStatus: string) {
  const shouldPoll = initialStatus !== 'completed' && initialStatus !== 'failed';

  return useQuery<DeepAnalysisResultSchema>({
    queryKey: ['deep-analysis', analysisId],
    queryFn: () => fetchGet<DeepAnalysisResultSchema>(`/v1/analysis/deep/${analysisId}`),
    enabled: !!analysisId && shouldPoll,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'completed' || status === 'failed') return false;
      return 3000;
    },
    refetchIntervalInBackground: true,
    staleTime: 0,
  });
}
