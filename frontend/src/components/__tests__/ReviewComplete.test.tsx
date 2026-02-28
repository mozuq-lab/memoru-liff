import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ReviewComplete } from '../ReviewComplete';
import type { SessionCardResult } from '@/types';

const renderReviewComplete = (reviewedCount: number) => {
  return render(
    <MemoryRouter>
      <ReviewComplete reviewedCount={reviewedCount} />
    </MemoryRouter>
  );
};

const renderReviewCompleteWithResults = (reviewedCount: number, results: SessionCardResult[]) => {
  return render(
    <MemoryRouter>
      <ReviewComplete reviewedCount={reviewedCount} results={results} />
    </MemoryRouter>
  );
};

describe('ReviewComplete', () => {
  describe('完了メッセージ', () => {
    it('復習完了メッセージが表示される', () => {
      renderReviewComplete(5);
      expect(screen.getByText(/復習完了/)).toBeInTheDocument();
    });

    it('復習枚数が表示される', () => {
      renderReviewComplete(5);
      expect(screen.getByText(/5枚/)).toBeInTheDocument();
    });
  });

  describe('0枚復習（全スキップ）', () => {
    it('reviewedCount=0 の場合、0枚と表示される', () => {
      renderReviewComplete(0);
      expect(screen.getByText(/0枚/)).toBeInTheDocument();
    });
  });

  describe('ホームに戻るリンク', () => {
    it('「ホームに戻る」リンクが存在する', () => {
      renderReviewComplete(5);
      const link = screen.getByRole('link', { name: /ホームに戻る/ });
      expect(link).toBeInTheDocument();
    });

    it('リンク先が / である', () => {
      renderReviewComplete(5);
      const link = screen.getByRole('link', { name: /ホームに戻る/ });
      expect(link).toHaveAttribute('href', '/');
    });
  });

  describe('アクセシビリティ', () => {
    it('見出し要素が存在する', () => {
      renderReviewComplete(5);
      expect(screen.getByRole('heading')).toBeInTheDocument();
    });
  });

  describe('再確認カウント', () => {
    // 【テスト目的】: type='reconfirmed' のカードが gradedCount に正しく計上されることを確認
    // 【テスト内容】: graded + reconfirmed 混在時のカウント、results 表示
    // 【期待される動作】: ReviewComplete.tsx 20行目のフィルタが reconfirmed を含む
    // 🔵 受け入れ基準 TC-RC-001 ~ TC-RC-006 に対応

    describe('正常系', () => {
      it('type="reconfirmed" のカードが gradedCount に含まれる (TC-RC-001)', () => {
        // 【テストデータ準備】: graded 1枚 + reconfirmed 1枚 = 合計2枚
        const results: SessionCardResult[] = [
          { cardId: 'c1', front: 'Q1', grade: 4, type: 'graded', nextReviewDate: '2026-03-01' },
          { cardId: 'c2', front: 'Q2', grade: 1, type: 'reconfirmed', reconfirmResult: 'remembered' },
        ];
        // 【実際の処理実行】: graded + reconfirmed 混在でレンダリング
        renderReviewCompleteWithResults(2, results);

        // 【結果検証】: gradedCount = 2 が表示されること
        // 【検証項目】: ReviewComplete.tsx 20行目のフィルタ条件 (r.type === 'graded' || r.type === 'reconfirmed') 🔵
        expect(screen.getByText(/2枚/)).toBeInTheDocument();
      });

      it('graded + reconfirmed + skipped 混在時の正しい枚数表示 (TC-RC-002)', () => {
        // 【テストデータ準備】: 全4種類の type が混在するシナリオ
        const results: SessionCardResult[] = [
          { cardId: 'c1', front: 'Q1', grade: 4, type: 'graded', nextReviewDate: '2026-03-01' },
          { cardId: 'c2', front: 'Q2', grade: 1, type: 'reconfirmed', reconfirmResult: 'remembered' },
          { cardId: 'c3', front: 'Q3', type: 'skipped' },
          { cardId: 'c4', front: 'Q4', type: 'undone' },
        ];
        // 【実際の処理実行】: 全 type 混在でレンダリング
        renderReviewCompleteWithResults(4, results);

        // 【結果検証】: graded:1 + reconfirmed:1 = 2枚（skipped と undone は除外）
        // 【検証項目】: gradedCount のフィルタ条件で skipped, undone は除外される 🔵
        expect(screen.getByText(/2枚/)).toBeInTheDocument();
      });

      it('全カードが reconfirmed の場合に正しい枚数表示 (TC-RC-003)', () => {
        // 【テストデータ準備】: 全カードが再確認結果のシナリオ
        const results: SessionCardResult[] = [
          { cardId: 'c1', front: 'Q1', grade: 0, type: 'reconfirmed', reconfirmResult: 'remembered' },
          { cardId: 'c2', front: 'Q2', grade: 2, type: 'reconfirmed', reconfirmResult: 'remembered' },
        ];
        // 【実際の処理実行】: 全カード再確認結果でレンダリング
        renderReviewCompleteWithResults(2, results);

        // 【結果検証】: gradedCount = 2 が表示されること
        // 【検証項目】: reconfirmed のみでも正しくカウント 🟡
        expect(screen.getByText(/2枚/)).toBeInTheDocument();
      });

      it('results に reconfirmed カードが含まれる場合の結果リスト表示 (TC-RC-004)', () => {
        // 【テストデータ準備】: graded + reconfirmed の混在リスト
        const results: SessionCardResult[] = [
          { cardId: 'c1', front: '問題1', grade: 4, type: 'graded', nextReviewDate: '2026-03-01' },
          { cardId: 'c2', front: '問題2', grade: 1, type: 'reconfirmed', reconfirmResult: 'remembered' },
        ];
        // 【実際の処理実行】: 混在結果リストでレンダリング
        renderReviewCompleteWithResults(2, results);

        // 【結果検証】: 全カードが結果リストに表示されること
        // 【検証項目】: results.map で全カードが ReviewResultItem にマップされる 🔵
        expect(screen.getByText('問題1')).toBeInTheDocument();
        expect(screen.getByText('問題2')).toBeInTheDocument();
      });

      it('results が空の場合に reviewedCount のフォールバック表示 (TC-RC-005)', () => {
        // 【テストデータ準備】: results 未提供（旧コードとの互換性）
        renderReviewCompleteWithResults(3, []);

        // 【結果検証】: reviewedCount のフォールバック動作
        // 【検証項目】: gradedCount=0 → displayCount = reviewedCount = 3 🔵
        expect(screen.getByText(/3枚/)).toBeInTheDocument();
      });
    });

    describe('境界値', () => {
      it('全スキップで0枚表示 (TC-RC-006)', () => {
        // 【テストデータ準備】: 全カードをスキップした場合
        const results: SessionCardResult[] = [
          { cardId: 'c1', front: 'Q1', type: 'skipped' },
        ];
        // 【実際の処理実行】: reviewedCount=0, 全スキップ
        renderReviewCompleteWithResults(0, results);

        // 【結果検証】: gradedCount=0 → displayCount = reviewedCount = 0
        // 【検証項目】: 既存テスト（ReviewComplete.test.tsx 28-31行目）と同じパターン 🔵
        expect(screen.getByText(/0枚/)).toBeInTheDocument();
      });
    });
  });
});
