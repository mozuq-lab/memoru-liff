/**
 * 【機能概要】: 弱点カード一覧コンポーネント
 * 【実装方針】: WeakCard 配列を受け取り WeakCardItem を一覧表示
 * 【テスト対応】: TASK-0154
 * 🔵 青信号: 設計文書 architecture.md のコンポーネント設計より
 */
import type { WeakCard } from '@/types';
import { WeakCardItem } from './WeakCardItem';

interface WeakCardsListProps {
  weakCards: WeakCard[];
}

export const WeakCardsList = ({ weakCards }: WeakCardsListProps) => {
  return (
    <section
      className="mb-6"
      aria-label="苦手カード"
      data-testid="weak-cards-list"
    >
      <h2 className="text-lg font-semibold text-gray-700 mb-3">
        <span aria-hidden="true">&#x26A0;</span> 苦手カード TOP 10
      </h2>

      {weakCards.length === 0 ? (
        <div
          className="bg-white rounded-lg shadow p-6 text-center text-gray-500"
          data-testid="weak-cards-empty"
        >
          苦手なカードはありません
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow divide-y divide-gray-100">
          {weakCards.map((card, index) => (
            <WeakCardItem
              key={card.card_id}
              card={card}
              rank={index + 1}
            />
          ))}
        </div>
      )}
    </section>
  );
};
