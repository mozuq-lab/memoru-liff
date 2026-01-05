import type { ReactNode } from 'react';
import { useAuthContext } from '@/contexts/AuthContext';
import { Loading } from './Loading';
import { Error } from './Error';

interface ProtectedRouteProps {
  children: ReactNode;
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isLoading, isAuthenticated, error, login } = useAuthContext();

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
    login();
    return <Loading message="ログインページに移動中..." />;
  }

  return <>{children}</>;
};
