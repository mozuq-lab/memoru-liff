/**
 * 【機能概要】: カードリストコンポーネント
 * 【実装方針】: カードの一覧表示とリンク機能を提供
 * 【テスト対応】: TASK-0016 テストケース1, 6
 * 🟡 黄信号: user-stories.md 3.2より
 */
import { Link } from 'react-router-dom';
import type { Card } from '@/types';
import { formatDueDate, getDueStatus } from '@/utils/date';

interface CardListProps {
  cards: Card[];
}

/**
 * 【機能概要】: カードリストコンポーネント
 * 【実装方針】: カードをリスト形式で表示
 */
export const CardList = ({ cards }: CardListProps) => {
  return (
    <div className="space-y-3" role="list" aria-label="カード一覧">
      {cards.map((card) => (
        <CardListItem key={card.id} card={card} />
      ))}
    </div>
  );
};

interface CardListItemProps {
  card: Card;
}

/**
 * 【機能概要】: カードリストアイテムコンポーネント
 * 【実装方針】: 個別カードの表示とリンク
 */
const CardListItem = ({ card }: CardListItemProps) => {
  const dueStatus = getDueStatus(card.due_date);

  // ステータスに応じた色設定
  const statusColors: Record<string, string> = {
    overdue: 'text-red-600 bg-red-50',
    today: 'text-orange-600 bg-orange-50',
    upcoming: 'text-green-600 bg-green-50',
    future: 'text-gray-600 bg-gray-50',
  };

  return (
    <Link
      to={`/cards/${card.id}`}
      className="block bg-white rounded-lg shadow p-4 hover:bg-gray-50 active:bg-gray-100 transition-colors"
      role="listitem"
      data-testid={`card-item-${card.id}`}
    >
      <div className="flex justify-between items-start">
        <div className="flex-1 min-w-0">
          <p className="text-gray-800 font-medium truncate" data-testid="card-front">
            {card.front}
          </p>
          <p className="text-gray-500 text-sm mt-1 truncate" data-testid="card-back">
            {card.back}
          </p>
        </div>
        <div className="ml-4 flex-shrink-0">
          <span
            className={`text-xs px-2 py-1 rounded ${statusColors[dueStatus.status]}`}
            data-testid="due-status"
          >
            {dueStatus.label}
          </span>
        </div>
      </div>
      <div className="mt-2 text-xs text-gray-400" data-testid="due-date">
        次回復習: {formatDueDate(card.due_date)}
      </div>
    </Link>
  );
};
