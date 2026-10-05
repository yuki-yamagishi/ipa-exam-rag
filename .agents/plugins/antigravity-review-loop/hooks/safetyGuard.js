/**
 * Safety Guard Hook (.agents/hooks/safetyGuard.js)
 * 
 * Enforces execution safety:
 * 1. Prohibits direct gh pr merge by the agent (merging is exclusively performed by human).
 * 2. Prohibits interactive watch tests.
 * 3. Prohibits network commands (curl) without explicit timeout to prevent process hangs.
 */

import path from 'path';
import { fileURLToPath } from 'url';
import { readStdinJson, writeStdoutJson } from './hookUtils.js';

/**
 * Validates that gh pr merge is not executed directly by autonomous agents.
 */
function verifyGhPrMergeProhibited(commandLine) {
  if (/\bgh\s+pr\s+merge\b/i.test(commandLine)) {
    return {
      decision: 'deny',
      reason: "[SafetyGuard Denied] Direct execution of 'gh pr merge' by the autonomous agent is strictly prohibited. Merging to main is exclusively performed by the user (human). Please request the user to review and merge the PR.",
    };
  }
  return { decision: 'allow' };
}

/**
 * Validates that interactive watch tests causing process hang are not executed.
 */
function verifyNonInteractiveTestExecution(commandLine) {
  if (/\bnpm(?:\.cmd)?\s+(?:run\s+)?test\b/i.test(commandLine) && 
      !/--run\b/i.test(commandLine) && 
      !/\btest:(?:run|coverage|fast|related)\b/i.test(commandLine)) {
    return {
      decision: 'deny',
      reason: "[SafetyGuard Denied] Interactive test runner detected. Use 'npm run test:fast', 'npm run test:related', or 'npm run test:run' for deterministic execution.",
    };
  }
  return { decision: 'allow' };
}

/**
 * Validates that network command 'curl' is executed with an explicit timeout.
 */
function verifyCurlTimeoutSpecified(commandLine) {
  // Only match when curl or curl.exe is invoked as the command (not as an argument to git, echo, etc.)
  if (/^\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*(?:sudo\s+)?curl(?:\.exe)?\b/i.test(commandLine)) {
    const hasTimeout = /(?:(?:^|\s)-m\s*\d+(?:\.\d+)?|(?:^|\s)(?:--max-time|--connect-timeout)(?:=|\s+)\d+(?:\.\d+)?)/i.test(commandLine);
    if (!hasTimeout) {
      return {
        decision: 'deny',
        reason: "[SafetyGuard Denied] Network command 'curl' executed without timeout. Specify a timeout using '--max-time <seconds>' or '-m <seconds>' (e.g. 'curl --max-time 10 ...') to prevent process hangs.",
      };
    }
  }
  return { decision: 'allow' };
}

export function handleSafetyGuard(payload = {}) {
  const toolCall = payload.toolCall || {};
  const toolName = toolCall.name || '';
  const args = toolCall.args || {};
  const commandLine = args.CommandLine || '';

  if (toolName !== 'run_command' || !commandLine) {
    return { decision: 'allow' };
  }

  const trimmed = commandLine.trim();

  // Safety verification pipeline
  const checks = [
    () => verifyGhPrMergeProhibited(trimmed),
    () => verifyNonInteractiveTestExecution(trimmed),
    () => verifyCurlTimeoutSpecified(trimmed),
  ];

  for (const check of checks) {
    const result = check();
    if (result.decision === 'deny') {
      return result;
    }
  }

  return { decision: 'allow' };
}

const isDirectExecution = process.argv[1] && 
  (fileURLToPath(import.meta.url).toLowerCase() === path.resolve(process.argv[1]).toLowerCase());

if (isDirectExecution) {
  readStdinJson().then((payload) => {
    const result = handleSafetyGuard(payload);
    writeStdoutJson(result);
    process.exit(0);
  });
}
