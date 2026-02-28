/**
 * 【機能概要】: カードリストコンポーネント
 * 【実装方針】: カードの一覧表示とリンク機能を提供
 * 【テスト対応】: TASK-0016 テストケース1, 6
 * 🟡 黄信号: user-stories.md 3.2より
 */
import { Link } from "react-router-dom";
import type { Card } from "@/types";
import { formatDueDate, getDueStatus } from "@/utils/date";
import { HighlightText } from "./HighlightText";

interface CardListProps {
  cards: Card[];
  /** 検索キーワード（HighlightText に渡す）。省略可 */
  highlightQuery?: string;
}

/**
 * 【機能概要】: カードリストコンポーネント
 * 【実装方針】: カードをリスト形式で表示
 */
export const CardList = ({ cards, highlightQuery = "" }: CardListProps) => {
  return (
    <ul className="space-y-3 list-none p-0 m-0" aria-label="カード一覧">
      {cards.map((card) => (
        <CardListItem
          key={card.card_id}
          card={card}
          highlightQuery={highlightQuery}
        />
      ))}
    </ul>
  );
};

interface CardListItemProps {
  card: Card;
  highlightQuery?: string;
}

/**
 * 【機能概要】: カードリストアイテムコンポーネント
 * 【実装方針】: 個別カードの表示とリンク
 */
const CardListItem = ({ card, highlightQuery = "" }: CardListItemProps) => {
  const dueStatus = card.next_review_at
    ? getDueStatus(card.next_review_at)
    : null;

  // ステータスに応じた色設定
  const statusColors: Record<string, string> = {
    overdue: "text-red-600 bg-red-50",
    today: "text-orange-600 bg-orange-50",
    upcoming: "text-green-600 bg-green-50",
    future: "text-gray-600 bg-gray-50",
  };

  return (
    <li>
      <Link
        to={`/cards/${card.card_id}`}
        className="block bg-white rounded-lg shadow p-4 hover:bg-gray-50 active:bg-gray-100 transition-colors"
        data-testid={`card-item-${card.card_id}`}
      >
        <div className="flex justify-between items-start">
          <div className="flex-1 min-w-0">
            <p
              className="text-gray-800 font-medium truncate"
              data-testid="card-front"
            >
              <HighlightText text={card.front} query={highlightQuery} />
            </p>
            <p
              className="text-gray-500 text-sm mt-1 truncate"
              data-testid="card-back"
            >
              <HighlightText text={card.back} query={highlightQuery} />
            </p>
          </div>
          {dueStatus && (
            <div className="ml-4 shrink-0">
              <span
                className={`text-xs px-2 py-1 rounded ${statusColors[dueStatus.status]}`}
                data-testid="due-status"
              >
                {dueStatus.label}
              </span>
            </div>
          )}
        </div>
        {card.next_review_at && (
          <div className="mt-2 text-xs text-gray-400" data-testid="due-date">
            次回復習: {formatDueDate(card.next_review_at)}
          </div>
        )}
      </Link>
    </li>
  );
};
