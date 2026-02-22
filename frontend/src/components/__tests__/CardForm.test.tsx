/**
 * 【テスト概要】: カード編集フォームコンポーネントのテスト
 * 【テスト対象】: CardForm コンポーネント
 * 【テスト対応】: TASK-0017 テストケース2〜5
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CardForm } from '../CardForm';

const defaultProps = {
  initialFront: '元の質問',
  initialBack: '元の回答',
  onSave: vi.fn(),
  onCancel: vi.fn(),
  isSaving: false,
};

const renderCardForm = (props = {}) => {
  return render(<CardForm {...defaultProps} {...props} />);
};

describe('CardForm', () => {
  describe('初期表示', () => {
    it('初期値が表示される', () => {
      renderCardForm();

      expect(screen.getByTestId('input-front')).toHaveValue('元の質問');
      expect(screen.getByTestId('input-back')).toHaveValue('元の回答');
    });

    it('フォームが表示される', () => {
      renderCardForm();

      expect(screen.getByTestId('card-form')).toBeInTheDocument();
    });

    it('ラベルが表示される', () => {
      renderCardForm();

      expect(screen.getByLabelText('表面（質問）')).toBeInTheDocument();
      expect(screen.getByLabelText('裏面（解答）')).toBeInTheDocument();
    });
  });

  describe('バリデーション', () => {
    it('変更がない場合、保存ボタンは無効', () => {
      renderCardForm();

      const saveButton = screen.getByTestId('save-button');
      expect(saveButton).toBeDisabled();
    });

    it('表面が空の場合、保存ボタンは無効', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);

      const saveButton = screen.getByTestId('save-button');
      expect(saveButton).toBeDisabled();
    });

    it('裏面が空の場合、保存ボタンは無効', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const backInput = screen.getByTestId('input-back');
      await user.clear(backInput);

      const saveButton = screen.getByTestId('save-button');
      expect(saveButton).toBeDisabled();
    });

    it('両方が空白のみの場合、保存ボタンは無効', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const frontInput = screen.getByTestId('input-front');
      const backInput = screen.getByTestId('input-back');

      await user.clear(frontInput);
      await user.type(frontInput, '   ');
      await user.clear(backInput);
      await user.type(backInput, '   ');

      const saveButton = screen.getByTestId('save-button');
      expect(saveButton).toBeDisabled();
    });

    it('変更があり両方に値がある場合、保存ボタンは有効', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '新しい質問');

      const saveButton = screen.getByTestId('save-button');
      expect(saveButton).toBeEnabled();
    });
  });

  describe('保存', () => {
    it('保存ボタンクリックでonSaveが呼ばれる', async () => {
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue(undefined);
      renderCardForm({ onSave });

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '新しい質問');

      const saveButton = screen.getByTestId('save-button');
      await user.click(saveButton);

      expect(onSave).toHaveBeenCalledWith('新しい質問', '元の回答');
    });

    it('保存中はボタンに「保存中...」と表示される', () => {
      renderCardForm({ isSaving: true });

      expect(screen.getByTestId('save-button')).toHaveTextContent('保存中...');
    });

    it('保存中は入力フィールドが無効化される', () => {
      renderCardForm({ isSaving: true });

      expect(screen.getByTestId('input-front')).toBeDisabled();
      expect(screen.getByTestId('input-back')).toBeDisabled();
    });

    it('保存中はキャンセルボタンが無効化される', () => {
      renderCardForm({ isSaving: true });

      expect(screen.getByTestId('cancel-button')).toBeDisabled();
    });

    it('値の前後の空白はトリムされる', async () => {
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue(undefined);
      renderCardForm({ onSave });

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '  新しい質問  ');

      const saveButton = screen.getByTestId('save-button');
      await user.click(saveButton);

      expect(onSave).toHaveBeenCalledWith('新しい質問', '元の回答');
    });
  });

  describe('キャンセル', () => {
    it('キャンセルボタンクリックでonCancelが呼ばれる', async () => {
      const user = userEvent.setup();
      const onCancel = vi.fn();
      renderCardForm({ onCancel });

      const cancelButton = screen.getByTestId('cancel-button');
      await user.click(cancelButton);

      expect(onCancel).toHaveBeenCalled();
    });
  });

  describe('入力操作', () => {
    it('表面のテキストを変更できる', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, 'テスト質問');

      expect(frontInput).toHaveValue('テスト質問');
    });

    it('裏面のテキストを変更できる', async () => {
      const user = userEvent.setup();
      renderCardForm();

      const backInput = screen.getByTestId('input-back');
      await user.clear(backInput);
      await user.type(backInput, 'テスト回答');

      expect(backInput).toHaveValue('テスト回答');
    });
  });
});
