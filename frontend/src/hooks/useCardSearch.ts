/**
 * 【機能概要】: カード検索・フィルター・ソート状態管理フック
 * 【実装方針】: useMemo で filteredCards を計算し、依存変化時のみ再計算
 * 【テスト対応】: TDD - useCardSearch.test.ts
 */
import { useState, useMemo } from 'react';
import type { Card, ReviewStatusFilter, SortByOption, SortOrder } from '@/types';

interface UseCardSearchOptions {
  /** フィルタリング対象のカード配列 */
  cards: Card[];
}

interface UseCardSearchReturn {
  // 状態
  query: string;
  reviewStatus: ReviewStatusFilter;
  sortBy: SortByOption;
  sortOrder: SortOrder;

  // 状態更新
  setQuery: (query: string) => void;
  setReviewStatus: (status: ReviewStatusFilter) => void;
  setSortBy: (sortBy: SortByOption) => void;
  setSortOrder: (order: SortOrder) => void;

  // 計算値
  /** フィルタリング・ソート済みカード配列 */
  filteredCards: Card[];

  // アクション
  /** すべてのフィルターをリセット */
  reset: () => void;
}

/** 文字列を NFKC 正規化して小文字に変換（全角・半角・大小文字統一） */
const normalize = (str: string): string => str.normalize('NFKC').toLowerCase();

/** カードの復習状態を判定する */
const getReviewStatus = (card: Card, today: string): ReviewStatusFilter => {
  if (card.repetitions === 0) return 'new';
  if (card.next_review_at && card.next_review_at <= today) return 'due';
  return 'learning';
};

/**
 * カード検索・フィルター・ソートの状態を管理するカスタムフック
 */
export const useCardSearch = ({ cards }: UseCardSearchOptions): UseCardSearchReturn => {
  const [query, setQuery] = useState('');
  const [reviewStatus, setReviewStatus] = useState<ReviewStatusFilter>('all');
  const [sortBy, setSortBy] = useState<SortByOption>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const filteredCards = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
    const normalizedQuery = normalize(query);

    // Step 1: クエリフィルター
    let result = cards;
    if (query) {
      result = result.filter((card) => {
        const normalizedFront = normalize(card.front);
        const normalizedBack = normalize(card.back);
        return (
          normalizedFront.includes(normalizedQuery) ||
          normalizedBack.includes(normalizedQuery)
        );
      });
    }

    // Step 2: reviewStatus フィルター
    if (reviewStatus !== 'all') {
      result = result.filter(
        (card) => getReviewStatus(card, today) === reviewStatus
      );
    }

    // Step 3: ソート（安定ソートのためスライスして元配列を保護）
    result = [...result].sort((a, b) => {
      let comparison = 0;

      if (sortBy === 'created_at') {
        comparison = a.created_at.localeCompare(b.created_at);
      } else if (sortBy === 'ease_factor') {
        comparison = a.ease_factor - b.ease_factor;
      } else if (sortBy === 'next_review_at') {
        // null は末尾
        const aVal = a.next_review_at ?? '\uFFFF'; // 最大文字で末尾にする
        const bVal = b.next_review_at ?? '\uFFFF';
        comparison = aVal.localeCompare(bVal);
      }

      return sortOrder === 'asc' ? comparison : -comparison;
    });

    return result;
  }, [cards, query, reviewStatus, sortBy, sortOrder]);

  const reset = () => {
    setQuery('');
    setReviewStatus('all');
    setSortBy('created_at');
    setSortOrder('desc');
  };

  return {
    query,
    reviewStatus,
    sortBy,
    sortOrder,
    setQuery,
    setReviewStatus,
    setSortBy,
    setSortOrder,
    filteredCards,
    reset,
  };
};
