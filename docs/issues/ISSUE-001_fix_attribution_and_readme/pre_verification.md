# Issue #1: 事前検証記録 (Pre-Verification)

## 1. 検証日時
2026-10-06

## 2. 現状の課題分析 (Problem Analysis)
- **現状のコード・アーキテクチャの振る舞い**:
  - `README.md` の章見出し構造が崩れており、「3. ローカル開発クイックスタート」の下位見出しが「2.1」「2.2」「2.3」とナンバリングされている。また後続の「ドキュメント体系」も「3.」と重複しており、章立てが論理的破綻を起こしている。
  - `README.md` および `data/seeds/README.md` において、IPAの知的財産権帰属は書かれているものの、IPA公式サイトの「試験の過去問題の使用方法」で明示されている公式指定書式（「出典：平成31年度 春期 基本情報技術者試験 午前 問1」）に準拠したルール・具体例が欠落している。
  - フロントエンドでは `{question.year}年 {question.term}` と `問 {question.question_number}` が別々にバッジ表示されているのみで、IPA公式指定の出典表記が統一適用されていない。
- **根本原因 (Root Cause)**:
  - リリース直前のデータセット説明セクション追加時に、後続の連番の見直しが漏れていた。
  - 出典表記要件が権利帰属の概要記述にとどまり、IPA公式FAQの厳密な書式要件への準拠が仕様化されていなかった。

## 3. 重複・パッチワーク点検 (Impact & Duplication Check)
- **既存基盤・ユーティリティ・ASTの横断調査**:
  - フロントエンドに和暦変換や公式出典フォーマッタが存在するか調査したところ、現在は各コンポーネント（`QuestionCard`, `QuestionBrowseCard`）で西暦と期を個別文字列展開している。
  - バックエンド側 `ExamQuestion` モデルの `format_full_text()` では `【問題 {self.question_number}】({self.category})` とのみフォーマットされており、出典フォーマッタは存在しない。
- **車輪の再発明・パッチワークの防止方針**:
  - コンポーネントごとに場当たり的な文字列結合（つぎはぎ改修）を行わず、フロントエンドの共通ユーティリティ（`frontend/src/utils/formatters.ts` または `frontend/src/utils/attribution.ts`）に型安全な関数 `formatQuestionSource` を集約する。
  - これにより、将来新たな画面やコンポーネントが追加された際も単一の真実（SSOT）から同一の公式表記を取得可能にする。

## 4. 改修方針 (Implementation Strategy)
1. `README.md` の見出し階層を整流化（3.1, 3.2, 3.3, 4, 5.1, 5.2）。
2. `README.md` および `data/seeds/README.md` に IPA 公式ガイドライン準拠の「出典の明記規則（和暦・期・試験区分・時間区分・問番号）」「著作権の不放棄」「教育目的」「独自解説の所在」を追記。
3. `frontend/src/utils/attribution.ts` を新規作成し、`formatQuestionSource`（設問オブジェクト用）、`formatQuestionSourceFromId`（ID文字列パース用）、和暦変換ロジック、および異常系・境界値フォールバックを実装。包括的な単体テスト `attribution.test.ts` を配置。
4. `QuestionCard.tsx`、`QuestionBrowseCard.tsx`、`InsightDetailModal.tsx` に公式出典表示を統合。
5. 全量テストおよび静的解析（pytest, ruff, npm test, npm run typecheck）を実行して無破壊を担保。
