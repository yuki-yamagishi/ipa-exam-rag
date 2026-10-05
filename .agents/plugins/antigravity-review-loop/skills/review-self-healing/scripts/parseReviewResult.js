/**
 * Review Result Parser (.agents/skills/review-self-healing/scripts/parseReviewResult.js)
 * 
 * Parses Fleet review markdown text to extract Conventional Comments prefixes
 * ([must], [should], [imo], [nits], [ask], [good]) and the overall verdict ([LGTM] or [要修正]).
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { recordReview, setReviewResult, STATUS } from '../../../state/loopState.js';

export function parseReviewResult(reviewText, options = {}) {
  if (typeof reviewText !== 'string') {
    reviewText = '';
  }

  // Detect agentType, verdict, and issues from JSON block if available
  let detectedAgentType = options.agentType || null;
  let jsonVerdict = null;
  let jsonIssues = null;

  const jsonMatches = [...reviewText.matchAll(/```json\s*([\s\S]*?)\s*```/gi)];
  for (let i = jsonMatches.length - 1; i >= 0; i--) {
    try {
      const parsedJson = JSON.parse(jsonMatches[i][1]);
      if (parsedJson) {
        if (!detectedAgentType && parsedJson.agentType) {
          detectedAgentType = parsedJson.agentType;
        }
        if (!jsonVerdict && parsedJson.verdict) {
          jsonVerdict = String(parsedJson.verdict).trim().toUpperCase();
        }
        if (!jsonIssues && Array.isArray(parsedJson.issues)) {
          jsonIssues = parsedJson.issues;
        }
        if (detectedAgentType && jsonVerdict) break;
      }
    } catch {}
  }

  const lines = reviewText.split(/\r?\n/);
  const prefixRegex = /^(?:[-*#\d.]+\s*)*(?:\*\*)?`?\[(must|should|imo|nits|ask|good)\]`?(?:\*\*)?[:\s]*(.*)$/i;

  const issues = [];
  const praises = [];

  const counts = {
    must: 0,
    should: 0,
    imo: 0,
    nits: 0,
    ask: 0,
    good: 0,
    blocking: 0,
    nonBlocking: 0,
    totalIssues: 0,
    totalPraises: 0,
  };

  let inLegendSection = false;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;

    if (line.match(/^(?:#+\s*)?(?:凡例|Legend|接頭辞ルール)/i)) {
      inLegendSection = true;
      continue;
    }

    if (inLegendSection && line.startsWith('#')) {
      inLegendSection = false;
    }

    if (inLegendSection) {
      continue;
    }

    const isLegendDefinition = /^[-*]\s*(?:\*\*)?`?\[(must|should|imo|nits|ask|good)\]`?(?:\*\*)?[:\s]*(?:マージ前に修正必須|強く推奨|私見・提案|些細な指摘|質問・確認|称賛・好ましい実装|修正必須|推奨)(?:[（(].*[）)])?\s*$/i.test(line);
    if (isLegendDefinition) {
      continue;
    }

    const match = line.match(prefixRegex);
    if (!match) continue;

    const rawType = match[1].toLowerCase();
    const description = match[2].trim();

    if (rawType === 'good') {
      praises.push({
        id: `praise-${praises.length + 1}`,
        type: 'good',
        description: description || 'Good implementation / practice',
      });
      counts.good++;
      counts.totalPraises++;
    } else {
      const issueItem = {
        id: `issue-${issues.length + 1}`,
        type: rawType,
        description: description || `Review issue (${rawType})`,
        resolved: false,
        resolvedCommit: null,
      };
      issues.push(issueItem);

      if (rawType === 'must' || rawType === 'should') {
        counts[rawType]++;
        counts.blocking++;
      } else {
        counts[rawType]++;
        counts.nonBlocking++;
      }
      counts.totalIssues++;
    }
  }

  // Fallback: If issues array was empty from lines, populate from JSON issues if present
  if (issues.length === 0 && Array.isArray(jsonIssues) && jsonIssues.length > 0) {
    for (const jIssue of jsonIssues) {
      const rawType = (jIssue.severity || jIssue.type || 'must').toLowerCase();
      const desc = jIssue.description || jIssue.title || 'Review issue';
      issues.push({
        id: `issue-${issues.length + 1}`,
        type: rawType,
        description: desc,
        resolved: false,
        resolvedCommit: null,
      });

      if (rawType === 'must' || rawType === 'should') {
        counts[rawType] = (counts[rawType] || 0) + 1;
        counts.blocking++;
      } else {
        counts[rawType] = (counts[rawType] || 0) + 1;
        counts.nonBlocking++;
      }
      counts.totalIssues++;
    }
  }

  let hasExplicitLgtm = false;
  let hasExplicitNeedsFix = false;

  if (jsonVerdict === 'LGTM') {
    hasExplicitLgtm = true;
  } else if (jsonVerdict === 'REQUEST_CHANGES' || jsonVerdict === 'NEEDS_FIX') {
    hasExplicitNeedsFix = true;
  } else {
    hasExplicitLgtm = /\[LGTM\]/i.test(reviewText) || /(?:^|\s)LGTM(?:\s|$)/i.test(reviewText);
    hasExplicitNeedsFix = /\[要修正\]/i.test(reviewText) || /(?:^|\s)要修正(?:\s|$)/i.test(reviewText) || /REQUEST_CHANGES/i.test(reviewText);
  }

  const isLgtm = !hasExplicitNeedsFix && counts.blocking === 0 && (hasExplicitLgtm || issues.length === 0);
  const verdict = isLgtm ? STATUS.RESOLVED_LGTM : STATUS.NEEDS_FIX;

  const result = {
    verdict,
    isLgtm,
    hasExplicitLgtm,
    hasExplicitNeedsFix,
    agentType: detectedAgentType,
    issues,
    praises,
    counts,
  };

  if (options.updateState) {
    if (options.stateUpdater) {
      const updatePayload = {
        lgtm: isLgtm,
        issues,
        ...(detectedAgentType ? { agentType: detectedAgentType } : {}),
      };
      result.updatedState = options.stateUpdater(updatePayload);
    } else if (detectedAgentType) {
      result.updatedState = recordReview(detectedAgentType, {
        verdict: isLgtm ? 'LGTM' : 'REQUEST_CHANGES',
        issues,
      });
    } else {
      result.updatedState = setReviewResult({
        lgtm: isLgtm,
        issues,
      });
    }
  }

  return result;
}

const isDirectExecution = process.argv[1] && 
  (fileURLToPath(import.meta.url).toLowerCase() === path.resolve(process.argv[1]).toLowerCase());

if (isDirectExecution) {
  const args = process.argv.slice(2);
  const updateStateFlag = args.includes('--update-state');
  
  let agentType = null;
  const agentTypeIdx = args.indexOf('--agent-type');
  if (agentTypeIdx !== -1 && args[agentTypeIdx + 1]) {
    agentType = args[agentTypeIdx + 1];
  }

  const nonFlagArgs = args.filter((a, idx) => {
    if (a === '--update-state' || a === '--agent-type') return false;
    if (idx > 0 && args[idx - 1] === '--agent-type') return false;
    return true;
  });

  const targetArg = nonFlagArgs[0];

  let text = '';
  if (targetArg) {
    if (fs.existsSync(targetArg) && fs.statSync(targetArg).isFile()) {
      text = fs.readFileSync(targetArg, 'utf8');
    } else {
      text = targetArg;
    }
  } else {
    try {
      text = fs.readFileSync(0, 'utf8');
    } catch {}
  }

  if (!text || text.trim().length === 0) {
    console.error('Usage: node parseReviewResult.js <reviewFileOrText> [--agent-type <type>] [--update-state]');
    process.exit(1);
  }

  const parsed = parseReviewResult(text, { updateState: updateStateFlag, agentType });
  console.log(JSON.stringify(parsed, null, 2));

  if (updateStateFlag) {
    const updatedStatus = parsed.updatedState?.status || parsed.verdict;
    console.log(`\n[OK] LoopState updated: status = ${updatedStatus}`);
  }

  process.exit(0);
}
