import { useState, useEffect, useRef, useCallback, type ReactNode } from 'react';
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
  const timeoutRef = useRef<number | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);

  // フォールバックタイマーを張り直す。login() が無言で進まない場合に、一定時間後
  // エラー表示へ倒すための保険。
  const startFallbackTimer = useCallback(() => {
    if (timeoutRef.current !== null) window.clearTimeout(timeoutRef.current);
    timeoutRef.current = window.setTimeout(() => {
      setLoginError('ログインに失敗しました。時間をおいて再度お試しください。');
    }, LOGIN_REDIRECT_TIMEOUT_MS);
  }, []);

  // 未認証が確定したら一度だけ自動ログインを開始し、フォールバックタイマーを張る。
  // 【重要】(レビュー P2): login() は内部で setIsLoading(true) するため isLoading が
  // 変化するが、この effect の cleanup でタイマーを消すと、リダイレクトが進まない
  // ケースでフォールバックが即解除され無限ローディングへ戻る。そのため解除はこの
  // effect では行わず、下の「認証成功・エラー時」専用 effect に委ねる。
  useEffect(() => {
    if (isLoading || isAuthenticated || error || loginAttemptedRef.current) {
      return;
    }
    loginAttemptedRef.current = true;
    startFallbackTimer();
    void login();
  }, [isLoading, isAuthenticated, error, login, startFallbackTimer]);

  // 認証成功・認証エラー時、およびアンマウント時のみフォールバックタイマーを解除する
  // （isLoading の変化では解除しない）。
  useEffect(() => {
    const clearTimer = () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
    if (isAuthenticated || error) {
      clearTimer();
    }
    return clearTimer;
  }, [isAuthenticated, error]);

  // 【自動ログイン再試行】: 遅延エラーを消し、フォールバックタイマーを張り直して login を
  // やり直す。loginAttemptedRef は据え置き、自動ログイン effect の二重起動を防ぐ。
  const retryLogin = () => {
    setLoginError(null);
    startFallbackTimer();
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
