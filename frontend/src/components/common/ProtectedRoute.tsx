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
    // 認証済み・認証エラー発生時・既に試行済みのいずれかなら自動ログインしない。
    if (isLoading || isAuthenticated || error || loginAttemptedRef.current) {
      return;
    }
    loginAttemptedRef.current = true;

    // 【リダイレクト遅延ガード】(M-25 / レビュー P2): signinRedirect が一定時間内に
    // ブラウザ遷移を起こさない場合のフォールバック。useAuth.login は内部で例外を
    // 握って rethrow しないため login() の .catch は発火しない。代わりにタイマーで
    // 救済し、login が error をセットした場合は deps の error 変化に伴う cleanup で
    // clearTimeout され、下の error 分岐（エラー表示）へ倒れる。
    const timeoutId = window.setTimeout(() => {
      setLoginError('ログインに失敗しました。時間をおいて再度お試しください。');
    }, LOGIN_REDIRECT_TIMEOUT_MS);

    void login();

    // アンマウント時・isAuthenticated/error 変化時にタイマーを破棄し、認証成功後や
    // エラー表示後に遅延エラーが誤発火するのを防ぐ。
    return () => window.clearTimeout(timeoutId);
  }, [isLoading, isAuthenticated, error, login]);

  // 【自動ログイン再試行】: 遅延エラーを消して login をやり直す。loginAttemptedRef は
  // true のまま据え置き、effect による二重起動を防ぐ。失敗時は useAuth が error を
  // セットし、下の error 分岐で表示される。
  const retryLogin = () => {
    setLoginError(null);
    void login();
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
