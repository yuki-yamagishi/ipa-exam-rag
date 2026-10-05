/**
 * Branch DoR Gate Hook (.agents/hooks/branchDoRGate.js)
 * 
 * Enforces Definition of Ready (DoR) before creating a topic branch:
 * 1. Working tree cleanliness (no uncommitted dirty changes).
 * 2. LoopState IDLE check (no unfinished active PR review loop).
 * 3. GitHub Issue state and DoR label (status: ready) validation.
 * 4. Why-First & Risks to Eliminate validation in docs/issues/ISSUE-XXX/issue.md.
 * 5. Impact & Duplication Check validation in docs/issues/ISSUE-XXX/pre_verification.md.
 * 6. Template placeholder elimination in specification documents.
 */

import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { readStdinJson, writeStdoutJson, findProjectRoot } from './hookUtils.js';
import { defaultStateMachine, STATUS } from '../state/loopState.js';

/**
 * Step 1: Validates working tree cleanliness.
 * Prohibits creating branches with uncommitted dirty changes (except untracked docs/issues/).
 */
function verifyWorkingTreeCleanliness(exec, projectRoot) {
  try {
    const statusOut = exec('git status --porcelain', { cwd: projectRoot, encoding: 'utf8' }).trim();
    if (statusOut.length > 0) {
      const lines = statusOut.split('\n').map((l) => l.trim()).filter(Boolean);
      // Allow untracked docs/issues/ files created for the new issue, but block any modified, deleted, staged, or other untracked files
      const dirtyLines = lines.filter((l) => !/^\?\?\s+"?docs[/\\]issues[/\\]/i.test(l));
      if (dirtyLines.length > 0) {
        return {
          decision: 'deny',
          reason: "[BranchDoRGate Denied] Working tree is dirty. Commit, stash, or clean up uncommitted changes before creating a new branch.",
        };
      }
    }
  } catch {
    // Ignored if git fails in mock/test
  }
  return { decision: 'allow' };
}

/**
 * Step 2: Validates that review loop state is IDLE.
 * Prohibits starting new branches while an active review loop is in progress.
 */
function verifyLoopStateIdle(stateMachine) {
  const currentState = stateMachine.getState();
  if (currentState && currentState.status && currentState.status !== STATUS.IDLE) {
    return {
      decision: 'deny',
      reason: `[BranchDoRGate Denied] An active review loop is still running (status: "${currentState.status}", PR: #${currentState.prNumber}). You must complete or merge the existing PR before starting a new branch.`,
    };
  }
  return { decision: 'allow' };
}

/**
 * Step 3: Validates that template placeholders are not left unfilled in specification files.
 */
function verifyNoTemplatePlaceholders(content, fileName, targetIssueDir) {
  const placeholderPatterns = [
    /\[ここに対象/i,
    /\[ここに[^\]\r\n]*(?:記載|記述)\]/i,
    /\[記入(?:してください)?\]/i,
    /<!--\s*TODO/i,
    /\bTODO:\s*(?:TBD|未定|後で書く)/i,
    /<(?:番号|簡潔な目的|シナリオ|前提|初期状態|操作|入力|期待|不正入力|境界値|異常値|エラー|要記述|TBD)[^>]*>/i,
    /<[ぁ-んァ-ヶー一-龠]+>/,
    /\bYYYY-MM-DD\b/,
    /\b(?:ADR-XXXX|ISSUE-XXX)\b/,
  ];

  for (const pattern of placeholderPatterns) {
    if (pattern.test(content)) {
      return {
        decision: 'deny',
        reason: `[BranchDoRGate Denied] Unfilled template placeholder detected in docs/issues/${targetIssueDir}/${fileName}. Fill in all specification details and remove template placeholders before creating a branch.`,
      };
    }
  }
  return { decision: 'allow' };
}

/**
 * Step 4: Validates GitHub Issue existence, open state, and DoR label (status: ready).
 */
function verifyGitHubIssueStatus(exec, issueNum, projectRoot) {
  try {
    const out = exec(`gh issue view ${issueNum} --json state,labels`, {
      cwd: projectRoot,
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    if (out && typeof out === 'string' && out.trim()) {
      const data = JSON.parse(out.trim());
      if (data.state && data.state.toUpperCase() !== 'OPEN') {
        return {
          decision: 'deny',
          reason: `[BranchDoRGate Denied] GitHub Issue #${issueNum} is closed (state: "${data.state}"). Cannot create a branch for a closed issue.`,
        };
      }
      const labels = Array.isArray(data.labels)
        ? data.labels.map((l) => (typeof l === 'string' ? l : l.name || ''))
        : [];
      const hasReadyOrInProgress = labels.some((l) => /status:\s*(?:ready|in-progress)/i.test(l));
      if (!hasReadyOrInProgress) {
        return {
          decision: 'deny',
          reason: `[BranchDoRGate Denied] GitHub Issue #${issueNum} does not satisfy Definition of Ready (current labels: [${labels.join(', ')}]). The issue must have 'status: ready' or 'status: in-progress' label before creating a branch. (Remediation Guidance: Add 'status: ready' via 'gh issue edit ${issueNum} --add-label "status: ready"' after completing requirements.)`,
        };
      }
    }
  } catch (err) {
    const errMsg = (err && (err.stderr || err.message || '')) + '';
    // Gracefully bypass if gh CLI is missing or not recognized in non-auth/minimal environments
    if (/command not found/i.test(errMsg) || /not recognized/i.test(errMsg) || /ENOENT/i.test(errMsg)) {
      return { decision: 'allow' };
    }
    if (/Could not resolve to an Issue/i.test(errMsg) || /\bissue.*not found\b/i.test(errMsg) || /HTTP 404/i.test(errMsg)) {
      return {
        decision: 'deny',
        reason: `[BranchDoRGate Denied] GitHub Issue #${issueNum} does not exist on GitHub. Create the issue on GitHub before creating a branch.`,
      };
    }
  }
  return { decision: 'allow' };
}

/**
 * Step 5: Validates Why-First, Risk Elimination, and Acceptance Criteria definitions in issue.md.
 */
function verifyWhyAndRiskSections(issuesDir, targetIssueDir) {
  const issueMdPath = path.resolve(issuesDir, targetIssueDir, 'issue.md');
  if (!fs.existsSync(issueMdPath)) {
    return {
      decision: 'deny',
      reason: `[BranchDoRGate Denied] issue.md does not exist in ${targetIssueDir}. (Remediation Guidance: Create 'docs/issues/${targetIssueDir}/issue.md' using 'docs/issues/template_issue.md' before creating a branch.)`,
    };
  }

  const issueContent = fs.readFileSync(issueMdPath, 'utf8');
  const hasWhySection = /##\s+(?:\d+\.\s+)?(?:解決すべき課題・背景|解決する課題・背景)\s*(?:\([^)]*Why[^)]*\))?/i.test(issueContent);
  const hasRiskSection = /##\s+(?:\d+\.\s+)?(?:排除するリスク)\s*(?:\([^)]*Risks?[^)]*\))?/i.test(issueContent);
  const hasCriteriaSection = /##\s+(?:\d+\.\s+)?(?:受け入れ基準|受入基準|(?:Acceptance Criteria|Definition of Done|DoD)\b)/i.test(issueContent);

  if (!hasWhySection || !hasRiskSection || !hasCriteriaSection) {
    const missing = [];
    if (!hasWhySection) missing.push("'Why (Background & Problem)'");
    if (!hasRiskSection) missing.push("'Risks to Eliminate'");
    if (!hasCriteriaSection) missing.push("'Acceptance Criteria / Definition of Done'");
    return {
      decision: 'deny',
      reason: `[BranchDoRGate Denied] Missing required sections in ${targetIssueDir}/issue.md: ${missing.join(', ')}. Define the root problem (Why), risks, and concrete acceptance criteria before jumping into implementation (What). (Remediation Guidance: Refer to 'docs/issues/template_issue.md' and add the required sections.)`,
    };
  }

  // Verify that Acceptance Criteria contains concrete scenarios or checklists (not just empty headers)
  const criteriaMatch = issueContent.match(/##\s+(?:\d+\.\s+)?(?:受け入れ基準|受入基準|(?:Acceptance Criteria|Definition of Done|DoD)\b)[\s\S]*?(?=\n##\s|$)/i);
  if (criteriaMatch) {
    const criteriaBody = criteriaMatch[0];

    // Strip blockquotes (e.g. '> ...') and HTML comments so template guidance doesn't self-trigger false positives
    const criteriaTextWithoutQuotes = criteriaBody
      .replace(/^\s*>.*$/gm, '')
      .replace(/<!--[\s\S]*?-->/g, '');

    // Detect ambiguous words that indicate unformed requirements in actual criteria text
    const hasVagueWords = /(?:適切に|よしなに|必要に応じて)/.test(criteriaTextWithoutQuotes);
    if (hasVagueWords) {
      return {
        decision: 'deny',
        reason: `[BranchDoRGate Denied] Acceptance Criteria in ${targetIssueDir}/issue.md contains ambiguous terms ('適切に', 'よしなに', or '必要に応じて'). Define concrete Given-When-Then scenarios with verifiable expectations before creating a branch. (Remediation Guidance: Use 'fleet_dor_auditor' to audit and refine 'docs/issues/${targetIssueDir}/issue.md'.)`,
      };
    }

    const hasConcreteItems = /(?:シナリオ|Given\b|When\b|Then\b|- \[[ x]\])/i.test(criteriaBody);
    if (!hasConcreteItems || criteriaBody.trim().length < 40) {
      return {
        decision: 'deny',
        reason: `[BranchDoRGate Denied] Acceptance Criteria in ${targetIssueDir}/issue.md is empty or too vague. Define concrete Given-When-Then scenarios or DoD checklists to eliminate ambiguity before creating a branch. (Remediation Guidance: Use 'fleet_dor_auditor' to audit and refine 'docs/issues/${targetIssueDir}/issue.md'.)`,
      };
    }
  }

  // Verify no template placeholders remain
  const placeholderResult = verifyNoTemplatePlaceholders(issueContent, 'issue.md', targetIssueDir);
  if (placeholderResult.decision === 'deny') {
    return placeholderResult;
  }

  return { decision: 'allow' };
}

/**
 * Step 6: Validates Impact & Duplication Check documentation in pre_verification.md.
 */
function verifyImpactDuplicationCheck(issuesDir, targetIssueDir) {
  const preVerifPath = path.resolve(issuesDir, targetIssueDir, 'pre_verification.md');
  if (!fs.existsSync(preVerifPath)) {
    return {
      decision: 'deny',
      reason: `[BranchDoRGate Denied] pre_verification.md does not exist in ${targetIssueDir}. Perform and document an Impact & Duplication Check before creating a branch. (Remediation Guidance: Create 'docs/issues/${targetIssueDir}/pre_verification.md' using 'docs/issues/template_pre_verification.md'.)`,
    };
  }

  const preVerifContent = fs.readFileSync(preVerifPath, 'utf8');
  const hasImpactSection = /##\s+(?:\d+\.\s+)?(?:重複・パッチワーク点検|重複・影響調査|Impact\s*(?:&|and)\s*Duplication\s*Check)/i.test(preVerifContent);
  if (!hasImpactSection) {
    return {
      decision: 'deny',
      reason: `[BranchDoRGate Denied] Missing 'Impact & Duplication Check' section in ${targetIssueDir}/pre_verification.md. Audit existing codebase, utilities, and past ADRs to prevent duplicated logic or patchwork fixes before creating a branch. (Remediation Guidance: Refer to 'docs/issues/template_pre_verification.md' and document Section 3 '重複・パッチワーク点検'.)`,
    };
  }

  // Verify no template placeholders remain
  const placeholderResult = verifyNoTemplatePlaceholders(preVerifContent, 'pre_verification.md', targetIssueDir);
  if (placeholderResult.decision === 'deny') {
    return placeholderResult;
  }

  return { decision: 'allow' };
}

export function handleBranchDoRGate(payload = {}, options = {}) {
  const toolCall = payload.toolCall || {};
  const toolName = toolCall.name || '';
  const args = toolCall.args || {};
  const commandLine = args.CommandLine || '';

  if (toolName !== 'run_command' || !commandLine) {
    return { decision: 'allow' };
  }

  const trimmed = commandLine.trim();
  const branchMatch = trimmed.match(/\bgit\s+(?:checkout\s+-b|switch\s+-c)\s+([^\s]+)/i);
  if (!branchMatch) {
    return { decision: 'allow' };
  }

  const branchName = branchMatch[1];
  const exec = options.execFn || execSync;
  const stateMachine = options.stateMachine || defaultStateMachine;
  const projectRoot = options.projectRoot || findProjectRoot(path.dirname(fileURLToPath(import.meta.url)));

  // Step 1: Working tree cleanliness
  const cleanlinessResult = verifyWorkingTreeCleanliness(exec, projectRoot);
  if (cleanlinessResult.decision === 'deny') {
    return cleanlinessResult;
  }

  // Step 2: LoopState IDLE check
  const idleResult = verifyLoopStateIdle(stateMachine);
  if (idleResult.decision === 'deny') {
    return idleResult;
  }

  // Step 3, 4, 5, 6: Issue specification & DoR documentation check
  const issueNumMatch = branchName.match(/issue-(\d+)/i);
  if (issueNumMatch) {
    const issueNum = parseInt(issueNumMatch[1], 10);

    // Step 3: GitHub Issue existence, open state, and DoR label check
    const ghIssueResult = verifyGitHubIssueStatus(exec, issueNum, projectRoot);
    if (ghIssueResult.decision === 'deny') {
      return ghIssueResult;
    }

    const issuesDir = path.resolve(projectRoot, 'docs/issues');
    
    let targetIssueDir = null;
    if (fs.existsSync(issuesDir)) {
      const entries = fs.readdirSync(issuesDir);
      const prefixPadded = `ISSUE-${String(issueNum).padStart(3, '0')}`;
      const prefixRaw = `ISSUE-${issueNum}`;
      targetIssueDir = entries.find((e) => e.startsWith(prefixPadded) || e.startsWith(prefixRaw));
    }

    if (!targetIssueDir) {
      return {
        decision: 'deny',
        reason: `[BranchDoRGate Denied] No issue document found for Issue #${issueNum} under docs/issues/. (Remediation Guidance: Create the issue document 'docs/issues/ISSUE-${String(issueNum).padStart(3, '0')}_.../issue.md' using 'docs/issues/template_issue.md' before creating a branch.)`,
      };
    }

    // Step 4 & 5: Why-First, Risk Elimination, and Placeholder check on issue.md
    const whyRiskResult = verifyWhyAndRiskSections(issuesDir, targetIssueDir);
    if (whyRiskResult.decision === 'deny') {
      return whyRiskResult;
    }

    // Step 6: Impact & Duplication Check and Placeholder check in pre_verification.md
    const impactResult = verifyImpactDuplicationCheck(issuesDir, targetIssueDir);
    if (impactResult.decision === 'deny') {
      return impactResult;
    }
  }

  return { decision: 'allow' };
}

const isDirectExecution = process.argv[1] && 
  (fileURLToPath(import.meta.url).toLowerCase() === path.resolve(process.argv[1]).toLowerCase());

if (isDirectExecution) {
  readStdinJson().then((payload) => {
    const result = handleBranchDoRGate(payload);
    writeStdoutJson(result);
    process.exit(0);
  });
}
