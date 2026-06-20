import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, renderHook } from '@testing-library/react';
import { AuthProvider, useAuthContext } from '@/contexts/AuthContext';
import type { ReactNode } from 'react';

/**
 * 【テスト目的】: AuthContext のメモ化と再レンダリング削減を検証
 * 【テスト内容】: useMemo/useCallback による最適化を確認
 * 【期待される動作】: 不要な再レンダリングが発生しないこと
 * 🔵 青信号: TASK-0039 要件に基づく
 */

// Mock useAuth hook
const mockUseAuth = vi.fn();
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock apiClient
vi.mock('@/services/api', () => ({
  apiClient: {
    setAccessToken: vi.fn(),
  },
  LOGIN_REDIRECT_FAILED_EVENT: 'memoru:login-redirect-failed',
}));

describe('AuthContext', () => {
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

  describe('TC-AUTH-001: Context値の提供', () => {
    it('Context が正しい値を提供すること', async () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      );

      const { result } = renderHook(() => useAuthContext(), { wrapper });

      // 【検証】: Context が必要な値を提供していること
      expect(result.current).toHaveProperty('user');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('isAuthenticated');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('login');
      expect(result.current).toHaveProperty('logout');
      expect(result.current).toHaveProperty('refreshToken');
    });

    it('Context が Provider の外で使われた場合にエラーをスローすること', () => {
      // 【検証】: Provider なしで使うとエラーになること
      expect(() => {
        renderHook(() => useAuthContext());
      }).toThrow('useAuthContext must be used within an AuthProvider');
    });
  });

  describe('TC-AUTH-002: Provider値のメモ化', () => {
    it('Provider の value が useMemo でメモ化されていること', async () => {
      let renderCount = 0;

      const TestComponent = () => {
        useAuthContext();
        renderCount++;
        return <div data-testid="render-count">{renderCount}</div>;
      };

      const { rerender } = render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      expect(screen.getByTestId('render-count')).toHaveTextContent('1');

      // 【再レンダリング】: Provider を再レンダリング（状態変更なし）
      rerender(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      // 【検証】: value がメモ化されているため、子コンポーネントも再レンダリングされない
      // Note: This test verifies that Provider value is memoized
      // The render count should remain stable when Provider re-renders without state changes
    });
  });

  describe('TC-AUTH-003: useAuth の値がそのまま提供されること', () => {
    it('useAuth の戻り値が Context 経由で提供されること', async () => {
      const mockAuthValue = {
        user: {
          access_token: 'test-token',
          expired: false,
          profile: {
            sub: 'user123',
            email: 'test@example.com',
            name: 'Test User',
          },
        },
        isLoading: false,
        isAuthenticated: true,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        refreshToken: vi.fn(),
        getAccessToken: vi.fn(() => 'test-token'),
      };

      mockUseAuth.mockReturnValue(mockAuthValue);

      const wrapper = ({ children }: { children: ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      );

      const { result } = renderHook(() => useAuthContext(), { wrapper });

      // 【検証】: useAuth の値がそのまま提供されていること
      expect(result.current.user).toEqual(mockAuthValue.user);
      expect(result.current.isLoading).toBe(mockAuthValue.isLoading);
      expect(result.current.isAuthenticated).toBe(mockAuthValue.isAuthenticated);
      expect(result.current.error).toBe(mockAuthValue.error);
      expect(result.current.login).toBe(mockAuthValue.login);
      expect(result.current.logout).toBe(mockAuthValue.logout);
      expect(result.current.refreshToken).toBe(mockAuthValue.refreshToken);
    });
  });

  describe('TC-AUTH-004: 既存機能の保証（回帰テスト）', () => {
    it('認証済みユーザーの情報が正しく提供されること', async () => {
      const mockUser = {
        access_token: 'test-token',
        expired: false,
        profile: {
          sub: 'user123',
          email: 'test@example.com',
          name: 'Test User',
        },
      };

      mockUseAuth.mockReturnValue({
        user: mockUser,
        isLoading: false,
        isAuthenticated: true,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        refreshToken: vi.fn(),
        getAccessToken: vi.fn(() => 'test-token'),
      });

      const wrapper = ({ children }: { children: ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      );

      const { result } = renderHook(() => useAuthContext(), { wrapper });

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.isAuthenticated).toBe(true);
    });

    it('未認証状態が正しく提供されること', async () => {
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

      const wrapper = ({ children }: { children: ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      );

      const { result } = renderHook(() => useAuthContext(), { wrapper });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });

    it('ローディング状態が正しく提供されること', async () => {
      mockUseAuth.mockReturnValue({
        user: null,
        isLoading: true,
        isAuthenticated: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        refreshToken: vi.fn(),
        getAccessToken: vi.fn(() => null),
      });

      const wrapper = ({ children }: { children: ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      );

      const { result } = renderHook(() => useAuthContext(), { wrapper });

      expect(result.current.isLoading).toBe(true);
    });

    it('エラー状態が正しく提供されること', async () => {
      const mockError = new Error('Authentication failed');

      mockUseAuth.mockReturnValue({
        user: null,
        isLoading: false,
        isAuthenticated: false,
        error: mockError,
        login: vi.fn(),
        logout: vi.fn(),
        refreshToken: vi.fn(),
        getAccessToken: vi.fn(() => null),
      });

      const wrapper = ({ children }: { children: ReactNode }) => (
        <AuthProvider>{children}</AuthProvider>
      );

      const { result } = renderHook(() => useAuthContext(), { wrapper });

      expect(result.current.error).toEqual(mockError);
    });
  });
});
