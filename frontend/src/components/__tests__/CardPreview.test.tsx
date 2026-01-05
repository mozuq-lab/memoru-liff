/**
 * 【テスト概要】: カードプレビューコンポーネントのテスト
 * 【テスト対象】: CardPreview コンポーネント
 * 【テスト対応】: TASK-0015 テストケース6, 7
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CardPreview } from '../CardPreview';
import type { GeneratedCardWithId } from '@/types';

const mockCard: GeneratedCardWithId = {
  tempId: 'test-id-1',
  front: 'テスト質問',
  back: 'テスト回答',
  suggested_tags: ['tag1', 'tag2'],
};

describe('CardPreview', () => {
  describe('プレビュー表示', () => {
    it('カードの表面が表示される', () => {
      render(
        <CardPreview
          card={mockCard}
          isSelected={false}
          onToggle={() => {}}
          onEdit={() => {}}
        />
      );

      expect(screen.getByTestId('card-front')).toHaveTextContent('テスト質問');
    });

    it('カードの裏面が表示される', () => {
      render(
        <CardPreview
          card={mockCard}
          isSelected={false}
          onToggle={() => {}}
          onEdit={() => {}}
        />
      );

      expect(screen.getByTestId('card-back')).toHaveTextContent('テスト回答');
    });
  });

  describe('選択状態', () => {
    it('選択時にチェックマークが表示される', () => {
      render(
        <CardPreview
          card={mockCard}
          isSelected={true}
          onToggle={() => {}}
          onEdit={() => {}}
        />
      );

      const toggleButton = screen.getByTestId('toggle-select');
      expect(toggleButton).toHaveClass('bg-blue-500');
    });

    it('未選択時はチェックマークが表示されない', () => {
      render(
        <CardPreview
          card={mockCard}
          isSelected={false}
          onToggle={() => {}}
          onEdit={() => {}}
        />
      );

      const toggleButton = screen.getByTestId('toggle-select');
      expect(toggleButton).not.toHaveClass('bg-blue-500');
    });

    it('トグルボタンクリックでonToggleが呼ばれる', async () => {
      const user = userEvent.setup();
      const mockOnToggle = vi.fn();

      render(
        <CardPreview
          card={mockCard}
          isSelected={false}
          onToggle={mockOnToggle}
          onEdit={() => {}}
        />
      );

      await user.click(screen.getByTestId('toggle-select'));
      expect(mockOnToggle).toHaveBeenCalled();
    });
  });

  describe('編集モード', () => {
    it('編集ボタンをクリックすると編集モードに切り替わる', async () => {
      const user = userEvent.setup();

      render(
        <CardPreview
          card={mockCard}
          isSelected={false}
          onToggle={() => {}}
          onEdit={() => {}}
        />
      );

      await user.click(screen.getByTestId('edit-button'));

      expect(screen.getByTestId('edit-front')).toBeInTheDocument();
      expect(screen.getByTestId('edit-back')).toBeInTheDocument();
    });

    it('編集モードでは現在の値が入力欄に表示される', async () => {
      const user = userEvent.setup();

      render(
        <CardPreview
          card={mockCard}
          isSelected={false}
          onToggle={() => {}}
          onEdit={() => {}}
        />
      );

      await user.click(screen.getByTestId('edit-button'));

      expect(screen.getByTestId('edit-front')).toHaveValue('テスト質問');
      expect(screen.getByTestId('edit-back')).toHaveValue('テスト回答');
    });

    it('保存ボタンでonEditが呼ばれる', async () => {
      const user = userEvent.setup();
      const mockOnEdit = vi.fn();

      render(
        <CardPreview
          card={mockCard}
          isSelected={false}
          onToggle={() => {}}
          onEdit={mockOnEdit}
        />
      );

      await user.click(screen.getByTestId('edit-button'));

      const frontInput = screen.getByTestId('edit-front');
      await user.clear(frontInput);
      await user.type(frontInput, '新しい質問');

      await user.click(screen.getByTestId('save-edit'));

      expect(mockOnEdit).toHaveBeenCalledWith('新しい質問', 'テスト回答');
    });

    it('キャンセルボタンで編集内容が破棄される', async () => {
      const user = userEvent.setup();

      render(
        <CardPreview
          card={mockCard}
          isSelected={false}
          onToggle={() => {}}
          onEdit={() => {}}
        />
      );

      await user.click(screen.getByTestId('edit-button'));

      const frontInput = screen.getByTestId('edit-front');
      await user.clear(frontInput);
      await user.type(frontInput, '新しい質問');

      await user.click(screen.getByTestId('cancel-edit'));

      // プレビューモードに戻り、元の値が表示される
      expect(screen.getByTestId('card-front')).toHaveTextContent('テスト質問');
    });
  });

  describe('アクセシビリティ', () => {
    it('選択ボタンにaria-labelがある', () => {
      render(
        <CardPreview
          card={mockCard}
          isSelected={false}
          onToggle={() => {}}
          onEdit={() => {}}
        />
      );

      expect(screen.getByLabelText('カードを選択')).toBeInTheDocument();
    });

    it('編集ボタンにaria-labelがある', () => {
      render(
        <CardPreview
          card={mockCard}
          isSelected={false}
          onToggle={() => {}}
          onEdit={() => {}}
        />
      );

      expect(screen.getByLabelText('カードを編集')).toBeInTheDocument();
    });

    it('編集ボタンが最小44pxのタップ領域を持つ', () => {
      render(
        <CardPreview
          card={mockCard}
          isSelected={false}
          onToggle={() => {}}
          onEdit={() => {}}
        />
      );

      const editButton = screen.getByTestId('edit-button');
      expect(editButton).toHaveClass('min-w-[44px]', 'min-h-[44px]');
    });
  });
});
