/**
 * 【機能概要】: 個別日予測バーコンポーネント
 * 【実装方針】: CSS のみで水平バーチャートの1行を表現
 * 【テスト対応】: TASK-0154
 * 🔵 青信号: 設計文書 architecture.md のコンポーネント設計より
 */
import type { ForecastDay } from '@/types';

interface ForecastBarProps {
  day: ForecastDay;
  maxCount: number;
}

/**
 * 【機能概要】: 日付文字列を M/DD 形式にフォーマット
 */
const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  return `${date.getMonth() + 1}/${String(date.getDate()).padStart(2, '0')}`;
};

export const ForecastBar = ({ day, maxCount }: ForecastBarProps) => {
  const widthPercent = maxCount > 0 ? Math.round((day.due_count / maxCount) * 100) : 0;

  return (
    <div
      className="flex items-center gap-2 py-1"
      data-testid="forecast-bar"
    >
      <span className="text-xs text-gray-500 w-12 flex-shrink-0" data-testid="forecast-date">
        {formatDate(day.date)}
      </span>
      <div className="flex-1 h-5 bg-gray-100 rounded overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded transition-all duration-300"
          style={{ width: `${widthPercent}%` }}
          data-testid="forecast-bar-fill"
        />
      </div>
      <span
        className="text-xs font-medium text-gray-700 w-8 text-right flex-shrink-0"
        data-testid="forecast-count"
      >
        {day.due_count}
      </span>
    </div>
  );
};
