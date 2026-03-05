/**
 * 【テスト概要】: 参考情報表示コンポーネントのテスト
 * 【テスト対象】: ReferenceDisplay コンポーネント
 * 【テスト対応】: TASK-0159
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReferenceDisplay } from '../ReferenceDisplay';
import type { Reference } from '@/types/card';

const renderDisplay = (references: Reference[]) => {
  return render(<ReferenceDisplay references={references} />);
};

describe('ReferenceDisplay', () => {
  describe('空の参考情報', () => {
    it('references が空配列の場合は何もレンダリングしない', () => {
      const { container } = renderDisplay([]);

      expect(container.firstChild).toBeNull();
      expect(screen.queryByTestId('reference-display')).not.toBeInTheDocument();
    });
  });

  describe('URL タイプ', () => {
    it('URL がクリック可能なリンクとして表示される', () => {
      renderDisplay([{ type: 'url', value: 'https://example.com' }]);

      const link = screen.getByTestId('reference-display-link-0');
      expect(link).toBeInTheDocument();
      expect(link.tagName).toBe('A');
      expect(link).toHaveAttribute('href', 'https://example.com');
      expect(link).toHaveTextContent('https://example.com');
    });

    it('URL リンクが新しいタブで開く', () => {
      renderDisplay([{ type: 'url', value: 'https://example.com' }]);

      const link = screen.getByTestId('reference-display-link-0');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('javascript: スキームの URL はリンク化されずテキスト表示になる', () => {
      renderDisplay([{ type: 'url', value: 'javascript:alert(1)' }]);

      expect(screen.queryByTestId('reference-display-link-0')).not.toBeInTheDocument();
      const item = screen.getByTestId('reference-display-item-0');
      expect(item).toHaveTextContent('javascript:alert(1)');
    });

    it('http:// で始まる URL はリンク化される', () => {
      renderDisplay([{ type: 'url', value: 'http://example.com' }]);

      const link = screen.getByTestId('reference-display-link-0');
      expect(link).toHaveAttribute('href', 'http://example.com');
    });
  });

  describe('書籍タイプ', () => {
    it('book タイプがテキストとして表示される', () => {
      renderDisplay([{ type: 'book', value: 'テスト書籍名' }]);

      const item = screen.getByTestId('reference-display-item-0');
      expect(item).toHaveTextContent('テスト書籍名');
      expect(screen.queryByTestId('reference-display-link-0')).not.toBeInTheDocument();
    });
  });

  describe('メモタイプ', () => {
    it('note タイプがテキストとして表示される', () => {
      renderDisplay([{ type: 'note', value: 'テストメモ' }]);

      const item = screen.getByTestId('reference-display-item-0');
      expect(item).toHaveTextContent('テストメモ');
      expect(screen.queryByTestId('reference-display-link-0')).not.toBeInTheDocument();
    });
  });

  describe('複数の参考情報', () => {
    it('複数の参考情報が正しく表示される', () => {
      const references: Reference[] = [
        { type: 'url', value: 'https://example.com' },
        { type: 'book', value: 'テスト書籍' },
        { type: 'note', value: 'テストメモ' },
      ];
      renderDisplay(references);

      expect(screen.getByTestId('reference-display')).toBeInTheDocument();
      expect(screen.getByTestId('reference-display-item-0')).toBeInTheDocument();
      expect(screen.getByTestId('reference-display-item-1')).toBeInTheDocument();
      expect(screen.getByTestId('reference-display-item-2')).toBeInTheDocument();
    });

    it('ヘッダー「参考情報」が表示される', () => {
      renderDisplay([{ type: 'url', value: 'https://example.com' }]);

      expect(screen.getByText('参考情報')).toBeInTheDocument();
    });
  });
});
