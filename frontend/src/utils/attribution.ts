/**
 * IPA Exam Official Attribution & Source Formatter Utility
 * 
 * Complies with Information-technology Promotion Agency, Japan (IPA) official guidelines:
 * Format: "出典：[元号]年度 [期] [試験区分] [時間区分] [問番号]"
 * Example: "出典：令和3年度 秋期 システムアーキテクト試験 午前Ⅱ 問1"
 */

export interface QuestionAttributionInput {
  year: number;
  term: string;
  exam_type?: string;
  question_number: number;
}

/**
 * Converts Western calendar year to Japanese era (Reiwa) string.
 * Falls back safely to Western year if earlier than 2019 (Reiwa era start).
 */
export function formatJapaneseEra(year: number): string {
  if (year < 2019) {
    return `${year}`;
  }
  const reiwaYear = year - 2018;
  if (reiwaYear === 1) {
    return '令和元';
  }
  return `令和${reiwaYear}`;
}

/**
 * Resolves human-readable exam division and time slot name from exam_type.
 */
export function resolveExamDetails(examType?: string): { division: string; timeSlot: string } {
  const normalized = (examType || 'SA').toUpperCase();
  if (normalized === 'SA') {
    return {
      division: 'システムアーキテクト試験',
      timeSlot: '午前Ⅱ',
    };
  }
  // Safe fallback for unmapped exam types
  return {
    division: examType || '情報処理技術者試験',
    timeSlot: '午前Ⅱ',
  };
}

/**
 * Generates official IPA past exam attribution string from structured question details.
 */
export function formatQuestionSource(input: QuestionAttributionInput): string {
  const eraStr = formatJapaneseEra(input.year);
  const { division, timeSlot } = resolveExamDetails(input.exam_type);
  const termStr = input.term ? ` ${input.term}` : '';
  const timeSlotStr = timeSlot ? ` ${timeSlot}` : '';
  return `出典：${eraStr}年度${termStr} ${division}${timeSlotStr} 問${input.question_number}`;
}

/**
 * Determines exam term for System Architect exam based on official IPA exam schedule:
 * SA was held in Autumn (秋期) up to 2022, and transitioned to Spring (春期) from 2023 onward.
 */
export function resolveSaExamTerm(year: number): string {
  return year <= 2022 ? '秋期' : '春期';
}

/**
 * Parses question ID string (e.g. "2021-SA-AM2-Q01") and returns official IPA attribution.
 * Falls back gracefully to `出典: ${id}` for non-matching or arbitrary IDs.
 */
export function formatQuestionSourceFromId(id: string | null | undefined): string {
  if (!id || typeof id !== 'string') {
    return '出典：IPA公表過去問題';
  }

  // Matches pattern like "2021-SA-AM2-Q01" or "2025-SA-AM2-Q25"
  const match = id.match(/^(\d{4})-(SA)-AM2-Q(\d{1,2})$/i);
  if (!match) {
    // Graceful fallback for custom IDs or non-conforming formats
    return `出典: ${id}`;
  }

  const year = parseInt(match[1], 10);
  const examType = match[2].toUpperCase();
  const questionNumber = parseInt(match[3], 10);
  const term = resolveSaExamTerm(year);

  return formatQuestionSource({
    year,
    term,
    exam_type: examType,
    question_number: questionNumber,
  });
}
