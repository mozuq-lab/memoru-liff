import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FlipCard } from '../FlipCard';

const defaultProps = {
  front: '質問テキスト',
  back: '解答テキスト',
  isFlipped: false,
  onFlip: vi.fn(),
};

const renderFlipCard = (props = {}) => {
  return render(<FlipCard {...defaultProps} {...props} />);
};

describe('FlipCard', () => {
  describe('表面表示', () => {
    it('isFlipped=false の場合、表面テキストが表示される', () => {
      renderFlipCard({ isFlipped: false });
      expect(screen.getByText('質問テキスト')).toBeInTheDocument();
    });

    it('isFlipped=false の場合、裏面テキストも DOM に存在する（非表示）', () => {
      renderFlipCard({ isFlipped: false });
      expect(screen.getByText('解答テキスト')).toBeInTheDocument();
    });
  });

  describe('裏面表示', () => {
    it('isFlipped=true の場合、裏面テキストが表示される', () => {
      renderFlipCard({ isFlipped: true });
      expect(screen.getByText('解答テキスト')).toBeInTheDocument();
    });
  });

  describe('フリップ操作', () => {
    it('カードをクリックすると onFlip が呼ばれる', async () => {
      const onFlip = vi.fn();
      renderFlipCard({ onFlip });

      const user = userEvent.setup();
      await user.click(screen.getByRole('button'));

      expect(onFlip).toHaveBeenCalledTimes(1);
    });

    it('Enter キーで onFlip が呼ばれる', async () => {
      const onFlip = vi.fn();
      renderFlipCard({ onFlip });

      const user = userEvent.setup();
      screen.getByRole('button').focus();
      await user.keyboard('{Enter}');

      expect(onFlip).toHaveBeenCalled();
    });

    it('Space キーで onFlip が呼ばれる', async () => {
      const onFlip = vi.fn();
      renderFlipCard({ onFlip });

      const user = userEvent.setup();
      screen.getByRole('button').focus();
      await user.keyboard(' ');

      expect(onFlip).toHaveBeenCalled();
    });

    it('他のキーでは onFlip が呼ばれない', async () => {
      const onFlip = vi.fn();
      renderFlipCard({ onFlip });

      const user = userEvent.setup();
      screen.getByRole('button').focus();
      await user.keyboard('a');

      // click from focus + keyboard interaction, but not from 'a' key handler
      // onFlip should not be called from onKeyDown for 'a'
      expect(onFlip).not.toHaveBeenCalled();
    });
  });

  describe('CSS クラス', () => {
    it('isFlipped=false の場合、flipped クラスが適用されない', () => {
      const { container } = renderFlipCard({ isFlipped: false });
      const inner = container.querySelector('.flip-card-inner');
      expect(inner).not.toHaveClass('flipped');
    });

    it('isFlipped=true の場合、flipped クラスが適用される', () => {
      const { container } = renderFlipCard({ isFlipped: true });
      const inner = container.querySelector('.flip-card-inner');
      expect(inner).toHaveClass('flipped');
    });
  });

  describe('アクセシビリティ', () => {
    it('role="button" が設定されている', () => {
      renderFlipCard();
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('aria-label が設定されている', () => {
      renderFlipCard({ isFlipped: false });
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label');
    });
  });
});
