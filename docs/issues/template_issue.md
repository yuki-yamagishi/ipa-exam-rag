# Issue #<番号>: <簡潔な目的と対象>

## 1. 解決すべき課題・背景 (Problem Statement / Why)
- **現在の問題点**:
  - 誰が、あるいは何が困っているのか（表層の事象ではなく根本原因を記述）。
- **放置した場合のリスク**:
  - 保守性低下、デッドロック、セキュリティ脆弱性、CI見落とし、自己承認など。
- **なぜ今解く必要があるのか**:
  - 優先度および着手の根拠。

## 2. 期待される成果と価値 (Desired Outcome / Value)
- この Issue が完了したとき、システムはどうあるべきか。
- 単なる「コードの変更」ではなく、「得られる安全性・保守性・機能的価値」。

## 3. 排除するリスク (Risks to Eliminate)
- 本改修によって根絶・防御される具体的なリスクのリスト。
- 今回の変更によって生じる副作用・リグレッションリスクの封じ込め方針。

## 4. スコープの定義 (Scope & Boundaries)
- **スコープ内 (In-Scope)**:
  - 今回解決する中核課題。
  - 改修対象そのものに内在するバグ・ガードレールの穴の修正。
- **スコープ外 (Non-Goals)**:
  - 将来的な拡張機能、無関係な別モジュールの改修。

## 5. 受け入れ基準 (Acceptance Criteria / Definition of Done)

> ⚠️ **【重要】曖昧語の禁止**:
> 「適切に」「よしなに」「〇〇の改善」「必要に応じて」「など」といった解釈が分かれる曖昧な言葉は使用禁止。必ず客観的・定量的に判定可能な表現で記述すること。

### 5.1. 機能受け入れシナリオ (Feature-specific Acceptance Criteria: Given-When-Then)
- **シナリオ 1: <正常系シナリオ名称>**
  - **Given (前提)**: <前提条件や初期状態>
  - **When (操作・入力)**: <実行される操作や入力データ>
  - **Then (期待結果)**: <期待される出力、状態変化、または動作>
- **シナリオ 2: <境界値・異常系・拒絶シナリオ名称>**
  - **Given (前提)**: <不正入力や異常状態の前提>
  - **When (操作・入力)**: <境界値や異常値の入力>
  - **Then (期待結果)**: <エラーが安全にハンドリングされること、またはガードレールによって適切に拒絶されること>

### 5.2. PR作成前プロセス完了基準 (Pre-PR Process DoD)
- [ ] 上記 5.1 の全機能受け入れシナリオを検証する実質的な単体テストが存在し PASS すること。
- [ ] 排除対象のリスクに対する物理的ガードレール（Hook / 状態マシン）が機能していること。
- [ ] 重複・パッチワーク点検（Impact & Duplication Check）が pre_verification.md に完了・記録されていること。
- [ ] 4軸ドキュメント（issue, pre_verification, plan, walkthrough）が揃っていること。
- [ ] フル品質ゲート（npm.cmd run check）が 100% PASS すること。

### 5.3. マージ前完了ゲート (Pre-Merge Gate)
- [ ] GitHub Actions CI が PASS していること。
- [ ] 2者合議レビュー（fleet_reviewer ＋ fleet_completion_auditor）による客観的再レビューで両者 LGTM を受領すること。
- [ ] 人間（ユーザー）による最終確認とマージが完了していること。

## 6. 関連ドキュメント・仕様正本 (References & SSOT)
- 事前検証記録: docs/issues/ISSUE-XXX/pre_verification.md (template_pre_verification.md 準拠)
- 関連 ADR: ADR-XXXX
- 影響を受けるアーキテクチャ設計書: docs/architecture_overview.md
