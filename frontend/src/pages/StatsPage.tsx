/**
 * 【機能概要】: 学習統計ダッシュボードページ
 * 【実装方針】: useStats フックでデータ取得、各サブコンポーネントにデータを渡す
 * 【テスト対応】: TASK-0154
 * 🔵 青信号: 設計文書 architecture.md のページ構成より
 */
import { Navigation } from '@/components/Navigation';
import { Loading } from '@/components/common/Loading';
import { Error } from '@/components/common/Error';
import { StreakDisplay } from '@/components/stats/StreakDisplay';
import { StatsSummary } from '@/components/stats/StatsSummary';
import { ReviewForecast } from '@/components/stats/ReviewForecast';
import { WeakCardsList } from '@/components/stats/WeakCardsList';
import { useStats } from '@/hooks/useStats';

/**
 * 【機能概要】: 学習統計ダッシュボードメインコンポーネント
 * 【実装方針】: ローディング・エラー・データ表示の3状態をハンドリング
 */
export const StatsPage = () => {
  const { stats, weakCards, forecast, isLoading, error, refresh } = useStats();

  // 【ローディング表示】
  if (isLoading) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center">
          <Loading message="統計データを読み込み中..." />
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
            message="統計データの取得に失敗しました"
            onRetry={refresh}
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
        <h1 className="text-xl font-bold text-gray-800">学習統計</h1>
      </header>

      {/* メインコンテンツ */}
      <main className="flex-1 px-4">
        {/* 連続学習日数 */}
        {stats && (
          <div className="mb-6">
            <StreakDisplay streakDays={stats.streak_days} />
          </div>
        )}

        {/* 統計サマリー */}
        {stats && <StatsSummary stats={stats} />}

        {/* 復習予測 */}
        {forecast && <ReviewForecast forecast={forecast.forecast} />}

        {/* 苦手カード */}
        {weakCards && <WeakCardsList weakCards={weakCards.weak_cards} />}
      </main>

      <Navigation />
    </div>
  );
};
