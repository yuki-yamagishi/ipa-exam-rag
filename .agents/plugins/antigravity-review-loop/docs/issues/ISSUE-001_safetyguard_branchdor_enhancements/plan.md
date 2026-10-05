# ライフサイクルフック改修実装計画 (safetyGuard & branchDoRGate)

本計画は、ユーザーからの要望に基づき、以下の 2 つの品質ガバナンス機構を強化するための技術実装計画です：
1. **`safetyGuard.js`**: タイムアウト未指定のネットワークコマンド（`curl`）遮断フックの追加
2. **`branchDoRGate.js`**: ブランチ作成時の Definition of Ready（DoR）ゲートの強化

---

## 1. Why-First & 排除リスクの定義

### 1.1. safetyGuard.js への curl タイムアウト強制フック
- **Why (真の動機・背景)**:
  自律エージェントがタイムアウトを指定せずに `curl` を実行すると、サーバーの無応答や遅延によってプロセスが無期限にハング・長時間ブロックし、エージェントセッション全体が膠着・停止する。精神論で「タイムアウトを付けよう」とするのではなく、物理フックで未指定の実行を拒絶（deny）する。
- **Problem (現状の課題)**:
  `hooks/safetyGuard.js` は現在 `gh pr merge` の直接実行と対話型 `npm test` のみを遮断対象としており、ネットワークコマンド（`curl`）のタイムアウト漏れを防止する仕組みが存在しない。
- **Risks to Eliminate (排除すべきリスク)**:
  - ネットワーク遅延・サーバーダウン時のプロセスハングとセッション膠着。
  - 有効なオプション指定（`-m 10`, `--max-time=10`, `-m10`, `--connect-timeout 5` など）を誤判定して正当なコマンドを弾いてしまう偽陽性（False Positive）。
  - エージェントがなぜ拒絶されたか理解できず立ち往生すること（明確な Remediation Guidance を返すことで解消）。

### 1.2. branchDoRGate.js の強化
- **Why (真の動機・背景)**:
  「ローカルに `docs/issues/ISSUE-001/` フォルダが存在する」という表面的な条件だけでブランチ作成を許容してしまうと、GitHub 上で管理されていない勝手な Issue 番号や、まだ着手準備が整っていない（`status: backlog` など）Issue、テンプレートのまま放置された仕様書で実装に突入してしまうリスクがある。
- **Problem (現状の課題)**:
  現状の `branchDoRGate.js` はローカルディレクトリの存在とファイル内の特定見出しの有無を静的に走査しているが、リモートの GitHub Issue の状態確認や、テンプレートプレースホルダーの残存チェック、DoR 監査ログの確認などが不足している。
- **Risks to Eliminate (排除すべきリスク)**:
  - GitHub 上で管理されていない架空の Issue 番号での勝手なブランチ作成。
  - `status: ready` に達していない（未精査の）Issue を自律エージェントが勝手に着手・ブランチ作成する暴走。
  - テンプレートの見出しだけ残して中身が未記入のままブランチ作成をすり抜けること。

---

## 2. 提案変更点

### 2.1. hooks/safetyGuard.js
- `verifyCurlTimeoutSpecified(commandLine)` 関数を追加。
- 独立したフラグ境界を持つ正規表現でタイムアウト指定を検証。

### 2.2. hooks/branchDoRGate.js
- `verifyGitHubIssueStatus(exec, issueNum, projectRoot)` による GitHub Issue 状態・ラベル検証。
- `verifyNoTemplatePlaceholders` による実テンプレートプレースホルダー検知。
