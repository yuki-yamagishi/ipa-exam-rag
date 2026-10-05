/**
 * Domain and API TypeScript type definitions matching backend Pydantic models.
 */

export type AnswerKey = 'ア' | 'イ' | 'ウ' | 'エ';

export type ExamType = 'SA' | 'AP' | 'FE' | 'NW' | 'DB' | 'SC' | 'PM' | 'ST';

export type DocType = 'exam_question' | 'learned_insight' | 'syllabus';

export type DojoMode = 'all' | 'category' | 'weak_incorrect' | 'unanswered';

export interface ExamChoice {
  key: AnswerKey;
  text: string;
}

export interface ExamQuestion {
  id: string;
  exam_type: ExamType;
  year: number;
  term: string;
  question_number: number;
  category: string;
  sub_category?: string | null;
  question_text: string;
  choices: ExamChoice[];
  correct_answer: AnswerKey;
  explanation: string;
  keywords: string[];
  doc_type: DocType;
}

export interface QuestionCatalogResponse {
  total: number;
  items: ExamQuestion[];
}

export interface DojoSessionConfig {
  mode: DojoMode;
  year?: number | null;
  category?: string | null;
  question_count: number;
  shuffle: boolean;
  user_email?: string;
}

export interface DojoSessionState {
  session_id: string;
  user_email?: string;
  mode: DojoMode;
  year?: number | null;
  category?: string | null;
  question_count: number;
  shuffle: boolean;
  question_ids: string[];
  current_index: number;
  results: Array<Record<string, unknown>>;
  is_completed: boolean;
  created_at: string;
  updated_at: string;
}

export interface PracticeAttempt {
  id: string;
  session_id?: string | null;
  question_id: string;
  exam_type: string;
  year: number;
  term: string;
  question_number: number;
  category: string;
  user_choice: AnswerKey;
  correct_answer: AnswerKey;
  is_correct: boolean;
  time_spent_seconds: number;
  user_email?: string;
  answered_at: string;
}

export interface PracticeSubmitRequest {
  question_id: string;
  choice_key: AnswerKey;
  session_id?: string | null;
  time_spent_seconds: number;
}

export interface PracticeSubmitResponse {
  question_id: string;
  question_number: number;
  user_choice: AnswerKey;
  correct_answer: AnswerKey;
  is_correct: boolean;
  selected_choice?: ExamChoice | null;
  correct_choice?: ExamChoice | null;
  category: string;
  attempt_id?: string | null;
}

export interface OverallStat {
  total_attempts: number;
  correct_attempts: number;
  accuracy_rate: number;
  distinct_questions_attempted: number;
  total_sessions: number;
}

export interface CategoryStat {
  category: string;
  total_attempts: number;
  correct_attempts: number;
  accuracy_rate: number;
}

export interface WeakQuestionStat {
  question_id: string;
  question_number: number;
  category: string;
  question_text: string;
  total_attempts: number;
  incorrect_count: number;
  latest_is_correct: boolean;
}

export interface AnalyticsSummaryResponse {
  overall: OverallStat;
  categories: CategoryStat[];
  weak_questions: WeakQuestionStat[];
}

export interface RetrievalChunk {
  id: string;
  content: string;
  score: number;
  doc_type: DocType;
  metadata: Record<string, unknown>;
}

export interface ExplainResponse {
  question_id: string;
  explanation: string;
  context_chunks: RetrievalChunk[];
}

export interface LearnedInsight {
  id: string;
  source_question_id: string;
  title: string;
  core_concept: string;
  trap_analysis: string;
  practical_takeaway: string;
  confidence_score: number;
  is_verified: boolean;
  tags: string[];
  created_at: string;
  updated_at?: string | null;
}

export interface SystemSettingsResponse {
  gemini_api_key_masked: string;
  gemini_model_generate: string;
  gemini_model_generate_fallback: string;
  gemini_model_embedding: string;
  vector_store_points_count: number;
  auth_enabled: boolean;
}

export interface AuthStatusResponse {
  auth_enabled: boolean;
  authenticated: boolean;
  user_email?: string | null;
}
