---
name: dev-lifecycle
description: IPA Exam RAG における実装・TDD高速反復・4軸ドキュメント作成・段階的コミット・ワンショット品質ゲートの実行 Runbook。機能開発や改修時に使用する。
---

# 開発・TDD反復 Runbook (dev-lifecycle)

このスキルは、**IPA Exam RAG** におけるクリーンアーキテクチャ実装、4軸ドキュメント整備、段階的コミット、およびフル品質ゲートの実行手順を定めます。

---

## 1. コア実装 & 4軸ドキュメント整備

1. **クリーンアーキテクチャ原則**:
   - 純粋ビジネスロジック（`src/core/`）は UI・外部依存ゼロ、100% 単体テスト可能を維持する。
2. **Issue フォルダ完結型ドキュメントの作成**:
   `docs/issues/ISSUE-XXX_<slug>/` 配下に以下の 4 ファイルを完全日本語で作成：
   - `issue.md`: Why・排除リスク・機能受け入れシナリオ (Given-When-Then)・受入基準
   - `pre_verification.md`: 4軸事前検証ログ ＋ 重複・パッチワーク点検（Impact & Duplication Check）
   - `plan.md`: 実装計画書（変更ファイル一覧、実装内容、検証手順）
   - `walkthrough.md`: 実装成果レポート（作業完了時に成果を記録）
3. **ルートポインタの更新**:
   `docs/pre_phase_verification.md`, `docs/implementation_plan.md`, `docs/walkthrough.md` を対象 Issue フォルダを指すよう更新。
4. **ADR（設計決定記録）の作成**:
   - 設計変更や計算式・永続化の変更時は `docs/adr/000X-xxx.md` を作成し、`docs/adr/README.md` の一覧テーブルにも登録する。

---

## 2. Inner Loop（高速反復）と Outer Loop（品質ゲート）の分離

1. **Inner Loop（開発中・TDD高速反復）**:
   - 思考のテンポと開発生産性を極大化するため、軽微な修正のたびに全量テストや重いビルドを実行しない。
   - **型チェックのみ瞬時確認 (約1秒)**:
     ```bash
     npm.cmd run check:fast
     ```
   - **変更ファイル関連テストのみ高速実行 (約1〜3秒)**:
     ```bash
     npm.cmd run test:related
     ```
   - **特定テストファイルのダイレクト実行**:
     ```bash
     npm.cmd run test:run <対象テストパス>
     ```

2. **段階的コミット (TDD中間コミット)**:
   - コミット時は `issue.md` と `plan.md` さえあれば中間コミット可能（`pre-commit` フックで `docCheck.js --pre-commit` が自動検証）。
   - Conventional Commits 規約に準拠（`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`, `ci:`）。

3. **Outer Loop（プッシュ前・Git Hook・CI）**:
   - リモートプッシュ時や PR レビュー時、および CI において、包括的な全量検査を実行する。
   - プッシュ時には Git Pre-Push Hook (`.githooks/pre-push`) により `npm.cmd run check` が自動実行される。手動でプッシュ前に事前確認する場合：
     ```bash
     npm.cmd run check
     ```
   - ※ シークレットスキャン + ドキュメント完全性 + 型検査 + 全単体テスト & カバレッジ + 本番ビルドが一括検証されます。

4. **リモートプッシュ**:
   ```bash
   git push origin <ブランチ名>
   ```
