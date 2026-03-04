/**
 * 【機能概要】: 連続学習日数表示コンポーネント
 * 【実装方針】: 連続学習日数に応じた励ましメッセージを表示
 * 【テスト対応】: TASK-0154
 * 🔵 青信号: 設計文書 architecture.md のコンポーネント設計より
 */

interface StreakDisplayProps {
  streakDays: number;
}

export const StreakDisplay = ({ streakDays }: StreakDisplayProps) => {
  return (
    <div
      className="bg-white rounded-lg shadow p-4 text-center"
      data-testid="streak-display"
    >
      {streakDays > 0 ? (
        <p className="text-lg font-semibold text-orange-600" data-testid="streak-message">
          <span aria-hidden="true">🔥</span> {streakDays}日連続学習中！
        </p>
      ) : (
        <p className="text-lg font-semibold text-gray-500" data-testid="streak-message">
          今日から始めよう！
        </p>
      )}
    </div>
  );
};
