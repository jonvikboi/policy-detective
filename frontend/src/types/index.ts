export type ScanStatus =
  | 'pending'
  | 'discovering'
  | 'extracting'
  | 'investigating'
  | 'analyzing'
  | 'completed'
  | 'failed';

export type VerdictType =
  | 'consistent'
  | 'potential_inconsistency'
  | 'strong_inconsistency'
  | 'unable_to_verify'
  | 'test_failed';

export type ClaimCategory =
  | 'cookies'
  | 'tracking'
  | 'analytics'
  | 'advertising'
  | 'third_party'
  | 'consent'
  | 'opt_out'
  | 'data_collection'
  | 'location'
  | 'fingerprinting'
  | 'data_deletion'
  | 'data_access'
  | 'data_retention';

export type Testability =
  | 'automatable'
  | 'partially_automatable'
  | 'manual_only'
  | 'not_testable';

export type TrackerCategory =
  | 'analytics'
  | 'advertising'
  | 'social_tracking'
  | 'functional'
  | 'authentication'
  | 'payment'
  | 'cdn'
  | 'first_party'
  | 'unknown';

export type ExperimentState =
  | 'pre_consent'
  | 'accept_all'
  | 'reject_all';

export interface Scan {
  id: string;
  url: string;
  domain: string;
  status: ScanStatus;
  progress: number;
  current_stage: string;
  stage_details: string;
  error?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface Policy {
  id: string;
  url: string;
  title: string;
  policy_type: string;
  content_preview?: string;
  content?: string;
  discovered_via: string;
}

export interface PolicyClaim {
  id: string;
  policy_id?: string;
  category: ClaimCategory;
  claim_text: string;
  testability: Testability;
  test_type: string;
  expected_behavior: Record<string, any>;
  source_section?: string;
}

export interface CookieEvidence {
  id: string;
  name: string;
  domain: string;
  path: string;
  expires?: number | null;
  secure: boolean;
  http_only: boolean;
  same_site: string;
  is_third_party: boolean;
  category: TrackerCategory;
  classification_source: string;
}

export interface NetworkEvidence {
  id: string;
  url: string;
  domain: string;
  method: string;
  resource_type: string;
  status_code?: number | null;
  is_third_party: boolean;
  category: TrackerCategory;
  classification_source: string;
}

export interface Experiment {
  id: string;
  state: ExperimentState;
  status: string;
  page_url: string;
  page_title: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  cookies: CookieEvidence[];
  network_requests: NetworkEvidence[];
}

export interface Verdict {
  id: string;
  claim_id: string;
  verdict_type: VerdictType;
  confidence: number;
  confidence_reasoning: string;
  explanation: string;
  expected_behavior: string;
  observed_behavior: string;
  evidence_summary: Record<string, any>;
}

export interface ScanSummary {
  total_claims: number;
  verdict_breakdown: Record<string, number>;
  consistent: number;
  potential_inconsistencies: number;
  strong_inconsistencies: number;
  unable_to_verify: number;
  test_failed: number;
  total_cookies_observed: number;
  third_party_cookies: number;
  total_network_requests: number;
  experiments_completed: number;
  policies_found: number;
}

export interface ScanReport {
  scan: Scan;
  policies: Policy[];
  claims: PolicyClaim[];
  verdicts: Verdict[];
  summary: ScanSummary;
}

export interface ScanEvent {
  id?: string;
  type: string;
  data: Record<string, any>;
  timestamp: string;
}
