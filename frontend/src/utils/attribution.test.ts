import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formatJapaneseEra,
  resolveExamDetails,
  formatQuestionSource,
  resolveSaExamTerm,
  formatQuestionSourceFromId,
} from './attribution.ts';

test('formatJapaneseEra: converts 2019 to 令和元', () => {
  assert.equal(formatJapaneseEra(2019), '令和元');
});

test('formatJapaneseEra: converts 2021 through 2025 to Reiwa era strings', () => {
  assert.equal(formatJapaneseEra(2021), '令和3');
  assert.equal(formatJapaneseEra(2022), '令和4');
  assert.equal(formatJapaneseEra(2023), '令和5');
  assert.equal(formatJapaneseEra(2024), '令和6');
  assert.equal(formatJapaneseEra(2025), '令和7');
});

test('formatJapaneseEra: falls back safely to Western year for years before 2019', () => {
  assert.equal(formatJapaneseEra(2018), '2018');
  assert.equal(formatJapaneseEra(2000), '2000');
});

test('resolveExamDetails: resolves SA to システムアーキテクト試験 and 午前Ⅱ', () => {
  const details = resolveExamDetails('SA');
  assert.equal(details.division, 'システムアーキテクト試験');
  assert.equal(details.timeSlot, '午前Ⅱ');
});

test('resolveExamDetails: resolves undefined to default SA values', () => {
  const details = resolveExamDetails(undefined);
  assert.equal(details.division, 'システムアーキテクト試験');
  assert.equal(details.timeSlot, '午前Ⅱ');
});

test('resolveExamDetails: gracefully handles unmapped exam codes', () => {
  const details = resolveExamDetails('CUSTOM_EXAM');
  assert.equal(details.division, 'CUSTOM_EXAM');
  assert.equal(details.timeSlot, '午前Ⅱ');
});

test('resolveSaExamTerm: returns 秋期 for 2021 and 2022, 春期 for 2023-2025', () => {
  assert.equal(resolveSaExamTerm(2021), '秋期');
  assert.equal(resolveSaExamTerm(2022), '秋期');
  assert.equal(resolveSaExamTerm(2023), '春期');
  assert.equal(resolveSaExamTerm(2024), '春期');
  assert.equal(resolveSaExamTerm(2025), '春期');
});

test('formatQuestionSource: generates official attribution for 2021 Autumn Question 1', () => {
  const source = formatQuestionSource({
    year: 2021,
    term: '秋期',
    exam_type: 'SA',
    question_number: 1,
  });
  assert.equal(source, '出典：令和3年度 秋期 システムアーキテクト試験 午前Ⅱ 問1');
});

test('formatQuestionSource: generates official attribution for 2025 Spring Question 25', () => {
  const source = formatQuestionSource({
    year: 2025,
    term: '春期',
    exam_type: 'SA',
    question_number: 25,
  });
  assert.equal(source, '出典：令和7年度 春期 システムアーキテクト試験 午前Ⅱ 問25');
});

test('formatQuestionSource: handles boundary year before Reiwa safely', () => {
  const source = formatQuestionSource({
    year: 2018,
    term: '秋期',
    exam_type: 'SA',
    question_number: 5,
  });
  assert.equal(source, '出典：2018年度 秋期 システムアーキテクト試験 午前Ⅱ 問5');
});

test('formatQuestionSourceFromId: parses authentic SA question IDs to official IPA format', () => {
  assert.equal(
    formatQuestionSourceFromId('2021-SA-AM2-Q01'),
    '出典：令和3年度 秋期 システムアーキテクト試験 午前Ⅱ 問1'
  );
  assert.equal(
    formatQuestionSourceFromId('2022-SA-AM2-Q10'),
    '出典：令和4年度 秋期 システムアーキテクト試験 午前Ⅱ 問10'
  );
  assert.equal(
    formatQuestionSourceFromId('2023-SA-AM2-Q15'),
    '出典：令和5年度 春期 システムアーキテクト試験 午前Ⅱ 問15'
  );
  assert.equal(
    formatQuestionSourceFromId('2024-SA-AM2-Q20'),
    '出典：令和6年度 春期 システムアーキテクト試験 午前Ⅱ 問20'
  );
  assert.equal(
    formatQuestionSourceFromId('2025-SA-AM2-Q25'),
    '出典：令和7年度 春期 システムアーキテクト試験 午前Ⅱ 問25'
  );
});

test('formatQuestionSourceFromId: gracefully falls back for custom or non-conforming IDs', () => {
  assert.equal(formatQuestionSourceFromId('custom-note-001'), '出典: custom-note-001');
  assert.equal(formatQuestionSourceFromId('arbitrary-id'), '出典: arbitrary-id');
});

test('formatQuestionSourceFromId: gracefully handles empty, null, or undefined values', () => {
  assert.equal(formatQuestionSourceFromId(''), '出典：IPA公表過去問題');
  assert.equal(formatQuestionSourceFromId(null), '出典：IPA公表過去問題');
  assert.equal(formatQuestionSourceFromId(undefined), '出典：IPA公表過去問題');
});
