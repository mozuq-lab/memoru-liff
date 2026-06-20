/**
 * 【テスト対象】: ProtectedRoute コンポーネント
 * 【テスト方針】: render中のlogin()呼び出しを防ぎ、useEffect内で1回のみ実行されることを確認
 * 【関連タスク】: TASK-0038
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { ProtectedRoute } from '../ProtectedRoute';
import { useAuthContext } from '@/contexts/AuthContext';

// Mock AuthContext
vi.mock('@/contexts/AuthContext', () => ({
  useAuthContext: vi.fn(),
}));

describe('ProtectedRoute', () => {
  const mockLogin = vi.fn();
  const mockUseAuthContext = useAuthContext as ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('認証済みユーザー', () => {
    it('children が表示されること', () => {
      // Arrange: 認証済み状態をモック
      mockUseAuthContext.mockReturnValue({
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: mockLogin,
        logout: vi.fn(),
        user: { access_token: 'token', expired: false, profile: { sub: '123' } },
        refreshToken: vi.fn(),
      });

      // Act: ProtectedRoute をレンダリング
      render(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      );

      // Assert: children が表示される
      expect(screen.getByText('Protected Content')).toBeInTheDocument();
      // login() が呼ばれないこと
      expect(mockLogin).not.toHaveBeenCalled();
    });
  });

  describe('Loading状態', () => {
    it('isLoading が true の場合、Loading コンポーネントが表示されること', () => {
      // Arrange: Loading 状態をモック
      mockUseAuthContext.mockReturnValue({
        isAuthenticated: false,
        isLoading: true,
        error: null,
        login: mockLogin,
        logout: vi.fn(),
        user: null,
        refreshToken: vi.fn(),
      });

      // Act: ProtectedRoute をレンダリング
      render(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      );

      // Assert: Loading メッセージが表示される
      expect(screen.getByText('認証中...')).toBeInTheDocument();
      // children は表示されない
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('未認証ユーザー - login()の呼び出し', () => {
    it('login() が useEffect 内で1回のみ呼ばれること', async () => {
      // Arrange: 未認証状態をモック (login成功を想定)
      mockLogin.mockResolvedValue(undefined);
      mockUseAuthContext.mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        error: null,
        login: mockLogin,
        logout: vi.fn(),
        user: null,
        refreshToken: vi.fn(),
      });

      // Act: ProtectedRoute をレンダリング
      render(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      );

      // Assert: login() が1回だけ呼ばれる
      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledTimes(1);
      });

      // 再レンダリングしても追加で呼ばれないことを確認
      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledTimes(1);
      }, { timeout: 500 });
    });

    it('未認証かつlogin試行中はLoadingが表示されること', async () => {
      // Arrange: 未認証状態をモック
      mockLogin.mockResolvedValue(undefined);
      mockUseAuthContext.mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        error: null,
        login: mockLogin,
        logout: vi.fn(),
        user: null,
        refreshToken: vi.fn(),
      });

      // Act: ProtectedRoute をレンダリング
      render(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      );

      // Assert: Loading が表示される
      expect(screen.getByText(/読み込み中.../)).toBeInTheDocument();
    });
  });

  describe('login() 失敗時', () => {
    // useAuth.login は失敗しても rethrow せず error state をセットする（P2）。
    // そのため ProtectedRoute は error 分岐でエラー画面へ倒す。
    it('認証エラー時にエラー画面が表示され、children が隠れること', () => {
      mockUseAuthContext.mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        error: new Error('Login failed'),
        login: mockLogin,
        logout: vi.fn(),
        user: null,
        refreshToken: vi.fn(),
      });

      render(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      );

      expect(screen.getByText('認証エラーが発生しました')).toBeInTheDocument();
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
      // error 分岐では自動ログインを試行しない
      expect(mockLogin).not.toHaveBeenCalled();
    });

    it('認証エラー時に再試行ボタンが表示されること', () => {
      // M-25 / P2: ログイン失敗時に無限ローディングへ陥らず、エラー画面と再試行手段を提供する。
      mockUseAuthContext.mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        error: new Error('Login failed'),
        login: mockLogin,
        logout: vi.fn(),
        user: null,
        refreshToken: vi.fn(),
      });

      render(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      );

      expect(screen.getByText('認証エラーが発生しました')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /再試行/ })).toBeInTheDocument();
    });

    it('リダイレクトが進まない場合、タイムアウト後にエラー画面へフォールバックすること', async () => {
      // P2: signinRedirect が無言で進まない（login が resolve も reject もしない）場合、
      // 8 秒のフォールバックタイマーでエラー画面へ倒れることを検証する。
      vi.useFakeTimers();
      try {
        mockLogin.mockReturnValue(new Promise<void>(() => {}));
        mockUseAuthContext.mockReturnValue({
          isAuthenticated: false,
          isLoading: false,
          error: null,
          login: mockLogin,
          logout: vi.fn(),
          user: null,
          refreshToken: vi.fn(),
        });

        render(
          <ProtectedRoute>
            <div>Protected Content</div>
          </ProtectedRoute>
        );

        // タイムアウト前はローディング表示
        expect(screen.getByText(/読み込み中/)).toBeInTheDocument();

        // 8 秒経過でフォールバックのエラー画面が出る
        await act(async () => {
          await vi.advanceTimersByTimeAsync(8000);
        });

        expect(screen.getByText(/時間をおいて再度お試しください/)).toBeInTheDocument();
      } finally {
        vi.useRealTimers();
      }
    });

    it('login 中に isLoading が変動してもフォールバックタイマーが維持されること', async () => {
      // P2 回帰: login() が setIsLoading(true) で isLoading を変えても、タイマーを
      // 解除せず 8 秒後にフォールバックが発火することを保証する（旧実装ではここで
      // タイマーが clearTimeout され、無限ローディングへ戻っていた）。
      vi.useFakeTimers();
      try {
        mockLogin.mockReturnValue(new Promise<void>(() => {}));
        const baseAuth = {
          isAuthenticated: false,
          error: null,
          login: mockLogin,
          logout: vi.fn(),
          user: null,
          refreshToken: vi.fn(),
        };
        mockUseAuthContext.mockReturnValue({ ...baseAuth, isLoading: false });
        const { rerender } = render(
          <ProtectedRoute>
            <div>Protected Content</div>
          </ProtectedRoute>
        );

        // login 開始で isLoading が true→false と変動する状況を再現
        mockUseAuthContext.mockReturnValue({ ...baseAuth, isLoading: true });
        rerender(<ProtectedRoute><div>Protected Content</div></ProtectedRoute>);
        mockUseAuthContext.mockReturnValue({ ...baseAuth, isLoading: false });
        rerender(<ProtectedRoute><div>Protected Content</div></ProtectedRoute>);

        await act(async () => {
          await vi.advanceTimersByTimeAsync(8000);
        });

        expect(screen.getByText(/時間をおいて再度お試しください/)).toBeInTheDocument();
      } finally {
        vi.useRealTimers();
      }
    });
  });

  describe('無限ループ防止', () => {
    it('login() が複数回レンダリングされても1回のみ呼ばれること', async () => {
      // Arrange: 未認証状態をモック
      mockLogin.mockResolvedValue(undefined);
      mockUseAuthContext.mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        error: null,
        login: mockLogin,
        logout: vi.fn(),
        user: null,
        refreshToken: vi.fn(),
      });

      // Act: ProtectedRoute をレンダリングして再レンダリング
      const { rerender } = render(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      );

      // 再レンダリングを実行
      rerender(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      );

      // Assert: login() が1回だけ呼ばれる
      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledTimes(1);
      });
    });
  });
});
