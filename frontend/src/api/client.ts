/**
 * Type-safe HTTP API client for IPA Exam RAG backend with normalized ApiError handling.
 */

import type {
  AuthStatusResponse,
  CategoryStat,
  DojoSessionConfig,
  DojoSessionState,
  ExamQuestion,
  ExplainResponse,
  LearnedInsight,
  OverallStat,
  PracticeAttempt,
  PracticeSubmitRequest,
  PracticeSubmitResponse,
  QuestionCatalogResponse,
  RetrievalChunk,
  SystemSettingsResponse,
  WeakQuestionStat,
} from '../types';

export class ApiError extends Error {
  status: number;
  detail: string;
  data?: unknown;

  constructor(status: number, detail: string, data?: unknown) {
    super(`API Error ${status}: ${detail}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.data = data;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  try {
    const response = await fetch(path, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let detail = `HTTP ${response.status} ${response.statusText}`;
      let data: unknown = null;
      try {
        const json = await response.json();
        data = json;
        if (json && typeof json === 'object' && 'detail' in json) {
          detail = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
        }
      } catch {
        // Response is not JSON
      }

      if (response.status === 401 && !path.includes('/api/auth/') && typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('auth:unauthorized', { detail: { path } }));
      }
      throw new ApiError(response.status, detail, data);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : String(err);
    throw new ApiError(0, `Network connection failed: ${message}`);
  }
}

// ==========================================
// Questions Catalog API (/api/questions)
// ==========================================
export const questionsApi = {
  getQuestions: (params?: {
    exam_type?: string;
    year?: number;
    category?: string;
    keyword?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.exam_type) query.set('exam_type', params.exam_type);
    if (params?.year) query.set('year', params.year.toString());
    if (params?.category) query.set('category', params.category);
    if (params?.keyword) query.set('keyword', params.keyword);
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset !== undefined) query.set('offset', params.offset.toString());
    const qs = query.toString();
    return request<QuestionCatalogResponse>(`/api/questions${qs ? `?${qs}` : ''}`);
  },

  getQuestionById: (id: string) => {
    return request<ExamQuestion>(`/api/questions/${encodeURIComponent(id)}`);
  },

  searchQuestions: (keyword: string, limit = 20) => {
    const query = new URLSearchParams({ keyword, limit: limit.toString() });
    return request<QuestionCatalogResponse>(`/api/questions?${query.toString()}`);
  },

  getYears: () => {
    return request<number[]>('/api/questions/years');
  },

  getCategories: () => {
    return request<string[]>('/api/questions/categories');
  },
};

// ==========================================
// Practice & Dojo Session API (/api/practice)
// ==========================================
export const practiceApi = {
  submitAnswer: (data: PracticeSubmitRequest) => {
    return request<PracticeSubmitResponse>('/api/practice/submit', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  createSession: (config: DojoSessionConfig) => {
    return request<{ session: DojoSessionState; questions: ExamQuestion[] }>('/api/practice/sessions', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  },

  getActiveSession: () => {
    return request<{ session: DojoSessionState | null; questions: ExamQuestion[] }>('/api/practice/sessions/active');
  },

  updateProgress: (sessionId: string, currentIndex: number, results?: Record<string, unknown>[]) => {
    return request<{ status: string }>(`/api/practice/sessions/${sessionId}/progress`, {
      method: 'POST',
      body: JSON.stringify({ current_index: currentIndex, results: results ?? [] }),
    });
  },

  completeSession: (sessionId: string) => {
    return request<{ status: string }>(`/api/practice/sessions/${sessionId}/complete`, {
      method: 'POST',
    });
  },

  abandonSession: (sessionId: string) => {
    return request<{ status: string }>(`/api/practice/sessions/${sessionId}`, {
      method: 'DELETE',
    });
  },
};

// ==========================================
// Analytics Dashboard API (/api/analytics)
// ==========================================
export const analyticsApi = {
  getSummary: () => {
    return request<OverallStat>('/api/analytics/summary');
  },

  getCategories: () => {
    return request<CategoryStat[]>('/api/analytics/categories');
  },

  getWeakQuestions: (limit = 10) => {
    return request<WeakQuestionStat[]>(`/api/analytics/weak-questions?limit=${limit}`);
  },

  getRecentAttempts: (limit = 20) => {
    return request<PracticeAttempt[]>(`/api/analytics/history?limit=${limit}`);
  },
};

// ==========================================
// RAG & Knowledge API (/api/rag)
// ==========================================
export const ragApi = {
  explainWithContext: (questionId: string, choiceKey: string) => {
    return request<ExplainResponse>('/api/rag/explain', {
      method: 'POST',
      body: JSON.stringify({ question_id: questionId, user_choice: choiceKey }),
    });
  },

  saveKnowledgeCandidate: (data: {
    question_id: string;
    dialogue_history: Array<{ role: string; content: string }>;
  }) => {
    return request<{ status: string; task_id?: string; message: string }>('/api/rag/save-knowledge', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getInsights: (limit = 50) => {
    return request<LearnedInsight[]>(`/api/rag/insights?limit=${limit}`);
  },

  chatStream: async (
    params: {
      question_id: string;
      user_message: string;
      dialogue_history?: Array<{ role: string; content: string }>;
    },
    callbacks: {
      onCitation?: (chunks: RetrievalChunk[]) => void;
      onToken?: (token: string) => void;
      onDone?: () => void;
      onError?: (err: ApiError) => void;
    },
    signal?: AbortSignal
  ): Promise<void> => {
    try {
      const response = await fetch('/api/rag/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question_id: params.question_id,
          user_message: params.user_message,
          dialogue_history: params.dialogue_history || [],
        }),
        signal,
      });

      if (!response.ok) {
        let detail = `HTTP ${response.status} ${response.statusText}`;
        try {
          const json = await response.json();
          if (json && typeof json === 'object' && 'detail' in json) {
            detail = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
          }
        } catch {
          // Non-JSON
        }
        const err = new ApiError(response.status, detail);
        callbacks.onError?.(err);
        return;
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let isFinished = false;

      try {
        while (!isFinished) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const events = buffer.split('\n\n');
          buffer = events.pop() || '';

          for (const rawEvent of events) {
            if (!rawEvent.trim()) continue;
            let eventType = 'message';
            let dataStr = '';

            for (const line of rawEvent.split('\n')) {
              if (line.startsWith('event: ')) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith('data: ')) {
                dataStr = line.slice(6).trim();
              }
            }

            if (eventType === 'citation') {
              try {
                const chunks: RetrievalChunk[] = JSON.parse(dataStr);
                callbacks.onCitation?.(chunks);
              } catch (parseErr) {
                console.warn('Failed to parse citation event data:', parseErr);
              }
            } else if (eventType === 'token') {
              try {
                const data = JSON.parse(dataStr);
                if (data && typeof data.token === 'string') {
                  callbacks.onToken?.(data.token);
                }
              } catch (parseErr) {
                console.warn('Failed to parse token event data:', parseErr);
              }
            } else if (eventType === 'done') {
              isFinished = true;
              callbacks.onDone?.();
              break;
            } else if (eventType === 'error') {
              isFinished = true;
              try {
                const errData = JSON.parse(dataStr);
                const err = new ApiError(500, errData.detail || 'Streaming error');
                callbacks.onError?.(err);
              } catch {
                callbacks.onError?.(new ApiError(500, dataStr || 'Streaming error'));
              }
              break;
            }
          }
        }

        if (!isFinished) {
          callbacks.onDone?.();
        }
      } finally {
        reader.releaseLock();
      }
    } catch (err) {
      if (signal?.aborted) return;
      const apiErr =
        err instanceof ApiError
          ? err
          : new ApiError(0, `Network connection failed: ${err instanceof Error ? err.message : String(err)}`);
      callbacks.onError?.(apiErr);
    }
  },
};

// ==========================================
// System Management API (/api/system)
// ==========================================
export const systemApi = {
  getSettings: () => {
    return request<SystemSettingsResponse>('/api/system/settings');
  },

  updateApiKey: (apiKey: string) => {
    return request<{ success: boolean; gemini_api_key_masked: string; message: string }>('/api/system/api-key', {
      method: 'POST',
      body: JSON.stringify({ api_key: apiKey }),
    });
  },

  reindexAll: () => {
    return request<{ success: boolean; reindexed_count: number; message: string }>('/api/system/reindex', {
      method: 'POST',
    });
  },

  resetHistory: () => {
    return request<{ success: boolean; message: string }>('/api/system/reset-history', {
      method: 'POST',
    });
  },
};

// ==========================================
// Google OAuth Authentication API (/api/auth)
// ==========================================
export const authApi = {
  getStatus: () => {
    return request<AuthStatusResponse>('/api/auth/status');
  },

  getLoginUrl: () => {
    return request<{ login_url: string; state: string }>('/api/auth/login');
  },

  logout: () => {
    return request<{ success: boolean; message: string }>('/api/auth/logout', {
      method: 'POST',
    });
  },
};
