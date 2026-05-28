import type { OcrResponse } from '../types';

// In dev mode, Vite proxy forwards /api to localhost:8000
// In production, set VITE_API_BASE to the backend URL
const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export async function uploadForOcr(file: File): Promise<OcrResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/api/ocr`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`OCR request failed (${response.status}): ${errorBody}`);
  }

  return response.json();
}
