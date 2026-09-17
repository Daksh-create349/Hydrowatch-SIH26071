import { UnifiedPredictionRequest, UnifiedPredictionResponse } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8001';

export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public details?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Trigger the unified end-to-end multi-source flood prediction pipeline.
 */
export async function runUnifiedPrediction(
  params: UnifiedPredictionRequest,
  signal?: AbortSignal
): Promise<UnifiedPredictionResponse> {
  const url = `${API_BASE_URL}/api/v1/predict`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(params),
      signal,
    });

    if (!response.ok) {
      let errorDetail = `HTTP ${response.status} ${response.statusText}`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          if (typeof errorJson.detail === 'string') {
            errorDetail = errorJson.detail;
          } else if (Array.isArray(errorJson.detail)) {
            errorDetail = errorJson.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ');
          } else {
            errorDetail = JSON.stringify(errorJson.detail);
          }
        }
      } catch {
        // Fallback to text if not JSON
        const rawText = await response.text().catch(() => '');
        if (rawText) errorDetail = rawText;
      }

      throw new ApiError(errorDetail, response.status);
    }

    const data: UnifiedPredictionResponse = await response.json();
    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw error;
    }
    throw new ApiError(
      error instanceof Error ? error.message : 'Network failure connecting to HydroWatch backend service.'
    );
  }
}

/**
 * Query backend health status.
 */
export async function checkBackendHealth(): Promise<{ status: string; version: string; project: string }> {
  const url = `${API_BASE_URL}/health`;
  const response = await fetch(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new ApiError(`Health check failed with status ${response.status}`);
  }
  return response.json();
}
