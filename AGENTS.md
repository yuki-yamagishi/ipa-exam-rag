# IPA Exam RAG エージェント憲章 (AGENTS.md)

IPA Exam RAG は、**情報処理技術者試験（基本情報・応用情報・高度試験）の過去問・シラバス・解説を対象とした高精度な Retrieval-Augmented Generation (RAG) システム** です。
本憲章は、AI エージェントが開発時に厳格に遵守すべき **「コア原則・不可侵規約・完了定義 (DoD)」** を定めます。

> 📖 **詳細実践ガイド**:
> 開発フェーズに応じた詳細な実践手順書は、Customization Layer のプラグインスキル群（`.agents/plugins/antigravity-review-loop/skills/issue-lifecycle/`, `.agents/plugins/antigravity-review-loop/skills/dev-lifecycle/`, `.agents/plugins/antigravity-review-loop/skills/review-self-healing/`）に Progressive Disclosure（段階的開示）としてカプセル化・集約されています。作業フェーズに合わせて各スキルを参照してください。

---

## 1. アーキテクチャ原則 & 仕様 SSOT

1. **クリーンアーキテクチャ & レイヤード設計の徹底**:
   - コアドメイン（試験問題データモデル、検索エンジン抽象、RAGパイプライン）は UI や外部フレームワークから完全に分離し、高カバレッジで単体テスト可能とすること。
2. **仕様正本 (Single Source of Truth: SSOT) の遵守**:
   - システム仕様および ADR の統合正本は **`docs/architecture_overview.md`** および **`docs/adr/`** です。
   - すべての Issue は **`docs/issues/`** 配下に 4 ファイル完結（`issue.md`, `pre_verification.md`, `plan.md`, `walkthrough.md`）で記録・保全すること。
   - ブランチ作成前には `issue.md`（Why・排除リスク・Given-When-Then受入シナリオ）と `pre_verification.md`（重複点検）を完備し、`fleet_dor_auditor` による DoR 監査を受領すること（プラグインフック `branchDoRGate` により物理強制）。
3. **純粋プラグイン設計原則 (Pure Plugin Architecture & Zero Pollution)**:
   - プロジェクトルート直下や `.agents/` 直下にエージェント管理用・開発支援用のスクリプト、スキル、フックを平置きすることを厳禁とする（リポジトリ非汚染の徹底）。
   - 今後、アプリ開発用や運用自動化のための Skill や Hook が必要になった場合は、**必ず `.agents/plugins/<plugin-name>/` 配下の独立した Plugin（公式仕様: `plugin.json`, `hooks.json`, `skills/`, `rules/`）として設計・カプセル化すること**。
   - すべてのエージェント拡張機能は、単一プラグインとして自己完結させ、他プロジェクトへの可搬性（Portability）と非侵食性を維持すること。

---

## 2. コンテキストドリフト & 仕様破壊の絶対防止ルール

1. **既存テストの弱体化・削除の厳禁**:
   - テストが失敗した際、テストの期待値やアサーションを安易に書き換えて合格させてはならない。仕様変更時は ADR の更新とユーザー合意が必須。
2. **ADR（設計決定記録）の遵守**:
   - 実装前に `docs/adr/` 配下のレコードを確認し、過去の設計決定と矛盾するコードを書いてはならない。
3. **完全日本語標準化 (内外分離: Boundary Design)**:
   - `docs/` 配下のすべての設計書・ADR・Issue・レポート、および PR 本文・チャット報告は完全日本語で記述・更新すること（人間向け意思決定レイヤー）。
   - 一方で、エージェント自身の内部統制（Hooks の判定メッセージ、ステートマシンのエラー、Remediation Guidance）は、トークン消費量を削減し指示追従性を最大化するため、英語を標準とする（機械向け制御レイヤー）。
4. **単一コマンド実行規約 (Single Command Execution)**:
   - シェルコマンド実行ツール（`run_command` 等）において、PowerShell のセミコロン（`;`）、`&&`、パイプ（`|`）による複数コマンド連結を厳禁とする。

---

## 3. ガバナンス & ループ完了定義 (Definition of Done: DoD)

1. **Conventional Commits 規約**:
   - すべてのコミットは Conventional Commits（`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`, `ci:`）に厳格に準拠すること。
2. **プラグインによる物理ライフサイクルガードの遵守**:
   - プラグイン（`.agents/plugins/antigravity-review-loop`）が提供するライフサイクルフック群が、エージェントの全アクションを自動監視・物理ブロックする：
     - `branchDoRGate.js`: ブランチ作成前の DoR（Why、排除リスク、受入シナリオ）完備を物理強制。
     - `safetyGuard.js`: エージェントによる `gh pr merge` の直接実行を物理遮断。
     - `prePrAuditGate.js`: PR作成前の 4軸ドキュメント・ADR同期・DoD完了を物理検証。
     - `stopHook.js`: レビューループ完了前のセッション早期終了を物理ブロック。
3. **PR 作成後の自動マージ厳禁**:
   - PR 発行直後の自動マージは厳禁。PR は必ず OPEN 状態を維持すること。
4. **2者 Fleet 並行合議レビューの必須受領**:
   - PR 発行後、思考コンテキストを切り離した独立サブエージェント 2 体（`fleet_reviewer` と `fleet_completion_auditor`）を並行起動し、コード品質（How）と批判的完了性（Why / What）の両面から客観的レビューを受領して合議（両者 LGTM）を成立させること。
   - 完了性監査は反例提示義務（Counterexample Obligation）およびゴールポスト移動禁止を遵守し、具体的な破綻シナリオがない言いがかり・過剰攻撃によるマージブロックを厳禁とする。
5. **ループエンジニアリング完了定義 (DoD) & 早期停止ガード**:
   - ループ状態マシン（`loopState`）により、PR 作成後の早期停止・会話終了は物理的にブロックされる。
   - レビュー指摘の修正後、解決報告ツール `resolveReview` を実行し、さらに Fleet の再レビュー（Re-review）を受領して状態を `RESOLVED_LGTM` に収束させること（自己承認は物理禁止）。
6. **人間（ユーザー）によるマージ**:
   - 全指摘解消後、ユーザーに報告してマージを依頼し、承認・マージ完了をもって作業を完了とすること（エージェントによる `gh pr merge` の直接実行はフックにより禁止）。
