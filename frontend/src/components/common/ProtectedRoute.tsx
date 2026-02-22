import { useState, useEffect, type ReactNode } from 'react';
import { useAuthContext } from '@/contexts/AuthContext';
import { Loading } from './Loading';
import { Error } from './Error';

interface ProtectedRouteProps {
  children: ReactNode;
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isLoading, isAuthenticated, error, login } = useAuthContext();
  const [loginAttempted, setLoginAttempted] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated && !loginAttempted) {
      setLoginAttempted(true);
      login().catch(() => {
        setLoginError('ログインに失敗しました');
      });
    }
  }, [isLoading, isAuthenticated, loginAttempted, login]);

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
