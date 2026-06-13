import { useState, useEffect, useRef, type ReactNode } from 'react';
import { useAuthContext } from '@/contexts/AuthContext';
import { Loading } from './Loading';
import { Error } from './Error';

interface ProtectedRouteProps {
  children: ReactNode;
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isLoading, isAuthenticated, error, login } = useAuthContext();
  const loginAttemptedRef = useRef(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated && !loginAttemptedRef.current) {
      loginAttemptedRef.current = true;
      login().catch(() => {
        setLoginError('ログインに失敗しました');
      });
    }
  }, [isLoading, isAuthenticated, login]);

  if (loginError) {
    return <Error message={loginError} />;
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
