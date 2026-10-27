import axios, { AxiosError } from 'axios';

// Get base URL from Vite environment, default to localhost FastAPI port
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const TOKEN_KEY = 'legalos_token';
export const DEMO_ROLE_KEY = 'legalos_fake_role'; // kept for the legacy workspaces
export const DEMO_FLAG_KEY = 'legalos_demo';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

// Attach the signed-in user's token; in demo mode attach the chosen persona instead.
apiClient.interceptors.request.use((config) => {
  const token = safeGet(TOKEN_KEY);
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  } else if (safeGet(DEMO_FLAG_KEY) === '1') {
    config.headers['X-User-Role'] = safeGet(DEMO_ROLE_KEY) || 'owner';
  }
  return config;
});

// A rejected token (expired/invalid) sends the user back to sign-in.
apiClient.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    const status = error.response?.status;
    const url = error.config?.url || '';
    if (status === 401 && !url.includes('/auth/login') && !url.includes('/auth/register')) {
      window.dispatchEvent(new CustomEvent('legalos:unauthorized'));
    }
    return Promise.reject(error);
  },
);

export interface FriendlyError {
  message: string;
  status?: number;
  kind?: string;
  retryable: boolean;
}

/** Turns any thrown value into a message a non-technical person can act on. */
export function toFriendlyError(err: unknown): FriendlyError {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    const data = err.response?.data as { detail?: unknown; kind?: string; retryable?: boolean } | undefined;
    if (!err.response) {
      return { message: "Can't reach the server. Check your internet connection and try again.", retryable: true };
    }
    let message = '';
    if (typeof data?.detail === 'string') message = data.detail;
    else if (Array.isArray(data?.detail) && data.detail.length) {
      const first = data.detail[0] as { msg?: string; loc?: unknown[] };
      message = first?.msg ? `${first.msg}${first.loc ? ` (${first.loc[first.loc.length - 1]})` : ''}` : 'Please check the details you entered.';
    }
    if (!message) {
      message =
        status === 413 ? 'That file is too large.' :
        status && status >= 500 ? 'Something went wrong on our side. Please try again.' :
        'Something went wrong. Please try again.';
    }
    return { message, status, kind: data?.kind, retryable: data?.retryable ?? (!!status && status >= 500) };
  }
  if (err instanceof Error) return { message: err.message, retryable: false };
  return { message: 'Something went wrong. Please try again.', retryable: false };
}

export default apiClient;
