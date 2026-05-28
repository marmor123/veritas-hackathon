export interface Biomarker {
  name: string;
  value: number;
  unit: string;
  ref_low: number | null;
  ref_high: number | null;
  flag: 'high' | 'low' | 'normal' | null;
}

export interface OcrResponse {
  biomarkers: Biomarker[];
  raw_text: string;
  parse_confidence: number;
}

export interface DrugInterference {
  drug: string;
  affected_biomarker: string;
  effect: string;
  recommendation: string;
}

export interface VerificationResponse {
  verified_results: Biomarker[];
  drug_interferences: DrugInterference[];
  corrected_values: Record<string, number>;
  quality_flags: string[];
}

export interface Citation {
  chunk_id: string;
  source: string;
  chapter: string;
}

export interface Pattern {
  name: string;
  severity: 'WARNING' | 'CAUTION' | 'ADVISORY';
  confidence: number;
  explanation: string;
  citations: Citation[];
  doctor_questions: string[];
  biomarkers: string[];
}

export interface AnalysisResponse {
  summary: string;
  patterns: Pattern[];
  verification_alerts: string[];
  disclaimer: string;
}

// Pipeline stage tracking for progressive rendering
export type PipelineStage = 'idle' | 'uploading' | 'ocr' | 'verification' | 'analysis' | 'complete' | 'error';
