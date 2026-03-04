/**
 * 【機能概要】: カードの読み上げ/停止トグルボタン
 * 【テスト対応】: SpeechButton.test.tsx
 */
interface SpeechButtonProps {
  /** 読み上げ対象テキスト（空のとき disabled を推奨） */
  text: string;
  /** 現在発話中かどうか */
  isSpeaking: boolean;
  /** クリック時のコールバック（発話開始 or 停止） */
  onClick: () => void;
  /** テキストが空のとき disabled にする。省略時 false */
  disabled?: boolean;
  /** アクセシビリティ用ラベル接頭辞（例: "表面", "裏面"） */
  label?: string;
}

export const SpeechButton = ({
  text: _text,
  isSpeaking,
  onClick,
  disabled = false,
  label,
}: SpeechButtonProps) => {
  const ariaLabel = label
    ? isSpeaking
      ? `${label}の読み上げを停止`
      : `${label}を読み上げ`
    : isSpeaking
      ? "読み上げを停止"
      : "読み上げ";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className={[
        "rounded-full p-2 leading-none transition-colors min-h-[36px] min-w-[36px] flex items-center justify-center text-base",
        disabled
          ? "opacity-40 cursor-not-allowed bg-gray-100 text-gray-400"
          : isSpeaking
            ? "bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800"
            : "bg-blue-100 text-blue-700 hover:bg-blue-200 active:bg-blue-300",
      ].join(" ")}
    >
      {isSpeaking ? "■" : "▶"}
    </button>
  );
};
