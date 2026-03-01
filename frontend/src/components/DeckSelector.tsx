/**
 * デッキ選択コンポーネント
 * ドロップダウンでデッキ一覧を表示し、選択中デッキのカラーインジケーターを付与する。
 */
import { useDecksContext } from '@/contexts/DecksContext';

/**
 * DeckSelector のプロパティ
 * @property value - 現在選択中のデッキID（null は未分類）
 * @property onChange - 選択変更時のコールバック
 * @property className - 追加 CSS クラス
 * @property disabled - 無効化フラグ
 */
interface DeckSelectorProps {
  value?: string | null;
  onChange: (deckId: string | null) => void;
  className?: string;
  disabled?: boolean;
}

/**
 * デッキ選択ドロップダウン
 * DecksContext からデッキ一覧を取得して select 要素で表示する。
 */
export const DeckSelector = ({
  value,
  onChange,
  className = '',
  disabled = false,
}: DeckSelectorProps) => {
  const { decks } = useDecksContext();

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
        {decks.map((deck) => (
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
              decks.find((d) => d.deck_id === value)?.color || '#6B7280',
          }}
        />
      )}
    </div>
  );
};
