import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loading } from '@/components/common';
import { authService } from '@/services/auth';

export const CallbackPage = () => {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const processCallback = async () => {
      try {
        await authService.handleCallback();
        navigate('/', { replace: true });
      } catch (err) {
        console.error('Callback error:', err);
        setError('認証に失敗しました');
      }
    };

    processCallback();
  }, [navigate]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] p-4">
        <div className="text-red-500 text-lg mb-4">
          <svg className="h-12 w-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <p className="text-gray-700 text-center mb-4">{error}</p>
        <button
          onClick={() => navigate('/', { replace: true })}
          className="btn-primary"
        >
          ホームに戻る
        </button>
      </div>
    );
  }

  return <Loading message="認証処理中..." />;
};
