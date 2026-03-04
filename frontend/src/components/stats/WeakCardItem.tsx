/**
 * 【機能概要】: 個別弱点カード表示コンポーネント
 * 【実装方針】: フロントテキスト（truncate）とease_factorバッジを表示
 * 【テスト対応】: TASK-0154
 * 🔵 青信号: 設計文書 architecture.md のコンポーネント設計より
 */
import { Link } from 'react-router-dom';
import type { WeakCard } from '@/types';

interface WeakCardItemProps {
  card: WeakCard;
  rank: number;
}

export const WeakCardItem = ({ card, rank }: WeakCardItemProps) => {
  return (
    <Link
      to={`/cards/${card.card_id}`}
      className="flex items-center justify-between p-3 hover:bg-gray-50 active:bg-gray-100 transition-colors min-h-[44px]"
      data-testid="weak-card-item"
    >
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <span className="text-sm font-medium text-gray-400 w-6 flex-shrink-0">
          {rank}.
        </span>
        <span className="text-sm text-gray-800 truncate" data-testid="weak-card-front">
          {card.front}
        </span>
      </div>
      <span
        className="ml-2 flex-shrink-0 text-xs font-medium px-2 py-1 rounded-full bg-red-100 text-red-700"
        data-testid="weak-card-ease"
      >
        EF:{card.ease_factor.toFixed(1)}
      </span>
    </Link>
  );
};
