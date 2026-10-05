import path from 'path';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { resolveReview } from '../skills/review-self-healing/scripts/resolveReview.js';
import { STATUS, LoopStateMachine } from '../state/loopState.js';

describe('resolveReview', () => {
  let mockStateMachine: LoopStateMachine;
  let mockPostCommentFn: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockPostCommentFn = vi.fn().mockReturnValue({
      success: true,
      output: 'https://github.com/org/repo/pull/48#issuecomment-999',
      prNumber: 48,
    });

    mockStateMachine = {
      filePath: '/dummy/path',
      getState: vi.fn().mockReturnValue({
        status: STATUS.NEEDS_FIX,
        prNumber: 48,
        reviewRequestedAt: '2026-09-09T00:00:00Z',
        issues: [
          {
            id: 'issue-1',
            type: 'must',
            description: 'Fix SQL injection vulnerability',
            resolved: false,
            resolvedCommit: null,
          },
          {
            id: 'issue-2',
            type: 'should',
            description: 'Add error boundary wrapper',
            resolved: false,
            resolvedCommit: null,
          },
          {
            id: 'issue-3',
            type: 'nits',
            description: 'Fix typo in comment',
            resolved: false,
            resolvedCommit: null,
          },
        ],
        activeSubagents: false,
        updatedAt: '2026-09-09T00:00:00Z',
      }),
      saveState: vi.fn(),
      setPrCreated: vi.fn(),
      setReviewRequested: vi.fn(),
      setActiveSubagents: vi.fn(),
      setReviewResult: vi.fn(),
      resolveIssues: vi.fn().mockImplementation((commit, targetIds) => ({
        status: STATUS.REVIEW_REQUESTED,
        prNumber: 48,
        issues: [],
      })),
      reset: vi.fn(),
      canStop: vi.fn(),
    } as unknown as LoopStateMachine;
  });

  describe('Validation', () => {
    it('throws error when commitHash is missing or empty', () => {
      expect(() =>
        resolveReview({
          // @ts-expect-error test missing commitHash
          commitHash: undefined,
          summary: 'Fix issues',
          stateMachine: mockStateMachine,
          postCommentFn: mockPostCommentFn,
        })
      ).toThrow('Commit hash is required');

      expect(() =>
        resolveReview({
          commitHash: '   ',
          summary: 'Fix issues',
          stateMachine: mockStateMachine,
          postCommentFn: mockPostCommentFn,
        })
      ).toThrow('Commit hash is required');
    });

    it('throws error when summary is missing or empty', () => {
      expect(() =>
        resolveReview({
          commitHash: 'abc1234',
          // @ts-expect-error test missing summary
          summary: '',
          stateMachine: mockStateMachine,
          postCommentFn: mockPostCommentFn,
        })
      ).toThrow('Summary is required');

      expect(() =>
        resolveReview({
          commitHash: 'abc1234',
          summary: '   \n\t  ',
          stateMachine: mockStateMachine,
          postCommentFn: mockPostCommentFn,
        })
      ).toThrow('Summary is required');
    });

    it('throws error when PR number is invalid or missing in both options and loopState', () => {
      vi.mocked(mockStateMachine.getState).mockReturnValue({
        status: STATUS.NEEDS_FIX,
        prNumber: null,
        reviewRequestedAt: null,
        issues: [],
        activeSubagents: false,
        updatedAt: '',
      });

      expect(() =>
        resolveReview({
          commitHash: 'abc1234',
          summary: 'Fix issues',
          stateMachine: mockStateMachine,
          postCommentFn: mockPostCommentFn,
        })
      ).toThrow('Invalid or missing PR number');

      expect(() =>
        resolveReview({
          commitHash: 'abc1234',
          summary: 'Fix issues',
          prNumber: -1,
          stateMachine: mockStateMachine,
          postCommentFn: mockPostCommentFn,
        })
      ).toThrow('Invalid or missing PR number');
    });
  });

  describe('All Issues Resolved (Transition to REVIEW_REQUESTED & Enforce Re-review)', () => {
    it('resolves all unresolved blocking issues by default, posts comment, and transitions to REVIEW_REQUESTED', () => {
      const result = resolveReview({
        commitHash: 'abc1234',
        summary: '脆弱性修正およびエラー境界ラッパーの追加',
        details: '単体テスト 10 件を追加し、網羅率 100% を達成しました。',
        stateMachine: mockStateMachine,
        postCommentFn: mockPostCommentFn,
      });

      expect(result.success).toBe(true);
      expect(result.status).toBe(STATUS.REVIEW_REQUESTED);
      expect(result.isAllResolved).toBe(true);
      expect(result.prNumber).toBe(48);
      expect(result.unresolvedBlockingCount).toBe(0);
      expect(result.posted).toBe(true);
      expect(result.resolvedIssueIds).toEqual(['issue-1', 'issue-2']);

      // postPrComment was called with PR number and formatted Markdown
      expect(mockPostCommentFn).toHaveBeenCalledTimes(1);
      expect(mockPostCommentFn).toHaveBeenCalledWith(48, expect.any(String));

      const commentBody = mockPostCommentFn.mock.calls[0][1];
      expect(commentBody).toContain('## 🛠️ 指摘自己修復・解決報告 (Self-Healing Resolution Report)');
      expect(commentBody).toContain('**対応コミット**: `abc1234`');
      expect(commentBody).toContain('**修正概要**: 脆弱性修正およびエラー境界ラッパーの追加');
      expect(commentBody).toContain('### 📝 対応詳細');
      expect(commentBody).toContain('単体テスト 10 件を追加し、網羅率 100% を達成しました。');
      expect(commentBody).toContain('- [x] **`issue-1`** `[must]`: Fix SQL injection vulnerability');
      expect(commentBody).toContain('- [x] **`issue-2`** `[should]`: Add error boundary wrapper');
      expect(commentBody).toContain('Fleet レビュアー 2 者（コード品質担当 `fleet_reviewer` および 批判的完了性監査担当 `fleet_completion_auditor`）を両方再起動し、客観的再レビュー・最終監査を受領してください。');

      // stateMachine.resolveIssues was called with target IDs
      expect(mockStateMachine.resolveIssues).toHaveBeenCalledTimes(1);
      expect(mockStateMachine.resolveIssues).toHaveBeenCalledWith('abc1234', ['issue-1', 'issue-2']);
    });
  });

  describe('Partial Issue Resolution (Maintains NEEDS_FIX)', () => {
    it('resolves only specified issues and keeps status as NEEDS_FIX if blocking issues remain', () => {
      const result = resolveReview({
        commitHash: 'def5678',
        summary: 'SQLインジェクションのみ先行して修正',
        issueIds: ['issue-1'],
        stateMachine: mockStateMachine,
        postCommentFn: mockPostCommentFn,
      });

      expect(result.success).toBe(true);
      expect(result.status).toBe(STATUS.NEEDS_FIX);
      expect(result.isAllResolved).toBe(false);
      expect(result.unresolvedBlockingCount).toBe(1);
      expect(result.resolvedIssueIds).toEqual(['issue-1']);

      const commentBody = mockPostCommentFn.mock.calls[0][1];
      expect(commentBody).toContain('- [x] **`issue-1`** `[must]`: Fix SQL injection vulnerability');
      expect(commentBody).toContain('### ⚠️ 残存ブロッキング指摘 (1件)');
      expect(commentBody).toContain('- [ ] **`issue-2`** `[should]`: Add error boundary wrapper');
      expect(commentBody).toContain('**判定**: `[要修正 (Remaining Blocking: 1件)]`');
      expect(commentBody).toContain('**ステータス**: `NEEDS_FIX` (修正継続中)');

      expect(mockStateMachine.resolveIssues).toHaveBeenCalledWith('def5678', ['issue-1']);
    });

    it('accepts comma-separated string for issueIds', () => {
      const result = resolveReview({
        commitHash: 'def5678',
        summary: '複数指摘の解消',
        issueIds: 'issue-1, issue-2',
        stateMachine: mockStateMachine,
        postCommentFn: mockPostCommentFn,
      });

      expect(result.resolvedIssueIds).toEqual(['issue-1', 'issue-2']);
      expect(result.isAllResolved).toBe(true);
      expect(result.status).toBe(STATUS.REVIEW_REQUESTED);
    });
  });

  describe('Dry-run Mode', () => {
    it('skips posting to PR and skipping state file persistence when dryRun is true', () => {
      const result = resolveReview({
        commitHash: 'abc1234',
        summary: 'Dry run test',
        dryRun: true,
        stateMachine: mockStateMachine,
        postCommentFn: mockPostCommentFn,
      });

      expect(result.success).toBe(true);
      expect(result.posted).toBe(false);
      expect(result.commentOutput).toContain('[DRY-RUN]');
      expect(result.commentBody).toContain('## 🛠️ 指摘自己修復・解決報告');

      // Neither postComment nor resolveIssues should be called in dryRun mode
      expect(mockPostCommentFn).not.toHaveBeenCalled();
      expect(mockStateMachine.resolveIssues).not.toHaveBeenCalled();
    });
  });

  describe('Explicit PR Number & Fallback', () => {
    it('uses explicit prNumber argument when provided even if state has a different one', () => {
      const result = resolveReview({
        commitHash: 'abc1234',
        summary: 'Override PR number',
        prNumber: 99,
        stateMachine: mockStateMachine,
        postCommentFn: mockPostCommentFn,
      });

      expect(result.prNumber).toBe(99);
      expect(mockPostCommentFn).toHaveBeenCalledWith(99, expect.any(String));
    });
  });

  describe('Error Handling', () => {
    it('propagates error without calling stateMachine.resolveIssues if postPrComment fails', () => {
      mockPostCommentFn.mockImplementation(() => {
        throw new Error('GitHub API rate limit exceeded');
      });

      expect(() =>
        resolveReview({
          commitHash: 'abc1234',
          summary: 'Error handling test',
          stateMachine: mockStateMachine,
          postCommentFn: mockPostCommentFn,
        })
      ).toThrow('GitHub API rate limit exceeded');

      // Crucial: State must not be updated if comment posting failed!
      expect(mockStateMachine.resolveIssues).not.toHaveBeenCalled();
    });
  });

  describe('Empty Issues Handling', () => {
    it('handles state with empty issues gracefully', () => {
      vi.mocked(mockStateMachine.getState).mockReturnValue({
        status: STATUS.NEEDS_FIX,
        prNumber: 48,
        reviewRequestedAt: null,
        issues: [],
        activeSubagents: false,
        updatedAt: '',
      });

      const result = resolveReview({
        commitHash: 'abc1234',
        summary: 'General quality improvements',
        stateMachine: mockStateMachine,
        postCommentFn: mockPostCommentFn,
      });

      expect(result.success).toBe(true);
      expect(result.isAllResolved).toBe(true);
      expect(result.status).toBe(STATUS.REVIEW_REQUESTED);
      expect(result.commentBody).toContain('全体的な品質ゲート・コードレビュー指摘事項の自己修復完了');
    });
  });

  describe('CLI Execution', () => {
    it('runs CLI in dry-run mode and prints markdown output', async () => {
      const { execFileSync } = await import('child_process');
      const scriptPath = path.resolve(__dirname, '../skills/review-self-healing/scripts/resolveReview.js');

      const stdout = execFileSync(
        process.execPath,
        [
          scriptPath,
          '--commit',
          'abc1234',
          '--summary',
          'CLI test summary',
          '--pr',
          '48',
          '--dry-run',
        ],
        {
          encoding: 'utf8',
          stdio: ['pipe', 'pipe', 'pipe'],
          env: {
            ...process.env,
          },
        }
      );

      expect(stdout).toContain('[OK] Review resolution report successfully processed!');
      expect(stdout).toContain('PR Number: #48');
      expect(stdout).toContain('Posted to PR: false');
      expect(stdout).toContain('--- Generated Markdown (Dry-run) ---');
      expect(stdout).toContain('**対応コミット**: `abc1234`');
    });

    it('handles summary values starting with a hyphen in CLI', async () => {
      const { execFileSync } = await import('child_process');
      const scriptPath = path.resolve(__dirname, '../skills/review-self-healing/scripts/resolveReview.js');

      const stdout = execFileSync(
        process.execPath,
        [
          scriptPath,
          '--commit',
          'abc1234',
          '--summary',
          '- Hyphen-prefixed summary description',
          '--pr',
          '48',
          '--dry-run',
        ],
        {
          encoding: 'utf8',
          stdio: ['pipe', 'pipe', 'pipe'],
        }
      );

      expect(stdout).toContain('[OK] Review resolution report successfully processed!');
      expect(stdout).toContain('**修正概要**: - Hyphen-prefixed summary description');
    });

    it('exits with code 1 when required arguments are missing', async () => {
      const { execFileSync } = await import('child_process');
      const scriptPath = path.resolve(__dirname, '../skills/review-self-healing/scripts/resolveReview.js');

      expect(() => {
        execFileSync(process.execPath, [scriptPath], {
          encoding: 'utf8',
          stdio: ['pipe', 'pipe', 'pipe'],
        });
      }).toThrow();
    });
  });
});
