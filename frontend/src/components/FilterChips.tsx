/**
 * 【機能概要】: 復習状態フィルターチップコンポーネント
 * 【実装方針】: 4つのチップ（all/due/learning/new）を表示し、選択状態を aria-pressed で管理
 * 【テスト対応】: FC-001〜FC-004
 */
import type { ReviewStatusFilter } from '@/types';

interface FilterChipsProps {
  /** 選択中の復習状態フィルター */
  value: ReviewStatusFilter;
  /** 変更ハンドラ */
  onChange: (status: ReviewStatusFilter) => void;
}

/** チップ定義 */
const CHIPS: { value: ReviewStatusFilter; label: string; testId: string }[] = [
  { value: 'all', label: 'すべて', testId: 'filter-chip-all' },
  { value: 'due', label: '期日（due）', testId: 'filter-chip-due' },
  { value: 'learning', label: '学習中', testId: 'filter-chip-learning' },
  { value: 'new', label: '新規', testId: 'filter-chip-new' },
];

/**
 * 復習状態フィルターチップコンポーネント。
 * 4つのチップで復習状態を切り替える。
 */
export const FilterChips = ({ value, onChange }: FilterChipsProps) => {
  return (
    <div className="flex gap-2 flex-wrap" role="radiogroup" aria-label="復習状態フィルター">
      {CHIPS.map((chip) => {
        const isSelected = value === chip.value;
        return (
          <button
            key={chip.value}
            type="button"
            data-testid={chip.testId}
            aria-pressed={isSelected}
            onClick={() => onChange(chip.value)}
            className={`px-3 py-1 text-xs font-medium rounded-full border transition-colors ${
              isSelected
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400 hover:text-blue-600'
            }`}
          >
            {chip.label}
          </button>
        );
      })}
    </div>
  );
};
