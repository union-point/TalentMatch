import { useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchPost } from '@/lib/api';
import type { FastTrackResponse } from '@/types';

interface FastTrackParams {
  job_description_id: string;
  resume_ids: string[];
}

export function useFastTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: FastTrackParams) =>
      fetchPost<FastTrackResponse>('/v1/analysis/fast-track', data),
    onSuccess: async (_result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['candidates', variables.job_description_id] }),
        ...variables.resume_ids.map((resumeId) =>
          queryClient.invalidateQueries({
            queryKey: ['candidate-detail', resumeId, variables.job_description_id],
          })
        ),
      ]);
    },
  });
}
