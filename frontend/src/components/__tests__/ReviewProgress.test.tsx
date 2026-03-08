import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReviewProgress } from '../ReviewProgress';

const renderReviewProgress = (current: number, total: number) => {
  return render(<ReviewProgress current={current} total={total} />);
};

describe('ReviewProgress', () => {
  describe('テキスト表示', () => {
    it('current/total 形式で表示される', () => {
      renderReviewProgress(3, 10);
      expect(screen.getByText('3 / 10')).toBeInTheDocument();
    });

    it('1枚目の場合 1/1 と表示される', () => {
      renderReviewProgress(1, 1);
      expect(screen.getByText('1 / 1')).toBeInTheDocument();
    });
  });

  describe('プログレスバー', () => {
    it('50% の場合、バーの幅が 50% になる', () => {
      renderReviewProgress(5, 10);
      const progressBar = screen.getByRole('progressbar');
      const innerBar = progressBar.firstElementChild;
      expect(innerBar).toHaveStyle({ width: '50%' });
    });

    it('100% の場合、バーの幅が 100% になる', () => {
      renderReviewProgress(1, 1);
      const progressBar = screen.getByRole('progressbar');
      const innerBar = progressBar.firstElementChild;
      expect(innerBar).toHaveStyle({ width: '100%' });
    });

    it('1/3 の場合、バーの幅が約 33% になる', () => {
      renderReviewProgress(1, 3);
      const progressBar = screen.getByRole('progressbar');
      const innerBar = progressBar.firstElementChild;
      expect(innerBar).toHaveStyle({ width: `${Math.round((1 / 3) * 100)}%` });
    });
  });

  describe('アクセシビリティ', () => {
    it('role="progressbar" が設定されている', () => {
      renderReviewProgress(3, 10);
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('aria-valuenow が設定されている', () => {
      renderReviewProgress(3, 10);
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '3');
    });

    it('aria-valuemin と aria-valuemax が設定されている', () => {
      renderReviewProgress(3, 10);
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '10');
    });
  });
});
