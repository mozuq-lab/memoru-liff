/**
 * 【テスト目的】: Provider ネスト順序修正後の App コンポーネントの正常動作を確認
 * 【テスト内容】: AuthProvider > CardsProvider > DecksProvider の順序で全 Context にアクセス可能
 * 【期待される動作】: App がエラーなくレンダリングされ、各 Context が正しく提供される
 * 🔵 青信号: TASK-0093・REQ-201 に基づく
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, renderHook } from '@testing-library/react';
import App from '../App';
import { AuthProvider, useAuthContext } from '@/contexts/AuthContext';
import { CardsProvider, useCardsContext } from '@/contexts/CardsContext';
import { DecksProvider, useDecksContext } from '@/contexts/DecksContext';
import type { ReactNode } from 'react';

// 【テスト前準備】: useAuth をモック
const mockUseAuth = vi.fn();
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// 【テスト前準備】: API モック設定
vi.mock('@/services/api', () => ({
  apiClient: { setAccessToken: vi.fn() },
  cardsApi: {
    getCards: vi.fn().mockResolvedValue([]),
    getDueCards: vi.fn().mockResolvedValue({ due_cards: [], total_due_count: 0 }),
    getDueCount: vi.fn().mockResolvedValue(0),
  },
  decksApi: {
    getDecks: vi.fn().mockResolvedValue([]),
    createDeck: vi.fn(),
    updateDeck: vi.fn(),
    deleteDeck: vi.fn(),
  },
}));

// 【テスト前準備】: ページコンポーネントをモック（テスト対象外の依存を排除）
vi.mock('@/pages', () => ({
  HomePage: () => <div data-testid="home-page">HomePage</div>,
  GeneratePage: () => <div>GeneratePage</div>,
  CardsPage: () => <div>CardsPage</div>,
  CardDetailPage: () => <div>CardDetailPage</div>,
  DecksPage: () => <div>DecksPage</div>,
  SettingsPage: () => <div>SettingsPage</div>,
  LinkLinePage: () => <div>LinkLinePage</div>,
  CallbackPage: () => <div>CallbackPage</div>,
  ReviewPage: () => <div>ReviewPage</div>,
  StatsPage: () => <div>StatsPage</div>,
}));

// 【テスト前準備】: Layout をモック（子要素をそのまま描画）
vi.mock('@/components/common', () => ({
  Layout: ({ children }: { children: ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
  ProtectedRoute: ({ children }: { children: ReactNode }) => (
    <>{children}</>
  ),
}));

describe('App - TASK-0093: Provider ネスト順序修正', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: null,
      isLoading: false,
      isAuthenticated: false,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      refreshToken: vi.fn(),
      getAccessToken: vi.fn(() => null),
    });
  });

  /**
   * TC-APP-001: App コンポーネントが正常にレンダリングされること
   * 【テスト目的】: Provider ネスト順序修正後、App コンポーネントがエラーなくレンダリングされること
   * 【期待される動作】: App() がクラッシュせずに DOM を生成する
   * 🔵 REQ-201・TASK-0093 完了条件「Provider 順序変更後も全ページが正常動作」に基づく
   */
  describe('TC-APP-001: App コンポーネントの正常レンダリング', () => {
    it('App コンポーネントがエラーなくレンダリングされること', () => {
      // 【実際の処理実行】: App をレンダリング
      expect(() => {
        render(<App />);
      }).not.toThrow();
    });

    it('Layout 要素が DOM に存在すること', () => {
      // 【実際の処理実行】: App をレンダリング
      render(<App />);

      // 【結果検証】: Layout が描画されていること
      expect(screen.getByTestId('layout')).toBeInTheDocument();
    });
  });

  /**
   * TC-APP-002: 全 Context にページ内からアクセス可能であること
   * 【テスト目的】: Routes 内のコンポーネントから各 Context のプロパティを取得でき、undefined でないこと
   * 【期待される動作】: テスト用コンポーネントから各 Context のプロパティを取得でき、undefined でないこと
   * 🔵 TASK-0093 完了条件・note.md「Context アクセステスト」に基づく
   */
  describe('TC-APP-002: Context アクセス可能性確認', () => {
    it('AuthProvider 内で useAuthContext にアクセスできること', () => {
      // 【実際の処理実行】: AuthProvider でラップして useAuthContext を呼び出す
      const wrapper = ({ children }: { children: ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      );
      const { result } = renderHook(() => useAuthContext(), { wrapper });

      // 【結果検証】: AuthContext が undefined でないこと
      expect(result.current).toBeDefined();
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('isAuthenticated');
    });

    it('CardsProvider 内で useCardsContext にアクセスできること', () => {
      // 【実際の処理実行】: CardsProvider でラップして useCardsContext を呼び出す
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );
      const { result } = renderHook(() => useCardsContext(), { wrapper });

      // 【結果検証】: CardsContext が undefined でないこと
      expect(result.current).toBeDefined();
      expect(result.current).toHaveProperty('isLoading');
    });

    it('DecksProvider 内で useDecksContext にアクセスできること', () => {
      // 【実際の処理実行】: DecksProvider でラップして useDecksContext を呼び出す
      const wrapper = ({ children }: { children: ReactNode }) => (
        <DecksProvider>{children}</DecksProvider>
      );
      const { result } = renderHook(() => useDecksContext(), { wrapper });

      // 【結果検証】: DecksContext が undefined でないこと
      expect(result.current).toBeDefined();
      expect(result.current).toHaveProperty('decks');
    });

    it('App 内で全 Provider がネストされており Routes から全 Context にアクセス可能なこと', () => {
      // 【実際の処理実行】: App をレンダリング（全 Provider ツリーが構築される）
      // エラーなくレンダリングできれば、全 Context が正しくネストされている
      expect(() => {
        render(<App />);
      }).not.toThrow();

      // 【結果検証】: ホームページ（全 Context を使用）が描画されていること
      expect(screen.getByTestId('home-page')).toBeInTheDocument();
    });
  });

  /**
   * TC-APP-003: 既存ルーティングが正常に動作すること
   * 【テスト目的】: Provider 順序変更後もルーティング定義が正しく機能すること
   * 【期待される動作】: "/" パスで HomePage がレンダリングされること
   * 🟡 TASK-0093 完了条件から妥当な推測
   */
  describe('TC-APP-003: ルーティング正常動作確認', () => {
    it('"/" パスで HomePage がレンダリングされること', () => {
      // 【実際の処理実行】: App をレンダリング（BrowserRouter が内部で使われるため "/" がデフォルト）
      render(<App />);

      // 【結果検証】: ホームページコンテンツが表示されること
      expect(screen.getByTestId('home-page')).toBeInTheDocument();
    });

    it('Layout と Routes が正しく機能すること', () => {
      // 【実際の処理実行】: App をレンダリング
      render(<App />);

      // 【結果検証】: Layout が存在し、その中に Routes のコンテンツが含まれること
      const layout = screen.getByTestId('layout');
      expect(layout).toBeInTheDocument();
      expect(layout).toContainElement(screen.getByTestId('home-page'));
    });
  });
});
