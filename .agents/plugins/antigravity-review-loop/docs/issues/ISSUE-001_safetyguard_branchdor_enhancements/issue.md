# Issue #1: safetyGuard curl タイムアウト遮断フックの追加および branchDoRGate の強化

## 1. 解決すべき課題・背景 (Why)
自律エージェントがタイムアウトを設定せずに `curl` コマンドを実行した場合、接続先サーバーの遅延や無応答によりプロセスが永久ハングまたは長時間ブロックされ、エージェントセッション全体が膠着するリスクがある。
また、ブランチ作成時の DoR ゲート（`branchDoRGate.js`）において、ローカルフォルダの存在のみに頼っていると、GitHub 上で管理されていない架空の Issue や、着手準備（Definition of Ready）が未完了の Issue、およびテンプレートの未記入プレースホルダーが残ったままの実装見切り発車を防止できない。

## 2. 変更内容の概要 (What)
1. `hooks/safetyGuard.js`: タイムアウト未指定の `curl` コマンド（`-m`, `--max-time`, `--connect-timeout` 未指定）を物理拒絶する `verifyCurlTimeoutSpecified` フックを追加。
2. `hooks/branchDoRGate.js`: GitHub Issue の実在性・ステータス（OPEN）・DoR ラベル（`status: ready` / `status: in-progress`）の検証、および仕様書テンプレートの未記入プレースホルダー検知を追加。
3. ドキュメント（README.md, skills/issue-lifecycle/SKILL.md）の同期とテスト拡充（124テスト合格）。

## 3. 排除するリスク (Risks to Eliminate)
- タイムアウト未指定のネットワークアクセスによるプロセスハングおよびセッション膠着。
- URL や出力ファイル名に `-m` 文字列が含まれる場合のタイムアウト判定誤認（すり抜け）。
- GitHub 上で管理されていない架空の Issue 番号での勝手なブランチ作成。
- `status: ready` に達していない Issue での実装見切り発車。
- 仕様書テンプレートのプレースホルダーを残したままの実装突入。

## 4. 設計方針
- `hooks/safetyGuard.js` において、コマンドライン先頭の実行コマンドとしての curl 呼び出しのみを正確に補足し、引数内の curl（`git commit -m "curl"` 等）に対する偽陽性を防止する。
- `hooks/branchDoRGate.js` において、`gh issue view` によるリモート状態監査とローカルファイルのプレースホルダー監査の多層防御を構築する。

## 5. 受け入れ基準 (Acceptance Criteria / DoD)

### 5.1. 機能受け入れシナリオ (Given-When-Then)
- **シナリオ 1: タイムアウト未指定 curl の遮断**
  - **Given**: 自律エージェントが `run_command` を呼び出す。
  - **When**: タイムアウトフラグのない `curl https://api.example.com` を実行しようとする。
  - **Then**: `safetyGuard.js` により `deny` され、タイムアウト指定を促すエラーが返る。
- **シナリオ 2: タイムアウト指定 curl の許可**
  - **Given**: 自律エージェントが `run_command` を呼び出す。
  - **When**: `curl -m 10 https://api.example.com` や `curl --max-time 15 ...` を実行する。
  - **Then**: `safetyGuard.js` により `allow` される。
- **シナリオ 3: DoR 未達成ブランチ作成の拒絶**
  - **Given**: GitHub Issue に `status: ready` または `status: in-progress` ラベルが付与されていない。
  - **When**: `git checkout -b feature/issue-1-...` を実行しようとする。
  - **Then**: `branchDoRGate.js` により `deny` される。
- **シナリオ 4: 未記入プレースホルダー検知**
  - **Given**: `issue.md` に未記入のテンプレート文字列が残っている。
  - **When**: `git checkout -b feature/issue-1-...` を実行しようとする。
  - **Then**: `branchDoRGate.js` により `deny` される。

### 5.2. PR作成前プロセス完了基準 (Pre-PR Process DoD)
- [x] Fast TDD による単体テスト通過
- [x] 全 124 件のテストが 100% 合格
- [x] 第三者サブエージェント合議レビュー（Code Reviewer & Completion Auditor）LGTM 受領

### 5.3. マージ前完了ゲート (Pre-Merge Gate)
- [ ] CI パス
- [ ] ユーザーによる最終マージ承認
