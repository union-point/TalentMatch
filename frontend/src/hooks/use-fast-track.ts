import { useMutation } from '@tanstack/react-query';
import { fetchPost } from '@/lib/api';
import type { FastTrackResponse } from '@/types';

interface FastTrackParams {
  job_description_id: string;
  resume_ids: string[];
}

export function useFastTrack() {
  return useMutation({
    mutationFn: (data: FastTrackParams) =>
      fetchPost<FastTrackResponse>('/v1/analysis/fast-track', data),
  });
}
