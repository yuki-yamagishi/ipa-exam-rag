import test from 'node:test';
import assert from 'node:assert/strict';
import { renderMarkdownSync, escapeHtml } from './markdownPipeline.ts';

test('Scenario 1: GFM table converts to structured table with overflow wrapper and classes', () => {
  const markdown = `
| 項目 | APIのインターフェース | APIゲートウェイ |
|:---|:---|:---|
| **本質** | 仕様・規約 | 中間サーバ |
`;

  const html = renderMarkdownSync(markdown);

  // Verify container wrapper for mobile horizontal scrolling
  assert.ok(html.includes('overflow-x-auto'), 'Must include overflow-x-auto container for mobile scrolling');

  // Verify standard HTML table elements
  assert.ok(html.includes('<table'), 'Must include <table> tag');
  assert.ok(html.includes('<thead'), 'Must include <thead> tag');
  assert.ok(html.includes('<tbody'), 'Must include <tbody> tag');
  assert.ok(html.includes('<th'), 'Must include <th> tags');
  assert.ok(html.includes('<td'), 'Must include <td> tags');

  // Verify child styling classes (confirming table child traversal bug is fixed)
  assert.ok(html.includes('text-emerald-300'), 'Header cell must have text-emerald-300 styling class');
  assert.ok(html.includes('py-2.5') || html.includes('py-2'), 'Header or body cell must have vertical padding');
  assert.ok(html.includes('px-3'), 'Cells must have horizontal padding px-3');
  assert.ok(html.includes('text-slate-200'), 'Body cell must have text-slate-200 styling class');

  // Verify cell contents
  assert.ok(html.includes('APIのインターフェース'), 'Table header cell must be rendered');
  assert.ok(html.includes('中間サーバ'), 'Table body cell must be rendered');
});

test('Scenario 2: Headings, bold, inline code, lists, and <br> render as designated HTML elements', () => {
  const markdown = `
### 1. 概念の決定的な違い

**本質**: 仕様・規約
- REST APIのURL設計 (\`GET /users/{id}\`) <br> - JSONリクエスト
`;

  const html = renderMarkdownSync(markdown);

  // Verify heading h3
  assert.ok(html.includes('<h3'), 'Must render <h3> tag for ### heading');
  assert.ok(html.includes('1. 概念の決定的な違い'), 'Heading text must be preserved');

  // Verify bold strong
  assert.ok(html.includes('<strong'), 'Must render <strong> tag for bold text');
  assert.ok(html.includes('本質'), 'Bold text must be preserved');

  // Verify inline code
  assert.ok(html.includes('<code'), 'Must render <code> tag for backtick code');
  assert.ok(html.includes('GET /users/{id}'), 'Inline code text must be preserved');

  // Verify list
  assert.ok(html.includes('<ul') || html.includes('<ol'), 'Must render list tag');
  assert.ok(html.includes('<li'), 'Must render list item tag');

  // Verify <br> tag is parsed as break
  assert.ok(html.includes('<br'), 'Must render <br> tag instead of escaping as literal text');
});

test('Scenario 3: Mobile table wrapper prevents layout breaking with constrained container', () => {
  const markdown = `
| 項目 | 列A | 列B | 列C | 列D |
|:---|:---|:---|:---|:---|
| 値1 | A1 | B1 | C1 | D1 |
`;

  const html = renderMarkdownSync(markdown);

  // Verify container styling classes ensure full-width and responsive containment
  assert.ok(html.includes('overflow-x-auto'), 'Must contain overflow-x-auto');
  assert.ok(html.includes('rounded-xl'), 'Must contain rounded border container');
  assert.ok(html.includes('border-slate-700'), 'Must contain border styling');
});

test('Scenario 4: Streaming cursor renders when isStreaming is true and handles incomplete markdown safely', () => {
  const incompleteMarkdown = `### 概念の途中\n**太字が閉じられていない状態で`;

  // Streaming ON: cursor must be rendered
  const htmlStreaming = renderMarkdownSync(incompleteMarkdown, { isStreaming: true });

  assert.ok(htmlStreaming.includes('data-testid="streaming-cursor"'), 'Streaming cursor must be rendered');
  assert.ok(htmlStreaming.includes('animate-pulse'), 'Streaming cursor must have animate-pulse class');
  assert.ok(htmlStreaming.includes('太字が閉じられていない状態で'), 'Incomplete content must not throw and be displayed');

  // Streaming OFF: cursor must not be rendered
  const htmlDone = renderMarkdownSync(incompleteMarkdown, { isStreaming: false });

  assert.ok(!htmlDone.includes('data-testid="streaming-cursor"'), 'Streaming cursor must not be rendered when isStreaming=false');
});

test('Scenario 5: Malicious HTML and scripts are sanitized for XSS prevention', () => {
  const xssPayload = `
### 安全性テスト
<script>alert("XSS")</script>
<img src="x" onerror="alert(1)" />
<a href="javascript:alert(1)">クリック</a>
`;

  const html = renderMarkdownSync(xssPayload);

  // Script tags must NOT be rendered
  assert.ok(!html.includes('<script>'), '<script> tag must be removed');
  assert.ok(!html.includes('onerror='), 'onerror attribute must be removed');
  assert.ok(!html.includes('href="javascript:'), 'javascript: href must be sanitized');
});

test('Scenario 6: Real-world IPA explanation markdown with tables, inline code, and breaks', () => {
  const realMarkdown = `
---

### 1. 概念の決定的な違い

| 項目 | APIのインターフェース (Interface) | APIゲートウェイ (API Gateway) |
|:---|:---|:---|
| **本質** | **「仕様・規約・接点」** (抽象概念) | **「中間サーバ・コンポーネント」** (実体・設計パターン) |
| **役割** | 呼び出し側と提供側が「どんな形式でデータをやり取りするか」を定義する（契約/Contract）。 | クライアントと複数のバックエンドサービスの間に入り、**リクエストの中継や共通処理を行う「単一の入り口」**。 |
| **具体例** | ・REST APIのURL設計 (\`GET /users/{id}\`) <br> ・JSONリクエスト/レスポンスのスキーマ | ・Amazon API Gateway<br>・Kong, Apigee, Envoy |
| **たとえ話** | レストランの**「メニュー表・注文票の書き方」** | レストランの**「受付係・ウェイター・レジ」** |

---

### 2. なぜ混同しやすいのか？
どちらも「アプリの境界」に関係する言葉
`;

  const html = renderMarkdownSync(realMarkdown);

  // Table must be wrapped in overflow container
  assert.ok(html.includes('overflow-x-auto'), 'Table must be horizontally scrollable on mobile');
  assert.ok(html.includes('<table'), 'Must have <table>');
  assert.ok(html.includes('<hr'), 'Must have horizontal rules <hr>');
  assert.ok(html.includes('<h3'), 'Must have headings');
  assert.ok(html.includes('<strong'), 'Must have strong elements');
  assert.ok(html.includes('<code'), 'Must have code elements');
  assert.ok(html.includes('<br>'), 'Must have <br> elements for line breaks in cells');
  assert.ok(html.includes('APIゲートウェイ (API Gateway)'), 'Header text rendered');
  assert.ok(html.includes('GET /users/{id}'), 'Code text rendered');
});

test('Scenario 7: Fallback on parsing error safely escapes HTML to prevent XSS', () => {
  const malicious = '<script>alert("fallback-xss")</script>&"\'';
  const escaped = escapeHtml(malicious);

  assert.ok(!escaped.includes('<script>'), '<script> tag must be escaped');
  assert.ok(escaped.includes('&lt;script&gt;'), 'Brackets must be converted to &lt; and &gt;');
  assert.ok(escaped.includes('&amp;'), '& must be converted to &amp;');
  assert.ok(escaped.includes('&quot;'), '" must be converted to &quot;');
  assert.ok(escaped.includes('&#039;'), "' must be converted to &#039;");
});

test('Scenario 8: Escaped markdown characters and code blocks with raw HTML preserve text and do not corrupt layout', () => {
  const markdownWithEscapes = `
### エスケープ文字の検証

- \\*アスタリスクは強調にならない\\*
- \\[角括弧もリンク構文にならない\\]
- パイプ記号のエスケープ: \\| はテーブル境界と誤認されない

\`\`\`html
<!-- コードブロック内の HTML タグはサニタイズで消されず保全されること -->
<div class="test-container" onclick="evil()">
  <span id="label">Safe Content</span>
</div>
\`\`\`

\`\`\`json
{
  "escaped_quote": "value with \\"quotes\\" and \\n newlines",
  "windows_path": "C:\\\\Users\\\\test\\\\file.txt"
}
\`\`\`
`;

  const html = renderMarkdownSync(markdownWithEscapes);

  // Escaped markdown must render literal symbols, not bold or link tags
  assert.ok(!html.includes('<strong>アスタリスクは強調にならない</strong>'), 'Escaped * must not become strong');
  assert.ok(html.includes('*アスタリスクは強調にならない*'), 'Literal * must be preserved in text');
  assert.ok(html.includes('[角括弧もリンク構文にならない]'), 'Literal [ ] must be preserved in text');

  // Code block must preserve HTML tags literally without stripping them or executing them
  assert.ok(html.includes('&#x3C;div class="test-container"') || html.includes('&lt;div class="test-container"'), 'Code block HTML tags must be properly encoded and preserved');
  assert.ok(html.includes('Safe Content'), 'Code block text content preserved');
  assert.ok(!html.includes('<div class="test-container" onclick'), 'Raw unescaped onclick attribute must not be injected into DOM');

  // Code block with JSON escape characters
  assert.ok(html.includes('"value with \\"quotes\\" and \\n newlines"'), 'Escaped JSON strings must be preserved');
  assert.ok(html.includes('C:\\\\Users\\\\test\\\\file.txt'), 'Windows backslash path must be preserved');
});

test('Scenario 9: Multiple consecutive code blocks and extremely long lines maintain responsive layout', () => {
  const extremelyLongLine = 'SELECT id, user_name, email_address, hashed_password_token_salt, created_at, updated_at, last_login_ip, user_preferences_json_payload FROM users_master_partitioned_table WHERE company_tenant_id = 999999999 AND is_active_status = true AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 500;';

  const multiCodeBlocks = `
\`\`\`python
def calculate_metrics(data: list[int]) -> dict[str, float]:
    return {"mean": sum(data) / len(data)}
\`\`\`

\`\`\`sql
${extremelyLongLine}
\`\`\`

\`\`\`bash
curl -X POST https://api.example.com/v1/auth -H "Authorization: Bearer test_token_string" -d '{"grant_type": "password"}'
\`\`\`
`;

  const html = renderMarkdownSync(multiCodeBlocks);

  // Must contain multiple pre blocks
  const preMatches = html.match(/<pre/g);
  assert.equal(preMatches?.length, 3, 'Must render exactly 3 consecutive <pre> code blocks');

  // All pre blocks must have overflow-x-auto and containment classes to prevent layout breaking
  assert.ok(html.includes('overflow-x-auto'), 'Pre blocks must have overflow-x-auto');
  assert.ok(html.includes('max-w-full'), 'Pre blocks must have max-w-full to prevent flex expansion');
  assert.ok(html.includes('bg-slate-950'), 'Pre blocks must have bg-slate-950');

  // Long line must be contained inside pre code block
  assert.ok(html.includes('users_master_partitioned_table'), 'Long SQL statement must be rendered inside code block');
});

test('Scenario 10: Nested multi-backtick code fences (e.g. 4 backticks containing 3 backticks) parse safely', () => {
  const nestedFences = `
\`\`\`\`markdown
Here is an example markdown snippet:

\`\`\`python
def hello():
    print("nested code block")
\`\`\`
\`\`\`\`
`;

  const html = renderMarkdownSync(nestedFences);

  assert.ok(html.includes('<pre'), 'Must render pre block for outer fence');
  assert.ok(html.includes('```python'), 'Inner triple backticks must be preserved as text inside the outer block');
  assert.ok(html.includes('nested code block'), 'Inner content must be preserved');
});


