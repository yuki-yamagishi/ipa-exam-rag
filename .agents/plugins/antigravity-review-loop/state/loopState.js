/**
 * Loop State Machine (.agents/plugins/antigravity-review-loop/state/loopState.js)
 * 
 * ADR-0016 / ADR-0018 / ADR-0022
 * Manages the deterministic lifecycle state of the self-healing review loop.
 * State is persisted to .agents/plugins/antigravity-review-loop/state/loop_state.json.
 */

import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

export const STATUS = Object.freeze({
  IDLE: 'IDLE',
  PR_CREATED: 'PR_CREATED',
  REVIEW_REQUESTED: 'REVIEW_REQUESTED',
  NEEDS_FIX: 'NEEDS_FIX',
  RESOLVED_LGTM: 'RESOLVED_LGTM',
});

const DIR_NAME = path.dirname(fileURLToPath(import.meta.url));
export const DEFAULT_STATE_FILE = process.env.LOOP_STATE_FILE || 
  path.resolve(DIR_NAME, 'loop_state.json');

/**
 * Creates a blank initial state object.
 */
export function createInitialState() {
  return {
    status: STATUS.IDLE,
    prNumber: null,
    reviewRequestedAt: null,
    reviews: {
      codeReviewer: null,
      completionAuditor: null,
    },
    issues: [],
    activeSubagents: false,
    updatedAt: new Date().toISOString(),
  };
}

/**
 * Deterministic Loop State Machine
 */
export class LoopStateMachine {
  constructor(stateFilePath = DEFAULT_STATE_FILE) {
    this.filePath = stateFilePath;
  }

  getState() {
    try {
      if (!fs.existsSync(this.filePath)) {
        return createInitialState();
      }
      const raw = fs.readFileSync(this.filePath, 'utf8');
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object' || !parsed.status) {
        return createInitialState();
      }
      return {
        ...createInitialState(),
        ...parsed,
        reviews: {
          codeReviewer: null,
          completionAuditor: null,
          ...(parsed.reviews || {}),
        },
      };
    } catch {
      return createInitialState();
    }
  }

  saveState(state) {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    const updatedState = {
      ...state,
      updatedAt: new Date().toISOString(),
    };
    fs.writeFileSync(this.filePath, JSON.stringify(updatedState, null, 2), 'utf8');
    return updatedState;
  }

  setPrCreated(prNumber) {
    const num = Number(prNumber);
    if (isNaN(num) || num <= 0) {
      throw new Error(`Invalid PR number: ${prNumber}`);
    }
    const newState = {
      status: STATUS.PR_CREATED,
      prNumber: num,
      reviewRequestedAt: null,
      reviews: {
        codeReviewer: null,
        completionAuditor: null,
      },
      issues: [],
      activeSubagents: false,
    };
    return this.saveState(newState);
  }

  setReviewRequested(options = {}) {
    const current = this.getState();

    // 1. CI Status Verification Gate (Mechanism against ignoring failing/pending CI)
    const skipCiCheck = Boolean(options.skipCiCheck);
    if (!skipCiCheck && current.prNumber) {
      const checkCiFn = options.checkCiFn || ((prNum) => {
        try {
          return execSync(`gh pr checks ${prNum}`, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
        } catch (err) {
          const out = (err.stdout || '') + (err.stderr || '');
          if (out) return out;
          throw new Error(`Failed to check CI status for PR #${prNum}: ${err.message}`);
        }
      });

      const ciOutput = checkCiFn(current.prNumber);
      if (typeof ciOutput === 'string') {
        const lower = ciOutput.toLowerCase();
        if (lower.includes('pending') || lower.includes('in_progress') || lower.includes('queued')) {
          throw new Error(
            `[CI Gate Denied] GitHub Actions CI for PR #${current.prNumber} is still pending or running. Please wait for CI to complete before requesting review.`
          );
        }
        if (lower.includes('fail') || lower.includes('failure') || lower.includes('error')) {
          throw new Error(
            `[CI Gate Denied] GitHub Actions CI for PR #${current.prNumber} has failing checks. Please investigate and fix failures before requesting review.`
          );
        }
      }
    }

    const updated = {
      ...current,
      status: STATUS.REVIEW_REQUESTED,
      reviewRequestedAt: new Date().toISOString(),
      reviews: {
        codeReviewer: null,
        completionAuditor: null,
      },
      activeSubagents: Boolean(options.activeSubagents),
    };
    return this.saveState(updated);
  }

  setActiveSubagents(active = true) {
    const current = this.getState();
    const updated = {
      ...current,
      activeSubagents: Boolean(active),
    };
    return this.saveState(updated);
  }

  /**
   * Records an individual review from a specific agent in the review consortium.
   * Consensus Gate: RESOLVED_LGTM is only reached when both codeReviewer and
   * completionAuditor have completed reviews and both have verdict === 'LGTM' with 0 blocking issues.
   */
  recordReview(agentType, { verdict = 'LGTM', issues = [] } = {}) {
    const current = this.getState();
    const validAgents = ['codeReviewer', 'completionAuditor'];
    const normalizedAgent = validAgents.includes(agentType) ? agentType : 'codeReviewer';

    const formattedIssues = issues.map((issue, idx) => ({
      id: issue.id || `${normalizedAgent}-${idx + 1}`,
      source: normalizedAgent,
      type: (issue.type || 'should').toLowerCase(),
      description: issue.description || '',
      resolved: Boolean(issue.resolved),
      resolvedCommit: issue.resolvedCommit || null,
    }));

    const updatedReviews = {
      ...(current.reviews || { codeReviewer: null, completionAuditor: null }),
      [normalizedAgent]: {
        verdict: String(verdict).toUpperCase(),
        issues: formattedIssues,
        reviewedAt: new Date().toISOString(),
      },
    };

    // Aggregate issues from all recorded reviews
    const allIssues = [
      ...(updatedReviews.codeReviewer?.issues || []),
      ...(updatedReviews.completionAuditor?.issues || []),
    ];

    const unresolvedBlocking = allIssues.filter(
      (issue) => ['must', 'should'].includes(issue.type) && !issue.resolved
    );

    const hasAnyRejection = 
      updatedReviews.codeReviewer?.verdict === 'REQUEST_CHANGES' ||
      updatedReviews.completionAuditor?.verdict === 'REQUEST_CHANGES' ||
      unresolvedBlocking.length > 0;

    const hasBothReviews = updatedReviews.codeReviewer !== null && updatedReviews.completionAuditor !== null;

    let nextStatus = STATUS.REVIEW_REQUESTED;
    if (!hasBothReviews) {
      // Both reviews must be submitted before deciding final consensus to prevent premature NEEDS_FIX and deadlock
      nextStatus = STATUS.REVIEW_REQUESTED;
    } else if (hasAnyRejection) {
      nextStatus = STATUS.NEEDS_FIX;
    } else if (updatedReviews.codeReviewer.verdict === 'LGTM' && updatedReviews.completionAuditor.verdict === 'LGTM') {
      nextStatus = STATUS.RESOLVED_LGTM;
    }

    const updated = {
      ...current,
      status: nextStatus,
      reviews: updatedReviews,
      issues: allIssues,
      activeSubagents: hasBothReviews ? false : Boolean(current.activeSubagents),
    };
    return this.saveState(updated);
  }

  setReviewResult({ lgtm, issues = [] }) {
    // Backward compatibility wrapper for single-agent tests
    const current = this.getState();
    const formattedIssues = issues.map((issue, idx) => ({
      id: issue.id || `issue-${idx + 1}`,
      type: (issue.type || 'should').toLowerCase(),
      description: issue.description || '',
      resolved: Boolean(issue.resolved),
      resolvedCommit: issue.resolvedCommit || null,
    }));

    const unresolvedBlocking = formattedIssues.filter(
      (issue) => ['must', 'should'].includes(issue.type) && !issue.resolved
    );

    const isLgtm = Boolean(lgtm) && unresolvedBlocking.length === 0;
    const nextStatus = isLgtm ? STATUS.RESOLVED_LGTM : STATUS.NEEDS_FIX;

    const updated = {
      ...current,
      status: nextStatus,
      reviews: {
        codeReviewer: {
          verdict: isLgtm ? 'LGTM' : 'REQUEST_CHANGES',
          issues: formattedIssues,
          reviewedAt: new Date().toISOString(),
        },
        completionAuditor: {
          verdict: isLgtm ? 'LGTM' : 'REQUEST_CHANGES',
          issues: [],
          reviewedAt: new Date().toISOString(),
        },
      },
      issues: formattedIssues,
      activeSubagents: false,
    };
    return this.saveState(updated);
  }

  resolveIssues(resolvedCommit, resolvedIssueIds = null) {
    const current = this.getState();
    const targetIds = resolvedIssueIds
      ? (Array.isArray(resolvedIssueIds) ? resolvedIssueIds : [resolvedIssueIds])
      : null;

    const updatedIssues = current.issues.map((issue) => {
      const shouldResolve = targetIds
        ? targetIds.includes(issue.id)
        : ['must', 'should'].includes(issue.type) && !issue.resolved;

      if (shouldResolve) {
        return {
          ...issue,
          resolved: true,
          resolvedCommit: resolvedCommit || null,
        };
      }
      return issue;
    });

    const unresolvedBlocking = updatedIssues.filter(
      (issue) => ['must', 'should'].includes(issue.type) && !issue.resolved
    );

    // ガバナンス厳格化: 全ての指摘に対応コミットを紐付けた場合でも、
    // 親エージェントが独断で RESOLVED_LGTM に遷移することは物理的に禁止。
    // 必ず STATUS.REVIEW_REQUESTED（再レビュー待ち）に遷移し、
    // コード変更が入ったため過去のレビュー判定は Stale（無効化）とし、
    // Fleet レビュー 2 者（codeReviewer, completionAuditor）双方による再レビュー・再監査を必須とする。
    const isAllResolved = unresolvedBlocking.length === 0;
    const nextStatus = isAllResolved ? STATUS.REVIEW_REQUESTED : STATUS.NEEDS_FIX;

    const updated = {
      ...current,
      status: nextStatus,
      issues: updatedIssues,
      reviews: isAllResolved
        ? { codeReviewer: null, completionAuditor: null }
        : current.reviews,
      activeSubagents: false,
    };
    return this.saveState(updated);
  }

  reset(options = {}) {
    const current = this.getState();
    const isForce = Boolean(options.force) || Boolean(options.isForce);

    // 2. Merge Verification Gate on Reset (Mechanism against resetting before human merge)
    if (!isForce && current.status !== STATUS.IDLE && current.prNumber) {
      const checkPrStateFn = options.checkPrStateFn || ((prNum) => {
        try {
          return execSync(`gh pr view ${prNum} --json state --jq .state`, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
        } catch {
          return 'UNKNOWN';
        }
      });

      const prState = checkPrStateFn(current.prNumber);
      if (prState !== 'MERGED' && prState !== 'UNKNOWN') {
        throw new Error(
          `[Reset Gate Denied] Cannot reset loopState: PR #${current.prNumber} is in state "${prState}". Loop state can only be safely reset after the PR has been merged to main by the user. (Emergency override: run 'node .agents/plugins/antigravity-review-loop/state/loopState.js reset --force')`
        );
      }
    }

    try {
      if (fs.existsSync(this.filePath)) {
        fs.unlinkSync(this.filePath);
      }
    } catch {
      // Ignored
    }
    return createInitialState();
  }

  canStop(options = {}) {
    const current = this.getState();
    const isSubagent = Boolean(options.isSubagent);
    const hasActiveSubagents = Boolean(options.hasActiveSubagents);

    // 1. Subagent execution context bypass
    if (isSubagent) {
      return {
        allowed: true,
        status: current.status,
        prNumber: current.prNumber,
        reason: 'Stop allowed: Execution is running inside a subagent context.',
      };
    }

    // 2. Active subagent waiting bypass (parent agent waiting for Reactive Wakeup)
    if (hasActiveSubagents && (current.status === STATUS.PR_CREATED || current.status === STATUS.REVIEW_REQUESTED)) {
      return {
        allowed: true,
        status: current.status,
        prNumber: current.prNumber,
        reason: `Stop allowed: Active subagent running in status "${current.status}". Parent agent is waiting for reactive wakeup notification.`,
      };
    }

    // 3. Normal status check
    const allowed = current.status === STATUS.IDLE || current.status === STATUS.RESOLVED_LGTM;

    let reason = '';
    if (allowed) {
      reason = current.status === STATUS.IDLE
        ? 'No active review loop running (IDLE).'
        : 'All review issues have been resolved and LGTM reached (RESOLVED_LGTM).';
    } else {
      const unresolvedCount = current.issues.filter(
        (i) => ['must', 'should'].includes(i.type) && !i.resolved
      ).length;

      let guidance = '';
      switch (current.status) {
        case STATUS.PR_CREATED:
          guidance = `Wait for GitHub Actions CI to pass on PR #${current.prNumber}, then run 'node .agents/plugins/antigravity-review-loop/state/loopState.js review-requested' and launch fleet reviewers ('fleet_reviewer' and 'fleet_completion_auditor').`;
          break;
        case STATUS.REVIEW_REQUESTED: {
          const pending = [];
          if (!current.reviews?.codeReviewer) pending.push('fleet_reviewer');
          if (!current.reviews?.completionAuditor) pending.push('fleet_completion_auditor');
          const pendingStr = pending.length > 0 ? pending.join(' and ') : 'fleet reviewers';
          guidance = `Multi-agent review consortium is in progress. Await review from [${pendingStr}]. Parse results with 'node .agents/plugins/antigravity-review-loop/skills/review-self-healing/scripts/parseReviewResult.js <file> --agent-type <codeReviewer|completionAuditor> --update-state'.`;
          break;
        }
        case STATUS.NEEDS_FIX:
          guidance = `Fix the ${unresolvedCount} unresolved blocking issue(s) from review consortium, commit changes, push to remote, and run 'node .agents/plugins/antigravity-review-loop/skills/review-self-healing/scripts/resolveReview.js' to report fixes and request re-review.`;
          break;
        default:
          guidance = `Complete the self-healing review cycle and reach RESOLVED_LGTM.`;
          break;
      }

      reason = `Stop rejected: Loop is currently in status "${current.status}" with ${unresolvedCount} unresolved blocking issue(s). (Remediation Guidance: ${guidance}) (Emergency abort: run 'node .agents/plugins/antigravity-review-loop/state/loopState.js reset --force')`;
    }

    return {
      allowed,
      status: current.status,
      prNumber: current.prNumber,
      reason,
    };
  }
}

export const defaultStateMachine = new LoopStateMachine();

export function getState() { return defaultStateMachine.getState(); }
export function saveState(state) { return defaultStateMachine.saveState(state); }
export function setPrCreated(prNumber) { return defaultStateMachine.setPrCreated(prNumber); }
export function setReviewRequested(options = {}) { return defaultStateMachine.setReviewRequested(options); }
export function setActiveSubagents(active = true) { return defaultStateMachine.setActiveSubagents(active); }
export function recordReview(agentType, result) { return defaultStateMachine.recordReview(agentType, result); }
export function setReviewResult(result) { return defaultStateMachine.setReviewResult(result); }
export function resolveIssues(resolvedCommit, resolvedIssueIds = null) { return defaultStateMachine.resolveIssues(resolvedCommit, resolvedIssueIds); }
export function reset(options = {}) { return defaultStateMachine.reset(options); }
export function canStop(options = {}) { return defaultStateMachine.canStop(options); }

// CLI Command Runner
const isDirectExecution = process.argv[1] && 
  (fileURLToPath(import.meta.url).toLowerCase() === path.resolve(process.argv[1]).toLowerCase() ||
   process.argv[1].toLowerCase().endsWith('loopstate.js'));

if (isDirectExecution) {
  const [,, command, ...args] = process.argv;
  switch (command) {
    case 'status': {
      console.log(JSON.stringify(getState(), null, 2));
      break;
    }
    case 'can-stop': {
      const hasActive = args.includes('--has-active-subagents');
      const isSub = args.includes('--is-subagent');
      const check = canStop({ hasActiveSubagents: hasActive, isSubagent: isSub });
      if (check.allowed) {
        console.log(`[PASS] ${check.reason}`);
        process.exit(0);
      } else {
        console.error(`[BLOCKED] ${check.reason}`);
        process.exit(1);
      }
      break;
    }
    case 'pr-created': {
      const prNumber = args[0];
      if (!prNumber) {
        console.error('Usage: node loopState.js pr-created <prNumber>');
        process.exit(1);
      }
      const state = setPrCreated(prNumber);
      console.log(`[OK] State transitioned to PR_CREATED for PR #${state.prNumber}`);
      break;
    }
    case 'review-requested': {
      const hasActive = args.includes('--active-subagents') || args.includes('true');
      const skipCi = args.includes('--skip-ci');
      try {
        const state = setReviewRequested({ activeSubagents: hasActive, skipCiCheck: skipCi });
        console.log(`[OK] State transitioned to REVIEW_REQUESTED (activeSubagents: ${state.activeSubagents})`);
      } catch (err) {
        console.error(`[BLOCKED] ${err.message}`);
        process.exit(1);
      }
      break;
    }
    case 'active-subagents': {
      const flag = args[0] !== 'false';
      const state = setActiveSubagents(flag);
      console.log(`[OK] activeSubagents set to ${state.activeSubagents}`);
      break;
    }
    case 'record-review': {
      const agentType = args[0] || 'codeReviewer';
      const verdict = args[1] || 'LGTM';
      let issues = [];
      if (args[2]) {
        try {
          issues = JSON.parse(args[2]);
        } catch {
          issues = [];
        }
      }
      const state = recordReview(agentType, { verdict, issues });
      console.log(`[OK] Review recorded for ${agentType}: status = ${state.status}`);
      break;
    }
    case 'reset': {
      const isForce = args.includes('--force');
      try {
        reset({ force: isForce });
        console.log(`[OK] State reset to IDLE`);
      } catch (err) {
        console.error(`[BLOCKED] ${err.message}`);
        process.exit(1);
      }
      break;
    }
    default: {
      console.log('Usage: node loopState.js <status|can-stop|pr-created|review-requested|active-subagents|record-review|reset>');
      process.exit(0);
    }
  }
}
