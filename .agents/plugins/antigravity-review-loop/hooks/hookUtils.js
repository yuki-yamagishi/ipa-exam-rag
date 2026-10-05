/**
 * Hook Utilities (.agents/plugins/antigravity-review-loop/hooks/hookUtils.js)
 * Helper functions for stdin/stdout JSON protocol in Antigravity lifecycle hooks.
 */

import fs from 'fs';
import path from 'path';

export async function readStdinJson(timeoutMs = 2000) {
  return new Promise((resolve) => {
    let raw = '';
    let resolved = false;

    const timer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        resolve({});
      }
    }, timeoutMs);
    if (timer.unref) timer.unref();

    process.stdin.setEncoding('utf8');

    process.stdin.on('data', (chunk) => {
      raw += chunk;
    });

    process.stdin.on('end', () => {
      if (!resolved) {
        resolved = true;
        clearTimeout(timer);
        try {
          const trimmed = raw.trim();
          resolve(trimmed ? JSON.parse(trimmed) : {});
        } catch {
          resolve({});
        }
      }
    });

    process.stdin.on('error', () => {
      if (!resolved) {
        resolved = true;
        clearTimeout(timer);
        resolve({});
      }
    });
  });
}

export function writeStdoutJson(data) {
  process.stdout.write(JSON.stringify(data, null, 2) + '\n');
}

/**
 * Searches upward from startDir to find the project root directory
 * identified by package.json and .git directory.
 */
export function findProjectRoot(startDir) {
  let cur = path.resolve(startDir);
  while (cur && path.dirname(cur) !== cur) {
    if (path.basename(cur) === '.agents' || cur.split(path.sep).includes('.agents')) {
      cur = path.dirname(cur);
      continue;
    }
    if (fs.existsSync(path.join(cur, 'package.json')) && fs.existsSync(path.join(cur, '.git'))) {
      return cur;
    }
    cur = path.dirname(cur);
  }
  return path.resolve(startDir, '../../../..');
}
