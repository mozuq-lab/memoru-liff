import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loading } from '@/components/common';
import { authService } from '@/services/auth';

export const CallbackPage = () => {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  // F-6: StrictMode の effect 二重実行で signinRedirectCallback が
  // 二重に走ると 2 回目が「認証応答なし」で偽エラーになるため ref でガードする
  const processedRef = useRef(false);

  useEffect(() => {
    if (processedRef.current) return;
    processedRef.current = true;

    const processCallback = async () => {
      try {
        await authService.handleCallback();
        navigate('/', { replace: true });
      } catch {
        // L-25: 認証応答（state / エラーコード等）を含みうるため
        // console.error には出力しない。UI のエラー表示のみで通知する。
        setError('認証に失敗しました');
      }
    };

    processCallback();
  }, [navigate]);

  // L-24: 認証コードは使い捨てのためコールバック失敗後に `/` へ戻すと
  // ProtectedRoute の自動 login() → 同じ /callback 再処理 → 再失敗という
  // ループに陥りうる。`/` への遷移ではなく login() で新規認証フローを
  // 開始し直すことでループを断ち切る。
  const handleRetryLogin = () => {
    authService.login().catch(() => {
      setError('ログインの開始に失敗しました');
    });
  };

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
          onClick={handleRetryLogin}
          className="btn-primary"
        >
          ログインし直す
        </button>
      </div>
    );
  }

  return <Loading message="認証処理中..." />;
};
