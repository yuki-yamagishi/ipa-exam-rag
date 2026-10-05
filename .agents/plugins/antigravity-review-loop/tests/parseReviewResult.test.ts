import { describe, it, expect, vi } from 'vitest';
import { parseReviewResult } from '../skills/review-self-healing/scripts/parseReviewResult.js';
import { STATUS } from '../state/loopState.js';

describe('parseReviewResult', () => {
  it('handles clean LGTM with no issues', () => {
    const markdown = `
# Fleet Code Review

## 総合判定: [LGTM]
問題は見当たりませんでした。素晴らしい実装です！
`;
    const result = parseReviewResult(markdown);

    expect(result.isLgtm).toBe(true);
    expect(result.verdict).toBe(STATUS.RESOLVED_LGTM);
    expect(result.counts.totalIssues).toBe(0);
    expect(result.counts.blocking).toBe(0);
    expect(result.issues).toEqual([]);
    expect(result.praises).toEqual([]);
  });

  it('correctly treats [good] as praise and excludes it from unresolved issue counts', () => {
    const markdown = `
# Fleet Code Review

## 凡例
- \`[must]\`: 修正必須
- \`[should]\`: 推奨
- \`[good]\`: 称賛

## レビュー結果
- [good] クリーンアーキテクチャの責務分離が非常に明快です。
- **[good]**: 単体テストの網羅性が高く、エッジケースもよく考慮されています。

## 総合判定: [LGTM]
`;
    const result = parseReviewResult(markdown);

    expect(result.isLgtm).toBe(true);
    expect(result.verdict).toBe(STATUS.RESOLVED_LGTM);
    // [good] must NOT be counted as an issue!
    expect(result.counts.totalIssues).toBe(0);
    expect(result.counts.blocking).toBe(0);
    expect(result.counts.good).toBe(2);
    expect(result.counts.totalPraises).toBe(2);
    expect(result.issues).toEqual([]);
    expect(result.praises).toHaveLength(2);
    expect(result.praises[0].description).toBe('クリーンアーキテクチャの責務分離が非常に明快です。');
    expect(result.praises[1].description).toBe('単体テストの網羅性が高く、エッジケースもよく考慮されています。');
  });

  it('keeps LGTM when only non-blocking issues ([imo], [nits], [ask]) and [good] are present', () => {
    const markdown = `
# Fleet Code Review

## レビュー結果
- [good] 適切なエラーハンドリングです。
- [nits] コメントの typo を修正するとより良くなります。
- [imo] 将来的にヘルパー関数を別ファイルに切り出してもよいかもしれません。
- [ask] この定数の命名意図を念のため確認させてください。

## 総合判定: [LGTM]
`;
    const result = parseReviewResult(markdown);

    expect(result.isLgtm).toBe(true);
    expect(result.verdict).toBe(STATUS.RESOLVED_LGTM);
    expect(result.counts.blocking).toBe(0);
    expect(result.counts.nits).toBe(1);
    expect(result.counts.imo).toBe(1);
    expect(result.counts.ask).toBe(1);
    expect(result.counts.good).toBe(1);
    expect(result.counts.nonBlocking).toBe(3);
    expect(result.counts.totalIssues).toBe(3); // nits + imo + ask
    expect(result.issues).toHaveLength(3);
    expect(result.praises).toHaveLength(1);
  });

  it('forces NEEDS_FIX if blocking issues ([must], [should]) exist, even if text says LGTM', () => {
    const markdown = `
# Fleet Code Review

## レビュー結果
- [must] SQLインジェクションの脆弱性を修正してください。
- [should] 未処理の例外を catch してログに出力してください。

## 総合判定: [LGTM]
`;
    const result = parseReviewResult(markdown);

    expect(result.isLgtm).toBe(false);
    expect(result.verdict).toBe(STATUS.NEEDS_FIX);
    expect(result.counts.blocking).toBe(2);
    expect(result.counts.must).toBe(1);
    expect(result.counts.should).toBe(1);
    expect(result.counts.totalIssues).toBe(2);
    expect(result.issues).toHaveLength(2);
  });

  it('detects explicit [要修正] verdict', () => {
    const markdown = `
# Fleet Code Review

## 総合判定: [要修正]
- [should] 入力バリデーションを追加してください。
`;
    const result = parseReviewResult(markdown);

    expect(result.isLgtm).toBe(false);
    expect(result.hasExplicitNeedsFix).toBe(true);
    expect(result.verdict).toBe(STATUS.NEEDS_FIX);
  });

  it('parses diverse markdown formats, numbering, headings, and case-insensitivity', () => {
    const markdown = `
1. [MUST] critical vulnerability in auth
* **[SHOULD]**: optimize memory usage
### [Good] wonderful implementation
- [NITS]: fix formatting indentation
[ask] what is the target node version?
`;
    const result = parseReviewResult(markdown);

    expect(result.counts.must).toBe(1);
    expect(result.counts.should).toBe(1);
    expect(result.counts.good).toBe(1);
    expect(result.counts.nits).toBe(1);
    expect(result.counts.ask).toBe(1);
    expect(result.counts.blocking).toBe(2);
    expect(result.counts.totalIssues).toBe(4); // must, should, nits, ask (excludes good)
    expect(result.counts.totalPraises).toBe(1);
  });

  it('ignores legend definition lines and does not mistake them for real review issues', () => {
    const markdown = `
# Fleet Review

## 凡例
- \`[must]\`: 修正必須（潜在バグ、規約違反）
- \`[should]\`: 強く推奨
- \`[good]\`: 称賛
- \`[nits]\`: 些細な指摘

## 判定: [LGTM]
指摘事項はありません。
`;
    const result = parseReviewResult(markdown);

    expect(result.counts.totalIssues).toBe(0);
    expect(result.counts.must).toBe(0);
    expect(result.counts.blocking).toBe(0);
    expect(result.isLgtm).toBe(true);
    expect(result.verdict).toBe(STATUS.RESOLVED_LGTM);
  });

  it('updates loopState when options.updateState is true', () => {
    const mockUpdater = vi.fn().mockReturnValue({
      status: STATUS.NEEDS_FIX,
      issues: [],
    });

    const markdown = `
## 総合判定: [要修正]
- [must] Fix bug in calculation
`;

    const result = parseReviewResult(markdown, {
      updateState: true,
      stateUpdater: mockUpdater,
    });

    expect(mockUpdater).toHaveBeenCalledTimes(1);
    expect(mockUpdater).toHaveBeenCalledWith({
      lgtm: false,
      issues: expect.arrayContaining([
        expect.objectContaining({
          type: 'must',
          description: 'Fix bug in calculation',
        }),
      ]),
    });
    expect(result.updatedState).toBeDefined();
  });

  it('handles empty or non-string inputs safely', () => {
    // @ts-expect-error test non-string
    const result1 = parseReviewResult(null);
    expect(result1.counts.totalIssues).toBe(0);
    expect(result1.issues).toEqual([]);

    const result2 = parseReviewResult('');
    expect(result2.counts.totalIssues).toBe(0);
    expect(result2.issues).toEqual([]);
  });

  it('correctly parses backtick-wrapped prefixes and distinguishes them from legend definitions', () => {
    const markdown = `
# Fleet Code Review

## 凡例
- \`[must]\`: マージ前に修正必須
- \`[should]\`: 強く推奨
- \`[good]\`: 称賛・好ましい実装

## 指摘事項
- \`[must]\`: 型安全性の欠落を修正してください。
* **\`[should]\`**: エラーハンドリングを強化してください。
- \`[nits]\`: typo を修正してください。
- \`[good]\`: テストカバレッジが充実しています。

## 総合判定: [要修正]
`;
    const result = parseReviewResult(markdown);

    expect(result.isLgtm).toBe(false);
    expect(result.verdict).toBe(STATUS.NEEDS_FIX);
    expect(result.counts.blocking).toBe(2);
    expect(result.counts.must).toBe(1);
    expect(result.counts.should).toBe(1);
    expect(result.counts.nits).toBe(1);
    expect(result.counts.good).toBe(1);
    expect(result.issues).toHaveLength(3); // must, should, nits
    expect(result.issues[0].description).toBe('型安全性の欠落を修正してください。');
    expect(result.issues[1].description).toBe('エラーハンドリングを強化してください。');
    expect(result.issues[2].description).toBe('typo を修正してください。');
    expect(result.praises).toHaveLength(1);
    expect(result.praises[0].description).toBe('テストカバレッジが充実しています。');
  });

  it('does not falsely skip genuine review issues that start with legend keywords like "マージ前に" or "強く推奨"', () => {
    const markdown = `
# Fleet Code Review

- [must]: マージ前に環境変数の設定ファイルを更新してください。
- [should]: 強く推奨されるパターンに従ってリファクタリングを検討してください。

## 総合判定: [要修正]
`;
    const result = parseReviewResult(markdown);

    expect(result.isLgtm).toBe(false);
    expect(result.counts.blocking).toBe(2);
    expect(result.counts.must).toBe(1);
    expect(result.counts.should).toBe(1);
    expect(result.issues).toHaveLength(2);
    expect(result.issues[0].description).toBe('マージ前に環境変数の設定ファイルを更新してください。');
    expect(result.issues[1].description).toBe('強く推奨されるパターンに従ってリファクタリングを検討してください。');
  });

  it('extracts agentType from JSON block when present', () => {
    const markdown = `
# Fleet Completion Audit

## 総合判定: [LGTM]
All criteria met!

\`\`\`json
{
  "agentType": "completionAuditor",
  "verdict": "LGTM",
  "issues": []
}
\`\`\`
`;
    const result = parseReviewResult(markdown);
    expect(result.agentType).toBe('completionAuditor');
    expect(result.isLgtm).toBe(true);
  });

  it('extracts agentType from the trailing JSON metadata block when multiple JSON blocks are present', () => {
    const markdown = `
# Fleet Code Review

Here is an example snippet of a JSON config:
\`\`\`json
{
  "exampleConfig": true,
  "threshold": 100
}
\`\`\`

And the final review verdict:
\`\`\`json
{
  "agentType": "codeReviewer",
  "verdict": "LGTM",
  "issues": []
}
\`\`\`
`;
    const result = parseReviewResult(markdown);
    expect(result.agentType).toBe('codeReviewer');
    expect(result.isLgtm).toBe(true);
  });

  it('passes agentType to stateUpdater when updateState is enabled', () => {
    const mockUpdater = vi.fn().mockReturnValue({ status: 'REVIEW_REQUESTED' });
    const markdown = `
# Fleet Code Review
[LGTM] Clean implementation!
`;
    const result = parseReviewResult(markdown, {
      updateState: true,
      agentType: 'codeReviewer',
      stateUpdater: mockUpdater,
    });

    expect(result.agentType).toBe('codeReviewer');
    expect(mockUpdater).toHaveBeenCalledWith(
      expect.objectContaining({
        lgtm: true,
        agentType: 'codeReviewer',
      })
    );
  });
});
