/**
 * デッキサマリーコンポーネント（ホーム画面用）
 * 最大5件のデッキを due 数付きで表示し、0件時は CTA メッセージを表示する。
 */
import { Link, useNavigate } from 'react-router-dom';
import { useDecksContext } from '@/contexts/DecksContext';

/** ホーム画面に表示するデッキの最大件数 */
const MAX_DISPLAY_DECKS = 5;

/**
 * ホーム画面に表示するデッキサマリー
 * DecksContext からデッキ一覧を取得し、最大 MAX_DISPLAY_DECKS 件を表示する。
 */
export const DeckSummary = () => {
  const { decks } = useDecksContext();
  const navigate = useNavigate();

  // デッキ 0 件時の CTA メッセージ
  if (decks.length === 0) {
    return (
      <section className="bg-white rounded-lg shadow p-6" aria-label="デッキサマリー">
        <h2 className="text-lg font-semibold text-gray-700 mb-2">デッキ</h2>
        <p className="text-gray-500 text-sm mb-4">
          デッキを作成して学習を整理しましょう
        </p>
        <Link
          to="/decks"
          className="inline-block px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 active:bg-blue-800 min-h-[44px] transition-colors"
        >
          デッキを作成
        </Link>
      </section>
    );
  }

  const displayDecks = decks.slice(0, MAX_DISPLAY_DECKS);
  const hasMore = decks.length > MAX_DISPLAY_DECKS;

  return (
    <section className="bg-white rounded-lg shadow p-6" aria-label="デッキサマリー">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold text-gray-700">デッキ</h2>
        {hasMore && (
          <Link
            to="/decks"
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            すべて表示
          </Link>
        )}
      </div>

      <ul className="space-y-3">
        {displayDecks.map((deck) => (
          <li
            key={deck.deck_id}
            className="flex items-center justify-between cursor-pointer hover:bg-gray-50 rounded-lg p-2 -mx-2 transition-colors"
            onClick={() => navigate(`/cards?deck_id=${deck.deck_id}`)}
          >
            <div className="flex items-center min-w-0">
              <div
                className="w-3 h-3 rounded-full mr-3 flex-shrink-0"
                style={{ backgroundColor: deck.color || '#6B7280' }}
              />
              <span className="text-sm font-medium text-gray-800 truncate">
                {deck.name}
              </span>
            </div>
            <div className="flex items-center ml-2 flex-shrink-0">
              <span className="text-xs text-gray-500 mr-2">
                {deck.card_count}枚
              </span>
              {deck.due_count > 0 && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  {deck.due_count}
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>

      {!hasMore && (
        <div className="mt-4 pt-3 border-t">
          <Link
            to="/decks"
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            デッキを管理
          </Link>
        </div>
      )}
    </section>
  );
};
