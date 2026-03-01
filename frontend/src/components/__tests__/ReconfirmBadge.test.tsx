import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReconfirmBadge } from '../ReconfirmBadge';

describe('ReconfirmBadge', () => {
  // 【テスト目的】: ReconfirmBadge が「再確認」テキストのバッジを正しく表示することを確認
  // 【テスト内容】: テキスト内容、背景色、テキスト色、形状のスタイリング検証
  // 【期待される動作】: パラメータ不要のプレゼンテーションコンポーネントとして正しくレンダリング
  // 🔵 要件定義書 REQ-101 に対応

  describe('正常系', () => {
    it('「再確認」テキストが表示される (TC-RB-001)', () => {
      // 【実際の処理実行】: ReconfirmBadge をレンダリング
      render(<ReconfirmBadge />);

      // 【結果検証】: テキスト「再確認」がDOMに存在すること
      // 【検証項目】: バッジのテキスト内容が正確に「再確認」であること 🔵
      expect(screen.getByText('再確認')).toBeInTheDocument();
    });

    it('背景色 bg-blue-100 クラスが適用されている (TC-RB-002)', () => {
      // 【実際の処理実行】: ReconfirmBadge をレンダリング
      render(<ReconfirmBadge />);

      // 【結果検証】: バッジ要素に bg-blue-100 クラスが含まれること
      // 【検証項目】: reconfirm-ui-requirements.md セクション2.2「背景色: bg-blue-100」 🔵
      const badge = screen.getByText('再確認');
      expect(badge.className).toContain('bg-blue-100');
    });

    it('テキスト色 text-blue-700 クラスが適用されている (TC-RB-003)', () => {
      // 【実際の処理実行】: ReconfirmBadge をレンダリング
      render(<ReconfirmBadge />);

      // 【結果検証】: バッジ要素に text-blue-700 クラスが含まれること
      // 【検証項目】: reconfirm-ui-requirements.md セクション2.2「テキスト色: text-blue-700」 🔵
      const badge = screen.getByText('再確認');
      expect(badge.className).toContain('text-blue-700');
    });

    it('rounded-full（ピル型）クラスが適用されている (TC-RB-004)', () => {
      // 【実際の処理実行】: ReconfirmBadge をレンダリング
      render(<ReconfirmBadge />);

      // 【結果検証】: バッジ要素に rounded-full クラスが含まれること
      // 【検証項目】: reconfirm-ui-requirements.md セクション2.2「形状: rounded-full（ピル型）」 🔵
      const badge = screen.getByText('再確認');
      expect(badge.className).toContain('rounded-full');
    });

    it('ReconfirmBadge が named export でインポートできる (TC-RB-005)', () => {
      // 【実際の処理実行】: コンポーネントをレンダリングしてエラーが出ないことを確認
      // 【検証項目】: import { ReconfirmBadge } from '../ReconfirmBadge' が成功し、render() でエラーが出ない 🔵
      expect(ReconfirmBadge).toBeTruthy();
      expect(() => render(<ReconfirmBadge />)).not.toThrow();
    });
  });
});
