import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { 
  LoopStateMachine, 
  STATUS, 
  createInitialState 
} from '../state/loopState.js';

describe('LoopStateMachine', () => {
  let tempDir: string;
  let testStateFile: string;
  let machine: LoopStateMachine;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'loop-state-test-'));
    testStateFile = path.join(tempDir, 'loop_state.json');
    machine = new LoopStateMachine(testStateFile);
  });

  afterEach(() => {
    try {
      if (fs.existsSync(tempDir)) {
        fs.rmSync(tempDir, { recursive: true, force: true });
      }
    } catch {
      // Ignored
    }
  });

  it('returns IDLE state when state file does not exist', () => {
    const state = machine.getState();
    expect(state.status).toBe(STATUS.IDLE);
    expect(state.prNumber).toBeNull();
    expect(state.issues).toEqual([]);

    const check = machine.canStop();
    expect(check.allowed).toBe(true);
    expect(check.status).toBe(STATUS.IDLE);
  });

  it('handles corrupted JSON files gracefully by returning initial state', () => {
    fs.writeFileSync(testStateFile, '{ broken_json: ', 'utf8');
    const state = machine.getState();
    expect(state.status).toBe(STATUS.IDLE);
  });

  it('transitions to PR_CREATED when setPrCreated is called', () => {
    const state = machine.setPrCreated(45);
    expect(state.status).toBe(STATUS.PR_CREATED);
    expect(state.prNumber).toBe(45);
    expect(state.issues).toEqual([]);

    // Verification from disk
    const diskState = machine.getState();
    expect(diskState.status).toBe(STATUS.PR_CREATED);
    expect(diskState.prNumber).toBe(45);

    // canStop should be rejected
    const check = machine.canStop();
    expect(check.allowed).toBe(false);
    expect(check.status).toBe(STATUS.PR_CREATED);
    expect(check.reason).toContain('Stop rejected');
  });

  it('throws error for invalid PR number in setPrCreated', () => {
    expect(() => machine.setPrCreated(0)).toThrow('Invalid PR number');
    expect(() => machine.setPrCreated(-1)).toThrow('Invalid PR number');
    expect(() => machine.setPrCreated(NaN)).toThrow('Invalid PR number');
    // @ts-expect-error invalid input test
    expect(() => machine.setPrCreated('abc')).toThrow('Invalid PR number');
  });

  it('transitions to REVIEW_REQUESTED when setReviewRequested is called', () => {
    machine.setPrCreated(45);
    const state = machine.setReviewRequested({ skipCiCheck: true });
    expect(state.status).toBe(STATUS.REVIEW_REQUESTED);
    expect(state.reviewRequestedAt).toBeTruthy();

    const check = machine.canStop();
    expect(check.allowed).toBe(false);
    expect(check.status).toBe(STATUS.REVIEW_REQUESTED);
  });

  describe('CI Gate Verification', () => {
    it('rejects setReviewRequested when CI checks are pending or in progress', () => {
      machine.setPrCreated(45);
      expect(() => {
        machine.setReviewRequested({
          checkCiFn: () => 'build (push) pending\ntest (push) in_progress',
        });
      }).toThrow('[CI Gate Denied] GitHub Actions CI for PR #45 is still pending or running');

      // Status should remain PR_CREATED
      expect(machine.getState().status).toBe(STATUS.PR_CREATED);
    });

    it('rejects setReviewRequested when CI checks have failed', () => {
      machine.setPrCreated(45);
      expect(() => {
        machine.setReviewRequested({
          checkCiFn: () => 'build (push) success\ntest (pull_request) failure',
        });
      }).toThrow('[CI Gate Denied] GitHub Actions CI for PR #45 has failing checks');

      // Status should remain PR_CREATED
      expect(machine.getState().status).toBe(STATUS.PR_CREATED);
    });

    it('allows setReviewRequested when all CI checks pass', () => {
      machine.setPrCreated(45);
      const state = machine.setReviewRequested({
        checkCiFn: () => 'build (push) success\ntest (pull_request) success\nlint (push) pass',
      });
      expect(state.status).toBe(STATUS.REVIEW_REQUESTED);
    });

    it('bypasses CI check when skipCiCheck is explicitly true', () => {
      machine.setPrCreated(45);
      const state = machine.setReviewRequested({
        skipCiCheck: true,
        checkCiFn: () => 'build (push) failure', // Even if failing, skipCiCheck bypasses
      });
      expect(state.status).toBe(STATUS.REVIEW_REQUESTED);
    });
  });

  it('transitions to NEEDS_FIX if review has blocking issues ([must], [should])', () => {
    machine.setPrCreated(45);
    machine.setReviewRequested({ skipCiCheck: true });

    const state = machine.setReviewResult({
      lgtm: false,
      issues: [
        { id: 'issue-1', type: 'must', description: 'Fix SQL injection vulnerability', resolved: false },
        { id: 'issue-2', type: 'nits', description: 'Fix typo in comment', resolved: false },
      ],
    });

    expect(state.status).toBe(STATUS.NEEDS_FIX);
    expect(state.issues).toHaveLength(2);

    const check = machine.canStop();
    expect(check.allowed).toBe(false);
    expect(check.status).toBe(STATUS.NEEDS_FIX);
    expect(check.reason).toContain('1 unresolved blocking issue(s)');
    expect(check.reason).toContain('resolveReview.js');
  });

  describe('Remediation Guidance Verification', () => {
    it('provides clear next-action guidance in PR_CREATED state', () => {
      machine.setPrCreated(45);
      const check = machine.canStop();
      expect(check.allowed).toBe(false);
      expect(check.reason).toContain('Remediation Guidance');
      expect(check.reason).toContain('Wait for GitHub Actions CI to pass on PR #45');
      expect(check.reason).toContain('review-requested');
      expect(check.reason).toContain('fleet_reviewer');
    });

    it('provides clear next-action guidance in REVIEW_REQUESTED state', () => {
      machine.setPrCreated(45);
      machine.setReviewRequested({ skipCiCheck: true });
      const check = machine.canStop();
      expect(check.allowed).toBe(false);
      expect(check.reason).toContain('Remediation Guidance');
      expect(check.reason).toContain('fleet_reviewer');
      expect(check.reason).toContain('parseReviewResult.js');
    });

    it('provides clear next-action guidance in NEEDS_FIX state', () => {
      machine.setPrCreated(45);
      machine.setReviewRequested({ skipCiCheck: true });
      machine.setReviewResult({
        lgtm: false,
        issues: [{ id: 'issue-1', type: 'must', description: 'Fix bug', resolved: false }],
      });
      const check = machine.canStop();
      expect(check.allowed).toBe(false);
      expect(check.reason).toContain('Remediation Guidance');
      expect(check.reason).toContain('resolveReview.js');
    });
  });

  it('transitions to RESOLVED_LGTM if review has LGTM and only non-blocking issues ([imo], [nits], [good])', () => {
    machine.setPrCreated(45);
    machine.setReviewRequested({ skipCiCheck: true });

    const state = machine.setReviewResult({
      lgtm: true,
      issues: [
        { id: 'issue-1', type: 'nits', description: 'Add optional docstring', resolved: false },
        { id: 'issue-2', type: 'good', description: 'Clean architecture implementation', resolved: false },
      ],
    });

    expect(state.status).toBe(STATUS.RESOLVED_LGTM);

    const check = machine.canStop();
    expect(check.allowed).toBe(true);
    expect(check.status).toBe(STATUS.RESOLVED_LGTM);
  });

  it('resolves specific issues and transitions to REVIEW_REQUESTED (re-review required) once all blocking issues are resolved', () => {
    machine.setPrCreated(45);
    machine.setReviewResult({
      lgtm: false,
      issues: [
        { id: 'issue-1', type: 'must', description: 'Fix issue 1', resolved: false },
        { id: 'issue-2', type: 'should', description: 'Fix issue 2', resolved: false },
        { id: 'issue-3', type: 'nits', description: 'Small typo', resolved: false },
      ],
    });

    expect(machine.getState().status).toBe(STATUS.NEEDS_FIX);

    // Resolve only issue-1
    const step1 = machine.resolveIssues('commit-abc1', ['issue-1']);
    expect(step1.status).toBe(STATUS.NEEDS_FIX);
    expect(step1.issues.find((i: { id: string }) => i.id === 'issue-1')?.resolved).toBe(true);
    expect(step1.issues.find((i: { id: string }) => i.id === 'issue-1')?.resolvedCommit).toBe('commit-abc1');
    expect(machine.canStop().allowed).toBe(false);

    // Resolve issue-2 -> Transitions to REVIEW_REQUESTED (self-LGTM is strictly prohibited!)
    const step2 = machine.resolveIssues('commit-abc2', ['issue-2']);
    expect(step2.status).toBe(STATUS.REVIEW_REQUESTED);
    expect(step2.issues.find((i: { id: string }) => i.id === 'issue-2')?.resolved).toBe(true);
    // Agent cannot stop yet because fleet re-review has not been performed!
    expect(machine.canStop().allowed).toBe(false);

    // Fleet reviewer runs re-review and grants LGTM
    const reReviewState = machine.setReviewResult({
      lgtm: true,
      issues: [],
    });
    expect(reReviewState.status).toBe(STATUS.RESOLVED_LGTM);
    expect(machine.canStop().allowed).toBe(true);
  });

  it('resolves all unresolved blocking issues to REVIEW_REQUESTED when resolveIssues is called with null targetIds', () => {
    machine.setPrCreated(45);
    machine.setReviewResult({
      lgtm: false,
      issues: [
        { id: 'issue-1', type: 'must', description: 'Fix issue 1', resolved: false },
        { id: 'issue-2', type: 'should', description: 'Fix issue 2', resolved: false },
      ],
    });

    const state = machine.resolveIssues('commit-batch');
    // Enforces Re-review: status is REVIEW_REQUESTED, NOT RESOLVED_LGTM
    expect(state.status).toBe(STATUS.REVIEW_REQUESTED);
    expect(state.issues.every((i: { resolved: boolean }) => i.resolved)).toBe(true);
    expect(machine.canStop().allowed).toBe(false);

    // Transitions to RESOLVED_LGTM only after Fleet grants LGTM
    const finalState = machine.setReviewResult({ lgtm: true, issues: [] });
    expect(finalState.status).toBe(STATUS.RESOLVED_LGTM);
    expect(machine.canStop().allowed).toBe(true);
  });

  describe('Reset Gate Verification', () => {
    it('rejects reset when PR is still OPEN on GitHub', () => {
      machine.setPrCreated(45);
      expect(fs.existsSync(testStateFile)).toBe(true);

      expect(() => {
        machine.reset({
          checkPrStateFn: () => 'OPEN',
        });
      }).toThrow('[Reset Gate Denied] Cannot reset loopState: PR #45 is in state "OPEN"');

      // State file and status must be preserved
      expect(fs.existsSync(testStateFile)).toBe(true);
      expect(machine.getState().status).toBe(STATUS.PR_CREATED);
    });

    it('allows reset when PR has been MERGED on GitHub', () => {
      machine.setPrCreated(45);
      expect(fs.existsSync(testStateFile)).toBe(true);

      const resetState = machine.reset({
        checkPrStateFn: () => 'MERGED',
      });
      expect(resetState.status).toBe(STATUS.IDLE);
      expect(fs.existsSync(testStateFile)).toBe(false);

      const check = machine.canStop();
      expect(check.allowed).toBe(true);
    });

    it('allows reset when force option is true even if PR is still OPEN', () => {
      machine.setPrCreated(45);
      expect(fs.existsSync(testStateFile)).toBe(true);

      const resetState = machine.reset({
        force: true,
        checkPrStateFn: () => 'OPEN',
      });
      expect(resetState.status).toBe(STATUS.IDLE);
      expect(fs.existsSync(testStateFile)).toBe(false);

      const check = machine.canStop();
      expect(check.allowed).toBe(true);
    });

    it('allows reset when already in IDLE state without executing checks', () => {
      let called = false;
      const resetState = machine.reset({
        checkPrStateFn: () => {
          called = true;
          return 'OPEN';
        },
      });
      expect(resetState.status).toBe(STATUS.IDLE);
      expect(called).toBe(false);
    });
  });

  it('allows stop when hasActiveSubagents is true in PR_CREATED or REVIEW_REQUESTED', () => {
    machine.setPrCreated(45);
    expect(machine.canStop().allowed).toBe(false);
    expect(machine.canStop({ hasActiveSubagents: true }).allowed).toBe(true);
    expect(machine.canStop({ hasActiveSubagents: true }).reason).toContain('Active subagent running');

    machine.setReviewRequested({ skipCiCheck: true });
    expect(machine.canStop({ hasActiveSubagents: true }).allowed).toBe(true);
    expect(machine.canStop({ hasActiveSubagents: false }).allowed).toBe(false);
  });

  it('allows stop unconditionally when isSubagent is true, even with blocking issues in NEEDS_FIX', () => {
    machine.setPrCreated(45);
    machine.setReviewResult({
      lgtm: false,
      issues: [{ id: '1', type: 'must', description: 'Blocker', resolved: false }],
    });

    expect(machine.canStop().allowed).toBe(false);
    const check = machine.canStop({ isSubagent: true });
    expect(check.allowed).toBe(true);
    expect(check.reason).toContain('subagent context');
  });

  it('manages activeSubagents state flag via setReviewRequested, setActiveSubagents, and setReviewResult', () => {
    machine.setPrCreated(45);
    expect(machine.getState().activeSubagents).toBe(false);

    // Default setReviewRequested sets activeSubagents to false unless specified
    machine.setReviewRequested({ skipCiCheck: true });
    expect(machine.getState().activeSubagents).toBe(false);
    expect(machine.canStop({ hasActiveSubagents: machine.getState().activeSubagents }).allowed).toBe(false);

    // Explicit true
    machine.setReviewRequested({ activeSubagents: true, skipCiCheck: true });
    expect(machine.getState().activeSubagents).toBe(true);
    expect(machine.canStop({ hasActiveSubagents: machine.getState().activeSubagents }).allowed).toBe(true);

    // Manual setActiveSubagents
    machine.setActiveSubagents(true);
    expect(machine.getState().activeSubagents).toBe(true);
    expect(machine.canStop({ hasActiveSubagents: machine.getState().activeSubagents }).allowed).toBe(true);

    // Completing review resets activeSubagents to false
    machine.setReviewResult({ lgtm: true, issues: [] });
    expect(machine.getState().activeSubagents).toBe(false);
  });

  describe('Review Consortium (2-Agent Consensus Gate)', () => {
    it('initializes with null review slots for codeReviewer and completionAuditor', () => {
      machine.setPrCreated(68);
      const state = machine.getState();
      expect(state.reviews).toBeDefined();
      expect(state.reviews.codeReviewer).toBeNull();
      expect(state.reviews.completionAuditor).toBeNull();
    });

    it('stays in REVIEW_REQUESTED when only one reviewer submits review', () => {
      machine.setPrCreated(68);
      machine.setReviewRequested({ skipCiCheck: true });

      const state = machine.recordReview('codeReviewer', {
        verdict: 'LGTM',
        issues: [],
      });

      expect(state.status).toBe(STATUS.REVIEW_REQUESTED);
      expect(state.reviews.codeReviewer).not.toBeNull();
      expect(state.reviews.codeReviewer.verdict).toBe('LGTM');
      expect(state.reviews.completionAuditor).toBeNull();
      expect(machine.canStop().allowed).toBe(false);
      expect(machine.canStop().reason).toContain('fleet_completion_auditor');
    });

    it('stays in REVIEW_REQUESTED and preserves activeSubagents when first reviewer submits REQUEST_CHANGES (preventing deadlock)', () => {
      machine.setPrCreated(68);
      machine.setReviewRequested({ activeSubagents: true, skipCiCheck: true });

      const state = machine.recordReview('codeReviewer', {
        verdict: 'REQUEST_CHANGES',
        issues: [
          { id: 'code-1', type: 'must', description: 'Fix race condition', resolved: false },
        ],
      });

      // Crucial: Must stay in REVIEW_REQUESTED until second reviewer finishes
      expect(state.status).toBe(STATUS.REVIEW_REQUESTED);
      expect(state.activeSubagents).toBe(true);
      expect(state.reviews.codeReviewer?.verdict).toBe('REQUEST_CHANGES');
      expect(state.reviews.completionAuditor).toBeNull();
      // Because activeSubagents is still true, canStop allows turn termination for Reactive Wakeup!
      expect(machine.canStop({ hasActiveSubagents: machine.getState().activeSubagents }).allowed).toBe(true);

      // Now second reviewer finishes with LGTM -> transitions to NEEDS_FIX because codeReviewer requested changes
      const finalState = machine.recordReview('completionAuditor', {
        verdict: 'LGTM',
        issues: [],
      });
      expect(finalState.status).toBe(STATUS.NEEDS_FIX);
      expect(finalState.activeSubagents).toBe(false);
      expect(machine.canStop().allowed).toBe(false);
      expect(machine.canStop().reason).toContain('NEEDS_FIX');
    });

    it('transitions to NEEDS_FIX and accumulates issues when both reviewers submit REQUEST_CHANGES', () => {
      machine.setPrCreated(68);
      machine.setReviewRequested({ skipCiCheck: true });

      machine.recordReview('codeReviewer', {
        verdict: 'REQUEST_CHANGES',
        issues: [
          { id: 'code-1', type: 'must', description: 'Code issue', resolved: false },
        ],
      });

      const state = machine.recordReview('completionAuditor', {
        verdict: 'REQUEST_CHANGES',
        issues: [
          { id: 'ca-1', type: 'should', description: 'Auditor issue', resolved: false },
        ],
      });

      expect(state.status).toBe(STATUS.NEEDS_FIX);
      expect(state.issues.length).toBe(2);
      expect(state.issues.map((i: { id: string }) => i.id)).toEqual(['code-1', 'ca-1']);
      expect(machine.canStop().allowed).toBe(false);
      expect(machine.canStop().reason).toContain('NEEDS_FIX');
    });

    it('transitions to NEEDS_FIX when one reviewer submits REQUEST_CHANGES even if other is LGTM', () => {
      machine.setPrCreated(68);
      machine.setReviewRequested({ skipCiCheck: true });

      machine.recordReview('codeReviewer', {
        verdict: 'LGTM',
        issues: [],
      });

      const state = machine.recordReview('completionAuditor', {
        verdict: 'REQUEST_CHANGES',
        issues: [
          { id: 'ca-1', type: 'must', description: 'Why section is not addressed in implementation', resolved: false },
        ],
      });

      expect(state.status).toBe(STATUS.NEEDS_FIX);
      expect(state.issues.length).toBe(1);
      expect(state.issues[0].id).toBe('ca-1');
      expect(machine.canStop().allowed).toBe(false);
      expect(machine.canStop().reason).toContain('NEEDS_FIX');
    });

    it('transitions to RESOLVED_LGTM only when both reviewers submit LGTM with zero blocking issues', () => {
      machine.setPrCreated(68);
      machine.setReviewRequested({ skipCiCheck: true });

      machine.recordReview('codeReviewer', {
        verdict: 'LGTM',
        issues: [],
      });
      expect(machine.getState().status).toBe(STATUS.REVIEW_REQUESTED);

      const state = machine.recordReview('completionAuditor', {
        verdict: 'LGTM',
        issues: [
          { id: 'ca-nits', type: 'nits', description: 'Small markdown polish' },
        ],
      });

      expect(state.status).toBe(STATUS.RESOLVED_LGTM);
      expect(state.reviews.codeReviewer.verdict).toBe('LGTM');
      expect(state.reviews.completionAuditor.verdict).toBe('LGTM');
      expect(machine.canStop().allowed).toBe(true);
      expect(machine.canStop().reason).toContain('RESOLVED_LGTM');
    });

    it('resets reviews slots when setReviewRequested is called for re-review', () => {
      machine.setPrCreated(68);
      machine.setReviewRequested({ skipCiCheck: true });
      machine.recordReview('codeReviewer', { verdict: 'LGTM', issues: [] });
      expect(machine.getState().reviews.codeReviewer).not.toBeNull();

      machine.setReviewRequested({ skipCiCheck: true });
      expect(machine.getState().reviews.codeReviewer).toBeNull();
      expect(machine.getState().reviews.completionAuditor).toBeNull();
    });

    it('invalidates and resets reviews slots when resolveIssues transitions to REVIEW_REQUESTED, requiring fresh consensus from both reviewers', () => {
      machine.setPrCreated(68);
      machine.setReviewRequested({ skipCiCheck: true });

      // completionAuditor gives LGTM, but codeReviewer requests changes
      machine.recordReview('completionAuditor', { verdict: 'LGTM', issues: [] });
      machine.recordReview('codeReviewer', {
        verdict: 'REQUEST_CHANGES',
        issues: [{ id: 'code-1', type: 'must', description: 'Fix race condition', resolved: false }],
      });
      expect(machine.getState().status).toBe(STATUS.NEEDS_FIX);
      expect(machine.getState().reviews.completionAuditor?.verdict).toBe('LGTM');

      // Parent agent fixes issue and reports resolution
      const resolvedState = machine.resolveIssues('commit-fix1', ['code-1']);
      expect(resolvedState.status).toBe(STATUS.REVIEW_REQUESTED);
      // Both slots MUST be invalidated (set to null) because new code was committed!
      expect(resolvedState.reviews.codeReviewer).toBeNull();
      expect(resolvedState.reviews.completionAuditor).toBeNull();

      // If only codeReviewer re-reviews and grants LGTM, still cannot terminate because completionAuditor has not re-audited
      machine.recordReview('codeReviewer', { verdict: 'LGTM', issues: [] });
      expect(machine.getState().status).toBe(STATUS.REVIEW_REQUESTED);
      expect(machine.canStop().allowed).toBe(false);

      // Only when completionAuditor also re-audits and grants LGTM, consensus is reached
      machine.recordReview('completionAuditor', { verdict: 'LGTM', issues: [] });
      expect(machine.getState().status).toBe(STATUS.RESOLVED_LGTM);
      expect(machine.canStop().allowed).toBe(true);
    });
  });
});
