import { createContext, useContext, useEffect, useMemo, type ReactNode } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { apiClient } from '@/services/api';

interface AuthUser {
  access_token: string;
  expired: boolean;
  profile?: {
    sub: string;
    email?: string;
    name?: string;
  };
}

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
  useEffect(() => {
    if (auth.user?.access_token) {
      apiClient.setAccessToken(auth.user.access_token);
    } else {
      apiClient.setAccessToken(null);
    }
  }, [auth.user?.access_token]);

  const value = useMemo(() => auth, [
    auth.user,
    auth.isLoading,
    auth.isAuthenticated,
    auth.error,
    auth.login,
    auth.logout,
    auth.refreshToken,
  ]);

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
