/**
 * 【テスト概要】: 参考情報編集コンポーネントのテスト
 * 【テスト対象】: ReferenceEditor コンポーネント
 * 【テスト対応】: TASK-0159
 */
import { useState } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReferenceEditor } from '../ReferenceEditor';
import type { Reference } from '@/types/card';

const defaultProps = {
  references: [] as Reference[],
  onChange: vi.fn(),
};

const renderEditor = (props = {}) => {
  return render(<ReferenceEditor {...defaultProps} {...props} />);
};

describe('ReferenceEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('初期表示', () => {
    it('参考情報がない場合、リストが表示されない', () => {
      renderEditor();

      expect(screen.queryByTestId('reference-list')).not.toBeInTheDocument();
    });

    it('参考情報がある場合、リストが表示される', () => {
      const references: Reference[] = [
        { type: 'url', value: 'https://example.com' },
        { type: 'book', value: 'テスト書籍' },
      ];
      renderEditor({ references });

      expect(screen.getByTestId('reference-list')).toBeInTheDocument();
      expect(screen.getByTestId('reference-item-0')).toHaveTextContent('https://example.com');
      expect(screen.getByTestId('reference-item-1')).toHaveTextContent('テスト書籍');
    });

    it('追加フォームが表示される', () => {
      renderEditor();

      expect(screen.getByTestId('reference-add-form')).toBeInTheDocument();
      expect(screen.getByTestId('reference-add-type')).toBeInTheDocument();
      expect(screen.getByTestId('reference-add-value')).toBeInTheDocument();
      expect(screen.getByTestId('reference-add-button')).toBeInTheDocument();
    });

    it('追加ボタンは入力が空の場合は無効', () => {
      renderEditor();

      expect(screen.getByTestId('reference-add-button')).toBeDisabled();
    });
  });

  describe('参考情報の追加', () => {
    it('値を入力して追加ボタンをクリックすると onChange が呼ばれる', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      renderEditor({ onChange });

      await user.type(screen.getByTestId('reference-add-value'), 'https://example.com');
      await user.click(screen.getByTestId('reference-add-button'));

      expect(onChange).toHaveBeenCalledWith([
        { type: 'url', value: 'https://example.com' },
      ]);
    });

    it('タイプを変更して追加できる', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      renderEditor({ onChange });

      await user.selectOptions(screen.getByTestId('reference-add-type'), 'book');
      await user.type(screen.getByTestId('reference-add-value'), 'テスト書籍');
      await user.click(screen.getByTestId('reference-add-button'));

      expect(onChange).toHaveBeenCalledWith([
        { type: 'book', value: 'テスト書籍' },
      ]);
    });

    it('追加後に入力フィールドがクリアされる', async () => {
      const user = userEvent.setup();
      renderEditor();

      await user.type(screen.getByTestId('reference-add-value'), 'テスト');
      await user.click(screen.getByTestId('reference-add-button'));

      expect(screen.getByTestId('reference-add-value')).toHaveValue('');
    });

    it('既存の参考情報がある場合、末尾に追加される', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const existing: Reference[] = [{ type: 'url', value: 'https://existing.com' }];
      renderEditor({ references: existing, onChange });

      await user.type(screen.getByTestId('reference-add-value'), '新しいメモ');
      await user.selectOptions(screen.getByTestId('reference-add-type'), 'note');
      await user.click(screen.getByTestId('reference-add-button'));

      expect(onChange).toHaveBeenCalledWith([
        { type: 'url', value: 'https://existing.com' },
        { type: 'note', value: '新しいメモ' },
      ]);
    });

    it('空白のみの入力では追加できない', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      renderEditor({ onChange });

      await user.type(screen.getByTestId('reference-add-value'), '   ');

      expect(screen.getByTestId('reference-add-button')).toBeDisabled();
    });
  });

  describe('参考情報の削除', () => {
    it('削除ボタンをクリックすると該当の参考情報が削除される', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const references: Reference[] = [
        { type: 'url', value: 'https://example.com' },
        { type: 'book', value: 'テスト書籍' },
      ];
      renderEditor({ references, onChange });

      await user.click(screen.getByTestId('reference-delete-0'));

      expect(onChange).toHaveBeenCalledWith([
        { type: 'book', value: 'テスト書籍' },
      ]);
    });

    it('最後の参考情報を削除すると空配列で onChange が呼ばれる', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const references: Reference[] = [{ type: 'note', value: 'メモ' }];
      renderEditor({ references, onChange });

      await user.click(screen.getByTestId('reference-delete-0'));

      expect(onChange).toHaveBeenCalledWith([]);
    });
  });

  describe('上限制御', () => {
    it('上限に達すると追加フォームが非表示になる', () => {
      const references: Reference[] = [
        { type: 'url', value: 'https://example1.com' },
        { type: 'url', value: 'https://example2.com' },
      ];
      renderEditor({ references, maxItems: 2 });

      expect(screen.queryByTestId('reference-add-form')).not.toBeInTheDocument();
      expect(screen.getByTestId('reference-max-message')).toBeInTheDocument();
    });

    it('上限以下では追加フォームが表示される', () => {
      const references: Reference[] = [
        { type: 'url', value: 'https://example.com' },
      ];
      renderEditor({ references, maxItems: 3 });

      expect(screen.getByTestId('reference-add-form')).toBeInTheDocument();
      expect(screen.queryByTestId('reference-max-message')).not.toBeInTheDocument();
    });
  });

  describe('タイプ選択', () => {
    it('デフォルトの追加タイプが URL になっている', () => {
      renderEditor();

      expect(screen.getByTestId('reference-add-type')).toHaveValue('url');
    });

    it('タイプセレクターに3つのオプションがある', () => {
      renderEditor();

      const select = screen.getByTestId('reference-add-type');
      const options = select.querySelectorAll('option');
      expect(options).toHaveLength(3);
      expect(options[0]).toHaveValue('url');
      expect(options[1]).toHaveValue('book');
      expect(options[2]).toHaveValue('note');
    });
  });

  describe('インライン編集', () => {
    it('参考情報をクリックすると編集モードになる', async () => {
      const user = userEvent.setup();
      const references: Reference[] = [
        { type: 'url', value: 'https://example.com' },
      ];
      renderEditor({ references });

      await user.click(screen.getByTestId('reference-item-0'));

      expect(screen.getByTestId('reference-edit-form-0')).toBeInTheDocument();
      expect(screen.getByTestId('reference-edit-value-0')).toHaveValue('https://example.com');
    });

    it('編集を保存すると onChange が呼ばれる', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const references: Reference[] = [
        { type: 'url', value: 'https://example.com' },
      ];
      renderEditor({ references, onChange });

      await user.click(screen.getByTestId('reference-item-0'));
      const input = screen.getByTestId('reference-edit-value-0');
      await user.clear(input);
      await user.type(input, 'https://updated.com');
      await user.click(screen.getByTestId('reference-edit-save-0'));

      expect(onChange).toHaveBeenCalledWith([
        { type: 'url', value: 'https://updated.com' },
      ]);
    });

    // 【回帰テスト】: 編集中に別の行を削除すると editingIndex がずれて
    // 保存時に別の行が編集内容で上書きされる問題（HIGH）の修正確認。
    // 親の state 更新を反映させるため、useState を持つラッパーで検証する。
    describe('編集中の行削除によるインデックスずれ', () => {
      const StatefulEditor = ({ initial }: { initial: Reference[] }) => {
        const [refs, setRefs] = useState<Reference[]>(initial);
        return <ReferenceEditor references={refs} onChange={setRefs} />;
      };

      const initialRefs: Reference[] = [
        { type: 'url', value: 'https://a.example.com' },
        { type: 'book', value: '書籍B' },
        { type: 'note', value: 'メモC' },
      ];

      it('[A,B,C] で C を編集開始 → A を削除 → 保存で C の位置が正しく更新される', async () => {
        const user = userEvent.setup();
        render(<StatefulEditor initial={initialRefs} />);

        // C（index 2）の編集を開始
        await user.click(screen.getByTestId('reference-item-2'));
        expect(screen.getByTestId('reference-edit-value-2')).toHaveValue('メモC');

        // A（index 0）を削除 → 編集対象 C は index 1 にずれる
        await user.click(screen.getByTestId('reference-delete-0'));

        // 編集フォームが C の新しい位置（index 1）に追従していること
        const editInput = screen.getByTestId('reference-edit-value-1');
        expect(editInput).toHaveValue('メモC');

        // 値を変更して保存
        await user.clear(editInput);
        await user.type(editInput, 'メモC更新');
        await user.click(screen.getByTestId('reference-edit-save-1'));

        // C の位置の要素だけが更新され、B は壊れないこと
        expect(screen.getByTestId('reference-item-0')).toHaveTextContent('書籍B');
        expect(screen.getByTestId('reference-item-1')).toHaveTextContent('メモC更新');
        expect(screen.queryByTestId('reference-item-2')).not.toBeInTheDocument();
      });

      it('編集中の行より後ろの行を削除しても編集位置は変わらない', async () => {
        const user = userEvent.setup();
        render(<StatefulEditor initial={initialRefs} />);

        // B（index 1）の編集を開始
        await user.click(screen.getByTestId('reference-item-1'));
        expect(screen.getByTestId('reference-edit-value-1')).toHaveValue('書籍B');

        // C（index 2）を削除 → 編集対象 B の位置は変わらない
        await user.click(screen.getByTestId('reference-delete-2'));

        const editInput = screen.getByTestId('reference-edit-value-1');
        expect(editInput).toHaveValue('書籍B');

        await user.clear(editInput);
        await user.type(editInput, '書籍B更新');
        await user.click(screen.getByTestId('reference-edit-save-1'));

        expect(screen.getByTestId('reference-item-0')).toHaveTextContent('https://a.example.com');
        expect(screen.getByTestId('reference-item-1')).toHaveTextContent('書籍B更新');
      });

    });

    it('編集をキャンセルすると元の表示に戻る', async () => {
      const user = userEvent.setup();
      const references: Reference[] = [
        { type: 'url', value: 'https://example.com' },
      ];
      renderEditor({ references });

      await user.click(screen.getByTestId('reference-item-0'));
      expect(screen.getByTestId('reference-edit-form-0')).toBeInTheDocument();

      await user.click(screen.getByTestId('reference-edit-cancel-0'));
      expect(screen.queryByTestId('reference-edit-form-0')).not.toBeInTheDocument();
      expect(screen.getByTestId('reference-item-0')).toBeInTheDocument();
    });
  });
});
