import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loading } from '@/components/common';

// Stub page - will be fully implemented in TASK-0012
export const CallbackPage = () => {
  const navigate = useNavigate();

  useEffect(() => {
    // TODO: Handle OIDC callback in TASK-0012
    const handleCallback = async () => {
      try {
        // Placeholder: redirect to home after handling callback
        navigate('/', { replace: true });
      } catch (error) {
        console.error('Callback error:', error);
        navigate('/', { replace: true });
      }
    };

    handleCallback();
  }, [navigate]);

  return <Loading message="認証処理中..." />;
};
