import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ReviewComplete } from '../ReviewComplete';

const renderReviewComplete = (reviewedCount: number) => {
  return render(
    <MemoryRouter>
      <ReviewComplete reviewedCount={reviewedCount} />
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
});
