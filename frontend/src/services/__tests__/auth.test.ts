import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// 【テスト目的】: AuthServiceのPKCE認証フローとトークン管理の動作確認
// 【テスト内容】: login, handleCallback, getUser, logout, refreshTokenの各メソッドを検証
// 【期待される動作】: Keycloak OIDCとの連携が正しく動作すること
// 🔵 青信号: 要件定義2.3データフロー・TASK-0012.mdに基づく

// 【モック設定】: UserManagerのモックメソッド
// 🔵 青信号: oidc-client-ts標準のUserManager API
const mockSigninRedirect = vi.fn();
const mockSigninRedirectCallback = vi.fn();
const mockSigninSilent = vi.fn();
const mockSignoutRedirect = vi.fn();
const mockGetUser = vi.fn();
const mockAddAccessTokenExpiring = vi.fn();
const mockAddUserSignedOut = vi.fn();

// 【モッククラス定義】: UserManagerをクラスとしてモック
// 🔵 青信号: oidc-client-ts標準のUserManager構造
class MockUserManager {
  signinRedirect = mockSigninRedirect;
  signinRedirectCallback = mockSigninRedirectCallback;
  signinSilent = mockSigninSilent;
  signoutRedirect = mockSignoutRedirect;
  getUser = mockGetUser;
  events = {
    addAccessTokenExpiring: mockAddAccessTokenExpiring,
    addUserSignedOut: mockAddUserSignedOut,
  };
}

// oidc-client-tsのモック
vi.mock('oidc-client-ts', () => ({
  UserManager: MockUserManager,
  User: vi.fn(),
}));

// oidcConfigのモック
vi.mock('@/config/oidc', () => ({
  oidcConfig: {
    authority: 'https://keycloak.example.com/realms/memoru',
    client_id: 'memoru-liff',
    redirect_uri: 'http://localhost:3000/callback',
    response_type: 'code',
    scope: 'openid profile email',
    automaticSilentRenew: true,
  },
}));

describe('AuthService', () => {
  // 【テスト前準備】: 各テスト実行前にモックをリセット
  // 【環境初期化】: UserManagerのモックインスタンスを取得
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    localStorage.clear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('TC-004: Keycloakログインリダイレクト', () => {
    it('login()でsigninRedirect()が呼び出される', async () => {
      // 【テストデータ準備】: signinRedirectのモック設定
      // 【初期条件設定】: 未認証状態
      mockSigninRedirect.mockResolvedValue(undefined);

      // 【実際の処理実行】: authService.login()を呼び出す
      // 【処理内容】: PKCEフローを開始し、Keycloakへリダイレクト
      const { authService } = await import('@/services/auth');
      await authService.login();

      // 【結果検証】: signinRedirect()が呼び出されたことを確認
      // 【期待値確認】: PKCE認証フローの開始

      // 【検証項目】: signinRedirect()が1回呼び出された
      // 🔵 青信号: PKCE認証フローの仕様
      expect(mockSigninRedirect).toHaveBeenCalledTimes(1);
    });
  });

  describe('TC-005: 認証コールバック処理', () => {
    it('handleCallback()でトークンを取得する', async () => {
      // 【テストデータ準備】: 認証成功後のUserオブジェクトモック
      // 【初期条件設定】: Keycloakから認証コードを受け取った状態
      const mockUser = {
        access_token: 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...',
        refresh_token: 'dGhpcyBpcyBhIHJlZnJlc2g...',
        id_token: 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...',
        expires_at: Math.floor(Date.now() / 1000) + 3600,
        expired: false,
        profile: {
          sub: 'user-123',
          email: 'user@example.com',
          name: 'Test User',
        },
      };
      mockSigninRedirectCallback.mockResolvedValue(mockUser);

      // 【実際の処理実行】: authService.handleCallback()を呼び出す
      // 【処理内容】: 認証コードをトークンに交換
      const { authService } = await import('@/services/auth');
      const result = await authService.handleCallback();

      // 【結果検証】: Userオブジェクトが返されることを確認
      // 【期待値確認】: OIDC標準のトークン形式

      // 【検証項目】: signinRedirectCallback()が呼び出された
      // 🔵 青信号: OIDC認証コールバックの仕様
      expect(mockSigninRedirectCallback).toHaveBeenCalledTimes(1);

      // 【検証項目】: トークン情報を含むUserオブジェクトが返される
      // 🔵 青信号: oidc-client-ts標準のUser形式
      expect(result.access_token).toBe(mockUser.access_token);
      expect(result.profile.sub).toBe('user-123');
    });
  });

  describe('TC-006: 認証済みユーザー取得', () => {
    it('getUser()で保存されたユーザー情報を取得する', async () => {
      // 【テストデータ準備】: 認証済みユーザーのモック
      // 【初期条件設定】: localStorage内に有効なセッションがある状態
      const mockUser = {
        access_token: 'valid-token',
        expired: false,
        profile: { sub: 'user-123' },
      };
      mockGetUser.mockResolvedValue(mockUser);

      // 【実際の処理実行】: authService.getUser()を呼び出す
      // 【処理内容】: 保存されたセッションからユーザー情報を復元
      const { authService } = await import('@/services/auth');
      const result = await authService.getUser();

      // 【結果検証】: Userオブジェクトが返されることを確認
      // 【期待値確認】: セッション復元の正確性

      // 【検証項目】: getUser()が呼び出された
      // 🔵 青信号: セッション管理の仕様
      expect(mockGetUser).toHaveBeenCalledTimes(1);
      expect(result).toBe(mockUser);
    });

    it('未認証時はnullを返す', async () => {
      // 【テストデータ準備】: ユーザーなしの状態
      // 【初期条件設定】: セッションが存在しない状態
      mockGetUser.mockResolvedValue(null);

      // 【実際の処理実行】: authService.getUser()を呼び出す
      // 【処理内容】: 未認証状態の確認
      const { authService } = await import('@/services/auth');
      const result = await authService.getUser();

      // 【結果検証】: nullが返されることを確認
      // 【期待値確認】: 未認証状態の正確な反映

      // 【検証項目】: 未認証時はnullを返す
      // 🔵 青信号: セッション管理の仕様
      expect(result).toBeNull();
    });
  });

  describe('TC-007: アクセストークン取得', () => {
    it('getAccessToken()でアクセストークンを取得する', async () => {
      // 【テストデータ準備】: 認証済みユーザーのモック
      // 【初期条件設定】: 有効なセッションが存在する状態
      const mockUser = {
        access_token: 'jwt-access-token',
        expired: false,
      };
      mockGetUser.mockResolvedValue(mockUser);

      // 【実際の処理実行】: authService.getAccessToken()を呼び出す
      // 【処理内容】: アクセストークンを取得
      const { authService } = await import('@/services/auth');
      const token = await authService.getAccessToken();

      // 【結果検証】: トークン文字列が返されることを確認
      // 【期待値確認】: API認可に使用可能なJWTトークン

      // 【検証項目】: アクセストークンが返される
      // 🔵 青信号: JWT形式のトークン
      expect(token).toBe('jwt-access-token');
    });

    it('未認証時はnullを返す', async () => {
      // 【テストデータ準備】: ユーザーなしの状態
      // 【初期条件設定】: セッションが存在しない状態
      mockGetUser.mockResolvedValue(null);

      // 【実際の処理実行】: authService.getAccessToken()を呼び出す
      // 【処理内容】: 未認証時のトークン取得
      const { authService } = await import('@/services/auth');
      const token = await authService.getAccessToken();

      // 【結果検証】: nullが返されることを確認
      // 【期待値確認】: 未認証時のフォールバック

      // 【検証項目】: 未認証時はnullを返す
      // 🔵 青信号: 未認証時の動作仕様
      expect(token).toBeNull();
    });
  });

  describe('TC-008: ログアウト処理', () => {
    it('logout()でsignoutRedirect()が呼び出される', async () => {
      // 【テストデータ準備】: signoutRedirectのモック設定
      // 【初期条件設定】: 認証済み状態
      mockSignoutRedirect.mockResolvedValue(undefined);

      // 【実際の処理実行】: authService.logout()を呼び出す
      // 【処理内容】: セッションをクリアしてログアウト
      const { authService } = await import('@/services/auth');
      await authService.logout();

      // 【結果検証】: signoutRedirect()が呼び出されたことを確認
      // 【期待値確認】: 完全なログアウト処理

      // 【検証項目】: signoutRedirect()が呼び出された
      // 🔵 青信号: OIDC標準のログアウト仕様
      expect(mockSignoutRedirect).toHaveBeenCalledTimes(1);
    });
  });

  describe('TC-010: 手動トークンリフレッシュ', () => {
    it('refreshToken()でsigninSilent()が呼び出される', async () => {
      // 【テストデータ準備】: signinSilentのモック設定
      // 【初期条件設定】: 有効なリフレッシュトークンがある状態
      mockSigninSilent.mockResolvedValue({});

      // 【実際の処理実行】: authService.refreshToken()を呼び出す
      // 【処理内容】: トークンをリフレッシュ
      const { authService } = await import('@/services/auth');
      await authService.refreshToken();

      // 【結果検証】: signinSilent()が呼び出されたことを確認
      // 【期待値確認】: サイレントリフレッシュの動作

      // 【検証項目】: signinSilent()が呼び出された
      // 🔵 青信号: oidc-client-tsのサイレントリフレッシュ仕様
      expect(mockSigninSilent).toHaveBeenCalledTimes(1);
    });
  });

  describe('TC-018: リフレッシュトークン無効エラー', () => {
    it('リフレッシュ失敗時にエラーをスローする', async () => {
      // 【テストデータ準備】: signinSilentがエラーをスローするモック
      // 【初期条件設定】: リフレッシュトークンが無効な状態
      mockSigninSilent.mockRejectedValue(new Error('Invalid refresh token'));

      // 【実際の処理実行】: authService.refreshToken()がエラーをスローすることを確認
      // 【処理内容】: 無効なリフレッシュトークンでのリフレッシュ失敗
      const { authService } = await import('@/services/auth');

      // 【結果検証】: エラーがスローされることを確認
      // 【期待値確認】: リフレッシュ失敗時のエラーハンドリング

      // 【検証項目】: 適切なエラーがスローされる
      // 🔵 青信号: セッション管理の堅牢性
      await expect(authService.refreshToken()).rejects.toThrow();
    });
  });

  describe('TC-017: トークン取得失敗エラー', () => {
    it('コールバック処理失敗時にエラーをスローする', async () => {
      // 【テストデータ準備】: signinRedirectCallbackがエラーをスローするモック
      // 【初期条件設定】: 認証コードが無効な状態
      mockSigninRedirectCallback.mockRejectedValue(
        new Error('Token exchange failed')
      );

      // 【実際の処理実行】: authService.handleCallback()がエラーをスローすることを確認
      // 【処理内容】: 無効な認証コードでのトークン取得失敗
      const { authService } = await import('@/services/auth');

      // 【結果検証】: エラーがスローされることを確認
      // 【期待値確認】: トークン取得失敗時のエラーハンドリング

      // 【検証項目】: 適切なエラーがスローされる
      // 🔵 青信号: エラーリカバリーの仕様
      await expect(authService.handleCallback()).rejects.toThrow();
    });
  });

  describe('isAuthenticated', () => {
    it('有効なユーザーが存在する場合はtrueを返す', async () => {
      // 【テストデータ準備】: 有効な未期限切れユーザー
      // 【初期条件設定】: 認証済みで有効なセッション
      const mockUser = {
        access_token: 'valid-token',
        expired: false,
      };
      mockGetUser.mockResolvedValue(mockUser);

      // 【実際の処理実行】: authService.isAuthenticated()を呼び出す
      // 【処理内容】: 認証状態を確認
      const { authService } = await import('@/services/auth');
      const result = await authService.isAuthenticated();

      // 【結果検証】: trueが返されることを確認
      // 【期待値確認】: 認証済み状態の正確な判定

      // 【検証項目】: 認証済みの場合はtrue
      // 🔵 青信号: 認証状態確認の仕様
      expect(result).toBe(true);
    });

    it('ユーザーが存在しない場合はfalseを返す', async () => {
      // 【テストデータ準備】: ユーザーなし
      // 【初期条件設定】: 未認証状態
      mockGetUser.mockResolvedValue(null);

      // 【実際の処理実行】: authService.isAuthenticated()を呼び出す
      // 【処理内容】: 未認証状態を確認
      const { authService } = await import('@/services/auth');
      const result = await authService.isAuthenticated();

      // 【結果検証】: falseが返されることを確認
      // 【期待値確認】: 未認証状態の正確な判定

      // 【検証項目】: 未認証の場合はfalse
      // 🔵 青信号: 認証状態確認の仕様
      expect(result).toBe(false);
    });

    it('トークンが期限切れの場合はfalseを返す', async () => {
      // 【テストデータ準備】: 期限切れユーザー
      // 【初期条件設定】: トークンが期限切れの状態
      const mockUser = {
        access_token: 'expired-token',
        expired: true,
      };
      mockGetUser.mockResolvedValue(mockUser);

      // 【実際の処理実行】: authService.isAuthenticated()を呼び出す
      // 【処理内容】: 期限切れトークンの検出
      const { authService } = await import('@/services/auth');
      const result = await authService.isAuthenticated();

      // 【結果検証】: falseが返されることを確認
      // 【期待値確認】: 期限切れトークンの正確な判定

      // 【検証項目】: 期限切れの場合はfalse
      // 🔵 青信号: トークン有効性確認の仕様
      expect(result).toBe(false);
    });
  });
});
