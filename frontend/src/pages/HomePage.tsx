/**
 * 【機能概要】: ホーム画面コンポーネント
 * 【実装方針】: 復習待ちカード数表示とクイックアクションを提供
 * 【テスト対応】: TASK-0014テストケース1〜6
 * 🟡 黄信号: 要件から妥当な推測
 */
import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useCardsContext } from '@/contexts/CardsContext';
import { useAuthContext } from '@/contexts/AuthContext';
import { Navigation } from '@/components/Navigation';
import { Loading } from '@/components/common/Loading';
import { Error } from '@/components/common/Error';

/**
 * 【機能概要】: ホーム画面メインコンポーネント
 * 【実装方針】: 復習待ちカード数とナビゲーションを表示
 */
export const HomePage = () => {
  const { user } = useAuthContext();
  const { dueCount, fetchDueCount, isLoading, error } = useCardsContext();

  // 【復習待ちカード数取得】: 画面表示時に取得
  useEffect(() => {
    fetchDueCount();
  }, [fetchDueCount]);

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

  // 【エラー表示】
  if (error) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center p-4">
          <Error
            message="データの取得に失敗しました"
            onRetry={fetchDueCount}
          />
        </div>
        <Navigation />
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen pb-20">
      {/* ヘッダー */}
      <header className="bg-white shadow-sm p-4 mb-6">
        <h1 className="text-xl font-bold text-gray-800">Memoru</h1>
        <p className="text-sm text-gray-600">
          こんにちは、{user?.profile?.name ?? 'ユーザー'}さん
        </p>
      </header>

      {/* メインコンテンツ */}
      <main className="flex-1 px-4">
        {/* 復習カード数表示 */}
        <section
          className="bg-white rounded-lg shadow p-6 mb-6"
          aria-label="今日の復習状況"
          data-testid="today-review-section"
        >
          <h2 className="text-lg font-semibold text-gray-700 mb-2">
            今日の復習
          </h2>
          <div className="flex items-center justify-between">
            <span
              className="text-3xl font-bold text-blue-600"
              data-testid="due-count"
            >
              {dueCount}
            </span>
            <span className="text-gray-500">枚のカード</span>
          </div>
          {dueCount > 0 && (
            <Link
              to="/cards"
              className="mt-4 block w-full py-3 bg-blue-600 text-white text-center rounded-lg hover:bg-blue-700 active:bg-blue-800 min-h-[44px] transition-colors"
            >
              復習を始める
            </Link>
          )}
          {dueCount === 0 && (
            <p className="mt-4 text-gray-500 text-center">
              復習待ちのカードはありません
            </p>
          )}
        </section>

        {/* クイックアクション */}
        <section aria-label="クイックアクション">
          <div className="grid grid-cols-2 gap-4">
            <Link
              to="/generate"
              className="bg-white rounded-lg shadow p-4 flex flex-col items-center justify-center min-h-[100px] hover:bg-gray-50 active:bg-gray-100 transition-colors"
            >
              <svg
                className="h-8 w-8 text-green-600 mb-2"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span className="text-sm font-medium text-gray-700">カード作成</span>
            </Link>

            <Link
              to="/cards"
              className="bg-white rounded-lg shadow p-4 flex flex-col items-center justify-center min-h-[100px] hover:bg-gray-50 active:bg-gray-100 transition-colors"
            >
              <svg
                className="h-8 w-8 text-blue-600 mb-2"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              <span className="text-sm font-medium text-gray-700">カード一覧</span>
            </Link>
          </div>
        </section>
      </main>

      <Navigation />
    </div>
  );
};
