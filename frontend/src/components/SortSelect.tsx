/**
 * 【機能概要】: カードソートセレクトコンポーネント
 * 【実装方針】: ソートキー選択ドロップダウンとソート方向トグルボタンを提供
 * 【テスト対応】: SS-001〜SS-006
 */
import type { SortByOption, SortOrder } from '@/types';

interface SortSelectProps {
  /** 現在のソートキー */
  sortBy: SortByOption;
  /** 現在のソート方向 */
  sortOrder: SortOrder;
  /** ソートキー変更ハンドラ */
  onSortByChange: (sortBy: SortByOption) => void;
  /** ソート方向変更ハンドラ */
  onSortOrderChange: (order: SortOrder) => void;
}

/** ソートキーオプション定義 */
const SORT_BY_OPTIONS: { value: SortByOption; label: string }[] = [
  { value: 'created_at', label: '作成日' },
  { value: 'next_review_at', label: '次回復習日' },
  { value: 'ease_factor', label: '習熟度' },
];

/** 型ガード: 文字列が有効な SortByOption か判定する */
const isSortByOption = (value: string): value is SortByOption =>
  SORT_BY_OPTIONS.some((option) => option.value === value);

/**
 * カードソートコンポーネント。
 * ソートキーのドロップダウンとソート方向のトグルボタンを提供する。
 */
export const SortSelect = ({
  sortBy,
  sortOrder,
  onSortByChange,
  onSortOrderChange,
}: SortSelectProps) => {
  const handleToggleOrder = () => {
    onSortOrderChange(sortOrder === 'asc' ? 'desc' : 'asc');
  };

  return (
    <div className="flex items-center gap-2">
      {/* ソートキー選択ドロップダウン */}
      <select
        data-testid="sort-by-select"
        value={sortBy}
        onChange={(e) => {
          const value = e.target.value;
          if (isSortByOption(value)) {
            onSortByChange(value);
          }
        }}
        aria-label="ソートキー"
        className="text-xs border border-gray-300 rounded px-2 py-1 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400"
      >
        {SORT_BY_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      {/* ソート方向トグルボタン */}
      <button
        type="button"
        data-testid="sort-order-toggle"
        onClick={handleToggleOrder}
        aria-label={sortOrder === 'asc' ? '昇順（クリックで降順に切り替え）' : '降順（クリックで昇順に切り替え）'}
        className="flex items-center px-2 py-1 text-xs border border-gray-300 rounded bg-white text-gray-700 hover:border-blue-400 hover:text-blue-600 transition-colors"
      >
        {sortOrder === 'asc' ? (
          <>
            <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
            </svg>
            昇順
          </>
        ) : (
          <>
            <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4" />
            </svg>
            降順
          </>
        )}
      </button>
    </div>
  );
};
