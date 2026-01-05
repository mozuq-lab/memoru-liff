/**
 * 【テスト概要】: ナビゲーションコンポーネントのテスト
 * 【テスト対象】: Navigation コンポーネント
 * 【テスト対応】: TASK-0014 テストケース4, 5
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Navigation } from '../Navigation';

const renderNavigation = (initialPath: string = '/') => {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Navigation />
    </MemoryRouter>
  );
};

describe('Navigation', () => {
  describe('ナビゲーションの表示', () => {
    it('ホームリンクが表示される', () => {
      renderNavigation();
      expect(screen.getByText('ホーム')).toBeInTheDocument();
    });

    it('作成リンクが表示される', () => {
      renderNavigation();
      expect(screen.getByText('作成')).toBeInTheDocument();
    });

    it('カードリンクが表示される', () => {
      renderNavigation();
      expect(screen.getByText('カード')).toBeInTheDocument();
    });

    it('設定リンクが表示される', () => {
      renderNavigation();
      expect(screen.getByText('設定')).toBeInTheDocument();
    });
  });

  describe('テストケース4: ナビゲーションのアクティブ状態', () => {
    it('ホームページでホームがアクティブ', () => {
      renderNavigation('/');
      const homeLink = screen.getByText('ホーム').closest('a');
      expect(homeLink).toHaveAttribute('aria-current', 'page');
      expect(homeLink).toHaveClass('text-blue-600');
    });

    it('生成ページで作成がアクティブ', () => {
      renderNavigation('/generate');
      const generateLink = screen.getByText('作成').closest('a');
      expect(generateLink).toHaveAttribute('aria-current', 'page');
      expect(generateLink).toHaveClass('text-blue-600');
    });

    it('カードページでカードがアクティブ', () => {
      renderNavigation('/cards');
      const cardsLink = screen.getByText('カード').closest('a');
      expect(cardsLink).toHaveAttribute('aria-current', 'page');
      expect(cardsLink).toHaveClass('text-blue-600');
    });

    it('設定ページで設定がアクティブ', () => {
      renderNavigation('/settings');
      const settingsLink = screen.getByText('設定').closest('a');
      expect(settingsLink).toHaveAttribute('aria-current', 'page');
      expect(settingsLink).toHaveClass('text-blue-600');
    });

    it('サブページでも親パスがアクティブ', () => {
      renderNavigation('/cards/123');
      const cardsLink = screen.getByText('カード').closest('a');
      expect(cardsLink).toHaveAttribute('aria-current', 'page');
    });
  });

  describe('テストケース5: ナビゲーションの画面遷移', () => {
    it('ホームリンクのパスが正しい', () => {
      renderNavigation();
      const homeLink = screen.getByText('ホーム').closest('a');
      expect(homeLink).toHaveAttribute('href', '/');
    });

    it('作成リンクのパスが正しい', () => {
      renderNavigation();
      const generateLink = screen.getByText('作成').closest('a');
      expect(generateLink).toHaveAttribute('href', '/generate');
    });

    it('カードリンクのパスが正しい', () => {
      renderNavigation();
      const cardsLink = screen.getByText('カード').closest('a');
      expect(cardsLink).toHaveAttribute('href', '/cards');
    });

    it('設定リンクのパスが正しい', () => {
      renderNavigation();
      const settingsLink = screen.getByText('設定').closest('a');
      expect(settingsLink).toHaveAttribute('href', '/settings');
    });
  });

  describe('アクセシビリティ', () => {
    it('ナビゲーションにrole属性がある', () => {
      renderNavigation();
      expect(screen.getByRole('navigation')).toBeInTheDocument();
    });

    it('ナビゲーションにaria-labelがある', () => {
      renderNavigation();
      expect(screen.getByLabelText('メインナビゲーション')).toBeInTheDocument();
    });

    it('各リンクが最小44pxのタップ領域を持つ', () => {
      renderNavigation();
      const links = screen.getAllByRole('link');
      links.forEach(link => {
        expect(link).toHaveClass('min-w-[44px]', 'min-h-[44px]');
      });
    });
  });
});
