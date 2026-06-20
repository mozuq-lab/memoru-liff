import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { AuthUser } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import { apiClient, LOGIN_REDIRECT_FAILED_EVENT } from '@/services/api';
import { toError } from '@/utils/error';

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: Error | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const auth = useAuth();
  // L-30: apiClient のセッション切れ再ログインリダイレクトが失敗した際のエラー。
  const [redirectError, setRedirectError] = useState<Error | null>(null);

  // Sync access token with API client
  // L-31: 依存配列を auth.user にする。access_token 文字列だけを依存にすると
  // 新しい User オブジェクトに差し替わってもトークン文字列が同一の場合に
  // effect が再実行されない。useAuth は user を useMemo でメモ化しているため、
  // auth.user を依存にしても不要な再実行は発生しない。
  useEffect(() => {
    if (auth.user?.access_token) {
      apiClient.setAccessToken(auth.user.access_token);
    } else {
      apiClient.setAccessToken(null);
    }
  }, [auth.user]);

  // L-30 (レビュー P3): apiClient がセッション切れでログイン画面へリダイレクトしようと
  // して失敗した場合に発火するグローバルイベントを購読し、UI へエラーを伝播する。
  // 未購読だとユーザーは操作不能のまま放置されるため、error として表面化させる。
  useEffect(() => {
    const handler = (e: Event) => {
      setRedirectError(toError((e as CustomEvent).detail));
    };
    window.addEventListener(LOGIN_REDIRECT_FAILED_EVENT, handler);
    return () => window.removeEventListener(LOGIN_REDIRECT_FAILED_EVENT, handler);
  }, []);

  // auth.error（初期化・login 由来）と redirectError（リダイレクト失敗由来）を統合する。
  // 認証済みのとき（再ログイン成功後など）は redirectError を表に出さない。render 中に
  // 導出することで「認証回復時にクリアする」副作用 effect を持たずに済む
  // （react-hooks/set-state-in-effect を回避）。
  const value = useMemo<AuthContextType>(
    () => ({
      ...auth,
      error: auth.error ?? (auth.isAuthenticated ? null : redirectError),
    }),
    [auth, redirectError]
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuthContext = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
};
