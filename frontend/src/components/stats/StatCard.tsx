/**
 * 【機能概要】: 個別統計値カードコンポーネント
 * 【実装方針】: ラベルと値を表示するカード。アイコンとカラー指定に対応
 * 【テスト対応】: TASK-0154
 * 🔵 青信号: 設計文書 architecture.md のコンポーネント設計より
 */
import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: number | string;
  icon?: ReactNode;
  color?: string;
}

export const StatCard = ({ label, value, icon, color = 'text-blue-600' }: StatCardProps) => {
  return (
    <div
      className="bg-white rounded-lg shadow p-4 flex flex-col items-center justify-center min-h-[100px]"
      data-testid="stat-card"
    >
      {icon && (
        <span className={`mb-1 ${color}`} aria-hidden="true">
          {icon}
        </span>
      )}
      <span
        className={`text-2xl font-bold ${color}`}
        data-testid="stat-card-value"
      >
        {value}
      </span>
      <span className="text-xs text-gray-500 mt-1">{label}</span>
    </div>
  );
};
