import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';

// 【テスト目的】: useAuthフックの認証状態管理機能を検証
// 【テスト内容】: 初期化、ログイン、ログアウト、エラー処理の動作確認
// 【期待される動作】: 認証状態が正しく管理され、UIに反映される
// 🔵 青信号: TASK-0012.md・architecture.mdに基づく

// authServiceのモック
const mockAuthService = {
  login: vi.fn(),
  logout: vi.fn(),
  getUser: vi.fn(),
  refreshToken: vi.fn(),
  handleCallback: vi.fn(),
  getAccessToken: vi.fn(),
  isAuthenticated: vi.fn(),
};

vi.mock('@/services/auth', () => ({
  authService: mockAuthService,
}));

describe('useAuth', () => {
  // 【テスト前準備】: 各テスト実行前にモックをリセット
  // 【環境初期化】: 独立したテスト環境を構築
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('TC-011: useAuth初期化', () => {
    it('初期化時に認証状態を確認する', async () => {
      // 【テストデータ準備】: 認証済みユーザーのモック
      // 【初期条件設定】: 既存のログインセッションがある状態
      const mockUser = {
        access_token: 'valid-token',
        expired: false,
        profile: {
          sub: 'user-123',
          email: 'user@example.com',
          name: 'Test User',
        },
      };
      mockAuthService.getUser.mockResolvedValue(mockUser);

      // 【実際の処理実行】: useAuthフックをレンダリング
      // 【処理内容】: 初期化時にauthService.getUser()を呼び出す
      const { useAuth } = await import('@/hooks/useAuth');
      const { result } = renderHook(() => useAuth());

      // 【結果検証】: 初期状態はローディング中
      // 【期待値確認】: isLoading初期値

      // 【検証項目】: 初期状態はisLoading=true
      // 🔵 青信号: 非同期初期化の標準パターン
      expect(result.current.isLoading).toBe(true);

      // 【結果検証】: 認証状態の確認完了を待機
      // 【期待値確認】: userが設定される
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 【検証項目】: 認証済み状態が正しく設定される
      // 🔵 青信号: セッション復元の仕様
      expect(result.current.user).toEqual(mockUser);
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.error).toBeNull();
    });
  });

  describe('TC-012: useAuth未認証状態', () => {
    it('未認証時はuser=null、isAuthenticated=false', async () => {
      // 【テストデータ準備】: ユーザーなしのモック
      // 【初期条件設定】: セッションが存在しない状態
      mockAuthService.getUser.mockResolvedValue(null);

      // 【実際の処理実行】: useAuthフックをレンダリング
      // 【処理内容】: 未認証状態の初期化
      const { useAuth } = await import('@/hooks/useAuth');
      const { result } = renderHook(() => useAuth());

      // 【結果検証】: 未認証状態が正しく反映される
      // 【期待値確認】: user=null, isAuthenticated=false
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 【検証項目】: 未認証状態の各プロパティ
      // 🔵 青信号: 未認証状態の正確な反映
      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBeNull();
    });
  });

  describe('TC-020: useAuth初期化エラー', () => {
    it('初期化時のエラーがerror状態に設定される', async () => {
      // 【テストデータ準備】: getUser()がエラーをスローするモック
      // 【初期条件設定】: 内部エラーが発生する状態
      const mockError = new Error('Failed to get user');
      mockAuthService.getUser.mockRejectedValue(mockError);

      // 【実際の処理実行】: useAuthフックをレンダリング
      // 【処理内容】: エラー発生時の状態管理
      const { useAuth } = await import('@/hooks/useAuth');
      const { result } = renderHook(() => useAuth());

      // 【結果検証】: エラー状態が正しく設定される
      // 【期待値確認】: error状態の設定
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 【検証項目】: エラー状態の各プロパティ
      // 🟡 黄信号: React Hooksのベストプラクティスから推測
      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toEqual(mockError);
    });
  });

  describe('login', () => {
    it('login()を呼び出すとauthService.login()が実行される', async () => {
      // 【テストデータ準備】: ユーザーなしの状態から開始
      // 【初期条件設定】: 未認証状態
      mockAuthService.getUser.mockResolvedValue(null);
      mockAuthService.login.mockResolvedValue(undefined);

      // 【実際の処理実行】: useAuthフックのlogin()を呼び出す
      // 【処理内容】: ログインフローの開始
      const { useAuth } = await import('@/hooks/useAuth');
      const { result } = renderHook(() => useAuth());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 【結果検証】: login()が呼び出されたことを確認
      // 【期待値確認】: authServiceへの委譲
      await act(async () => {
        await result.current.login();
      });

      // 【検証項目】: authService.login()が呼び出された
      // 🔵 青信号: ログインフローの仕様
      expect(mockAuthService.login).toHaveBeenCalledTimes(1);
    });

    it('login()エラー時にerror状態が設定される', async () => {
      // 【テストデータ準備】: login()がエラーをスローするモック
      // 【初期条件設定】: ログイン失敗の状態
      const loginError = new Error('Login failed');
      mockAuthService.getUser.mockResolvedValue(null);
      mockAuthService.login.mockRejectedValue(loginError);

      // 【実際の処理実行】: useAuthフックのlogin()を呼び出す
      // 【処理内容】: ログインエラーの処理
      const { useAuth } = await import('@/hooks/useAuth');
      const { result } = renderHook(() => useAuth());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 【結果検証】: エラー状態が設定される
      // 【期待値確認】: エラーハンドリング
      await act(async () => {
        await result.current.login();
      });

      // 【検証項目】: error状態が設定される
      // 🔵 青信号: エラーハンドリングの仕様
      expect(result.current.error).toEqual(loginError);
    });
  });

  describe('logout', () => {
    it('logout()を呼び出すとauthService.logout()が実行される', async () => {
      // 【テストデータ準備】: 認証済み状態から開始
      // 【初期条件設定】: ログイン済みの状態
      const mockUser = { access_token: 'token', expired: false };
      mockAuthService.getUser.mockResolvedValue(mockUser);
      mockAuthService.logout.mockResolvedValue(undefined);

      // 【実際の処理実行】: useAuthフックのlogout()を呼び出す
      // 【処理内容】: ログアウトフローの開始
      const { useAuth } = await import('@/hooks/useAuth');
      const { result } = renderHook(() => useAuth());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 【結果検証】: logout()が呼び出されたことを確認
      // 【期待値確認】: authServiceへの委譲
      await act(async () => {
        await result.current.logout();
      });

      // 【検証項目】: authService.logout()が呼び出された
      // 🔵 青信号: ログアウトフローの仕様
      expect(mockAuthService.logout).toHaveBeenCalledTimes(1);

      // 【検証項目】: userがnullになる
      // 🔵 青信号: ログアウト後の状態
      expect(result.current.user).toBeNull();
    });
  });

  describe('refreshToken', () => {
    it('refreshToken()を呼び出すとauthService.refreshToken()が実行される', async () => {
      // 【テストデータ準備】: 認証済み状態から開始
      // 【初期条件設定】: トークンリフレッシュ可能な状態
      const mockUser = { access_token: 'old-token', expired: false };
      const refreshedUser = { access_token: 'new-token', expired: false };
      mockAuthService.getUser
        .mockResolvedValueOnce(mockUser)
        .mockResolvedValueOnce(refreshedUser);
      mockAuthService.refreshToken.mockResolvedValue(undefined);

      // 【実際の処理実行】: useAuthフックのrefreshToken()を呼び出す
      // 【処理内容】: トークンリフレッシュの実行
      const { useAuth } = await import('@/hooks/useAuth');
      const { result } = renderHook(() => useAuth());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 【結果検証】: refreshToken()が呼び出されたことを確認
      // 【期待値確認】: authServiceへの委譲
      await act(async () => {
        await result.current.refreshToken();
      });

      // 【検証項目】: authService.refreshToken()が呼び出された
      // 🔵 青信号: トークンリフレッシュの仕様
      expect(mockAuthService.refreshToken).toHaveBeenCalledTimes(1);
    });

    it('refreshToken()エラー時にerror状態が設定される', async () => {
      // 【テストデータ準備】: refreshToken()がエラーをスローするモック
      // 【初期条件設定】: リフレッシュ失敗の状態
      const mockUser = { access_token: 'token', expired: false };
      const refreshError = new Error('Refresh failed');
      mockAuthService.getUser.mockResolvedValue(mockUser);
      mockAuthService.refreshToken.mockRejectedValue(refreshError);

      // 【実際の処理実行】: useAuthフックのrefreshToken()を呼び出す
      // 【処理内容】: リフレッシュエラーの処理
      const { useAuth } = await import('@/hooks/useAuth');
      const { result } = renderHook(() => useAuth());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 【結果検証】: エラー状態が設定される
      // 【期待値確認】: エラーハンドリング
      await act(async () => {
        await result.current.refreshToken();
      });

      // 【検証項目】: error状態が設定される
      // 🔵 青信号: エラーハンドリングの仕様
      expect(result.current.error).toEqual(refreshError);
    });
  });

  describe('getAccessToken', () => {
    it('getAccessToken()でアクセストークンを取得できる', async () => {
      // 【テストデータ準備】: 認証済み状態
      // 【初期条件設定】: 有効なアクセストークンがある状態
      const mockUser = {
        access_token: 'jwt-access-token',
        expired: false,
      };
      mockAuthService.getUser.mockResolvedValue(mockUser);

      // 【実際の処理実行】: useAuthフックのgetAccessToken()を呼び出す
      // 【処理内容】: アクセストークンの取得
      const { useAuth } = await import('@/hooks/useAuth');
      const { result } = renderHook(() => useAuth());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 【結果検証】: アクセストークンが返される
      // 【期待値確認】: JWT形式のトークン
      const token = result.current.getAccessToken();

      // 【検証項目】: アクセストークンが正しく取得される
      // 🔵 青信号: トークン取得の仕様
      expect(token).toBe('jwt-access-token');
    });

    it('未認証時はnullを返す', async () => {
      // 【テストデータ準備】: 未認証状態
      // 【初期条件設定】: ユーザーが存在しない状態
      mockAuthService.getUser.mockResolvedValue(null);

      // 【実際の処理実行】: useAuthフックのgetAccessToken()を呼び出す
      // 【処理内容】: 未認証時のトークン取得
      const { useAuth } = await import('@/hooks/useAuth');
      const { result } = renderHook(() => useAuth());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 【結果検証】: nullが返される
      // 【期待値確認】: 未認証時のフォールバック
      const token = result.current.getAccessToken();

      // 【検証項目】: 未認証時はnullを返す
      // 🔵 青信号: 未認証時の動作仕様
      expect(token).toBeNull();
    });
  });
});
