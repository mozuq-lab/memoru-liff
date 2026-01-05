import { useState, useEffect, useCallback } from 'react';

// Note: This is a stub implementation.
// Full implementation will be done in TASK-0012 with oidc-client-ts and Keycloak.

interface AuthUser {
  access_token: string;
  expired: boolean;
  profile: {
    sub: string;
    email?: string;
    name?: string;
  };
}

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

export const useAuth = (): UseAuthReturn => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    // TODO: Implement actual auth initialization in TASK-0012
    const initAuth = async () => {
      try {
        // Stub: Check for existing session
        const storedToken = localStorage.getItem('access_token');
        if (storedToken) {
          setUser({
            access_token: storedToken,
            expired: false,
            profile: {
              sub: 'stub-user-id',
              email: 'stub@example.com',
              name: 'Stub User',
            },
          });
        }
      } catch (err) {
        setError(err as Error);
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // TODO: Implement actual login in TASK-0012
      console.log('Login not implemented yet. See TASK-0012.');
    } catch (err) {
      setError(err as Error);
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      // TODO: Implement actual logout in TASK-0012
      localStorage.removeItem('access_token');
      setUser(null);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshToken = useCallback(async () => {
    try {
      // TODO: Implement actual token refresh in TASK-0012
      console.log('Token refresh not implemented yet. See TASK-0012.');
    } catch (err) {
      setError(err as Error);
    }
  }, []);

  const getAccessToken = useCallback(() => {
    return user?.access_token ?? null;
  }, [user]);

  return {
    user,
    isLoading,
    isAuthenticated: !!user && !user.expired,
    error,
    login,
    logout,
    refreshToken,
    getAccessToken,
  };
};
