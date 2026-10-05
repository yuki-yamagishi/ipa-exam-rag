# Antigravity Review Loop (`antigravity-review-loop`)

[![CI](https://github.com/yuki-yamagishi/antigravity-review-loop/actions/workflows/ci.yml/badge.svg)](https://github.com/yuki-yamagishi/antigravity-review-loop/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**Autonomous self-healing PR review loop & quality governance plugin for Google Antigravity.**

Antigravity 公式プラグイン仕様（`plugins/<plugin-name>/plugin.json`）に完全準拠した、AIペアプログラミング向け自律レビューループ＆品質ガバナンス機構です。

---

## 🌟 主な機能 (Key Features)

1. **物理ライフサイクルフック (`hooks.json`)**:
   - `branchDoRGate.js`: ブランチ作成前の Definition of Ready（DoR: GitHub Issue状態/ラベル、Why・排除リスク・Given-When-Then受入シナリオ・テンプレート未記入検知）および作業ツリーのクリーン性を物理強制。
   - `safetyGuard.js`: 自律エージェントによる `gh pr merge` の直接実行（人間による最終マージ専権の侵害）、対話型テストによるハング、およびタイムアウト未指定のネットワークコマンド（`curl`）を物理遮断。
   - `prePrAuditGate.js`: PR作成前の4軸ドキュメント（issue, pre_verification, plan, walkthrough）およびPre-PR DoDの未完了チェックを物理検証。
   - `stopHook.js`: PR作成後、レビューループが解決（`RESOLVED_LGTM`）に達する前の早期セッション停止を物理ブロック。
   - `postPrCreate.js`: PR作成成功時にループ状態マシンを自動で `PR_CREATED` に遷移。

2. **独立サブエージェント合議制 (`agents/`)**:
   - `fleet_dor_auditor`: Pre-Phase（ブランチ前）の要件定義・DoR・Why・受入シナリオを厳格に監査。
   - `fleet_reviewer`: コード品質・型安全性・設計原則・セキュリティを客観的に精査する専門レビュアー。
   - `fleet_completion_auditor`: Issue の Why・排除リスク・受け入れ基準（DoD）の達成度を反証的かつ公正に検証する批判的完了性監査役。

3. **段階的開示スキル群 (`skills/`)**:
   - `issue-lifecycle`: Definition of Ready（DoR）および Issue 着手・ブランチ作成プロトコル。
   - `dev-lifecycle`: TDD高速反復・4軸ドキュメント・段階的コミット・品質ゲート Runbook。
   - `review-self-healing`: PR作成、CI監視、Fleetレビュー受領、指摘自己修復（`resolveReview`）、解決報告、マージ依頼プロトコル。

4. **単一コマンド実行規約 (`rules/`)**:
   - `single-command.md`: シェルコマンド連結（`;`, `&&`, `|`）を禁止し、セキュリティ監査性と自動承認精度を維持。

---

## 🚀 導入方法 (Installation)

### 方式 1: Git Submodule としてプロジェクトに導入 (推奨)

プロジェクトのルートで以下を実行します：

```bash
git submodule add https://github.com/yuki-yamagishi/antigravity-review-loop.git .agents/plugins/antigravity-review-loop
```

他メンバーや CI 環境では、通常のクローン時に以下でプラグインも展開されます：

```bash
git clone --recurse-submodules <YOUR_PROJECT_URL>
# または既存リポジトリで
git submodule update --init --recursive
```

### 方式 2: Git Clone として配置

```bash
git clone https://github.com/yuki-yamagishi/antigravity-review-loop.git .agents/plugins/antigravity-review-loop
```

---

## 📁 プラグイン構造 (Directory Layout)

```text
.agents/plugins/antigravity-review-loop/
├── plugin.json                    # 公式プラグインマニフェスト
├── hooks.json                     # ライフサイクルフック定義
├── hooks/                         # フック実装スクリプト
│   ├── branchDoRGate.js
│   ├── hookUtils.js
│   ├── postPrCreate.js
│   ├── prePrAuditGate.js
│   ├── safetyGuard.js
│   └── stopHook.js
├── skills/                        # 専門スキル群
│   ├── dev-lifecycle/SKILL.md
│   ├── issue-lifecycle/SKILL.md
│   └── review-self-healing/SKILL.md
├── rules/                         # ルール群
│   └── single-command.md
├── agents/                        # 同梱サブエージェント群
│   ├── fleet_reviewer.md
│   ├── fleet_completion_auditor.md
│   └── fleet_dor_auditor.md
└── state/                         # 状態マシン
    ├── loopState.js
    └── .gitignore
```

---

## 🧪 テストの実行 (Testing)

本リポジトリ単体で Vitest による全テストを実行できます：

```bash
npm install
npm test
```

---

## 📄 ライセンス (License)

[MIT License](LICENSE) © 2026 Yuki Yamagishi
