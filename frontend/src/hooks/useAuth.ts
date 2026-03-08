/**
 * 【機能概要】: Keycloak OIDC認証状態を管理するReactフック
 * 【実装方針】: authServiceをラップして状態管理を提供
 * 【テスト対応】: TC-011, TC-012, TC-020
 * 🔵 青信号: 要件定義・TASK-0012.mdに基づく
 */
import { useState, useEffect, useCallback, useMemo } from 'react';
import { authService } from '@/services/auth';

/**
 * 【型定義】: 認証ユーザー情報
 * 🔵 青信号: oidc-client-tsのUser型に準拠
 */
interface AuthUser {
  access_token: string;
  expired: boolean;
  profile?: {
    sub: string;
    email?: string;
    name?: string;
  };
}

/**
 * 【型定義】: useAuthフックの戻り値
 * 🔵 青信号: TASK-0012.mdの実装仕様に基づく
 */
interface UseAuthReturn {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: Error | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  getAccessToken: () => string | null;
}

/**
 * 【機能概要】: 認証状態を管理するカスタムフック
 * 【実装方針】: authServiceと連携して認証状態を提供
 * 【テスト対応】: TC-011〜TC-012, TC-020
 * 🔵 青信号: React Hooksのベストプラクティスに準拠
 */
export const useAuth = (): UseAuthReturn => {
  // 【状態定義】: ユーザー情報、ローディング状態、エラー状態
  // 🔵 青信号: React Hooksの標準パターン
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  /**
   * 【副作用】: コンポーネントマウント時に認証状態を初期化
   * 【処理内容】: authServiceから現在のユーザーを取得
   * 🔵 青信号: 要件定義のセッション復元仕様
   */
  useEffect(() => {
    const initAuth = async () => {
      try {
        // 【認証状態確認】: authServiceから現在のユーザーを取得
        // 🔵 青信号: oidc-client-tsのgetUser()を使用
        const currentUser = await authService.getUser();

        if (currentUser) {
          // 【ユーザー設定】: 認証済みユーザー情報を状態に反映
          // 🔵 青信号: User型からAuthUser型への変換
          setUser({
            access_token: currentUser.access_token,
            expired: currentUser.expired ?? false,
            profile: currentUser.profile ? {
              sub: currentUser.profile.sub,
              email: currentUser.profile.email,
              name: currentUser.profile.name,
            } : undefined,
          });
        } else {
          // 【未認証状態】: ユーザーが存在しない場合
          // 🔵 青信号: 未認証状態の初期値
          setUser(null);
        }
      } catch (err) {
        // 【エラー処理】: 初期化エラーを状態に設定
        // 🔵 青信号: エラーハンドリングの仕様
        setError(err instanceof Error ? err : new Error(String(err)));
        setUser(null);
      } finally {
        // 【ローディング完了】: 初期化処理の完了を通知
        // 🔵 青信号: 非同期処理完了時の標準パターン
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  /**
   * 【機能概要】: ログイン処理を実行
   * 【実装方針】: authServiceのlogin()に委譲
   * 【テスト対応】: login関連テスト
   * 🔵 青信号: Keycloakリダイレクト認証フロー
   */
  const login = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // 【ログイン実行】: Keycloak認証ページへリダイレクト
      // 🔵 青信号: authService.login()への委譲
      await authService.login();
    } catch (err) {
      // 【エラー処理】: ログインエラーを状態に設定
      // 🔵 青信号: エラーハンドリングの仕様
      setError(err instanceof Error ? err : new Error(String(err)));
      setIsLoading(false);
    }
  }, []);

  /**
   * 【機能概要】: ログアウト処理を実行
   * 【実装方針】: authServiceのlogout()に委譲してユーザー状態をクリア
   * 【テスト対応】: logout関連テスト
   * 🔵 青信号: セッションクリアの仕様
   */
  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      // 【ログアウト実行】: セッションをクリア
      // 🔵 青信号: authService.logout()への委譲
      await authService.logout();

      // 【状態クリア】: ユーザー情報をリセット
      // 🔵 青信号: ログアウト後の状態管理
      setUser(null);
    } catch (err) {
      // 【エラー処理】: ログアウトエラーを状態に設定
      // 🔵 青信号: エラーハンドリングの仕様
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * 【機能概要】: トークンリフレッシュを実行
   * 【実装方針】: authServiceのrefreshToken()に委譲
   * 【テスト対応】: refreshToken関連テスト
   * 🔵 青信号: サイレントリフレッシュの仕様
   */
  const refreshToken = useCallback(async () => {
    try {
      // 【トークンリフレッシュ】: サイレントリフレッシュを実行
      // 🔵 青信号: authService.refreshToken()への委譲
      await authService.refreshToken();

      // 【ユーザー再取得】: リフレッシュ後の最新ユーザー情報を取得
      // 🔵 青信号: トークン更新後の状態同期
      const refreshedUser = await authService.getUser();
      if (refreshedUser) {
        setUser({
          access_token: refreshedUser.access_token,
          expired: refreshedUser.expired ?? false,
          profile: refreshedUser.profile ? {
            sub: refreshedUser.profile.sub,
            email: refreshedUser.profile.email,
            name: refreshedUser.profile.name,
          } : undefined,
        });
      }
    } catch (err) {
      // 【エラー処理】: リフレッシュエラーを状態に設定
      // 🔵 青信号: エラーハンドリングの仕様
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  }, []);

  /**
   * 【機能概要】: アクセストークンを取得
   * 【実装方針】: 現在のユーザー状態からトークンを返却
   * 【テスト対応】: getAccessToken関連テスト
   * 🔵 青信号: JWT形式のトークン取得
   */
  const getAccessToken = useCallback(() => {
    // 【トークン返却】: ユーザーのアクセストークンを返す
    // 🔵 青信号: nullセーフなトークン取得
    return user?.access_token ?? null;
  }, [user]);

  // 【フック戻り値】: 認証状態と操作関数を返却
  // 🔵 青信号: useAuthフックの戻り値仕様
  // 【メモ化】: useMemoで不要な再レンダリングを削減
  return useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated: !!user && !user.expired,
      error,
      login,
      logout,
      refreshToken,
      getAccessToken,
    }),
    [user, isLoading, error, login, logout, refreshToken, getAccessToken]
  );
};
