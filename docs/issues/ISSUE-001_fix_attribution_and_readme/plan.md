# Issue #1: 実装計画書 (Implementation Plan)

## 1. 概要
IPA（独立行政法人情報処理推進機構）の公式過去問題使用ガイドラインに準拠した過去問出典の明記、および README.md の章立て階層不整合の是正を実施する。

## 2. 変更対象ファイル一覧
- `README.md`: 章立て階層の整流化（3.1, 3.2, 3.3, 4, 5.1, 5.2）および IPA 公式指定の出典表記方針・権利帰属・独自解説所在の追記。
- `data/seeds/README.md`: データセット仕様書における公式指定出典書式（令和X年度...）および知的財産権・独自解説の所在の明記。
- `frontend/src/utils/attribution.ts`: 和暦変換・IPA公式出典文字列生成ユーティリティ（`formatQuestionSource`, `formatQuestionSourceFromId`）の新設。
- `frontend/src/utils/attribution.test.ts`: ユーティリティの包括的単体テスト（全年度、境界値、IDパース、フォールバック）。
- `frontend/src/components/practice/QuestionCard.tsx`: 演習設問カード下部への公式出典表示の統合。
- `frontend/src/components/browse/QuestionBrowseCard.tsx`: 過去問ブラウズカードへの公式出典表示の統合。
- `frontend/src/components/insights/InsightDetailModal.tsx`: 知見詳細モーダルヘッダーでの公式出典表示の統合。
- `frontend/package.json`: 非対話型テスト実行スクリプト `test:run` の追加およびテスト対象への `attribution.test.ts` の追加。

## 3. 実装手順
1. `README.md` の見出し番号を修正し、IPA公式ガイドラインに基づく「5.1. 過去問題の出典明記および知的財産権の帰属」を追記。
2. `data/seeds/README.md` の「3. 権利帰属・著作権表示」を更新。
3. `frontend/src/utils/attribution.ts` を実装し、Node.js 組み込みテスト（`node:test`）で単体テスト `attribution.test.ts` を作成。
4. UI コンポーネント（`QuestionCard`, `QuestionBrowseCard`, `InsightDetailModal`）に公式出典表示を組み込み。
5. フロントエンドの全テスト（`npm.cmd run test:run`）および型検査（`npm.cmd run typecheck`）を実行。
6. バックエンドの全テスト（`uv run pytest`）およびリント（`uv run ruff check .`）を実行。

## 4. 検証計画
- 単体テスト: 和暦（令和元〜令和7年）、令和以前（2018年以前）の西暦フォールバック、SA 以外の未知コード、ID文字列（2021-SA-AM2-Q01等）のパース、不正IDフォールバックが全て PASS すること。
- リグレッション検証: 既存のフロントエンド 83 件のテスト、バックエンド 153 件のテストが 100% PASS すること。
