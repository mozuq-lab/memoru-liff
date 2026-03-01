/**
 * 【テスト概要】: カード一覧画面のテスト
 * 【テスト対象】: CardsPage コンポーネント
 * 【テスト対応】: TASK-0016 テストケース1〜8, TASK-0091 deck_id フィルタ対応
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CardsPage } from '../CardsPage';
import type { Card } from '@/types';
import type { Deck } from '@/types';

// CardsContext モック
const mockFetchCards = vi.fn();
const mockFetchDueCards = vi.fn();
const mockCardsContext = {
  cards: [] as Card[],
  dueCards: [] as Card[],
  isLoading: false,
  error: null as Error | null,
  fetchCards: mockFetchCards,
  fetchDueCards: mockFetchDueCards,
  addCard: vi.fn(),
  updateCard: vi.fn(),
  deleteCard: vi.fn(),
  dueCount: 0,
  fetchDueCount: vi.fn(),
};

vi.mock('@/contexts/CardsContext', () => ({
  useCardsContext: () => mockCardsContext,
}));

// DecksContext モック（TASK-0091: deck_id フィルタ対応）
const mockDecksContext = {
  decks: [] as Deck[],
  isLoading: false,
  error: null as Error | null,
  fetchDecks: vi.fn(),
  createDeck: vi.fn(),
  updateDeck: vi.fn(),
  deleteDeck: vi.fn(),
};

vi.mock('@/contexts/DecksContext', () => ({
  useDecksContext: () => mockDecksContext,
}));

const mockCards: Card[] = [
  {
    card_id: 'card-1',
    user_id: 'user-1',
    front: '質問1',
    back: '回答1',
    tags: [],
    ease_factor: 2.5,
    interval: 1,
    repetitions: 0,
    next_review_at: '2024-01-15',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    card_id: 'card-2',
    user_id: 'user-1',
    front: '質問2',
    back: '回答2',
    tags: [],
    ease_factor: 2.5,
    interval: 3,
    repetitions: 1,
    next_review_at: '2024-01-20',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

const renderCardsPage = (locationState?: { message: string }, searchParams?: string) => {
  const path = searchParams ? `/cards?${searchParams}` : '/cards';
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/cards', search: searchParams ? `?${searchParams}` : '', state: locationState }]}>
      <CardsPage />
    </MemoryRouter>
  );
};

describe('CardsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCardsContext.cards = [];
    mockCardsContext.dueCards = [];
    mockCardsContext.isLoading = false;
    mockCardsContext.error = null;

    // 2024年1月15日を「今日」として固定
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-15T00:00:00'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('テストケース1: カード一覧の表示', () => {
    it('カードが表示される', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage();

      expect(screen.getByText('質問1')).toBeInTheDocument();
      expect(screen.getByText('質問2')).toBeInTheDocument();
    });

    it('カード数が表示される', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage();

      expect(screen.getByTestId('card-count')).toHaveTextContent('2枚のカード');
    });

    it('初期読み込み時にfetchCardsが呼ばれる', () => {
      renderCardsPage();
      expect(mockFetchCards).toHaveBeenCalled();
    });
  });

  describe('テストケース2: 次回復習日の表示', () => {
    it('復習日が日本語フォーマットで表示される', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage();

      expect(screen.getByText('次回復習: 1月15日(月)')).toBeInTheDocument();
    });
  });

  describe('テストケース3: 期限切れカードの表示', () => {
    it('期限切れステータスが表示される', () => {
      const overdueCard: Card = {
        ...mockCards[0],
        next_review_at: '2024-01-14',
      };
      mockCardsContext.cards = [overdueCard];
      renderCardsPage();

      expect(screen.getByTestId('due-status')).toHaveTextContent('期限切れ');
    });
  });

  describe('テストケース4: 今日が復習日のカード', () => {
    it('今日ステータスが表示される', () => {
      const todayCard: Card = {
        ...mockCards[0],
        next_review_at: '2024-01-15',
      };
      mockCardsContext.cards = [todayCard];
      renderCardsPage();

      expect(screen.getByTestId('due-status')).toHaveTextContent('今日');
    });
  });

  describe('テストケース6: カード詳細への遷移', () => {
    it('カードに詳細画面へのリンクがある', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage();

      const cardLink = screen.getByTestId('card-item-card-1');
      expect(cardLink).toHaveAttribute('href', '/cards/card-1');
    });
  });

  describe('テストケース7: 空状態の表示', () => {
    it('カードがない場合は空状態が表示される', () => {
      mockCardsContext.cards = [];
      renderCardsPage();

      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText('カードがありません')).toBeInTheDocument();
    });

    it('カード作成ボタンが表示される', () => {
      mockCardsContext.cards = [];
      renderCardsPage();

      expect(screen.getByText('カードを作成する')).toBeInTheDocument();
    });
  });

  describe('テストケース8: ローディング状態', () => {
    it('読み込み中はローディングが表示される', () => {
      mockCardsContext.isLoading = true;
      renderCardsPage();

      expect(screen.getByText('カードを読み込み中...')).toBeInTheDocument();
    });
  });

  describe('エラー状態', () => {
    it('エラー時はエラーメッセージが表示される', () => {
      mockCardsContext.error = new Error('API Error');
      renderCardsPage();

      expect(screen.getByText('カードの取得に失敗しました')).toBeInTheDocument();
    });
  });

  describe('復習開始ボタン', () => {
    it('復習対象タブでカードがある場合に復習開始ボタンが表示される', () => {
      mockCardsContext.dueCards = mockCards;
      renderCardsPage(undefined, 'tab=due');

      expect(screen.getByTestId('start-review-button')).toBeInTheDocument();
      expect(screen.getByTestId('start-review-button')).toHaveAttribute('href', '/review');
    });

    it('復習対象タブでカードが0枚の場合は復習開始ボタンが非表示', () => {
      mockCardsContext.dueCards = [];
      renderCardsPage(undefined, 'tab=due');

      expect(screen.queryByTestId('start-review-button')).not.toBeInTheDocument();
    });

    it('すべてタブでは復習開始ボタンが非表示', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage();

      expect(screen.queryByTestId('start-review-button')).not.toBeInTheDocument();
    });
  });

  describe('成功メッセージ', () => {
    it('location.stateからのメッセージが表示される', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage({ message: '3枚のカードを保存しました' });

      expect(screen.getByTestId('success-message')).toHaveTextContent('3枚のカードを保存しました');
    });
  });
});

/**
 * TASK-0091: CardsPage deck_id フィルタ対応テスト
 * 【テスト対象】: URL クエリパラメータ deck_id によるフィルタ機能
 * 【テスト対応】: TC-091-005〜TC-091-009, TC-091-E01〜E03, TC-091-B01〜B03
 */
describe('TASK-0091: CardsPage deck_id フィルタ対応', () => {
  // 【テスト前準備】: モック関数をクリア、デッキ情報を設定
  // 【環境初期化】: 各テストが独立した状態で実行されるよう初期化
  beforeEach(() => {
    vi.clearAllMocks();
    mockCardsContext.cards = [];
    mockCardsContext.dueCards = [];
    mockCardsContext.isLoading = false;
    mockCardsContext.error = null;
    mockDecksContext.decks = [];

    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-15T00:00:00'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('deck_id 指定時のカード取得（TC-091-005, TC-091-006）', () => {
    it('TC-091-005: URL に deck_id パラメータがある場合に fetchCards(deckId) が呼ばれる', () => {
      // 【テスト目的】: deck_id クエリパラメータによるカードフィルタが正しく動作すること
      // 【テスト内容】: URL に deck_id=deck-abc-123 がある場合、fetchCards('deck-abc-123') が呼ばれることを確認
      // 【期待される動作】: fetchCards が指定された deckId 引数付きで呼び出される
      // 🔵 青信号: REQ-001・architecture.md セクション6・dataflow.md フロー1 に基づく

      // 【初期条件設定】: MemoryRouter の initialEntries に deck_id パラメータ付き URL をセット
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=deck-abc-123' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証】: fetchCards が deckId 引数付きで呼ばれたことを確認
      // 【期待値確認】: mockFetchCards が 'deck-abc-123' を引数として呼び出される
      expect(mockFetchCards).toHaveBeenCalledWith('deck-abc-123'); // 【確認内容】: URL パラメータから Context への deckId 伝搬の正確性を保証 🔵
    });

    it('TC-091-006: URL に deck_id がない場合に fetchCards() が引数なしで呼ばれる', () => {
      // 【テスト目的】: deck_id 未指定時の従来動作が維持されること
      // 【テスト内容】: /cards（deck_id なし）でアクセスした際、fetchCards(undefined) が呼ばれることを確認
      // 【期待される動作】: fetchCards が引数なし（undefined）で呼び出される
      // 🔵 青信号: REQ-102・既存 CardsPage 動作に基づく

      // 【初期条件設定】: deck_id なしの通常アクセス
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証】: fetchCards が引数なし（undefined）で呼ばれたことを確認
      // 【期待値確認】: deck_id パラメータがない場合に全カード取得が行われること
      expect(mockFetchCards).toHaveBeenCalledWith(undefined); // 【確認内容】: 引数なしの呼び出しで全カード取得 🔵
    });
  });

  describe('deck_id 指定時のヘッダー表示（TC-091-007, TC-091-008）', () => {
    it('TC-091-007: deck_id 指定時にヘッダーにデッキ名が表示される', () => {
      // 【テスト目的】: deck_id が指定され DecksContext にデッキが存在する場合にデッキ名が表示されること
      // 【テスト内容】: URL に deck_id があり DecksContext.decks にデッキ名「英語基礎」が存在する場合のヘッダー
      // 【期待される動作】: ヘッダーに「英語基礎」のデッキ名が表示される
      // 🟡 黄信号: REQ-101 から妥当な推測（表示方法の詳細は要件で一部未定義）

      // 【テストデータ準備】: DecksContext にデッキ情報をセット（デッキ名検索用）
      mockDecksContext.decks = [
        {
          deck_id: 'deck-abc-123',
          name: '英語基礎',
          user_id: 'user-1',
          description: null,
          color: null,
          card_count: 10,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ];

      // 【初期条件設定】: deck_id パラメータ付き URL
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=deck-abc-123' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証】: ヘッダーにデッキ名が含まれることを確認
      // 【期待値確認】: cards-title 要素に「英語基礎」が表示されること
      expect(screen.getByTestId('cards-title')).toHaveTextContent('英語基礎'); // 【確認内容】: DecksContext から正しいデッキ名を検索して表示 🟡
    });

    it('TC-091-008: deck_id 未指定時にヘッダーが「カード一覧」を表示する', () => {
      // 【テスト目的】: deck_id がない場合に従来の「カード一覧」ヘッダーが表示されること
      // 【テスト内容】: /cards（deck_id なし）でアクセスした際のヘッダー表示
      // 【期待される動作】: ヘッダーに「カード一覧」が表示される
      // 🔵 青信号: 既存 CardsPage 実装・REQ-102 に基づく

      // 【初期条件設定】: deck_id なしの通常アクセス
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証】: ヘッダーに「カード一覧」が表示されることを確認
      // 【期待値確認】: 後方互換性。既存のUIを維持
      expect(screen.getByTestId('cards-title')).toHaveTextContent('カード一覧'); // 【確認内容】: 既存のヘッダー表示が維持されていること 🔵
    });
  });

  describe('タブ切り替え時の deck_id 保持（TC-091-009, TC-091-B02, TC-091-B03）', () => {
    it('TC-091-009: deck_id 指定時にタブが due の場合、fetchDueCards(deckId) が呼ばれる', () => {
      // 【テスト目的】: deck_id 指定時に復習対象タブで fetchDueCards に deckId が渡されること
      // 【テスト内容】: URL に deck_id=deck-abc-123&tab=due がある場合、fetchDueCards('deck-abc-123') が呼ばれること
      // 【期待される動作】: タブ切り替え後も deck_id パラメータが保持され fetchDueCards に deckId が渡される
      // 🟡 黄信号: TC-001-03 から妥当な推測

      // 【初期条件設定】: deck_id と tab=due の両方を含む URL
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=deck-abc-123&tab=due' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証】: fetchDueCards が deckId 引数付きで呼ばれたことを確認
      // 【期待値確認】: mockFetchDueCards が 'deck-abc-123' を引数として呼び出される
      expect(mockFetchDueCards).toHaveBeenCalledWith('deck-abc-123'); // 【確認内容】: タブ切り替え時に deck_id が失われていないこと 🟡
    });

    it('TC-091-B02: deck_id と tab=due の両方が指定された場合に正しくフィルタされる', () => {
      // 【テスト目的】: 複数クエリパラメータが同時指定された場合の正しい動作確認
      // 【テスト内容】: /cards?deck_id=deck-abc-123&tab=due でアクセスした際の動作
      // 【期待される動作】: fetchDueCards が 'deck-abc-123' を引数として呼ばれ、activeTab が 'due' で表示される
      // 🟡 黄信号: TC-001-03・既存 useSearchParams 実装パターンから妥当な推測

      // 【初期条件設定】: deck_id と tab=due の両方を含む URL
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=deck-abc-123&tab=due' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証1】: fetchDueCards が deckId 引数付きで呼ばれたことを確認
      expect(mockFetchDueCards).toHaveBeenCalledWith('deck-abc-123'); // 【確認内容】: deck_id が getDueCards に伝搬している 🟡
      // 【結果検証2】: fetchCards が呼ばれていないことを確認（tab=due のため）
      expect(mockFetchCards).not.toHaveBeenCalled(); // 【確認内容】: 復習対象タブでは fetchCards が呼ばれないこと 🟡
    });

    it('TC-091-B03: タブ切り替え後も URL の deck_id パラメータが保持される', async () => {
      // 【テスト目的】: setActiveTab による setSearchParams がタブ変更時に deck_id を失わないこと
      // 【テスト内容】: deck_id パラメータ付きで復習対象タブボタンをクリックした場合、deck_id が URL に残ること
      // 【期待される動作】: タブ切り替え後の URL が ?deck_id=deck-abc-123&tab=due のように deck_id を維持する
      // 🟡 黄信号: setActiveTab の setSearchParams 実装修正（Green フェーズ課題1）から妥当な推測

      // 【初期条件設定】: deck_id パラメータ付き URL（tab=all = デフォルト）
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=deck-abc-123' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【実際の処理実行】: 復習対象タブをクリック（fireEvent でクリックイベントを発火）
      const dueTab = screen.getByTestId('tab-due');
      fireEvent.click(dueTab);

      // 【結果検証】: タブ切り替え後に fetchDueCards が deckId 引数付きで呼ばれたことを確認
      // 【期待値確認】: setSearchParams が deck_id を保持してタブを変更すること
      expect(mockFetchDueCards).toHaveBeenCalledWith('deck-abc-123'); // 【確認内容】: タブ切り替え後も deck_id フィルタが維持されること 🟡
    });
  });

  describe('NFR-201: 全カードへの戻るナビゲーション', () => {
    it('TC-091-N01: deck_id 指定時に「全カードを表示」リンクが表示される', () => {
      // 【テスト目的】: deck_id 指定時に全カード一覧への戻りリンクが存在すること（NFR-201）
      // 【テスト内容】: deck_id パラメータ付き URL でアクセスした場合に back-to-all-cards リンクが表示されること
      // 【期待される動作】: ヘッダー部分に「全カードを表示」リンクが表示される
      // 🟡 黄信号: NFR-201 ユーザビリティ要件より

      // 【初期条件設定】: deck_id パラメータ付き URL
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=deck-abc-123' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証】: 全カードへのリンクが表示されることを確認
      const backLink = screen.getByTestId('back-to-all-cards');
      expect(backLink).toBeInTheDocument(); // 【確認内容】: deck_id 指定時に戻るリンクが表示されること 🟡
      expect(backLink).toHaveAttribute('href', '/cards'); // 【確認内容】: リンク先が /cards であること 🟡
    });

    it('TC-091-N02: deck_id 未指定時に「全カードを表示」リンクが表示されない', () => {
      // 【テスト目的】: deck_id がない場合に戻るリンクが表示されないこと（従来動作維持）
      // 【テスト内容】: /cards（deck_id なし）でアクセスした際に back-to-all-cards が存在しないこと
      // 【期待される動作】: 戻るリンクは非表示
      // 🟡 黄信号: NFR-201 から妥当な推測

      // 【初期条件設定】: deck_id なしの通常アクセス
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証】: 戻るリンクが表示されていないことを確認
      expect(screen.queryByTestId('back-to-all-cards')).not.toBeInTheDocument(); // 【確認内容】: deck_id なし時は戻るリンクが非表示 🟡
    });
  });

  describe('エッジケース（TC-091-E01, TC-091-E02, TC-091-E03, TC-091-B01）', () => {
    it('TC-091-E01: 存在しない deck_id で空のカード一覧が表示される', () => {
      // 【テスト目的】: 存在しないデッキへの安全なフォールバック確認（EDGE-003）
      // 【テスト内容】: API が空のカード配列を返した場合に空状態表示になること
      // 【期待される動作】: empty-state が表示され「カードがありません」メッセージが表示される
      // 🟡 黄信号: EDGE-003 から妥当な推測

      // 【テストデータ準備】: cards が空配列（空のカード一覧）
      mockCardsContext.cards = [];

      // 【初期条件設定】: 存在しない deck_id を含む URL
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=nonexistent-deck' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証】: 空状態が表示されることを確認
      // 【期待値確認】: アプリがクラッシュせず、正常な空状態を表示する
      expect(screen.getByTestId('empty-state')).toBeInTheDocument(); // 【確認内容】: 空状態要素が表示されている 🟡
      expect(screen.getByText('カードがありません')).toBeInTheDocument(); // 【確認内容】: 「カードがありません」メッセージが表示されている 🟡
    });

    it('TC-091-E02: DecksContext にデッキ情報がない場合のヘッダー表示フォールバック', () => {
      // 【テスト目的】: DecksContext 未ロード時の安全なフォールバック確認
      // 【テスト内容】: deck_id は URL に存在するが DecksContext.decks が空配列の場合
      // 【期待される動作】: ヘッダーにフォールバック表示（アプリがクラッシュしない）
      // 🟡 黄信号: REQ-201・note.md 注意事項より妥当な推測

      // 【テストデータ準備】: DecksContext.decks が空（未ロード状態を再現）
      mockDecksContext.decks = [];

      // 【初期条件設定】: deck_id パラメータ付き URL（ただし DecksContext にデッキなし）
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=deck-abc-123' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証】: アプリがクラッシュせず、何らかのヘッダーが表示されることを確認
      // 【期待値確認】: undefined のプロパティアクセスでクラッシュしない
      expect(screen.getByTestId('cards-title')).toBeInTheDocument(); // 【確認内容】: ヘッダー要素が存在すること（クラッシュしないこと）🟡
    });

    it('TC-091-E03: deck_id 指定時に API エラーが発生した場合にエラー表示される', () => {
      // 【テスト目的】: deck_id 指定時でもエラーハンドリングが正常に動作すること
      // 【テスト内容】: CardsContext.error がセットされた場合のエラー表示
      // 【期待される動作】: 「カードの取得に失敗しました」エラーメッセージが表示される
      // 🔵 青信号: 既存 CardsPage エラー表示パターンに基づく

      // 【テストデータ準備】: API エラーを模擬
      mockCardsContext.error = new Error('API Error');

      // 【初期条件設定】: deck_id パラメータ付き URL でエラー状態
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=deck-abc-123' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証】: エラーメッセージが表示されることを確認
      // 【期待値確認】: 既存のエラーハンドリングがフィルタ追加で壊れていないこと
      expect(screen.getByText('カードの取得に失敗しました')).toBeInTheDocument(); // 【確認内容】: エラーがハンドリングされエラーメッセージが表示される 🔵
    });

    it('TC-091-B01: deck_id が空文字列の場合は全カードが表示される（fetchCards(undefined) が呼ばれる）', () => {
      // 【テスト目的】: 空文字列の deck_id が適切にハンドリングされること
      // 【テスト内容】: ?deck_id= のように値なしのクエリパラメータが指定された場合
      // 【期待される動作】: fetchCards が引数なし（undefined）で呼ばれ、全カードが表示される
      // 🟡 黄信号: 一般的なクエリパラメータ処理のベストプラクティスから妥当な推測

      // 【初期条件設定】: 空文字列の deck_id を含む URL
      render(
        <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=' }]}>
          <CardsPage />
        </MemoryRouter>
      );

      // 【結果検証】: fetchCards が引数なし（undefined）で呼ばれたことを確認
      // 【期待値確認】: 空文字列を falsy として扱い、フィルタなしと同等に動作
      expect(mockFetchCards).toHaveBeenCalledWith(undefined); // 【確認内容】: 空文字列の deck_id は undefined として扱われること 🟡
    });
  });
});
