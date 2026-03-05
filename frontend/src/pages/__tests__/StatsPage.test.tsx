/**
 * 【テスト概要】: 学習統計ダッシュボードページのテスト
 * 【テスト対象】: StatsPage コンポーネント + 各サブコンポーネント
 * 【テスト対応】: TASK-0154
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { StatsPage } from '../StatsPage';
import type { StatsResponse, WeakCardsResponse, ForecastResponse } from '@/types';

// useStats フックのモック
const mockRefresh = vi.fn();
const mockUseStats = vi.fn();

vi.mock('@/hooks/useStats', () => ({
  useStats: () => mockUseStats(),
}));

// テスト用モックデータ
const mockStats: StatsResponse = {
  total_cards: 120,
  learned_cards: 95,
  unlearned_cards: 25,
  cards_due_today: 12,
  total_reviews: 450,
  average_grade: 3.2,
  streak_days: 5,
  tag_performance: {},
};

const mockWeakCards: WeakCardsResponse = {
  weak_cards: [
    {
      card_id: 'card-1',
      front: 'What is the capital of France?',
      back: 'Paris',
      ease_factor: 1.3,
      repetitions: 5,
    },
    {
      card_id: 'card-2',
      front: 'What is photosynthesis?',
      back: 'The process by which plants convert light into energy',
      ease_factor: 1.5,
      repetitions: 3,
    },
  ],
  total_count: 2,
};

const mockForecast: ForecastResponse = {
  forecast: [
    { date: '2026-03-05', due_count: 12 },
    { date: '2026-03-06', due_count: 8 },
    { date: '2026-03-07', due_count: 5 },
    { date: '2026-03-08', due_count: 15 },
    { date: '2026-03-09', due_count: 3 },
    { date: '2026-03-10', due_count: 7 },
    { date: '2026-03-11', due_count: 10 },
  ],
};

const renderStatsPage = () => {
  return render(
    <MemoryRouter>
      <StatsPage />
    </MemoryRouter>,
  );
};

describe('StatsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseStats.mockReturnValue({
      stats: mockStats,
      weakCards: mockWeakCards,
      forecast: mockForecast,
      isLoading: false,
      error: null,
      refresh: mockRefresh,
    });
  });

  describe('ローディング状態', () => {
    beforeEach(() => {
      mockUseStats.mockReturnValue({
        stats: null,
        weakCards: null,
        forecast: null,
        isLoading: true,
        error: null,
        refresh: mockRefresh,
      });
    });

    it('ローディング中はスピナーが表示される', () => {
      renderStatsPage();
      expect(screen.getByText('統計データを読み込み中...')).toBeInTheDocument();
    });

    it('ローディング中はメインコンテンツが表示されない', () => {
      renderStatsPage();
      expect(screen.queryByText('学習統計')).not.toBeInTheDocument();
    });
  });

  describe('エラー状態', () => {
    beforeEach(() => {
      mockUseStats.mockReturnValue({
        stats: null,
        weakCards: null,
        forecast: null,
        isLoading: false,
        error: new Error('API Error'),
        refresh: mockRefresh,
      });
    });

    it('エラー時にエラーメッセージが表示される', () => {
      renderStatsPage();
      expect(screen.getByText('統計データの取得に失敗しました')).toBeInTheDocument();
    });

    it('再試行ボタンが表示され、クリックで refresh が呼ばれる', async () => {
      renderStatsPage();
      const retryButton = screen.getByText('再試行');
      await userEvent.click(retryButton);
      expect(mockRefresh).toHaveBeenCalledTimes(1);
    });
  });

  describe('統計データ表示', () => {
    it('ページタイトル「学習統計」が表示される', () => {
      renderStatsPage();
      expect(screen.getByRole('heading', { name: '学習統計' })).toBeInTheDocument();
    });

    it('連続学習日数が表示される', () => {
      renderStatsPage();
      expect(screen.getByTestId('streak-display')).toBeInTheDocument();
      expect(screen.getByText(/5日連続学習中/)).toBeInTheDocument();
    });

    it('統計サマリーが表示される', () => {
      renderStatsPage();
      expect(screen.getByTestId('stats-summary')).toBeInTheDocument();
    });

    it('統計カードに正しい値が表示される', () => {
      renderStatsPage();
      const cards = screen.getAllByTestId('stat-card');
      expect(cards).toHaveLength(4);
      expect(screen.getByText('120')).toBeInTheDocument();
      expect(screen.getByText('95')).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('12枚')).toBeInTheDocument();
    });

    it('進捗バーが表示される', () => {
      renderStatsPage();
      expect(screen.getByTestId('progress-bar')).toBeInTheDocument();
      expect(screen.getByTestId('progress-percentage')).toHaveTextContent('79%');
    });

    it('追加統計（総復習、平均）が表示される', () => {
      renderStatsPage();
      expect(screen.getByTestId('total-reviews')).toHaveTextContent('450回');
      expect(screen.getByTestId('average-grade')).toHaveTextContent('3.2');
    });

    it('復習予測が表示される', () => {
      renderStatsPage();
      expect(screen.getByTestId('review-forecast')).toBeInTheDocument();
      const bars = screen.getAllByTestId('forecast-bar');
      expect(bars).toHaveLength(7);
    });

    it('予測日付とカード数が表示される', () => {
      renderStatsPage();
      const counts = screen.getAllByTestId('forecast-count');
      expect(counts[0]).toHaveTextContent('12');
      expect(counts[1]).toHaveTextContent('8');
    });

    it('苦手カード一覧が表示される', () => {
      renderStatsPage();
      expect(screen.getByTestId('weak-cards-list')).toBeInTheDocument();
      const items = screen.getAllByTestId('weak-card-item');
      expect(items).toHaveLength(2);
    });

    it('苦手カードのフロントテキストとEFが表示される', () => {
      renderStatsPage();
      expect(screen.getByText('What is the capital of France?')).toBeInTheDocument();
      expect(screen.getByText('EF:1.3')).toBeInTheDocument();
    });

    it('苦手カードがカード詳細にリンクされる', () => {
      renderStatsPage();
      const items = screen.getAllByTestId('weak-card-item');
      expect(items[0]).toHaveAttribute('href', '/cards/card-1');
    });
  });

  describe('空の苦手カード', () => {
    beforeEach(() => {
      mockUseStats.mockReturnValue({
        stats: mockStats,
        weakCards: { weak_cards: [], total_count: 0 },
        forecast: mockForecast,
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });
    });

    it('苦手カードが0件の場合、空メッセージが表示される', () => {
      renderStatsPage();
      expect(screen.getByTestId('weak-cards-empty')).toBeInTheDocument();
      expect(screen.getByText('苦手なカードはありません')).toBeInTheDocument();
    });
  });

  describe('ストリーク表示バリエーション', () => {
    it('ストリーク0日の場合「今日から始めよう！」が表示される', () => {
      mockUseStats.mockReturnValue({
        stats: { ...mockStats, streak_days: 0 },
        weakCards: mockWeakCards,
        forecast: mockForecast,
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });
      renderStatsPage();
      expect(screen.getByText('今日から始めよう！')).toBeInTheDocument();
    });

    it('ストリーク1日以上の場合「N日連続学習中！」が表示される', () => {
      mockUseStats.mockReturnValue({
        stats: { ...mockStats, streak_days: 10 },
        weakCards: mockWeakCards,
        forecast: mockForecast,
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });
      renderStatsPage();
      expect(screen.getByText(/10日連続学習中/)).toBeInTheDocument();
    });
  });

  describe('ナビゲーション', () => {
    it('フッターナビゲーションが表示される', () => {
      renderStatsPage();
      expect(screen.getByRole('navigation', { name: 'メインナビゲーション' })).toBeInTheDocument();
    });

    it('ローディング時もナビゲーションが表示される', () => {
      mockUseStats.mockReturnValue({
        stats: null,
        weakCards: null,
        forecast: null,
        isLoading: true,
        error: null,
        refresh: mockRefresh,
      });
      renderStatsPage();
      expect(screen.getByRole('navigation', { name: 'メインナビゲーション' })).toBeInTheDocument();
    });

    it('エラー時もナビゲーションが表示される', () => {
      mockUseStats.mockReturnValue({
        stats: null,
        weakCards: null,
        forecast: null,
        isLoading: false,
        error: new Error('Error'),
        refresh: mockRefresh,
      });
      renderStatsPage();
      expect(screen.getByRole('navigation', { name: 'メインナビゲーション' })).toBeInTheDocument();
    });
  });
});
