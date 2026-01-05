/**
 * 【機能概要】: カード一覧画面
 * 【実装方針】: カードの一覧表示、ページネーション、詳細へのナビゲーション
 * 【テスト対応】: TASK-0016 テストケース1〜8
 * 🟡 黄信号: user-stories.md 3.2より
 */
import { useEffect, useState, useCallback } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { CardList } from '@/components/CardList';
import { Navigation } from '@/components/Navigation';
import { Loading } from '@/components/common/Loading';
import { Error } from '@/components/common/Error';
import { useCardsContext } from '@/contexts/CardsContext';

/**
 * 【機能概要】: カード一覧ページコンポーネント
 */
export const CardsPage = () => {
  const location = useLocation();
  const { cards, isLoading, error, fetchCards } = useCardsContext();
  const [successMessage, setSuccessMessage] = useState<string | null>(
    (location.state as { message?: string } | null)?.message || null
  );

  // 【初期読み込み】: 画面表示時にカードを取得
  useEffect(() => {
    fetchCards();
  }, [fetchCards]);

  // 【成功メッセージの自動非表示】
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // 【再取得ハンドラ】
  const handleRetry = useCallback(() => {
    fetchCards();
  }, [fetchCards]);

  // 【ローディング表示】
  if (isLoading) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center">
          <Loading message="カードを読み込み中..." />
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
          <Error message="カードの取得に失敗しました" onRetry={handleRetry} />
        </div>
        <Navigation />
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen pb-20">
      <header className="bg-white shadow-sm p-4 mb-4">
        <h1 className="text-xl font-bold text-gray-800">カード一覧</h1>
        <p className="text-sm text-gray-600" data-testid="card-count">
          {cards.length}枚のカード
        </p>
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

        {cards.length === 0 ? (
          /* 空状態 */
          <div className="text-center py-12" data-testid="empty-state">
            <svg
              className="mx-auto h-16 w-16 text-gray-400 mb-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
            <p className="text-gray-600 mb-4">カードがありません</p>
            <Link
              to="/generate"
              className="inline-block px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 min-h-[44px] transition-colors"
            >
              カードを作成する
            </Link>
          </div>
        ) : (
          <CardList cards={cards} />
        )}
      </main>

      <Navigation />
    </div>
  );
};
