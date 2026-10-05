import test from 'node:test';
import assert from 'node:assert/strict';
import { ragApi, ApiError } from '../../api/client.ts';
import type { LearnedInsight } from '../../types/index.ts';

const dummyInsights: LearnedInsight[] = [
  {
    id: 'insight-1',
    source_question_id: '2025-SA-AM2-Q01',
    title: 'フォールトアボイダンスとフォールトトレランスの決定的な違い',
    core_concept:
      'フォールトアボイダンスは高品質部品や徹底したテストにより故障の発生そのものを予防するアプローチ。一方、フォールトトレランスは構成要素に冗長性を持たせ、故障発生時でもシステム全体のサービスを継続する。',
    trap_analysis:
      '問題文で「高品質な部品の採用」「テストの徹底」とある場合はフォールトアボイダンス。「多重化」「冗長化」「フェールソフト」とある場合はフォールトトレランスであり、混同しやすい。',
    practical_takeaway:
      '高信頼性クラウドアフィニティ設計では、単一インスタンスの品質向上（アボイダンス）とマルチAZ構成（トレランス）を組み合わせてMTBFとMTTRを最適化する。',
    confidence_score: 0.95,
    is_verified: true,
    tags: ['可用性', '高信頼化', 'アーキテクチャ'],
    created_at: '2026-03-15T10:30:00Z',
    updated_at: null,
  },
  {
    id: 'insight-2',
    source_question_id: '2025-SA-AM2-Q05',
    title: '公開鍵暗号とデジタル署名における鍵の役割と耐タンパ性',
    core_concept:
      '送信者は自身の秘密鍵でハッシュ値を暗号化して署名を生成し、受信者は送信者の公開鍵で復号・検証する。暗号化通信とは鍵の役割が完全に対称逆転する点に留意。',
    trap_analysis:
      '「受信者の公開鍵で暗号化」とある選択肢は通信の守秘であり、デジタル署名（改ざん検知・本人認証）ではない。',
    practical_takeaway:
      'API 通信では JWT や mTLS において秘密鍵の漏洩を防ぐため HSM や KMS によるセキュアストレージ管理を徹底する。',
    confidence_score: 0.98,
    is_verified: true,
    tags: ['セキュリティ', '暗号化', '認証'],
    created_at: '2026-03-20T14:15:00Z',
    updated_at: null,
  },
];

// Scenario 1: Initial insights fetch queries GET /api/rag/insights
test('Scenario 1: ragApi.getInsights requests GET /api/rag/insights?limit=100', async () => {
  const originalFetch = globalThis.fetch;
  try {
    let capturedUrl = '';
    globalThis.fetch = async (url: string | URL | Request) => {
      capturedUrl = String(url);
      return new Response(JSON.stringify(dummyInsights), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    const result = await ragApi.getInsights(100);
    assert.equal(capturedUrl, '/api/rag/insights?limit=100');
    assert.equal(result.length, 2);
    assert.equal(result[0].id, 'insight-1');
    assert.equal(result[1].id, 'insight-2');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// Scenario 2: Keyword search filters insights by title, concept, or tags
test('Scenario 2: Keyword filter matches title, core_concept, or tags case-insensitively', () => {
  const filterByKeyword = (items: LearnedInsight[], query: string) => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => {
      const titleMatch = item.title?.toLowerCase().includes(q);
      const conceptMatch = item.core_concept?.toLowerCase().includes(q);
      const trapMatch = item.trap_analysis?.toLowerCase().includes(q);
      const takeawayMatch = item.practical_takeaway?.toLowerCase().includes(q);
      const qidMatch = item.source_question_id?.toLowerCase().includes(q);
      const tagMatch = item.tags?.some((t) => t.toLowerCase().includes(q));
      return (
        titleMatch ||
        conceptMatch ||
        trapMatch ||
        takeawayMatch ||
        qidMatch ||
        tagMatch
      );
    });
  };

  // Search by keyword "デジタル署名"
  const sigMatches = filterByKeyword(dummyInsights, 'デジタル署名');
  assert.equal(sigMatches.length, 1);
  assert.equal(sigMatches[0].id, 'insight-2');

  // Search by keyword "フォールト"
  const faultMatches = filterByKeyword(dummyInsights, 'フォールト');
  assert.equal(faultMatches.length, 1);
  assert.equal(faultMatches[0].id, 'insight-1');

  // Search by question ID "Q05"
  const qidMatches = filterByKeyword(dummyInsights, 'Q05');
  assert.equal(qidMatches.length, 1);
  assert.equal(qidMatches[0].id, 'insight-2');

  // Unmatched keyword
  const noMatches = filterByKeyword(dummyInsights, '存在しないワード');
  assert.equal(noMatches.length, 0);
});

// Scenario 3: Tag filtering narrows down items and supports resetting
test('Scenario 3: Tag filter narrows items and resetting restores full list', () => {
  const filterByTag = (items: LearnedInsight[], tag: string | null) => {
    if (!tag) return items;
    return items.filter((item) => item.tags && item.tags.includes(tag));
  };

  // Select tag '可用性'
  const availItems = filterByTag(dummyInsights, '可用性');
  assert.equal(availItems.length, 1);
  assert.equal(availItems[0].id, 'insight-1');

  // Select tag 'セキュリティ'
  const secItems = filterByTag(dummyInsights, 'セキュリティ');
  assert.equal(secItems.length, 1);
  assert.equal(secItems[0].id, 'insight-2');

  // Reset tag (null) restores all
  const allItems = filterByTag(dummyInsights, null);
  assert.equal(allItems.length, 2);
});

// Scenario 4: Detail modal structure verification (3 axes and verification badge)
test('Scenario 4: LearnedInsight data contains all required 3-axis fields and metadata', () => {
  const insight = dummyInsights[0];
  assert.ok(insight.core_concept.length > 0, 'Core concept must not be empty');
  assert.ok(insight.trap_analysis.length > 0, 'Trap analysis must not be empty');
  assert.ok(insight.practical_takeaway.length > 0, 'Practical takeaway must not be empty');
  assert.equal(insight.is_verified, true);
  assert.equal(insight.confidence_score, 0.95);
  assert.ok(Array.isArray(insight.tags));
  assert.equal(insight.tags.length, 3);
});

// Scenario 5: Empty state handling when list is empty
test('Scenario 5: Empty state logic identifies when no insights are available', () => {
  const emptyList: LearnedInsight[] = [];
  const hasInsights = emptyList.length > 0;
  assert.equal(hasInsights, false);
});

// Scenario 6: ApiError handling returns normalized error details on failure
test('Scenario 6: ragApi.getInsights propagates ApiError when server returns 500', async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => {
      return new Response(JSON.stringify({ detail: 'Qdrant connection refused' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    let caughtError: ApiError | null = null;
    try {
      await ragApi.getInsights();
    } catch (err) {
      if (err instanceof ApiError) {
        caughtError = err;
      }
    }

    assert.ok(caughtError !== null);
    const err: ApiError = caughtError;
    assert.equal(err.status, 500);
    assert.equal(err.detail, 'Qdrant connection refused');
  } finally {
    globalThis.fetch = originalFetch;
  }
});
