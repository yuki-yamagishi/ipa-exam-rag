---
name: review-self-healing
description: Pull Request 作成、GitHub Actions CI 監視、Fleet レビュー受領、指摘自己修復ループ、解決報告、および人間へのマージ依頼を行う Runbook。PR 発行から完了までに使用する。
---

# レビュー & 自己修復ループ Runbook (review-self-healing)

このスキルは、**IPA Exam RAG** における PR 作成後の自律的自己修復ループ、リモート CI 監視、および人間マージ完了までの手順を定めます。

---

## 1. PR 作成 & 早期停止ガード発動

1. **★【物理制約】PR 作成前最終監査 (Pre-PR Final Audit) の確認**:
   `gh pr create` 実行前に、以下が満たされている必要があります（満たされていない場合は `prePrAuditGate.js`（`pre-pr-audit-gate` フック）により物理ブロックされます）：
   - **4軸ドキュメントの完備**: `docs/issues/<Issue>/` 配下に `issue.md`, `pre_verification.md`, `plan.md`, `walkthrough.md` がすべて存在し、内容が記載されていること。
   - **Pre-PR DoD（PR作成前受け入れ基準）の完全達成**: `issue.md` 内の「5.2. PR作成前プロセス完了基準 (Pre-PR Process DoD)」（旧フォーマットでは 5.1）に未チェック項目（`- [ ]`）が残っていないこと（すべて `[x]` に更新済であること）。
   - **SSOT (`architecture_overview.md`) と最新 ADR の同期**: `docs/adr/` 配下の最新 ADR が `docs/architecture_overview.md` に登録・反映されていること。

2. **PR 作成**:
   ```bash
   gh pr create --title "<タイトル>" --body-file <一時ファイル>
   ```
   - PR 本文には `Closes #<Issue番号>` を必ず含める。
   - `postPrCreate.js` が PR 作成を自動検知し、`loopState.js` の状態が `PR_CREATED` に遷移します。
   - この時点で Stop フック（`stopHook.js`）による早期停止ガードが有効になります。

3. **★【必須】リモート CI (GitHub Actions) の待機 & 監視**:
   PR 作成直後、Fleet レビューに進む前に、GitHub Actions CI が正常にパスすることを確認します：
   ```bash
   gh pr checks
   ```
   - CI が失敗している場合は、手元で原因を調査・修正して追加プッシュし、CI がグリーンになるまで待機します。

---

## 2. Antigravity 2者 Fleet 並行レビュー (Review Consortium)

1. **レビュー待機状態への遷移**:
   ```bash
   node .agents/plugins/antigravity-review-loop/state/loopState.js review-requested --active-subagents
   ```
2. **Fleet 2者の並行起動 (invoke_subagent)**:
   - Antigravity の `invoke_subagent` ツールを用い、以下の 2 体の専門サブエージェントを配列で**同時に並行起動**します：
      - **`fleet_reviewer`**: コード品質・型安全性・セキュリティ・アーキテクチャ原則・デッドロック防止の専門レビュー
      - **`fleet_completion_auditor`**: 批判的完了性・Why / 排除リスク・受け入れ基準（DoD）・やり残し監査。反例提示の義務化（Counterexample Obligation）に基づき、具体的な破綻シナリオが示せない場合は無理な指摘を禁止し、`[good]` を付与して速やかに合格判定を行う。また、PR 段階でのゴールポスト移動（後出し要求）を厳禁とする。
   - 各 Fleet は Conventional Comments 形式（`[must]`, `[should]`, `[imo]`, `[nits]`, `[ask]`, `[good]`）および JSON メタデータブロック（`agentType: "codeReviewer" | "completionAuditor"`, `verdict: "LGTM" | "REQUEST_CHANGES"`）を出力します。
3. **Reactive Wakeup 待機**:
   - 親エージェントはツール呼び出しを行わずにターンを終了し、両 Fleet の完了通知を待ちます。
4. **各レビュー結果の PR コメント投稿 & loopState 記録**:
   - 一時ファイル経由で PR スレッドに公式コメントとして投稿：
     ```bash
     gh pr comment <PR番号> --body-file <コードレビューファイル>
     gh pr comment <PR番号> --body-file <完了性監査ファイル>
     ```
   - それぞれの結果をステートマシンに記録：
     ```bash
     node .agents/plugins/antigravity-review-loop/skills/review-self-healing/scripts/parseReviewResult.js <コードレビューファイル> --agent-type codeReviewer --update-state
     node .agents/plugins/antigravity-review-loop/skills/review-self-healing/scripts/parseReviewResult.js <完了性監査ファイル> --agent-type completionAuditor --update-state
     ```

---

## 3. 合議制判定 & 自己修復 & 再レビュー受領（セルフLGTMの物理禁止）

1. **合議制（Consortium Consensus Gate）判定**:
   - **両者 LGTM**: `codeReviewer` と `completionAuditor` の両方が `LGTM`（未解決ブロッキング指摘 0 件）の場合のみ、状態マシンは `STATUS.RESOLVED_LGTM` に収束します。
   - **片方でも REQUEST_CHANGES**: いずれか片方でも未解決の `[must]` または `[should]` 指摘がある場合、状態は `STATUS.NEEDS_FIX` となり、全指摘が集約されます。
   - **片方のみ完了時**: もう片方の完了を待つため、`STATUS.REVIEW_REQUESTED` に留まり、Stop フックにより停止はブロックされます。
2. **手元自己修復コミット**:
   - 両レビュアーからの指摘事項（コード品質および完了性・Why/リスク）を修正し、テストを追加。
   - `npm.cmd run check` で 100% PASS を確認後、追加コミット＆プッシュ。
   - GitHub Actions CI がパスするまで待機（`gh pr checks`）。
3. **公式修正報告の投稿 & 再レビュー待機遷移**:
   ```bash
   node .agents/plugins/antigravity-review-loop/skills/review-self-healing/scripts/resolveReview.js --commit <コミットハッシュ> --summary "<修正概要>"
   ```
   - PR スレッドに公式修正報告が投稿され、状態は `STATUS.REVIEW_REQUESTED`（再レビュー待ち）に遷移します。
   - **【最重要】コード修正が入ったため過去の全レビュー判定は Stale（無効化）され、`reviews` スロットは両者ともリセットされます。親エージェントによる自己承認（セルフLGTM）および片方の承認のみでの通過は物理的に禁止されています。**
4. **★【必須】Fleet サブエージェント 2 者の再起動（Re-review & Re-audit）**:
   - コード変更が入った以上、指摘を受けた側だけでなく Fleet レビュアー 2 者（`fleet_reviewer` および `fleet_completion_auditor`）を両方再起動し、客観的再検証（Re-review）と批判的再監査（Re-audit）を受領します。
   - 両者から `[LGTM]` を獲得し、ステートマシンが正真正銘の `STATUS.RESOLVED_LGTM` に収束して初めて、Stop フックの停止ガードが解除されます。

---

## 4. 人間へのマージ依頼 & 完了

1. **人間（ユーザー）への報告**:
   - 全指摘解消と総合判定 `[LGTM (All Resolved)]` を確認し、ユーザーにマージを依頼します。
   - **【最重要】PR のマージは人間（ユーザー）が実施します。エージェント自身が `gh pr merge` を実行することは `safetyGuard.js`（`safety-guard` フック）により物理禁止されています。**
2. **状態リセット**:
   マージ完了後、ループ状態をリセットします：
   ```bash
   node .agents/plugins/antigravity-review-loop/state/loopState.js reset
   ```
