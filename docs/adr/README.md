# 設計決定記録 (Architectural Decision Records: ADR)

本ディレクトリは、IPA Exam RAG システムにおける主要なアーキテクチャ設計決定を不可逆的に記録・保全する正本リポジトリです。

---

## ADR 一覧 (ADR Index)

| 番号 | タイトル | ステータス | 決定日 |
| :--- | :--- | :--- | :--- |
| [ADR-0001](0001-clean-architecture-and-plugin-governance.md) | クリーンアーキテクチャの採用と Antigravity プラグインガバナンス | Accepted | 2026-09-15 |
| [ADR-0002](0002-self-improving-rag-and-knowledge-verification-pipeline.md) | 自己成長型 RAG パイプラインと 2 段階知見審査アーキテクチャ | Accepted | 2026-09-15 |
| [ADR-0003](0003-fastapi-asgi-and-vite-react-single-container-architecture.md) | FastAPI ASGI バックエンドと Vite/React 19 SPA による Single Container アーキテクチャ | Accepted | 2026-09-19 |
| [ADR-0004](0004-sqlite-automatic-schema-migration-and-single-instance-constraint.md) | SQLite PRAGMA 自動マイグレーションと単一インスタンス制約 (PostgreSQL 移行パス) | Accepted | 2026-09-17 |
| [ADR-0005](0005-cloud-run-serverless-execution-and-google-oauth-architecture.md) | Google Cloud Run サーバーレス実行と Google OAuth 2.0 認証・常時 CPU 割当アーキテクチャ | Accepted | 2026-09-15 |

---

## 運用ルール
- 新規の設計決定は `0000-template.md` を複製して `XXXX-<title>.md` 形式で連番作成してください。
- 作成した ADR は必ず本 `README.md` の一覧テーブルに追記してください。
