/**
 * 【機能概要】: デッキ選択コンポーネント
 * 【実装方針】: ドロップダウンでデッキ一覧を表示、カラーインジケーター付き
 */
import { useDecksContext } from '@/contexts/DecksContext';

interface DeckSelectorProps {
  value?: string | null;
  onChange: (deckId: string | null) => void;
  className?: string;
  disabled?: boolean;
}

/**
 * 【機能概要】: デッキ選択ドロップダウン
 * 【実装方針】: DecksContext からデッキ一覧を取得して select で表示
 */
export const DeckSelector = ({
  value,
  onChange,
  className = '',
  disabled = false,
}: DeckSelectorProps) => {
  const { decks } = useDecksContext();

  // 「未分類」疑似デッキを除外
  const regularDecks = decks.filter((d) => d.deck_id !== 'unassigned');

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedValue = e.target.value;
    onChange(selectedValue === '' ? null : selectedValue);
  };

  return (
    <div className={`relative ${className}`}>
      <select
        value={value ?? ''}
        onChange={handleChange}
        disabled={disabled}
        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 pl-3 pr-10 disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="デッキを選択"
      >
        <option value="">未分類</option>
        {regularDecks.map((deck) => (
          <option key={deck.deck_id} value={deck.deck_id}>
            {deck.name}
          </option>
        ))}
      </select>
      {/* カラーインジケーター */}
      {value && (
        <div
          className="absolute left-1 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full pointer-events-none"
          style={{
            backgroundColor:
              regularDecks.find((d) => d.deck_id === value)?.color || '#6B7280',
          }}
        />
      )}
    </div>
  );
};
