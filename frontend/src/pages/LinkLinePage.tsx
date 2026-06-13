/**
 * 【機能概要】: LINE連携画面
 * 【実装方針】: LINE連携の状態表示と連携/解除処理を提供
 * 【セキュリティ】: liff.getIDToken() で取得したIDトークンをサーバーに送信し、
 *                  サーバー側で LINE API を通じて検証する (TASK-0044)
 * 【テスト対応】: TASK-0019 テストケース1〜7, TASK-0044 TC-14〜16
 * 🔵 青信号: user-stories.md 1.2, REQ-V2-021〜023より
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Navigation } from '@/components/Navigation';
import { Loading } from '@/components/common/Loading';
import { Error } from '@/components/common/Error';
import { usersApi } from '@/services/api';
import { getLiffIdToken, initializeLiff, isInLiffClient } from '@/services/liff';
import type { User } from '@/types';

/**
 * 【機能概要】: LINE連携ページコンポーネント
 */
export const LinkLinePage = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLinking, setIsLinking] = useState(false);
  const [isUnlinking, setIsUnlinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // 【ユーザー情報取得】
  const fetchUser = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await usersApi.getCurrentUser();
      setUser(data);
    } catch {
      setError('LINE連携状態の取得に失敗しました');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  // 【成功メッセージの自動非表示】
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // 【LINE連携ハンドラ】
  const handleLinkLine = async () => {
    setIsLinking(true);
    setError(null);

    try {
      // LINEアプリ内かチェック
      if (!isInLiffClient()) {
        setError('LINEアプリからアクセスしてください');
        setIsLinking(false);
        return;
      }

      // LIFF SDKを初期化
      await initializeLiff();

      // LIFF ID トークンを取得
      const idToken = getLiffIdToken();
      if (!idToken) {
        setError('LINEの認証情報を取得できませんでした');
        setIsLinking(false);
        return;
      }

      // サーバーに連携リクエスト
      const updatedUser = await usersApi.linkLine({
        id_token: idToken,
      });

      setUser(updatedUser);
      setSuccessMessage('LINE連携が完了しました');
    } catch {
      setError('LINE連携に失敗しました');
    } finally {
      setIsLinking(false);
    }
  };

  // 【LINE連携解除ハンドラ】
  const handleUnlinkLine = async () => {
    setIsUnlinking(true);
    setError(null);

    try {
      const updatedUser = await usersApi.unlinkLine();
      setUser(updatedUser);
      setSuccessMessage('LINE連携を解除しました');
    } catch {
      setError('LINE連携の解除に失敗しました');
    } finally {
      setIsUnlinking(false);
    }
  };

  // 【戻るハンドラ】
  const handleBack = () => {
    navigate(-1);
  };

  const isLinked = user?.line_linked ?? false;

  // 【ローディング表示】
  if (isLoading) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center">
          <Loading message="読み込み中..." />
        </div>
        <Navigation />
      </div>
    );
  }

  // 【エラー表示（ユーザー取得失敗）】
  if (error && !user) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center p-4">
          <Error message={error} onRetry={fetchUser} />
        </div>
        <Navigation />
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen pb-20">
      <header className="bg-white shadow-sm p-4 mb-4">
        <div className="flex items-center">
          <button
            onClick={handleBack}
            className="flex items-center text-gray-600 hover:text-gray-800 min-w-[44px] min-h-[44px]"
            data-testid="back-button"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            <span className="ml-1">戻る</span>
          </button>
        </div>
        <h1 className="text-xl font-bold text-gray-800 mt-2" data-testid="page-title">
          LINE連携
        </h1>
      </header>

      <main className="flex-1 px-4">
        {/* 成功メッセージ */}
        {successMessage && (
          <div
            className="mb-4 p-3 bg-green-100 border border-green-300 text-green-700 rounded-lg"
            data-testid="success-message"
          >
            {successMessage}
          </div>
        )}

        {/* エラーメッセージ */}
        {error && (
          <div
            className="mb-4 p-3 bg-red-100 border border-red-300 text-red-700 rounded-lg"
            data-testid="error-message"
          >
            {error}
          </div>
        )}

        {/* LINE連携状態表示 */}
        <section className="bg-white rounded-lg shadow p-6 mb-6" data-testid="line-status-section">
          <div className="flex items-center mb-4">
            {/* LINE アイコン */}
            <div className="w-12 h-12 bg-[#00B900] rounded-full flex items-center justify-center mr-4">
              <svg className="w-7 h-7 text-white" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M19.365 9.863c.349 0 .63.285.63.631 0 .345-.281.63-.63.63H17.61v1.125h1.755c.349 0 .63.283.63.63 0 .344-.281.629-.63.629h-2.386c-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.627-.63h2.386c.349 0 .63.285.63.63 0 .349-.281.63-.63.63H17.61v1.125h1.755zm-3.855 3.016c0 .27-.174.51-.432.596-.064.021-.133.031-.199.031-.211 0-.391-.09-.51-.25l-2.443-3.317v2.94c0 .344-.279.629-.631.629-.346 0-.626-.285-.626-.629V8.108c0-.27.173-.51.43-.595.06-.023.136-.033.194-.033.195 0 .375.104.495.254l2.462 3.33V8.108c0-.345.282-.63.63-.63.345 0 .63.285.63.63v4.771zm-5.741 0c0 .344-.282.629-.631.629-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.627-.63.349 0 .631.285.631.63v4.771zm-2.466.629H4.917c-.345 0-.63-.285-.63-.629V8.108c0-.345.285-.63.63-.63.349 0 .63.285.63.63v4.141h1.756c.348 0 .629.283.629.63 0 .344-.281.629-.629.629M24 10.314C24 4.943 18.615.572 12 .572S0 4.943 0 10.314c0 4.811 4.27 8.842 10.035 9.608.391.082.923.258 1.058.59.12.301.079.766.038 1.08l-.164 1.02c-.045.301-.24 1.186 1.049.645 1.291-.539 6.916-4.078 9.436-6.975C23.176 14.393 24 12.458 24 10.314" />
              </svg>
            </div>

            <div className="flex-1">
              <h2 className="text-lg font-semibold text-gray-800">
                LINE連携
              </h2>
              <p
                className={`text-sm ${isLinked ? 'text-green-600' : 'text-gray-500'}`}
                data-testid="link-status"
              >
                {isLinked ? '連携済み' : '未連携'}
              </p>
            </div>
          </div>

          {isLinked ? (
            /* 連携済み状態 */
            <div data-testid="linked-content">
              <div className="flex items-center p-4 bg-gray-50 rounded-lg mb-4">
                <div className="w-12 h-12 bg-gray-300 rounded-full mr-4 flex items-center justify-center">
                  <svg className="w-6 h-6 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
                <div>
                  <p className="font-medium text-gray-800" data-testid="line-status-text">
                    LINE連携中
                  </p>
                </div>
              </div>

              <p className="text-sm text-gray-600 mb-4">
                復習リマインダーがLINEに送信されます。
              </p>

              <button
                onClick={handleUnlinkLine}
                disabled={isUnlinking}
                className="w-full py-3 text-red-600 border border-red-600 rounded-lg hover:bg-red-50 min-h-[44px] transition-colors"
                data-testid="unlink-button"
              >
                {isUnlinking ? '解除中...' : '連携を解除'}
              </button>
            </div>
          ) : (
            /* 未連携状態 */
            <div data-testid="unlinked-content">
              <p className="text-gray-600 mb-4">
                LINEと連携すると、復習リマインダーをLINEで受け取れます。
              </p>

              <ul className="text-sm text-gray-600 mb-6 space-y-2">
                <li className="flex items-start">
                  <svg className="w-5 h-5 text-green-500 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span>毎日の復習リマインダーを受信</span>
                </li>
                <li className="flex items-start">
                  <svg className="w-5 h-5 text-green-500 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span>LINEから直接アプリにアクセス</span>
                </li>
              </ul>

              <button
                onClick={handleLinkLine}
                disabled={isLinking}
                className={`w-full py-3 rounded-lg font-medium min-h-[44px] transition-colors ${
                  isLinking
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-[#00B900] text-white hover:bg-[#009900]'
                }`}
                data-testid="link-button"
              >
                {isLinking ? '連携中...' : 'LINEと連携する'}
              </button>
            </div>
          )}
        </section>

        {/* 注意事項 */}
        <section className="bg-gray-50 rounded-lg p-4" data-testid="notes-section">
          <h3 className="text-sm font-medium text-gray-700 mb-2">注意事項</h3>
          <ul className="text-sm text-gray-600 space-y-1">
            <li>• 連携にはLINEアプリが必要です</li>
            <li>• 連携を解除すると通知が届かなくなります</li>
            <li>• 連携情報は安全に保管されます</li>
          </ul>
        </section>
      </main>

      <Navigation />
    </div>
  );
};
