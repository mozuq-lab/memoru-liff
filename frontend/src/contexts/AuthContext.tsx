import { createContext, useContext, useEffect, type ReactNode } from 'react';
import type { AuthUser } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import { apiClient } from '@/services/api';

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

  const value = auth;

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
