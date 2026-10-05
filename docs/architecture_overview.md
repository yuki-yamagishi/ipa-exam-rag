# IPA Exam RAG システム基本設計書 (SSOT)

本ドキュメントは、IPA Exam RAG（情報処理技術者試験 RAG システム）の全体アーキテクチャ、設計原則、およびコンポーネント構成を定義する **仕様正本 (Single Source of Truth: SSOT)** です。

---

## 1. システム概要と目的

IPA Exam RAG は、情報処理推進機構（IPA）が主催する各種情報処理技術者試験（基本情報技術者、応用情報技術者、各種高度情報処理技術者試験）の過去問題、公式シラバス、解説講評を統合し、高精度な文脈検索と回答生成・学習支援を提供する RAG（Retrieval-Augmented Generation）システムです。

### 主なターゲットユースケース
1. **過去問類似検索 & 関連知識解説**:
   - ユーザーからの質問や出題文に対し、関連する過去問題（午前・午後）およびシラバス項目をピンポイントで検索・提示。
2. **根拠付き解答生成**:
   - IPA 公式のシラバス・採点講評をグラウンディングソースとし、ハルシネーション（虚偽回答）を排除した確実な解説を提供。
3. **出題傾向分析**:
   - テクノロジ系・マネジメント系・ストラテジ系のカテゴリ別出題トレンドや重点キーワードの抽出。

---

## 2. コアアーキテクチャ

システムは関心の分離（SoC）と高テスト容易性を担保するため、クリーンアーキテクチャのレイヤード構造を採用します。

```text
┌────────────────────────────────────────────────────────┐
│                   Presentation Layer                   │
│         (CLI / Web UI / API Endpoints)                 │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                   Application Layer                    │
│   (RAG Orchestrator / Question Answerer / Evaluator)   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                      Domain Layer                      │
│ (ExamQuestion / SyllabusItem / RetrievalContext / ...) │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                  Infrastructure Layer                  │
│ (Vector Store / Document Loader / LLM Provider / Cache)│
└────────────────────────────────────────────────────────┘
```

---

## 3. ガバナンス・開発プロセス統合

本システムは、[`antigravity-review-loop`](../.agents/plugins/antigravity-review-loop/) による完全な自律レビューループと品質ゲートのもとで進化します。
- すべての機能追加・改修は `docs/issues/` 配下の 4 軸ドキュメント（`issue.md`, `pre_verification.md`, `plan.md`, `walkthrough.md`）で設計・追跡されます。
- 設計決定は `docs/adr/` 配下に不可逆記録され、アーキテクチャのドリフトを防止します。
  - [ADR-0001: クリーンアーキテクチャの採用と Antigravity プラグインガバナンス](adr/0001-clean-architecture-and-plugin-governance.md)
  - [ADR-0002: 自己成長型 RAG パイプラインと 2 段階知見審査アーキテクチャ](adr/0002-self-improving-rag-and-knowledge-verification-pipeline.md)
  - [ADR-0003: FastAPI ASGI バックエンドと Vite/React 19 SPA による Single Container アーキテクチャ](adr/0003-fastapi-asgi-and-vite-react-single-container-architecture.md)
  - [ADR-0004: SQLite PRAGMA 自動マイグレーションと単一インスタンス制約 (PostgreSQL 移行パス)](adr/0004-sqlite-automatic-schema-migration-and-single-instance-constraint.md)
  - [ADR-0005: Google Cloud Run サーバーレス実行と Google OAuth 2.0 認証・常時 CPU 割当アーキテクチャ](adr/0005-cloud-run-serverless-execution-and-google-oauth-architecture.md)
- **自己成長型（Closed-Loop）パイプライン**:
  - 単なる検索（Read）にとどまらず、ユーザーとの対話・解説から生じた知見を自律的に精査・構造化してナレッジベースへ再インデックス（Write）する閉ループ進化を実現します。
- **システム全面刷新（FastAPI ＋ Vite/React SPA）設計基本文書**:
  - PoC（Streamlit）の限界を突破し、完全非同期 Web API およびモバイル特化 SPA への破壊的リプレイスを行う基本設計書・15大DoD・全体Issue計画は **[`docs/system_redesign_blueprint.md`](system_redesign_blueprint.md)** に正本化されています。各 Issue の進行に合わせて本設計書は常に最新状態へ同期・更新されます。
- **Plugin-First 拡張原則**:
  - 今後アプリ開発や運用に必要な Skill、Hook、Tool 連携は、プロジェクトルートを一切汚染せず、すべて `.agents/plugins/<plugin-name>/` 配下の独立プラグインとしてカプセル化して設計・配備します。

