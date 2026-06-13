interface BackButtonProps {
  /** クリック時のハンドラ（通常は navigate(-1) など）。 */
  onClick: () => void;
  /** ボタン要素に付与する追加クラス（デフォルトは戻る矢印の標準スタイル）。 */
  className?: string;
  /** アクセシビリティラベル。 */
  ariaLabel?: string;
}

const DEFAULT_CLASS =
  "text-gray-600 min-h-[44px] min-w-[44px] flex items-center";

/**
 * 画面ヘッダーで使う「戻る」ボタン。
 * 複数ページで重複していた戻る矢印 SVG ボタンを共通化する。
 */
export const BackButton = ({
  onClick,
  className = DEFAULT_CLASS,
  ariaLabel = "戻る",
}: BackButtonProps) => (
  <button
    type="button"
    onClick={onClick}
    className={className}
    aria-label={ariaLabel}
  >
    <svg
      className="h-6 w-6"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15 19l-7-7 7-7"
      />
    </svg>
  </button>
);
