export interface InjectionScanDetails {
  passed: boolean;
  suspicion_score?: number;
  details?: Record<string, unknown> | null;
}

export interface JobDescriptionUploadResponse {
  id: string;
  filename: string;
  file_type: string;
  original_content_length: number;
  normalized_content_length: number;
  injection_scan: InjectionScanDetails;
}

export interface ResumeUploadResponse {
  id: string;
  filename: string;
  file_type: string;
  original_content_length: number;
  normalized_content_length: number;
  injection_scan: InjectionScanDetails;
}

export interface BatchUploadResponse {
  resumes: ResumeUploadResponse[];
  total: number;
  succeeded: number;
  failed: number;
}

export interface FastTrackResultSchema {
  resume_id: string;
  result_id?: string | null;
  pass_fail?: boolean | null;
  score?: number | null;
  explanation?: string | null;
  injection_warning?: boolean;
  error?: string | null;
}

export interface FastTrackResponse {
  job_description_id: string;
  results: FastTrackResultSchema[];
  total: number;
  succeeded: number;
  failed: number;
}

export interface FastTrackSummarySchema {
  result_id: string;
  score: number;
  pass_fail: boolean;
  explanation: string;
  created_at?: string | null;
}

export interface DeepAnalysisRequest {
  resume_id: string;
  job_description_id: string;
}

export interface DeepAnalysisResponse {
  analysis_id: string;
  status: string;
}

export interface EvidenceSchema {
  text: string;
  category: string;
}

export interface DeepAnalysisResultSchema {
  analysis_id: string;
  status: string;
  overall_score?: number | null;
  strengths?: string[] | null;
  weaknesses?: string[] | null;
  risks?: string[] | null;
  detailed_reasoning?: string | null;
  evidence?: EvidenceSchema[] | null;
  error_message?: string | null;
}

export interface DeepAnalysisSummarySchema {
  analysis_id: string;
  status: string;
  overall_score?: number | null;
  strengths?: string[] | null;
  weaknesses?: string[] | null;
  risks?: string[] | null;
  detailed_reasoning?: string | null;
  error_message?: string | null;
}

export interface RankedCandidateSchema {
  resume_id: string;
  candidate_name?: string | null;
  email?: string | null;
  score: number;
  pass_fail: boolean;
  explanation: string;
  injection_scan_passed: boolean;
  has_deep_analysis?: boolean;
  created_at?: string | null;
}

export interface PaginatedResponse {
  items: RankedCandidateSchema[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface JobDescriptionListItem {
  id: string;
  title: string;
  company: string;
  file_type: string;
  injection_scan_passed: boolean;
  created_at?: string | null;
}

export interface JobDescriptionListResponse {
  items: JobDescriptionListItem[];
  total: number;
}

export interface JobDescriptionDetailResponse {
  id: string;
  title: string;
  company: string;
  file_type: string;
  original_content: string;
  normalized_content: string;
  injection_scan: InjectionScanDetails;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CandidateDetailSchema {
  resume_id: string;
  filename: string;
  candidate_name?: string | null;
  email?: string | null;
  file_type: string;
  injection_scan_passed: boolean;
  fast_track?: FastTrackSummarySchema | null;
  deep_analysis?: DeepAnalysisSummarySchema | null;
}
