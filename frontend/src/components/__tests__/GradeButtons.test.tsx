import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GradeButtons } from '../GradeButtons';

const defaultProps = {
  onGrade: vi.fn(),
  onSkip: vi.fn(),
  disabled: false,
};

const renderGradeButtons = (props = {}) => {
  return render(<GradeButtons {...defaultProps} {...props} />);
};

describe('GradeButtons', () => {
  describe('ボタン表示', () => {
    it('0-5 の6つの採点ボタンが表示される', () => {
      renderGradeButtons();
      for (let i = 0; i <= 5; i++) {
        expect(screen.getByRole('button', { name: new RegExp(`${i}`) })).toBeInTheDocument();
      }
    });

    it('スキップボタンが表示される', () => {
      renderGradeButtons();
      expect(screen.getByRole('button', { name: /スキップ/ })).toBeInTheDocument();
    });
  });

  describe('採点ボタンクリック', () => {
    it('グレード0のボタンをクリックすると onGrade(0) が呼ばれる', async () => {
      const onGrade = vi.fn();
      renderGradeButtons({ onGrade });

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /^0/ }));

      expect(onGrade).toHaveBeenCalledWith(0);
    });

    it('グレード3のボタンをクリックすると onGrade(3) が呼ばれる', async () => {
      const onGrade = vi.fn();
      renderGradeButtons({ onGrade });

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /^3/ }));

      expect(onGrade).toHaveBeenCalledWith(3);
    });

    it('グレード5のボタンをクリックすると onGrade(5) が呼ばれる', async () => {
      const onGrade = vi.fn();
      renderGradeButtons({ onGrade });

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /^5/ }));

      expect(onGrade).toHaveBeenCalledWith(5);
    });
  });

  describe('スキップボタンクリック', () => {
    it('スキップボタンをクリックすると onSkip が呼ばれる', async () => {
      const onSkip = vi.fn();
      renderGradeButtons({ onSkip });

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /スキップ/ }));

      expect(onSkip).toHaveBeenCalledTimes(1);
    });
  });

  describe('disabled 状態', () => {
    it('disabled=true の場合、採点ボタンが無効化される', () => {
      renderGradeButtons({ disabled: true });
      for (let i = 0; i <= 5; i++) {
        expect(screen.getByRole('button', { name: new RegExp(`^${i}`) })).toBeDisabled();
      }
    });

    it('disabled=true の場合、スキップボタンも無効化される', () => {
      renderGradeButtons({ disabled: true });
      expect(screen.getByRole('button', { name: /スキップ/ })).toBeDisabled();
    });

    it('disabled=true の場合、クリックしても onGrade が呼ばれない', async () => {
      const onGrade = vi.fn();
      renderGradeButtons({ onGrade, disabled: true });

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /^3/ }));

      expect(onGrade).not.toHaveBeenCalled();
    });
  });

  describe('アクセシビリティ', () => {
    it('各採点ボタンに aria-label が設定されている', () => {
      renderGradeButtons();
      for (let i = 0; i <= 5; i++) {
        const button = screen.getByRole('button', { name: new RegExp(`^${i}`) });
        expect(button).toHaveAttribute('aria-label');
      }
    });
  });
});
