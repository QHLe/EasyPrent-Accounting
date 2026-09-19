import createClient from 'openapi-fetch';
import type { paths } from './schema';

export const apiClient = createClient<paths>({ baseUrl: '/' });

export interface ApiError {
  code: string;
  reason: string;
}

export class TransportError extends Error {
  public code: string;
  public reason: string;

  constructor(errorDetail: ApiError) {
    super(errorDetail.reason);
    this.name = 'TransportError';
    this.code = errorDetail.code;
    this.reason = errorDetail.reason;
  }
}

/**
 * Handles errors and unifies them into a generic TransportError.
 */
export function handleApiError(errorResponse?: { error: ApiError }): never {
  if (errorResponse?.error?.code) {
    throw new TransportError(errorResponse.error);
  }
  throw new TransportError({ code: 'unknown_error', reason: 'An unknown network error occurred.' });
}

apiClient.use({
  async onResponse({ response }) {
    if (!response.ok) {
      let data: any;
      try {
        data = await response.clone().json();
      } catch {
        // Fallback for non-JSON errors
      }
      handleApiError(data);
    }
  }
});

