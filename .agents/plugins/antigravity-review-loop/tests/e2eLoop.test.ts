import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { LoopStateMachine, STATUS } from '../state/loopState.js';
import { parseReviewResult } from '../skills/review-self-healing/scripts/parseReviewResult.js';
import { resolveReview } from '../skills/review-self-healing/scripts/resolveReview.js';
import { handlePostPrCreate } from '../hooks/postPrCreate.js';
import { handleStop } from '../hooks/stopHook.js';

describe('Self-Healing Review Loop E2E Integration Test', () => {
  let tempDir: string;
  let stateFilePath: string;
  let stateMachine: LoopStateMachine;
  let postedComments: Array<{ prNumber: number; body: string }>;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'e2e-loop-test-'));
    stateFilePath = path.join(tempDir, 'loop_state.json');
    stateMachine = new LoopStateMachine(stateFilePath);
    postedComments = [];
  });

  afterEach(() => {
    try {
      if (fs.existsSync(tempDir)) {
        fs.rmSync(tempDir, { recursive: true, force: true });
      }
    } catch {
      // Ignored
    }
    vi.restoreAllMocks();
  });

  const mockPostCommentFn = (prNum: number | string, body: string) => {
    postedComments.push({ prNumber: Number(prNum), body });
    return {
      success: true,
      output: `https://github.com/org/repo/pull/${prNum}#issuecomment-${Date.now()}`,
      prNumber: Number(prNum),
    };
  };

  it('completes the full self-healing cycle: PR Created -> Block Stop -> Review -> Fix -> Resolve -> LGTM -> Reset', async () => {
    // =========================================================================
    // Stage 1: Initial State (IDLE)
    // =========================================================================
    const initialCheck = handleStop({}, stateMachine);
    expect(initialCheck.decision).toBe('allow');
    expect(initialCheck.reason).toContain('IDLE');

    // =========================================================================
    // Stage 2: PR Creation Detected -> State: PR_CREATED -> Stop Blocked!
    // =========================================================================
    const prCreationPayload = {
      toolCall: {
        name: 'run_command',
        args: {
          CommandLine: 'gh pr create --title "feat: new feature" --body "Closes #49"',
        },
      },
      result: 'https://github.com/example/ipa-exam-rag/pull/49\n',
    };

    handlePostPrCreate(prCreationPayload, stateMachine);
    const prCreatedState = stateMachine.getState();
    expect(prCreatedState.status).toBe(STATUS.PR_CREATED);
    expect(prCreatedState.prNumber).toBe(49);

    // Agent attempts to stop immediately after creating PR (Premature Stop Attempt)
    // Stop hook rejects stop with decision 'continue' to keep agent working
    const prematureStopCheck = handleStop({}, stateMachine);
    expect(prematureStopCheck.decision).toBe('continue');
    expect(prematureStopCheck.reason).toContain('PR_CREATED');

    // =========================================================================
    // Stage 3: Fleet Review Requested -> Subagent Spawned -> Waiting Stop Allowed
    // =========================================================================
    stateMachine.setReviewRequested({ activeSubagents: true });
    expect(stateMachine.getState().status).toBe(STATUS.REVIEW_REQUESTED);
    expect(stateMachine.getState().activeSubagents).toBe(true);

    // Parent agent waits for Fleet reviewer (Reactive Wakeup); Stop is allowed
    const waitingStopCheck = handleStop({ hasActiveSubagents: true }, stateMachine);
    expect(waitingStopCheck.decision).toBe('allow');
    expect(waitingStopCheck.reason).toContain('Active subagent running in status "REVIEW_REQUESTED"');

    // =========================================================================
    // Stage 4: Fleet Review Completed with Blocking Issues -> State: NEEDS_FIX
    // =========================================================================
    const fleetReviewMarkdown = `
# 🧐 Fleet 客観第三者コードレビュー結果 (PR #49)

## 凡例
- \`[must]\`: 修正必須
- \`[should]\`: 推奨
- \`[good]\`: 称賛
- \`[nits]\`: 些細な指摘

## レビュー結果
- [good] クリーンアーキテクチャに準拠した美しい責務分離です。
- [must] 認証トークン検証において署名の有効期限チェックが欠落しています。
- [should] ストレージ書き込み処理を try-catch で保護し、例外ログを出力してください。
- [nits] コメントのスペルミス（typo）を修正してください。

## 総合判定
### **[要修正]**
`;

    const parsedResult = parseReviewResult(fleetReviewMarkdown, {
      updateState: true,
      stateUpdater: (res) => stateMachine.setReviewResult(res),
    });

    expect(parsedResult.isLgtm).toBe(false);
    expect(parsedResult.verdict).toBe(STATUS.NEEDS_FIX);
    expect(parsedResult.counts.blocking).toBe(2);
    expect(parsedResult.counts.good).toBe(1);
    expect(parsedResult.counts.totalIssues).toBe(3); // must + should + nits (excludes good)

    const needsFixState = stateMachine.getState();
    expect(needsFixState.status).toBe(STATUS.NEEDS_FIX);
    expect(needsFixState.activeSubagents).toBe(false);
    expect(needsFixState.issues).toHaveLength(3);

    // Agent attempts to stop without fixing the blocking issues -> Blocked!
    const unfixedStopCheck = handleStop({}, stateMachine);
    expect(unfixedStopCheck.decision).toBe('continue');
    expect(unfixedStopCheck.reason).toContain('2 unresolved blocking issue(s)');

    // =========================================================================
    // Stage 5: Partial Resolution -> Still NEEDS_FIX -> Stop Blocked!
    // =========================================================================
    const partialResolutionResult = resolveReview({
      commitHash: 'a1b2c3d',
      summary: '認証トークンの有効期限チェックを追加',
      issueIds: ['issue-1'], // Only resolve [must]
      stateMachine,
      postCommentFn: mockPostCommentFn,
    });

    expect(partialResolutionResult.success).toBe(true);
    expect(partialResolutionResult.status).toBe(STATUS.NEEDS_FIX);
    expect(partialResolutionResult.isAllResolved).toBe(false);
    expect(partialResolutionResult.unresolvedBlockingCount).toBe(1);

    const partialStopCheck = handleStop({}, stateMachine);
    expect(partialStopCheck.decision).toBe('continue');
    expect(partialStopCheck.reason).toContain('1 unresolved blocking issue(s)');

    // =========================================================================
    // Stage 6: Full Self-Healing Fix Reported -> Transitions to REVIEW_REQUESTED (Stop Blocked!)
    // =========================================================================
    const fullResolutionResult = resolveReview({
      commitHash: 'e5f6g7h',
      summary: 'ストレージ例外処理の追加と単体テスト拡充',
      details: '全品質ゲート通過、カバレッジ 98% 達成',
      issueIds: ['issue-2'], // Resolve remaining [should]
      stateMachine,
      postCommentFn: mockPostCommentFn,
    });

    expect(fullResolutionResult.success).toBe(true);
    // ガバナンス厳格化: 自己LGTMは物理禁止！ステータスは REVIEW_REQUESTED に留まる
    expect(fullResolutionResult.status).toBe(STATUS.REVIEW_REQUESTED);
    expect(fullResolutionResult.isAllResolved).toBe(true);
    expect(fullResolutionResult.unresolvedBlockingCount).toBe(0);

    // Verified generated resolution comment
    const latestComment = postedComments[postedComments.length - 1];
    expect(latestComment.prNumber).toBe(49);
    expect(latestComment.body).toContain('## 🛠️ 指摘自己修復・解決報告');
    expect(latestComment.body).toContain('**対応コミット**: `e5f6g7h`');
    expect(latestComment.body).toContain('- [x] **`issue-2`** `[should]`');
    expect(latestComment.body).toContain('**ステータス**: `[修正完了 / 再レビュー待機中 (Pending Re-review)]`');

    // Agent attempts to stop without Fleet Re-review -> Strictly Blocked!
    const unreviewedStopCheck = handleStop({}, stateMachine);
    expect(unreviewedStopCheck.decision).toBe('continue');
    expect(unreviewedStopCheck.reason).toContain('REVIEW_REQUESTED');

    // =========================================================================
    // Stage 6.5: Fleet Re-review Spawned -> Approved LGTM -> RESOLVED_LGTM -> Stop Allowed!
    // =========================================================================
    // Parent spawns fleet_reviewer for Re-review (Stop allowed during waiting)
    stateMachine.setActiveSubagents(true);
    const reReviewWaitingCheck = handleStop({ hasActiveSubagents: true }, stateMachine);
    expect(reReviewWaitingCheck.decision).toBe('allow');

    // Fleet Re-review finishes with official LGTM
    const fleetReReviewMarkdown = `
# Fleet 客観的第三者コード再レビュー結果 (Re-review Report)
### 総合判定: [LGTM]
指摘事項はすべて解消されました。LGTMです。
`;
    parseReviewResult(fleetReReviewMarkdown, {
      updateState: true,
      stateUpdater: stateMachine.setReviewResult.bind(stateMachine),
    });

    expect(stateMachine.getState().status).toBe(STATUS.RESOLVED_LGTM);

    // Stop guard is now genuinely cleared by third-party reviewer!
    const resolvedStopCheck = handleStop({}, stateMachine);
    expect(resolvedStopCheck.decision).toBe('allow');
    expect(resolvedStopCheck.reason).toContain('RESOLVED_LGTM');

    // =========================================================================
    // Stage 7: Human Approval Merge & Reset -> Back to IDLE
    // =========================================================================
    const resetState = stateMachine.reset();
    expect(resetState.status).toBe(STATUS.IDLE);
    expect(resetState.prNumber).toBeNull();
    expect(fs.existsSync(stateFilePath)).toBe(false);

    const finalStopCheck = handleStop({}, stateMachine);
    expect(finalStopCheck.decision).toBe('allow');
    expect(finalStopCheck.reason).toContain('IDLE');
  });

  it('subagent context always bypasses stop checks regardless of status', () => {
    // Put loop in NEEDS_FIX status
    stateMachine.setPrCreated(49);
    stateMachine.setReviewResult({
      lgtm: false,
      issues: [{ id: 'issue-1', type: 'must', description: 'Bug', resolved: false }],
    });

    // Subagent should be allowed to exit cleanly
    const subagentCheck = handleStop({ isSubagent: true }, stateMachine);
    expect(subagentCheck.decision).toBe('allow');
    expect(subagentCheck.reason).toContain('subagent context');
  });
});
