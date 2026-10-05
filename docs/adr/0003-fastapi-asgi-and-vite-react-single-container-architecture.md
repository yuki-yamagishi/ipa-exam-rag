# ADR-0003: FastAPI ASGI バックエンドと Vite/React 19 SPA による Single Container アーキテクチャ

- **ステータス**: Accepted
- **決定日**: 2026-09-19

---

## 1. 背景と課題 (Context & Problem Statement)

本システムは、過去問演習（道場モード）、AI 対話チャット、マイ知見ノート、および弱点分析ダッシュボードを統合して提供する。

これを実現するにあたり、以下の要件と技術的課題が存在した：
1. **モバイル特化の操作性と即時応答**:
   スマートフォンでの移動中学習を主用途とするため、親指操作に適した大型タッチ領域（56px）、スレートダーク調の読解しやすい UI、およびオフライン PWA キャッシュが求められる。
2. **低遅延 SSE ストリーミング**:
   AI の回答を 0.5 秒未満で文字送りストリーミング配信し、思考のテンポを阻害しないレスポンス性能が必要。
3. **運用複雑性と CORS 障害の根絶**:
   フロントエンド（SPA）とバックエンド（API）を別々のドメインやコンテナでホスティングすると、CORS 設定ミス、SSL 証明書管理の二重化、ネットワーク遅延が発生する。単一のコンテナで同一オリジン・同一ポート（PORT 8080）配信することが望ましい。

---

## 2. 検討した選択肢 (Considered Options)

1. **選択肢 A: FastAPI (ASGI) ＋ Vite/React 19 SPA の Multi-stage Docker Single Container（採用）**
2. **選択肢 B: フロントエンド（Cloud Storage / Firebase Hosting）とバックエンド（Cloud Run）の完全分離ホスティング**
3. **選択肢 C: サーバーサイドレンダリング (Next.js / SSR)**

---

## 3. 決定事項 (Decision)

**選択肢 A を採用する。**

### 3.1. 技術スタックの選定
- **バックエンド**: Python 3.12 ＋ FastAPI (ASGI / Uvicorn)。非同期 I/O、SSE ストリーミング (`StreamingResponse`)、およびバックグラウンド非同期処理 (`BackgroundTasks`) をネイティブにサポート。
- **フロントエンド**: Vite ＋ React 19 ＋ TypeScript ＋ Tailwind CSS。バンドルサイズの極小化、高速なビルド、型安全性を確保。

### 3.2. Multi-stage Docker による単一コンテナ統合
3 つのステージで構成される単一コンテナイメージを構築する：
- **Stage 1 (frontend-builder)**: `node:20-slim` 環境で Vite ビルドを実行し、静的アセット（HTML/JS/CSS）を `/app/frontend/dist` に出力。
- **Stage 2 (backend-builder)**: `python:3.12-slim` 環境で Python 依存関係およびホイールをビルド。
- **Stage 3 (runner)**: 最小限の Python 実行環境にバックエンドコードおよび Stage 1 の静的アセットを統合配置。非 root ユーザー（`appuser`）で PORT 8080 にて稼働。

### 3.3. HTML5 History API Fallback によるルーティング保護
FastAPI のミドルウェアおよびルートフォールバックハンドラにより、`/api/*` 以外のすべてのクライアントサイドルート遷移（`/practice`, `/questions`, `/chat`, `/insights`, `/analytics` 等）および未知のパスに対して、キャッシュ無効化ヘッダーを付与した `dist/index.html` を返却する。
これにより、クライアント側の React Router / SPA 画面遷移時の 404 エラーを物理防止する。

---

## 4. 影響と結果 (Consequences)

### ポジティブな影響
- **CORS 問題の完全根絶**: フロントエンドとバックエンドが同一ドメイン・同一ポートで動作するため、クロスオリジン制約に起因する不具合が発生しない。
- **運用保守の最小化**: 単一の Docker コンテナ・単一の Cloud Run サービスを管理するだけでインフラ運用が完結する。
- **高速なモバイル UX**: Vite による最適化されたチャンク分割（Code Splitting）と、PWA Service Worker キャッシュによる高速な初期表示を実現。

### トレードオフ・留意点
- 静的アセットの変更時にも Docker コンテナの再ビルドが必要となるが、Docker レイヤーキャッシュおよび GitHub Actions CI の最適化により、数分以内でデプロイを完了できる。
