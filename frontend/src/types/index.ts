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
  confidence: 'HIGH' | 'MODERATE' | 'LOW';
  explanation: string;
  symptomatic_note: string | null;
  supporting_markers: string[];   // e.g. ["Ferritin: 12 ng/mL (Low)", "MCV: 78 fL (Low)"]
  citations: Citation[];
  doctor_questions: string[];
  biomarkers: string[];           // kept for backward compat (just names)
}

export interface AnalysisResponse {
  summary: string;
  patterns: Pattern[];
  verification_alerts: string[];
  disclaimer: string;
}

// Pipeline stage tracking for progressive rendering
export type PipelineStage = 'idle' | 'uploading' | 'ocr' | 'health_form' | 'verification' | 'analysis' | 'complete' | 'error';
