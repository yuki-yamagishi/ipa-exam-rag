# Cloud Run デプロイ仕様書 & 運用ガイド（唯一の正本）

本書は IPA Exam RAG を Google Cloud Run にデプロイするための**唯一の手順書**です（旧 `docs/deploy_cloud_run.md` は本書に統合・廃止しました）。

> [!IMPORTANT]
> **認証は必須です（Secure by Default）**
> - `AUTH_ENABLED` の既定値は `true` です。
> - Cloud Run 上（環境変数 `K_SERVICE` が存在する環境）で `AUTH_ENABLED=false` を指定すると、**アプリケーションは起動を拒否します**（[config.py](../src/infrastructure/config.py) の `forbid_auth_disabled_on_cloud_run`）。
> - これにより、設定ミスで Gemini API の課金操作（再インデックス）・API キー変更・履歴全消去が公開される事故を物理的に防止します。

---

## 1. 全体アーキテクチャ

Vite/React SPA と FastAPI（Uvicorn）バックエンドを、単一のマルチステージ Docker コンテナで同一オリジン・同一ポート（8080）から配信します。

```text
[ スマートフォン / PC ブラウザ ]
              │ HTTPS
              ▼
[ Google Cloud Run (Gen2) ]
  ├── FastAPI + SPA (Port 8080)
  ├── Google OAuth 2.0 認証ガード (ALLOWED_EMAILS 限定)
  └── GCS FUSE マウント (/app/storage -> Cloud Storage バケット)
        └── SQLite 演習履歴 DB (practice_history.db)
              ├── 生成・埋め込み ──> [ Google Gemini API ]
              └── ベクトル検索 ────> [ Qdrant Cloud ]
```

- `/api/*` 以外のパスには `index.html` を返却します（SPA History API Fallback）。
- 公開範囲は Cloud Run の `--allow-unauthenticated`（URL 到達可能）ですが、`/api/auth/*` と `/health` 以外の API はアプリ側の Google OAuth 認証で保護されます。

---

## 2. 前提条件

1. **GCP プロジェクト**（課金有効）と API の有効化:
   ```bash
   gcloud services enable run.googleapis.com storage.googleapis.com secretmanager.googleapis.com
   ```
2. **Qdrant Cloud** のクラスタ URL と API キー。
3. **Google AI Studio** で取得した Gemini API キー。
4. （推奨）Gemini API / GCP に**予算アラート**を設定する。

---

## 3. Google OAuth 2.0 クライアントの作成

1. **API とサービス > OAuth 同意画面**:
   - ユーザータイプ: 「外部」（Workspace 組織内なら「内部」）
   - スコープ: `openid`, `.../auth/userinfo.email`, `.../auth/userinfo.profile`
   - テストユーザー: 自分の Google アカウント
2. **認証情報 > OAuth クライアント ID**（ウェブ アプリケーション）:
   - **承認済みのリダイレクト URI**: `https://<SERVICE_URL>/api/auth/callback`
   - 初回デプロイ前は URL が未確定のため、デプロイ後に登録・更新します（§7）。
3. 発行された `Client ID` と `Client Secret` を控えます。

---

## 4. GCS バケットの作成（SQLite 演習履歴の永続化）

> [!WARNING]
> `/app/data` に直接マウントすると、イメージ同梱の試験問題データ（`/app/data/seeds/*.json`）が空バケットで隠蔽され、問題が 0 問になります。マウント先は必ず `/app/storage` とし、`SQLITE_DB_PATH=/app/storage/practice_history.db` を指定してください。

```bash
gcloud storage buckets create gs://ipa-exam-rag-data-<YOUR_PROJECT_ID> --location=asia-northeast1
```

---

## 5. Secret Manager への機密情報登録

機密情報は環境変数に平文で埋め込まず、Secret Manager から注入します。

```bash
# セッション署名鍵（32 バイト以上のランダム値）
python -c "import secrets; print(secrets.token_hex(32), end='')" | gcloud secrets create session-secret --data-file=-

echo -n "YOUR_GEMINI_API_KEY"       | gcloud secrets create gemini-api-key --data-file=-
echo -n "YOUR_QDRANT_URL"           | gcloud secrets create qdrant-url --data-file=-
echo -n "YOUR_QDRANT_API_KEY"       | gcloud secrets create qdrant-api-key --data-file=-
echo -n "YOUR_GOOGLE_CLIENT_ID"     | gcloud secrets create google-client-id --data-file=-
echo -n "YOUR_GOOGLE_CLIENT_SECRET" | gcloud secrets create google-client-secret --data-file=-
```

---

## 6. 環境変数一覧

| 環境変数名 | 必須 | 既定値 | 説明 |
|---|---|---|---|
| `AUTH_ENABLED` | 任意 | `true` | Cloud Run 上では `false` 指定時に起動拒否。ローカル開発時のみ `false` 可 |
| `SESSION_SECRET` | **必須** | - | HMAC セッション / CSRF state 署名鍵（`SESSION_SECRET_KEY` も可）。未設定だと起動拒否 |
| `GOOGLE_CLIENT_ID` | **必須** | - | OAuth 2.0 クライアント ID |
| `GOOGLE_CLIENT_SECRET` | **必須** | - | OAuth 2.0 クライアント シークレット |
| `GOOGLE_REDIRECT_URI` | **必須** | - | `https://<SERVICE_URL>/api/auth/callback` |
| `ALLOWED_EMAILS` | **必須** | 空（全拒否） | ログインを許可するメールアドレス（カンマ区切り） |
| `COOKIE_SECURE` | 任意 | `false` | HTTPS リクエスト時は自動で Secure 属性付与。明示的に `true` 推奨 |
| `GEMINI_API_KEY` | **必須** | - | Gemini API キー |
| `QDRANT_URL` / `QDRANT_API_KEY` | **必須** | - | Qdrant Cloud 接続情報 |
| `SQLITE_DB_PATH` | **必須** | `data/practice_history.db` | `/app/storage/practice_history.db` を指定 |

---

## 7. デプロイ

> [!WARNING]
> **インスタンス数は 1 に固定します。** GCS FUSE は POSIX ファイルロックをサポートしないため、複数インスタンスから SQLite に書き込むと DB 破損の恐れがあります（ADR-0004）。

> [!NOTE]
> **`--no-cpu-throttling` は必須です。** 知見保存は HTTP 202 を返した後に `BackgroundTasks` で処理するため、CPU が凍結されると処理が中断されます（ADR-0005）。

```bash
gcloud run deploy ipa-exam-rag \
  --source . \
  --region asia-northeast1 \
  --execution-environment gen2 \
  --port 8080 \
  --memory 2Gi \
  --cpu 1 \
  --no-cpu-throttling \
  --min-instances 0 \
  --max-instances 1 \
  --timeout 300 \
  --allow-unauthenticated \
  --add-volume name=data-storage,type=cloud-storage,bucket=ipa-exam-rag-data-<YOUR_PROJECT_ID> \
  --add-volume-mount volume=data-storage,mount-path=/app/storage \
  --set-env-vars AUTH_ENABLED=true,COOKIE_SECURE=true,SQLITE_DB_PATH=/app/storage/practice_history.db,GOOGLE_REDIRECT_URI=https://<SERVICE_URL>/api/auth/callback,ALLOWED_EMAILS=your-email@gmail.com \
  --set-secrets SESSION_SECRET=session-secret:latest,GEMINI_API_KEY=gemini-api-key:latest,QDRANT_URL=qdrant-url:latest,QDRANT_API_KEY=qdrant-api-key:latest,GOOGLE_CLIENT_ID=google-client-id:latest,GOOGLE_CLIENT_SECRET=google-client-secret:latest
```

**初回デプロイ時**:
1. `GOOGLE_REDIRECT_URI` は仮値でデプロイし、発行された `Service URL` を確認します。
2. `https://<SERVICE_URL>/api/auth/callback` を OAuth クライアントの「承認済みのリダイレクト URI」に登録します。
3. 環境変数を本番 URL に更新します:
   ```bash
   gcloud run services update ipa-exam-rag --region asia-northeast1 --update-env-vars GOOGLE_REDIRECT_URI=https://<SERVICE_URL>/api/auth/callback
   ```

---

## 8. 疎通確認

| 確認内容 | コマンド | 期待値 |
|---|---|---|
| ヘルスチェック | `curl -f https://<SERVICE_URL>/health` | `200 {"status":"healthy"}` |
| SPA Fallback | `curl -I https://<SERVICE_URL>/practice` | `200 text/html` |
| **未認証アクセスの遮断** | `curl -i https://<SERVICE_URL>/api/questions` | **`401 Unauthorized`** |
| 認証状態 | `curl https://<SERVICE_URL>/api/auth/status` | `"auth_enabled": true` |

ブラウザで Service URL にアクセスし、`ALLOWED_EMAILS` のアカウントでログインできること、それ以外のアカウントが `403` で拒否されることを確認します。
