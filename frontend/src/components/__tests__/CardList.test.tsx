/**
 * 【テスト概要】: カードリストコンポーネントのテスト
 * 【テスト対象】: CardList コンポーネント
 * 【テスト対応】: TASK-0016 テストケース1, 2, 6
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CardList } from '../CardList';
import type { Card } from '@/types';

const mockCards: Card[] = [
  {
    id: 'card-1',
    user_id: 'user-1',
    front: '質問1',
    back: '回答1',
    tags: ['tag1'],
    ease_factor: 2.5,
    interval: 1,
    repetitions: 0,
    due_date: '2024-01-15',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'card-2',
    user_id: 'user-1',
    front: '質問2',
    back: '回答2',
    tags: [],
    ease_factor: 2.5,
    interval: 3,
    repetitions: 1,
    due_date: '2024-01-20',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

const renderCardList = (cards: Card[] = mockCards) => {
  return render(
    <MemoryRouter>
      <CardList cards={cards} />
    </MemoryRouter>
  );
};

describe('CardList', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-15T00:00:00'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('カード表示', () => {
    it('複数のカードが表示される', () => {
      renderCardList();

      expect(screen.getByText('質問1')).toBeInTheDocument();
      expect(screen.getByText('質問2')).toBeInTheDocument();
    });

    it('カードの表面と裏面が表示される', () => {
      renderCardList();

      expect(screen.getByText('質問1')).toBeInTheDocument();
      expect(screen.getByText('回答1')).toBeInTheDocument();
    });

    it('リストにrole属性がある', () => {
      renderCardList();

      expect(screen.getByRole('list', { name: 'カード一覧' })).toBeInTheDocument();
    });
  });

  describe('復習日表示', () => {
    it('次回復習日が表示される', () => {
      renderCardList();

      expect(screen.getAllByTestId('due-date')[0]).toHaveTextContent('次回復習: 1月15日(月)');
    });

    it('今日のカードは「今日」と表示される', () => {
      const todayCard: Card = {
        ...mockCards[0],
        due_date: '2024-01-15',
      };
      renderCardList([todayCard]);

      expect(screen.getByTestId('due-status')).toHaveTextContent('今日');
    });

    it('期限切れのカードは「期限切れ」と表示される', () => {
      const overdueCard: Card = {
        ...mockCards[0],
        due_date: '2024-01-14',
      };
      renderCardList([overdueCard]);

      expect(screen.getByTestId('due-status')).toHaveTextContent('期限切れ');
    });

    it('もうすぐのカードは「もうすぐ」と表示される', () => {
      const upcomingCard: Card = {
        ...mockCards[0],
        due_date: '2024-01-16',
      };
      renderCardList([upcomingCard]);

      expect(screen.getByTestId('due-status')).toHaveTextContent('もうすぐ');
    });
  });

  describe('リンク', () => {
    it('各カードに詳細画面へのリンクがある', () => {
      renderCardList();

      const card1Link = screen.getByTestId('card-item-card-1');
      const card2Link = screen.getByTestId('card-item-card-2');

      expect(card1Link).toHaveAttribute('href', '/cards/card-1');
      expect(card2Link).toHaveAttribute('href', '/cards/card-2');
    });
  });

  describe('空配列', () => {
    it('空配列の場合は何も表示されない', () => {
      renderCardList([]);

      expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
    });
  });
});
