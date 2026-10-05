# ADR-0005: Google Cloud Run サーバーレス実行と Google OAuth 2.0 認証・常時 CPU 割当アーキテクチャ

- **ステータス**: Accepted
- **決定日**: 2026-09-15

---

## 1. 背景と課題 (Context & Problem Statement)

本システムをインターネット上で安全かつ低コストに本番運用するにあたり、以下のインフラ要件とセキュリティ要件を満たす必要がある：

1. **常時 CPU 割当の必須性 (Background Task Execution)**:
   対話から抽出された知見を保存する際、ユーザーの待機時間をなくすために API は即座に `HTTP 202 Accepted` を返却し、裏側の FastAPI `BackgroundTasks` で知見審査およびベクトル登録を実行する。
   一般的なサーバーレス環境のデフォルト（リクエスト処理中のみ CPU 割当）では、HTTP レスポンス返却直後に CPU が凍結され、バックグラウンド処理が破壊・中断される。
2. **不正利用防止とプライバシー保護 (Strict Access Control)**:
   Gemini API の従量課金保護および個人学習履歴の保護のため、認可された特定ユーザーのみにアクセスを制限するホワイトリスト制の認証基盤が必要。
3. **ステートレスかつセキュアなセッション管理**:
   Cookie ベースのセッション管理において、CSRF 攻撃やトークン改ざんを確実に防ぐ暗号学的保護が必要。

---

## 2. 検討した選択肢 (Considered Options)

1. **選択肢 A: Google Cloud Run (`--no-cpu-throttling`) ＋ Google OAuth 2.0 ＋ 暗号署名 Cookie（採用）**
2. **選択肢 B: 常時起動 VM (Compute Engine / GCE) による運用**
3. **選択肢 C: Firebase Authentication ＋ Cloud Functions**

---

## 3. 決定事項 (Decision)

**選択肢 A を採用する。**

### 3.1. Google Cloud Run によるサーバーレス実行基盤
- **リージョン**: 東京リージョン (`asia-northeast1`) を採用し、国内からのアクセス遅延を極小化。
- **リソーススペック**: 1 vCPU / 2GB メモリ。ベクトル検索キャッシュと並列審査に十分なスペックを確保。
- **CPU アロケーション**: **`--no-cpu-throttling`（常に CPU を割り当て）を必須指定**。レスポンス返却後のバックグラウンド審査タスクの完走を物理保証する。

### 3.2. Google OAuth 2.0 ＋ ホワイトリスト認可
- Google Cloud Console の OAuth 2.0 クライアント認証を活用。
- 環境変数 `ALLOWED_EMAILS` に登録された正規の Google アカウントメールアドレスのみログインを許可するホワイトリスト制を採用。
- 未認可アカウントのログイン試行時は `403 Forbidden` で即座にアクセスを遮断。

### 3.3. 暗号学的 HMAC セッション署名と二重保護
- **セッション署名**: `session_secret`（32バイト以上のランダム暗号鍵）を用いて HMAC-SHA256 で署名したセッション Cookie（`session_user`）を発行。
- **Fail-fast 設計 & Secure by Default**:
  - `AUTH_ENABLED` の既定値を `True` とし、安全側に倒す設計（Secure by Default）を採用。
  - `AUTH_ENABLED=true` かつ `session_secret` が未設定の場合は、起動時の Pydantic バリデーションで即座に起動を停止し、安全でない状態での稼働を物理防止。
  - Cloud Run 実行環境（`K_SERVICE` 環境変数が存在）において、誤って `AUTH_ENABLED=false` が指定された場合は起動を物理拒否（`forbid_auth_disabled_on_cloud_run`）。Gemini API 課金操作（再インデックス）や API キー更新、履歴全消去が未認証で外部公開される事故を根絶。
- **フロント・バックエンド二重防御**: フロントエンド（全画面 `AuthGuard`）とバックエンド（FastAPI `require_auth` 依存関係）の双方で未認証アクセスを遮断。

### 3.4. 機密情報の Secret Manager 統合
API キー（`GEMINI_API_KEY`）、OAuth シークレット（`GOOGLE_CLIENT_SECRET`）、およびセッション署名鍵（`SESSION_SECRET`）はコンテナ環境変数に平文で埋め込まず、Google Secret Manager から安全に注入する。

---

## 4. 影響と結果 (Consequences)

### ポジティブな影響
- **バックグラウンドタスクの信頼性担保**: `--no-cpu-throttling` により、自律知見審査が確実に完走し、データの不整合や欠落を防止。
- **堅牢なアクセス制御**: 信頼性の高い Google アカウント基盤と暗号署名により、なりすましや不正な API 消費を完全に防止。
- **低運用コスト**: サーバーレスの柔軟性を活かしつつ、最小限のインフラ構成で安全な本番運用を実現。

### トレードオフ・留意点
- `--no-cpu-throttling` の指定により、CPU 待機時もインスタンス稼働料金が発生するが、1 インスタンス（1 vCPU / 2GB）の個人・少人数運用におけるコストは極めて少額であり、タスクの完走保証という不可欠なメリットが上回る。
