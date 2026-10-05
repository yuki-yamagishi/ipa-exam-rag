---
name: issue-lifecycle
description: IPA Exam RAG における GitHub Issue のステータスラベル運用規約（Definition of Ready）および着手・ブランチ作成プロトコル。Issue の着手判断や状態変更時に使用する。
---

# Issue ライフサイクル規定と着手プロトコル (issue-lifecycle)

このスキルは、**IPA Exam RAG** における GitHub Issue のステータス遷移および着手可否の機械的判定ルールを定めます。

---

## 1. 進行ステータスラベル (`status:*`)

| ステータス / ラベル | 意味・状態 | AIエージェントの行動基準 |
| :--- | :--- | :--- |
| **🟡 `status: backlog`** | **アイデア・要件の保管**<br>価値はあるが、今すぐは着手しない。 | **自律着手禁止**。<br>ユーザーから明示的に「Issue #X を着手して」と指示されるまで待機。 |
| **🟠 `status: todo`** | **直近の実施候補**<br>方向性は合意したが、要件詳細化中。 | 要件・設計の整理・対話を優先。 |
| **🔵 `status: ready`** | **着手準備完了 (Definition of Ready 達成)**<br>要件・受入基準・設計論点が100%確定。 | **自律的に開発開始可能**。<br>トピックブランチを作成して実装を開始してよい。 |
| **🟣 `status: in-progress`** | **開発中**<br>トピックブランチで作業中。 | コミット・テスト・PR作成を実行中。 |
| **State: `CLOSED`** | **完了**（ラベル不要）<br>PRマージ＆品質ゲート合格完了。 | GitHub 標準機能で自動クローズ（statusラベルは剥がす）。 |

---

## 2. Issue 着手プロトコル
 
1. **着手判定**:
   - `status: backlog` の Issue は、ユーザーからの明示指示がない限り勝手に着手してはならない。
   - ユーザー指示または `status: ready` の Issue のみ自律着手可能。
2. **ラベル更新**:
   着手時は速やかにラベルを更新する：
   ```bash
   gh issue edit <id> --remove-label "status: backlog,status: ready" --add-label "status: in-progress"
   ```
3. **★【物理制約】着手準備完了 (Definition of Ready) の確認**:
   ブランチ作成前（`git checkout -b` 実行前）に、以下が満たされている必要があります（満たされていない場合は `branchDoRGate.js`（`branch-dor-gate` フック）により物理ブロックされます）：
   - **ワーキングツリーの清浄度 (Step 1)**: 未コミットの変更が一切ないこと（clean、新Issueのdocs/issues/のみ許容）。
   - **前タスクの完了 (Step 2)**: 前回のレビュー状態マシンが `IDLE` であること（未マージの PR が残存していないこと）。
   - **GitHub Issue の実在性と DoR 達成 (Step 3)**: Issue が GitHub 上で OPEN であり、かつ `status: ready` または `status: in-progress` ラベルが付与されていること（`status: backlog` や `status: todo` のままの自律着手は物理遮断）。
   - **Issue 仕様書 (`issue.md`) の作成 (Step 4)**: `docs/issues/template_issue.md` をベースに `docs/issues/ISSUE-<番号>_<slug>/issue.md` を作成し、テンプレートの未記入プレースホルダーを残さず、特に **「Why（解決すべき課題・背景）」**、**「排除するリスク」**、および **「5.1 機能受け入れシナリオ (Given-When-Then & 境界値・異常系)」** を曖昧語（「適切に」「よしなに」「〇〇の改善」「など」）を排除して具体的に定義すること。
   - **事前検証・パッチワーク点検 (`pre_verification.md`) の作成 (Step 5)**: `docs/issues/template_pre_verification.md` をベースに `pre_verification.md` を作成し、テンプレートの未記入プレースホルダーを残さず、特に **「重複・パッチワーク点検 (Impact & Duplication Check)」** を実施・記録すること。未実施の場合はブランチ作成が物理拒絶される。
   - **Pre-Phase DoR 要件監査の受領 (Step 6)**: 要件の具体性および反証可能性を保証するため、サブエージェント `fleet_dor_auditor` を呼び出して DoR 監査を受領すること。指摘があれば要件を研ぎ澄まし、`READY_TO_BRANCH` の判定をもって着手準備完了（DoR 達成）とする。
4. **トピックブランチ作成**:
   ```bash
   git checkout -b feature/issue-<番号>-<概要>
   ```
5. **完了時クリーンアップ**:
   PR マージ後、自動クローズされた Issue から進行ラベルを剥がす：
   ```bash
   gh issue edit <id> --remove-label "status: in-progress"
   ```
