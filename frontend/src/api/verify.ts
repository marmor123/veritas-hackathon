import type { Biomarker, VerificationResponse } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export interface VerifyPayload {
  biomarkers: Biomarker[];
  supplements?: string[];
  medications?: string[];
}

export async function verifyBiomarkers(payload: VerifyPayload): Promise<VerificationResponse> {
  const response = await fetch(`${API_BASE}/api/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Verification failed (${response.status}): ${errorBody}`);
  }

  return response.json();
}
