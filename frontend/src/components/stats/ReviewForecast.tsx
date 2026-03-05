/**
 * 【機能概要】: 復習予測セクションコンポーネント
 * 【実装方針】: 7日間の復習予測をCSS-onlyバーチャートで表示
 * 【テスト対応】: TASK-0154
 * 🔵 青信号: 設計文書 architecture.md のコンポーネント設計より
 */
import type { ForecastDay } from '@/types';
import { ForecastBar } from './ForecastBar';

interface ReviewForecastProps {
  forecast: ForecastDay[];
}

export const ReviewForecast = ({ forecast }: ReviewForecastProps) => {
  const maxCount = Math.max(...forecast.map(d => d.due_count), 1);

  return (
    <section
      className="mb-6"
      aria-label="復習予測"
      data-testid="review-forecast"
    >
      <h2 className="text-lg font-semibold text-gray-700 mb-3">
        <span aria-hidden="true">&#x1F4C5;</span> 今後7日の復習予測
      </h2>
      <div className="bg-white rounded-lg shadow p-4">
        {forecast.length === 0 ? (
          <p className="text-center text-gray-500" data-testid="forecast-empty">
            予測データがありません
          </p>
        ) : (
          <div className="space-y-1">
            {forecast.map((day) => (
              <ForecastBar key={day.date} day={day} maxCount={maxCount} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
};
