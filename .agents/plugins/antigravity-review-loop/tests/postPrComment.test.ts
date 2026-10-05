import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { postPrComment } from '../skills/review-self-healing/scripts/postPrComment.js';

describe('postPrComment', () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'post-pr-test-'));
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

  it('throws error for invalid PR numbers', () => {
    expect(() => postPrComment(0, 'Test body')).toThrow('Invalid PR number');
    expect(() => postPrComment(-5, 'Test body')).toThrow('Invalid PR number');
    expect(() => postPrComment('abc', 'Test body')).toThrow('Invalid PR number');
    expect(() => postPrComment(12.34, 'Test body')).toThrow('Invalid PR number');
  });

  it('throws error for empty comment bodies', () => {
    expect(() => postPrComment(10, '')).toThrow('Comment body cannot be empty');
    expect(() => postPrComment(10, '   \n  \t  ')).toThrow('Comment body cannot be empty');
    // @ts-expect-error invalid input test
    expect(() => postPrComment(10, null)).toThrow('Comment body cannot be empty');
  });

  it('writes comment to temp file, executes gh command with --body-file, and cleans up temp file', () => {
    let capturedCommand = '';
    let capturedArgs: string[] = [];
    let fileExistedDuringExec = false;
    let fileContentDuringExec = '';
    let capturedTempFile = '';

    const mockExec = vi.fn((cmd: string, args: string[]) => {
      capturedCommand = cmd;
      capturedArgs = args;
      const bodyFileIndex = args.indexOf('--body-file');
      if (bodyFileIndex !== -1 && args[bodyFileIndex + 1]) {
        capturedTempFile = args[bodyFileIndex + 1];
        fileExistedDuringExec = fs.existsSync(capturedTempFile);
        if (fileExistedDuringExec) {
          fileContentDuringExec = fs.readFileSync(capturedTempFile, 'utf8');
        }
      }
      return 'https://github.com/org/repo/pull/47#issuecomment-12345';
    });

    const markdownBody = '# Review Title\n\n- [good] Excellent architecture!\n- [nits] Minor formatting';

    const result = postPrComment(47, markdownBody, {
      execFn: mockExec,
      tmpDir: tempDir,
    });

    expect(result.success).toBe(true);
    expect(result.prNumber).toBe(47);
    expect(result.output).toBe('https://github.com/org/repo/pull/47#issuecomment-12345');

    // Exec was called with expected binary and arguments
    expect(capturedCommand).toBe('gh');
    expect(capturedArgs).toEqual(['pr', 'comment', '47', '--body-file', capturedTempFile]);

    // Temp file existed during exec with exact UTF-8 content
    expect(fileExistedDuringExec).toBe(true);
    expect(fileContentDuringExec).toBe(markdownBody);

    // Temp file was deleted after execution
    expect(fs.existsSync(capturedTempFile)).toBe(false);
  });

  it('ensures temp file cleanup even if gh command execution fails', () => {
    let capturedTempFile = '';

    const mockExec = vi.fn((_cmd: string, args: string[]) => {
      const bodyFileIndex = args.indexOf('--body-file');
      if (bodyFileIndex !== -1 && args[bodyFileIndex + 1]) {
        capturedTempFile = args[bodyFileIndex + 1];
      }
      throw new Error('gh command failed: network timeout');
    });

    expect(() => {
      postPrComment(47, 'Failure test comment', {
        execFn: mockExec,
        tmpDir: tempDir,
      });
    }).toThrow('gh command failed: network timeout');

    // Temp file should be removed in finally block
    expect(capturedTempFile).toBeTruthy();
    expect(fs.existsSync(capturedTempFile)).toBe(false);
  });
});
