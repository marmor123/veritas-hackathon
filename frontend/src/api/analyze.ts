import type { AnalysisResponse, Biomarker } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE ?? '';

/**
 * Call the full analysis pipeline (Verify → RAG → LLM Synthesis).
 * Accepts biomarkers from OCR + optional context.
 */
export async function analyzeResults(
  biomarkers: Biomarker[],
  options?: {
    medications?: string[];
    supplements?: string[];
    wearable_data?: Record<string, unknown>;
  }
): Promise<AnalysisResponse> {
  // Convert frontend Biomarker format to backend BiomarkerResult format
  const backendBiomarkers = biomarkers.map((b) => ({
    name: b.name,
    value: b.value,
    unit: b.unit,
    ref_low: b.ref_low,
    ref_high: b.ref_high,
    flag: b.flag === 'high' ? 'H' : b.flag === 'low' ? 'L' : null,
  }));

  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      biomarkers: backendBiomarkers,
      medications: options?.medications ?? null,
      supplements: options?.supplements ?? null,
      wearable_data: options?.wearable_data ?? null,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Analysis failed (${response.status}): ${errorBody}`);
  }

  const data = await response.json();
  return transformBackendResponse(data);
}

/**
 * Load a pre-cached demo scenario from the backend (instant, no LLM).
 */
export async function loadDemoScenario(
  scenario: 'iron_deficiency' | 'metabolic_syndrome' | 'biotin_interference' | 'hemolysis_artifact'
): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE}/api/analyze?demo=${scenario}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ biomarkers: [] }), // demo mode ignores input
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Demo load failed (${response.status}): ${errorBody}`);
  }

  const data = await response.json();
  return transformBackendResponse(data);
}

/**
 * Transform backend AnalysisOutput into frontend AnalysisResponse format.
 * The backend uses slightly different field names/structures.
 */
function transformBackendResponse(data: Record<string, unknown>): AnalysisResponse {
  const patterns = (data.patterns as Array<Record<string, unknown>> || []).map((p) => ({
    name: p.name as string,
    severity: p.severity as 'WARNING' | 'CAUTION' | 'ADVISORY',
    confidence: confidenceToNumber(p.confidence as string),
    explanation: p.explanation as string,
    citations: (p.citations as string[] || []).map((c, i) => ({
      chunk_id: `cite_${i}`,
      source: c,
      chapter: '',
    })),
    doctor_questions: (p.doctor_questions as string[]) || [],
    biomarkers: (p.supporting_markers as string[] || []).map((m) =>
      m.split(':')[0].trim()
    ),
  }));

  const alerts = (data.verification_alerts as Array<Record<string, unknown>> || []).map(
    (a) => {
      if (typeof a === 'string') return a;
      return `${a.biomarker}: ${a.issue}. ${a.recommendation}`;
    }
  );

  return {
    summary: data.summary as string,
    patterns,
    verification_alerts: alerts as string[],
    disclaimer: data.disclaimer as string,
  };
}

function confidenceToNumber(confidence: string): number {
  switch (confidence?.toUpperCase()) {
    case 'HIGH': return 0.9;
    case 'MODERATE': return 0.7;
    case 'LOW': return 0.5;
    default: return 0.7;
  }
}
