/**
 * AIカード生成画面 - テキスト入力 / URL入力の2モード対応
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { CardPreview } from '@/components/CardPreview';
import { DeckSelector } from '@/components/DeckSelector';
import { Navigation } from '@/components/Navigation';
import { Loading } from '@/components/common/Loading';
import { Error } from '@/components/common/Error';
import { UrlInput } from '@/components/UrlInput';
import { GenerateProgress } from '@/components/GenerateProgress';
import { GenerateOptions } from '@/components/GenerateOptions';
import { BrowserProfileSettings } from '@/components/BrowserProfileSettings';
import { cardsApi } from '@/services/api';
import { useDecksContext } from '@/contexts/DecksContext';
import type {
  GeneratedCardWithId,
  GenerateCardsRequest,
  GenerateFromUrlRequest,
  CreateCardRequest,
  PageInfo,
  CardType,
} from '@/types';

type InputMode = 'text' | 'url';
type UrlProgressStage = 'fetching' | 'analyzing' | 'generating';

const MIN_CHARS = 5;
const MAX_CHARS = 2000;
const MAX_GENERATION_TIME = 30000; // 30秒
const MAX_URL_GENERATION_TIME = 90000; // 90秒

export const GeneratePage = () => {
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
  const progressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 生成オプション state
  const [cardType, setCardType] = useState<CardType>('qa');
  const [targetCount, setTargetCount] = useState(10);
  const [difficulty, setDifficulty] = useState<'easy' | 'medium' | 'hard'>('medium');
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);

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
    progressTimerRef.current = timer1;

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
      } else if (err instanceof Error) {
        setError(err.message || 'URLからのカード生成に失敗しました。');
      } else {
        setError('URLからのカード生成に失敗しました。');
      }
    } finally {
      setIsGenerating(false);
      progressTimerRef.current = null;
    }
  }, [canGenerateUrl, inputUrl]);

  useEffect(() => {
    return () => {
      if (progressTimerRef.current) {
        clearTimeout(progressTimerRef.current);
      }
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

    setIsSaving(true);
    setError(null);

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
      }
      navigate('/cards', { state: { message: `${cardsToSave.length}枚のカードを保存しました` } });
    } catch {
      setError('カードの保存に失敗しました。もう一度お試しください。');
    } finally {
      setIsSaving(false);
    }
  }, [generatedCards, selectedCards, selectedDeckId, inputMode, pageInfo, navigate]);

  const selectedCount = selectedCards.size;

  return (
    <div className="flex flex-col min-h-screen pb-20">
      <header className="bg-white shadow-sm p-4 mb-4">
        <h1 className="text-xl font-bold text-gray-800">AIカード生成</h1>
      </header>

      <main className="flex-1 px-4">
        {/* タブ切り替え */}
        <div className="flex mb-4 border-b border-gray-200">
          <button
            onClick={() => handleTabSwitch('text')}
            className={`flex-1 py-2 text-sm font-medium border-b-2 transition-colors ${
              inputMode === 'text'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            data-testid="tab-text"
          >
            テキスト入力
          </button>
          <button
            onClick={() => handleTabSwitch('url')}
            className={`flex-1 py-2 text-sm font-medium border-b-2 transition-colors ${
              inputMode === 'url'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            data-testid="tab-url"
          >
            URLから生成
          </button>
        </div>

        {/* テキスト入力モード */}
        {inputMode === 'text' && (
          <>
            <section className="mb-6" aria-label="テキスト入力">
              <label htmlFor="input-text" className="block text-sm font-medium text-gray-700 mb-2">
                学習したいテキストを入力してください
              </label>
              <textarea
                id="input-text"
                value={inputText}
                onChange={handleInputChange}
                placeholder="テキストを入力..."
                className={`w-full h-40 p-3 border rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                  isOverLimit ? 'border-red-500' : 'border-gray-300'
                }`}
                disabled={isGenerating}
                data-testid="input-text"
              />
              <div className="flex justify-between mt-2">
                <span
                  className={`text-sm ${isOverLimit ? 'text-red-500' : 'text-gray-500'}`}
                  data-testid="char-count"
                >
                  {charCount} / {MAX_CHARS}文字
                </span>
                {isUnderLimit && (
                  <span className="text-sm text-orange-500" data-testid="under-limit-error">
                    {MIN_CHARS}文字以上入力してください
                  </span>
                )}
                {isOverLimit && (
                  <span className="text-sm text-red-500" data-testid="over-limit-error">
                    文字数制限を超えています
                  </span>
                )}
              </div>
            </section>

            <button
              onClick={handleGenerateFromText}
              disabled={!canGenerateText}
              className={`w-full py-3 rounded-lg font-medium min-h-[44px] transition-colors ${
                canGenerateText
                  ? 'bg-green-600 text-white hover:bg-green-700 active:bg-green-800'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
              data-testid="generate-button"
            >
              {isGenerating ? '生成中...' : 'AIでカードを生成'}
            </button>
          </>
        )}

        {/* URL入力モード */}
        {inputMode === 'url' && (
          <>
            <section className="mb-4" aria-label="URL入力">
              <UrlInput
                value={inputUrl}
                onChange={setInputUrl}
                disabled={isGenerating}
              />
            </section>

            <section className="mb-4" aria-label="生成オプション">
              <GenerateOptions
                cardType={cardType}
                targetCount={targetCount}
                difficulty={difficulty}
                onCardTypeChange={setCardType}
                onTargetCountChange={setTargetCount}
                onDifficultyChange={setDifficulty}
                disabled={isGenerating}
              />
            </section>

            <section className="mb-6" aria-label="認証プロファイル">
              <BrowserProfileSettings
                selectedProfileId={selectedProfileId}
                onProfileSelect={setSelectedProfileId}
                disabled={isGenerating}
              />
            </section>

            <button
              onClick={handleGenerateFromUrl}
              disabled={!canGenerateUrl}
              className={`w-full py-3 rounded-lg font-medium min-h-[44px] transition-colors ${
                canGenerateUrl
                  ? 'bg-green-600 text-white hover:bg-green-700 active:bg-green-800'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
              data-testid="generate-from-url-button"
            >
              {isGenerating ? '生成中...' : 'URLからカードを生成'}
            </button>

            {isGenerating && (
              <div className="mt-4">
                <GenerateProgress stage={urlProgressStage} />
              </div>
            )}

            {pageInfo && !isGenerating && (
              <div className="mt-4 p-3 bg-blue-50 rounded-lg text-sm" data-testid="page-info">
                <p className="font-medium text-blue-800">{pageInfo.title}</p>
                <p className="text-blue-600 truncate">{pageInfo.url}</p>
              </div>
            )}
          </>
        )}

        {/* ローディング状態（テキストモード） */}
        {isGenerating && inputMode === 'text' && (
          <div className="mt-6" data-testid="loading">
            <Loading message="カードを生成中...（最大30秒）" />
          </div>
        )}

        {/* エラー表示 */}
        {error && (
          <div className="mt-6" data-testid="error">
            <Error
              message={error}
              onRetry={inputMode === 'text' ? handleGenerateFromText : handleGenerateFromUrl}
            />
          </div>
        )}

        {/* 生成されたカード一覧 */}
        {generatedCards.length > 0 && !isGenerating && (
          <section className="mt-6" aria-label="生成されたカード">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-gray-800">
                生成されたカード ({generatedCards.length}枚)
              </h2>
              <span className="text-sm text-gray-600" data-testid="selected-count">
                {selectedCount}枚選択中
              </span>
            </div>

            <div className="space-y-4">
              {generatedCards.map((card) => (
                <CardPreview
                  key={card.tempId}
                  card={card}
                  isSelected={selectedCards.has(card.tempId)}
                  onToggle={() => handleToggleCard(card.tempId)}
                  onEdit={(front, back) => handleEditCard(card.tempId, front, back)}
                />
              ))}
            </div>

            {/* デッキ選択 */}
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                保存先デッキ
              </label>
              <DeckSelector
                value={selectedDeckId}
                onChange={setSelectedDeckId}
                disabled={isSaving}
              />
            </div>

            {/* 保存ボタン */}
            <button
              onClick={handleSave}
              disabled={selectedCount === 0 || isSaving}
              className={`w-full py-3 mt-6 rounded-lg font-medium min-h-[44px] transition-colors ${
                selectedCount > 0 && !isSaving
                  ? 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
              data-testid="save-button"
            >
              {isSaving ? '保存中...' : `選択したカードを保存 (${selectedCount}枚)`}
            </button>
          </section>
        )}
      </main>

      <Navigation />
    </div>
  );
};
