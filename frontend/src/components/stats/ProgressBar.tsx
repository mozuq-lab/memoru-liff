/**
 * 【機能概要】: 学習進捗バーコンポーネント
 * 【実装方針】: 水平プログレスバーでパーセンテージを表示
 * 【テスト対応】: TASK-0154
 * 🔵 青信号: 設計文書 architecture.md のコンポーネント設計より
 */

interface ProgressBarProps {
  current: number;
  total: number;
  label?: string;
}

export const ProgressBar = ({ current, total, label }: ProgressBarProps) => {
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0;

  return (
    <div className="w-full" data-testid="progress-bar">
      {label && (
        <div className="flex justify-between items-center mb-1">
          <span className="text-sm text-gray-600">{label}</span>
          <span className="text-sm font-medium text-gray-700" data-testid="progress-percentage">
            {percentage}%
          </span>
        </div>
      )}
      {!label && (
        <div className="flex justify-end mb-1">
          <span className="text-sm font-medium text-gray-700" data-testid="progress-percentage">
            {percentage}%
          </span>
        </div>
      )}
      <div
        className="w-full bg-gray-200 rounded-full h-3"
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label || '学習進捗'}
      >
        <div
          className="bg-blue-600 h-3 rounded-full transition-all duration-300"
          style={{ width: `${percentage}%` }}
          data-testid="progress-fill"
        />
      </div>
    </div>
  );
};
