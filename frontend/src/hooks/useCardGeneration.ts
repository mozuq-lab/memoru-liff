import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { cardsApi, getUserFacingMessage } from '@/services/api';
import { useDecksContext } from '@/contexts/DecksContext';
import type {
  GeneratedCard,
  GeneratedCardWithId,
  GenerateCardsRequest,
  GenerateFromUrlRequest,
  CreateCardRequest,
  PageInfo,
  CardType,
} from '@/types';

export type InputMode = 'text' | 'url';
export type UrlProgressStage = 'fetching' | 'analyzing' | 'generating';

export const MIN_CHARS = 5;
export const MAX_CHARS = 2000;
const MAX_GENERATION_TIME = 30000; // 30秒
const MAX_URL_GENERATION_TIME = 90000; // 90秒

type GeneratedCardsPayload = {
  generated_cards: GeneratedCard[];
};

type UrlGeneratedCardsPayload = GeneratedCardsPayload & {
  page_info: {
    url: string;
    title: string;
    fetched_at?: string;
  };
};

const hasGeneratedCardsPayload = (response: unknown): response is GeneratedCardsPayload => {
  if (typeof response !== 'object' || response === null) return false;
  const cards = (response as { generated_cards?: unknown }).generated_cards;
  return Array.isArray(cards) && cards.every(card => (
    typeof card === 'object' &&
    card !== null &&
    typeof (card as { front?: unknown }).front === 'string' &&
    typeof (card as { back?: unknown }).back === 'string' &&
    Array.isArray((card as { suggested_tags?: unknown }).suggested_tags)
  ));
};

const hasUrlGeneratedCardsPayload = (response: unknown): response is UrlGeneratedCardsPayload => {
  if (!hasGeneratedCardsPayload(response)) return false;
  const pageInfo = (response as { page_info?: unknown }).page_info;
  return (
    typeof pageInfo === 'object' &&
    pageInfo !== null &&
    typeof (pageInfo as { url?: unknown }).url === 'string' &&
    typeof (pageInfo as { title?: unknown }).title === 'string'
  );
};

const isAbortLikeError = (err: unknown): boolean => {
  if (typeof err !== 'object' || err === null || !('name' in err)) return false;
  const name = (err as { name?: unknown }).name;
  return name === 'AbortError' || name === 'TimeoutError';
};

const addTemporaryIds = (cards: GeneratedCard[]): GeneratedCardWithId[] =>
  cards.map((card, index) => ({
    ...card,
    tempId: `temp-${Date.now()}-${index}`,
  }));

/**
 * 【フック概要】: AI カード生成画面（テキスト / URL の 2 モード）の状態機械を GeneratePage の
 * 描画から分離して集約する。生成・保存・選択・編集・タブ切替・進捗タイマー・デッキ取得を担う。
 * 【設計方針】: ナビゲーションとデッキ取得はフック内で useNavigate / useDecksContext を直接呼び、
 * ページ側は本フックが返す状態・セッター・ハンドラを描画に使うだけにする。
 */
export const useCardGeneration = () => {
  const navigate = useNavigate();
  const { fetchDecks } = useDecksContext();

  // 共通 state
  const [inputMode, setInputMode] = useState<InputMode>('text');
  const [generatedCards, setGeneratedCards] = useState<GeneratedCardWithId[]>([]);
  const [selectedCards, setSelectedCards] = useState<Set<string>>(new Set());
  const [selectedDeckId, setSelectedDeckId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // テキストモード state
  const [inputText, setInputText] = useState('');

  // URLモード state
  const [inputUrl, setInputUrl] = useState('');
  const [urlProgressStage, setUrlProgressStage] = useState<UrlProgressStage>('fetching');
  const [pageInfo, setPageInfo] = useState<PageInfo | null>(null);
  const progressTimerRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  // M-30 / L-28: 生成中の AbortController とタイムアウトタイマーを ref で保持し、
  //   アンマウント時の cleanup で確実にキャンセルする。これにより
  //   アンマウント後の setState（警告・メモリリーク）とタイマーリークを防ぐ。
  const controllerRef = useRef<AbortController | null>(null);
  const timeoutTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // M-30: アンマウント後の setState を抑止するマウントフラグ
  const isMountedRef = useRef(true);

  // 生成オプション state
  const [cardType, setCardType] = useState<CardType>('qa');
  const [targetCount, setTargetCount] = useState(10);
  const [difficulty, setDifficulty] = useState<'easy' | 'medium' | 'hard'>('medium');
  // NOTE: 認証ページ取得（AgentCore Browser）無効化中は profile 選択 UI を閉じているため、
  //       selectedProfileId は常に null。再有効化時は BrowserProfileSettings から設定する。
  const selectedProfileId: string | null = null;

  useEffect(() => {
    fetchDecks();
  }, [fetchDecks]);

  // テキストモード計算
  const charCount = inputText.length;
  const isUnderLimit = inputText.trim().length > 0 && inputText.trim().length < MIN_CHARS;
  const isOverLimit = charCount > MAX_CHARS;
  const canGenerateText = inputText.trim().length >= MIN_CHARS && !isOverLimit && !isGenerating;
  const canGenerateUrl = inputUrl.trim().length > 0 && !isGenerating;

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    setError(null);
  };

  const handleTabSwitch = (mode: InputMode) => {
    if (isGenerating) return;
    setInputMode(mode);
    setError(null);
    setGeneratedCards([]);
    setSelectedCards(new Set());
    setPageInfo(null);
  };

  // テキストからカード生成
  const handleGenerateFromText = useCallback(async () => {
    if (!canGenerateText) return;

    setIsGenerating(true);
    setError(null);
    setGeneratedCards([]);
    setSelectedCards(new Set());

    // M-30 / L-28: controller / timeout を ref に保持し cleanup で abort/clear できるようにする
    const controller = new AbortController();
    controllerRef.current = controller;
    const timeoutId = setTimeout(() => controller.abort(), MAX_GENERATION_TIME);
    timeoutTimerRef.current = timeoutId;

    try {
      const request: GenerateCardsRequest = {
        input_text: inputText,
        language: 'ja',
      };
      const response = await cardsApi.generateCards(request, { signal: controller.signal });
      clearTimeout(timeoutId);
      // M-30: アンマウント済みなら state 更新を行わない
      if (!isMountedRef.current) return;
      if (!hasGeneratedCardsPayload(response)) {
        throw new Error('Invalid card generation response');
      }

      setGeneratedCards(addTemporaryIds(response.generated_cards));
      setSelectedCards(new Set());
    } catch (err) {
      clearTimeout(timeoutId);
      // M-30: アンマウント済み（cleanup の abort 含む）なら state 更新を行わない
      if (!isMountedRef.current) return;
      if (isAbortLikeError(err)) {
        setError('生成がタイムアウトしました。もう一度お試しください。');
      } else {
        setError('カードの生成に失敗しました。もう一度お試しください。');
      }
    } finally {
      controllerRef.current = null;
      timeoutTimerRef.current = null;
      if (isMountedRef.current) {
        setIsGenerating(false);
      }
    }
  }, [canGenerateText, inputText]);

  // URLからカード生成
  const handleGenerateFromUrl = useCallback(async () => {
    if (!canGenerateUrl) return;

    setIsGenerating(true);
    setError(null);
    setGeneratedCards([]);
    setSelectedCards(new Set());
    setPageInfo(null);
    setUrlProgressStage('fetching');

    // プログレスステージのシミュレーション
    const timer1 = setTimeout(() => setUrlProgressStage('analyzing'), 3000);
    const timer2 = setTimeout(() => setUrlProgressStage('generating'), 8000);
    progressTimerRef.current = [timer1, timer2];

    // M-30 / L-28: controller / timeout を ref に保持し cleanup で abort/clear できるようにする
    const controller = new AbortController();
    controllerRef.current = controller;
    const timeoutId = setTimeout(() => controller.abort(), MAX_URL_GENERATION_TIME);
    timeoutTimerRef.current = timeoutId;

    try {
      const request: GenerateFromUrlRequest = {
        url: inputUrl,
        card_type: cardType,
        target_count: targetCount,
        difficulty: difficulty,
        language: 'ja',
        ...(selectedProfileId ? { profile_id: selectedProfileId } : {}),
      };
      const response = await cardsApi.generateFromUrl(request, { signal: controller.signal });
      clearTimeout(timeoutId);
      clearTimeout(timer1);
      clearTimeout(timer2);
      // M-30: アンマウント済みなら state 更新を行わない
      if (!isMountedRef.current) return;
      if (!hasUrlGeneratedCardsPayload(response)) {
        throw new Error('Invalid URL card generation response');
      }

      setPageInfo({
        url: response.page_info.url,
        title: response.page_info.title,
        fetched_at: response.page_info.fetched_at ?? '',
      });

      setGeneratedCards(addTemporaryIds(response.generated_cards));
      setSelectedCards(new Set());
    } catch (err) {
      clearTimeout(timeoutId);
      clearTimeout(timer1);
      clearTimeout(timer2);
      // M-30: アンマウント済み（cleanup の abort 含む）なら state 更新を行わない
      if (!isMountedRef.current) return;
      if (isAbortLikeError(err)) {
        setError('生成がタイムアウトしました。URLが正しいか確認してください。');
      } else {
        // E-1: 業務エラー(4xx)はメッセージを表示、想定外(5xx/ネットワーク)は固定文言
        setError(getUserFacingMessage(err, 'URLからのカード生成に失敗しました。'));
      }
    } finally {
      controllerRef.current = null;
      timeoutTimerRef.current = null;
      progressTimerRef.current = [];
      if (isMountedRef.current) {
        setIsGenerating(false);
      }
    }
  }, [canGenerateUrl, inputUrl, cardType, targetCount, difficulty, selectedProfileId]);

  // M-30 / L-28: アンマウント時に進行中のリクエストとタイマーを確実にキャンセルする。
  //   AbortController.abort() で API リクエスト自体を中断し、タイムアウト/プログレス
  //   タイマーを clear し、isMountedRef を false にして以降の setState を抑止する。
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      controllerRef.current?.abort();
      if (timeoutTimerRef.current !== null) {
        clearTimeout(timeoutTimerRef.current);
      }
      progressTimerRef.current.forEach(clearTimeout);
    };
  }, []);

  const handleToggleCard = (tempId: string) => {
    setSelectedCards(prev => {
      const next = new Set(prev);
      if (next.has(tempId)) {
        next.delete(tempId);
      } else {
        next.add(tempId);
      }
      return next;
    });
  };

  const handleEditCard = (tempId: string, front: string, back: string) => {
    setGeneratedCards(prev =>
      prev.map(card =>
        card.tempId === tempId ? { ...card, front, back } : card
      )
    );
  };

  const handleSave = useCallback(async () => {
    const cardsToSave = generatedCards.filter(c => selectedCards.has(c.tempId));
    if (cardsToSave.length === 0) return;

    const totalCount = cardsToSave.length;
    setIsSaving(true);
    setError(null);

    // F-4: 途中失敗時の部分保存・再試行による二重登録を防ぐため、
    //      保存成功した tempId を逐次 selectedCards/generatedCards から除去する
    let savedCount = 0;
    try {
      for (const card of cardsToSave) {
        const request: CreateCardRequest = {
          front: card.front,
          back: card.back,
          tags: card.suggested_tags,
          ...(selectedDeckId ? { deck_id: selectedDeckId } : {}),
          ...(inputMode === 'url' && pageInfo
            ? { references: [{ type: 'url' as const, value: pageInfo.url }] }
            : {}),
        };
        await cardsApi.createCard(request);
        savedCount += 1;
        // 【保存済みカードの除去】: 成功したカードは選択集合・一覧から取り除く
        // → 再試行時は未保存分のみが送信される
        setSelectedCards(prev => {
          const next = new Set(prev);
          next.delete(card.tempId);
          return next;
        });
        setGeneratedCards(prev => prev.filter(c => c.tempId !== card.tempId));
      }
      navigate('/cards', { state: { message: `${totalCount}枚のカードを保存しました` } });
    } catch {
      // F-4: 部分保存の状況を提示。残りは未保存のまま選択集合に残るため再試行で重複しない
      if (savedCount > 0) {
        setError(
          `${totalCount}枚中${savedCount}枚保存しました。残りを再試行してください。`,
        );
      } else {
        setError('カードの保存に失敗しました。もう一度お試しください。');
      }
    } finally {
      setIsSaving(false);
    }
  }, [generatedCards, selectedCards, selectedDeckId, inputMode, pageInfo, navigate]);

  const selectedCount = selectedCards.size;

  return {
    // state
    inputMode,
    inputText,
    inputUrl,
    generatedCards,
    selectedCards,
    selectedDeckId,
    isGenerating,
    isSaving,
    error,
    urlProgressStage,
    pageInfo,
    cardType,
    targetCount,
    difficulty,
    // derived
    charCount,
    isUnderLimit,
    isOverLimit,
    canGenerateText,
    canGenerateUrl,
    selectedCount,
    // setters used by presentational sub-components
    setInputUrl,
    setSelectedDeckId,
    setCardType,
    setTargetCount,
    setDifficulty,
    // handlers
    handleInputChange,
    handleTabSwitch,
    handleGenerateFromText,
    handleGenerateFromUrl,
    handleToggleCard,
    handleEditCard,
    handleSave,
  };
};
