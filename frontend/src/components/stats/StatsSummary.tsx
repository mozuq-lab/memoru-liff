/**
 * 【機能概要】: 学習統計サマリーコンポーネント
 * 【実装方針】: 2x2 グリッドの StatCard + ProgressBar + 追加統計テキスト
 * 【テスト対応】: TASK-0154
 * 🔵 青信号: 設計文書 architecture.md のコンポーネント設計より
 */
import type { StatsResponse } from '@/types';
import { StatCard } from './StatCard';
import { ProgressBar } from './ProgressBar';

interface StatsSummaryProps {
  stats: StatsResponse;
}

export const StatsSummary = ({ stats }: StatsSummaryProps) => {
  return (
    <section
      className="mb-6"
      aria-label="学習統計サマリー"
      data-testid="stats-summary"
    >
      {/* 2x2 統計カードグリッド */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <StatCard
          label="総カード"
          value={stats.total_cards}
          color="text-blue-600"
        />
        <StatCard
          label="学習済み"
          value={stats.learned_cards}
          color="text-green-600"
        />
        <StatCard
          label="未学習"
          value={stats.unlearned_cards}
          color="text-gray-600"
        />
        <StatCard
          label="今日"
          value={`${stats.cards_due_today}枚`}
          color="text-orange-600"
        />
      </div>

      {/* 学習進捗バー */}
      <div className="bg-white rounded-lg shadow p-4 mb-4">
        <ProgressBar
          current={stats.learned_cards}
          total={stats.total_cards}
          label="学習進捗"
        />
      </div>

      {/* 追加統計 */}
      <div
        className="bg-white rounded-lg shadow p-4 flex justify-between text-sm text-gray-600"
        data-testid="stats-additional"
      >
        <span>
          総復習: <strong className="text-gray-800" data-testid="total-reviews">{stats.total_reviews}回</strong>
        </span>
        <span>
          平均: <strong className="text-gray-800" data-testid="average-grade">{stats.average_grade.toFixed(1)}</strong>
        </span>
      </div>
    </section>
  );
};
