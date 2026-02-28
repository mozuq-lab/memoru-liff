/**
 * 【機能概要】: カード検索バーコンポーネント
 * 【実装方針】: 入力フィールドとクリアボタンを提供
 * 【テスト対応】: SB-001〜SB-008
 */

interface SearchBarProps {
  /** 現在の検索文字列 */
  value: string;
  /** 検索文字列変更ハンドラ */
  onChange: (value: string) => void;
  /** プレースホルダーテキスト（デフォルト: "カードを検索..."） */
  placeholder?: string;
  /** 最大文字数（デフォルト: 100） */
  maxLength?: number;
}

/**
 * 検索バーコンポーネント。キーワード入力と one-click クリアボタンを提供する。
 */
export const SearchBar = ({
  value,
  onChange,
  placeholder = 'カードを検索...',
  maxLength = 100,
}: SearchBarProps) => {
  return (
    <div className="relative flex items-center">
      {/* 検索アイコン */}
      <svg
        className="absolute left-3 w-4 h-4 text-gray-400 pointer-events-none"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>

      {/* 入力フィールド */}
      <input
        type="search"
        role="searchbox"
        data-testid="search-bar-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        aria-label="カードを検索"
        className="w-full pl-9 pr-9 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent bg-white"
      />

      {/* クリアボタン（value が空でないときのみ表示） */}
      {value && (
        <button
          type="button"
          data-testid="search-bar-clear"
          onClick={() => onChange('')}
          aria-label="検索をクリア"
          className="absolute right-3 w-4 h-4 flex items-center justify-center text-gray-400 hover:text-gray-600"
        >
          <svg
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      )}
    </div>
  );
};
