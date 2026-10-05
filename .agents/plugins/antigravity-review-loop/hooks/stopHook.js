/**
 * Stop Hook Handler (.agents/hooks/stopHook.js)
 * 
 * Intercepts agent Stop event.
 * Rejects stop with {"decision": "continue", "reason": "..."} if self-healing loop
 * has not yet reached RESOLVED_LGTM.
 * Supports Antigravity official payload.fullyIdle === false to allow Reactive Wakeup waiting.
 */

import path from 'path';
import { fileURLToPath } from 'url';
import { defaultStateMachine } from '../state/loopState.js';
import { readStdinJson, writeStdoutJson } from './hookUtils.js';

export function detectSubagentContext(payload = {}) {
  if (payload.isSubagent === true || payload.subagent === true) return true;
  if (typeof payload.role === 'string' && /\b(reviewer|fleet|subagent)\b/i.test(payload.role)) return true;
  if (typeof payload.agentRole === 'string' && /\b(reviewer|fleet|subagent)\b/i.test(payload.agentRole)) return true;
  if (typeof payload.agentType === 'string' && /\b(reviewer|fleet|subagent)\b/i.test(payload.agentType)) return true;
  if (payload.conversationType === 'subagent') return true;
  if (payload.parentConversationId || payload.parentId) return true;

  if (process.env.ANTIGRAVITY_SUBAGENT === 'true' || process.env.IS_SUBAGENT === 'true') return true;
  if (process.env.SUBAGENT_ROLE || process.env.AGENT_ROLE) {
    const envRole = process.env.SUBAGENT_ROLE || process.env.AGENT_ROLE || '';
    if (/\b(reviewer|fleet|subagent)\b/i.test(envRole)) return true;
  }

  try {
    const cwd = process.cwd();
    if (/[\\/]agents[\\/]fleet_reviewer/i.test(cwd) || /[\\/]fleet[-_]reviewer/i.test(cwd)) return true;
  } catch {}

  return false;
}

export function detectActiveSubagents(payload = {}, stateMachine = defaultStateMachine) {
  // Official Antigravity payload: fullyIdle is false when background tasks or subagents are running
  if (payload.fullyIdle === false) return true;

  if (payload.hasActiveSubagents === true || payload.activeSubagents === true) return true;
  if (typeof payload.activeSubagents === 'number' && payload.activeSubagents > 0) return true;
  if (Array.isArray(payload.activeSubagents) && payload.activeSubagents.length > 0) return true;
  if (Array.isArray(payload.subagents) && payload.subagents.length > 0) return true;
  if (Array.isArray(payload.active_subagents) && payload.active_subagents.length > 0) return true;
  if (typeof payload.active_subagents === 'number' && payload.active_subagents > 0) return true;
  if (payload.waitingForSubagent === true) return true;

  if (process.env.ACTIVE_SUBAGENTS === 'true') return true;

  try {
    const state = stateMachine.getState();
    if (state.activeSubagents === true) return true;
  } catch {}

  return false;
}

export function handleStop(payload = {}, stateMachine = defaultStateMachine) {
  const isSubagent = detectSubagentContext(payload);
  const hasActiveSubagents = detectActiveSubagents(payload, stateMachine);

  const check = stateMachine.canStop({
    hasActiveSubagents,
    isSubagent,
  });

  if (!check.allowed) {
    return {
      decision: 'continue',
      reason: check.reason,
    };
  }

  return {
    decision: 'allow',
    reason: check.reason,
  };
}

const isDirectExecution = process.argv[1] && 
  (fileURLToPath(import.meta.url).toLowerCase() === path.resolve(process.argv[1]).toLowerCase());

if (isDirectExecution) {
  readStdinJson().then((payload) => {
    const result = handleStop(payload);
    writeStdoutJson(result);
    process.exit(0);
  });
}
