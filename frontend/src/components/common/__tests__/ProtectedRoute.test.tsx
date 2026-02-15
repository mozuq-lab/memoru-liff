/**
 * 【テスト対象】: ProtectedRoute コンポーネント
 * 【テスト方針】: render中のlogin()呼び出しを防ぎ、useEffect内で1回のみ実行されることを確認
 * 【関連タスク】: TASK-0038
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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
    it('login() 失敗時にエラー画面が表示されること', async () => {
      // Arrange: login失敗をモック
      const loginError = new Error('Login failed');
      mockLogin.mockRejectedValue(loginError);
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

      // Assert: エラーメッセージが表示される
      await waitFor(() => {
        expect(screen.getByText('ログインに失敗しました')).toBeInTheDocument();
      });

      // children は表示されない
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });

    it('login() 失敗後、再試行ボタンが表示されないこと', async () => {
      // Arrange: login失敗をモック
      const loginError = new Error('Login failed');
      mockLogin.mockRejectedValue(loginError);
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

      // Assert: エラーメッセージが表示される
      await waitFor(() => {
        expect(screen.getByText('ログインに失敗しました')).toBeInTheDocument();
      });

      // 再試行ボタンが表示されないこと
      expect(screen.queryByRole('button', { name: /再試行/ })).not.toBeInTheDocument();
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
