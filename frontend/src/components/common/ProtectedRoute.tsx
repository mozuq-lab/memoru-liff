import { useState, useEffect, useRef, type ReactNode } from 'react';
import { useAuthContext } from '@/contexts/AuthContext';
import { Loading } from './Loading';
import { Error } from './Error';

interface ProtectedRouteProps {
  children: ReactNode;
}

// 【定数】(M-25): 自動ログインのリダイレクトが完了するまでの猶予時間 (ms)。
// signinRedirect は通常ブラウザ遷移を起こして戻ってこないが、ポップアップ
// ブロック・IdP 疎通不可・設定不備等でリダイレクトが起きないと catch にも
// 到達せず未認証のまま無限ローディングになる。この時間を超えても未認証なら
// エラー表示へフォールバックして再試行手段を提供する。
const LOGIN_REDIRECT_TIMEOUT_MS = 8000;

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isLoading, isAuthenticated, error, login } = useAuthContext();
  const loginAttemptedRef = useRef(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated && !loginAttemptedRef.current) {
      loginAttemptedRef.current = true;

      // 【リダイレクト遅延ガード】(M-25): signinRedirect が一定時間内に
      // ブラウザ遷移を起こさない場合、ユーザーを無限ローディングに
      // 留めずエラー表示へフォールバックさせる。
      const timeoutId = window.setTimeout(() => {
        setLoginError('ログインに失敗しました。時間をおいて再度お試しください。');
      }, LOGIN_REDIRECT_TIMEOUT_MS);

      login().catch(() => {
        window.clearTimeout(timeoutId);
        setLoginError('ログインに失敗しました');
      });
    }
  }, [isLoading, isAuthenticated, login]);

  // 【自動ログイン再試行】(M-25): フラグをリセットしてから login() を呼び直す。
  const retryLogin = () => {
    loginAttemptedRef.current = false;
    setLoginError(null);
    login().catch(() => {
      setLoginError('ログインに失敗しました');
    });
  };

  if (loginError) {
    return <Error message={loginError} onRetry={retryLogin} />;
  }

  if (isLoading) {
    return <Loading message="認証中..." />;
  }

  if (error) {
    return (
      <Error
        message="認証エラーが発生しました"
        onRetry={login}
      />
    );
  }

  if (!isAuthenticated) {
    return <Loading message="読み込み中..." />;
  }

  return <>{children}</>;
};
