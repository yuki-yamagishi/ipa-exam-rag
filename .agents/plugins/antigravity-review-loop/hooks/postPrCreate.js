/**
 * Post PR Create Hook (.agents/hooks/postPrCreate.js)
 * 
 * Intercepts PostToolUse for run_command.
 * Automatically transitions loop state to PR_CREATED when gh pr create succeeds.
 */

import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { defaultStateMachine } from '../state/loopState.js';
import { readStdinJson, writeStdoutJson } from './hookUtils.js';

export function handlePostPrCreate(payload = {}, stateMachine = defaultStateMachine) {
  if (payload.error) {
    return {};
  }

  const toolCall = payload.toolCall || {};
  const toolName = toolCall.name || '';
  const args = toolCall.args || {};
  const commandLine = args.CommandLine || '';

  if (toolName === 'run_command' && /\bgh\s+pr\s+create\b/i.test(commandLine)) {
    try {
      let prNumber = null;

      // 1. Try extracting PR number from tool execution result if present
      const rawOutput = String(payload.result || payload.output || payload.toolResult || '');
      const urlMatch = rawOutput.match(/\/pull\/(\d+)/i);
      if (urlMatch) {
        prNumber = parseInt(urlMatch[1], 10);
      }

      // 2. Try gh CLI query
      if (!prNumber) {
        try {
          const output = execSync('gh pr view --json number -q .number', {
            encoding: 'utf8',
            stdio: ['ignore', 'pipe', 'ignore'],
            timeout: 5000,
          });
          const parsed = parseInt(output.trim(), 10);
          if (!isNaN(parsed) && parsed > 0) {
            prNumber = parsed;
          }
        } catch {}
      }

      // 3. Try git branch name or CI environment variables
      if (!prNumber) {
        try {
          const branchRef = process.env.GITHUB_HEAD_REF || 
            process.env.GITHUB_REF_NAME || 
            execSync('git branch --show-current', {
              encoding: 'utf8',
              stdio: ['ignore', 'pipe', 'ignore'],
            });
          const match = branchRef.match(/(?:pull\/|pr[/-])(\d+)/i);
          if (match) {
            prNumber = parseInt(match[1], 10);
          }
        } catch {}
      }

      // 4. Safe fallback
      if (!prNumber || isNaN(prNumber) || prNumber <= 0) {
        prNumber = 1;
      }

      stateMachine.setPrCreated(prNumber);
    } catch {}
  }

  return {};
}

const isDirectExecution = process.argv[1] && 
  (fileURLToPath(import.meta.url).toLowerCase() === path.resolve(process.argv[1]).toLowerCase());

if (isDirectExecution) {
  readStdinJson().then((payload) => {
    const result = handlePostPrCreate(payload);
    writeStdoutJson(result);
    process.exit(0);
  });
}
