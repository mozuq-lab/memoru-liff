import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { cardsApi, getUserFacingMessage } from '@/services/api';
import { useDecksContext } from '@/contexts/DecksContext';
import type {
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

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), MAX_GENERATION_TIME);

    try {
      const request: GenerateCardsRequest = {
        input_text: inputText,
        language: 'ja',
      };
      const response = await cardsApi.generateCards(request, { signal: controller.signal });
      clearTimeout(timeoutId);

      const cardsWithId: GeneratedCardWithId[] = response.generated_cards.map((card, index) => ({
        ...card,
        tempId: `temp-${Date.now()}-${index}`,
      }));

      setGeneratedCards(cardsWithId);
      setSelectedCards(new Set());
    } catch (err) {
      clearTimeout(timeoutId);
      if (err instanceof DOMException && err.name === 'AbortError') {
        setError('生成がタイムアウトしました。もう一度お試しください。');
      } else {
        setError('カードの生成に失敗しました。もう一度お試しください。');
      }
    } finally {
      setIsGenerating(false);
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

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), MAX_URL_GENERATION_TIME);

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

      setPageInfo(response.page_info);

      const cardsWithId: GeneratedCardWithId[] = response.generated_cards.map((card, index) => ({
        ...card,
        tempId: `temp-${Date.now()}-${index}`,
      }));

      setGeneratedCards(cardsWithId);
      setSelectedCards(new Set());
    } catch (err) {
      clearTimeout(timeoutId);
      clearTimeout(timer1);
      clearTimeout(timer2);
      if (err instanceof DOMException && err.name === 'AbortError') {
        setError('生成がタイムアウトしました。URLが正しいか確認してください。');
      } else {
        // E-1: 業務エラー(4xx)はメッセージを表示、想定外(5xx/ネットワーク)は固定文言
        setError(getUserFacingMessage(err, 'URLからのカード生成に失敗しました。'));
      }
    } finally {
      setIsGenerating(false);
      progressTimerRef.current = [];
    }
  }, [canGenerateUrl, inputUrl, cardType, targetCount, difficulty, selectedProfileId]);

  useEffect(() => {
    return () => {
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
