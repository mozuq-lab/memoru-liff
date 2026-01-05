/**
 * 【機能概要】: AIカード生成画面
 * 【実装方針】: テキスト入力→AI生成→カード選択・編集→保存のフロー
 * 【テスト対応】: TASK-0015 テストケース1〜9
 * 🔵 青信号: user-stories.md 2.1より
 */
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { CardPreview } from '@/components/CardPreview';
import { Navigation } from '@/components/Navigation';
import { Loading } from '@/components/common/Loading';
import { Error } from '@/components/common/Error';
import { cardsApi } from '@/services/api';
import type { GeneratedCardWithId, GenerateCardsRequest, CreateCardRequest } from '@/types';

const MAX_CHARS = 2000;
const MAX_GENERATION_TIME = 30000; // 30秒

/**
 * 【機能概要】: AIカード生成ページコンポーネント
 */
export const GeneratePage = () => {
  const navigate = useNavigate();
  const [inputText, setInputText] = useState('');
  const [generatedCards, setGeneratedCards] = useState<GeneratedCardWithId[]>([]);
  const [selectedCards, setSelectedCards] = useState<Set<string>>(new Set());
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const charCount = inputText.length;
  const isOverLimit = charCount > MAX_CHARS;
  const canGenerate = inputText.trim().length > 0 && !isOverLimit && !isGenerating;

  // 【テキスト入力ハンドラ】
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    setError(null);
  };

  // 【AI生成実行】
  const handleGenerate = useCallback(async () => {
    if (!canGenerate) return;

    setIsGenerating(true);
    setError(null);
    setGeneratedCards([]);
    setSelectedCards(new Set());

    // タイムアウト設定
    const timeoutId = setTimeout(() => {
      setIsGenerating(false);
      setError('生成がタイムアウトしました。もう一度お試しください。');
    }, MAX_GENERATION_TIME);

    try {
      const request: GenerateCardsRequest = {
        input_text: inputText,
        language: 'ja',
      };
      const response = await cardsApi.generateCards(request);
      clearTimeout(timeoutId);

      // tempIdを付与
      const cardsWithId: GeneratedCardWithId[] = response.generated_cards.map((card, index) => ({
        ...card,
        tempId: `temp-${Date.now()}-${index}`,
      }));

      setGeneratedCards(cardsWithId);
      // デフォルトで全てのカードを選択
      setSelectedCards(new Set(cardsWithId.map(c => c.tempId)));
    } catch (err) {
      clearTimeout(timeoutId);
      setError('カードの生成に失敗しました。もう一度お試しください。');
    } finally {
      setIsGenerating(false);
    }
  }, [canGenerate, inputText]);

  // 【カード選択切り替え】
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

  // 【カード編集】
  const handleEditCard = (tempId: string, front: string, back: string) => {
    setGeneratedCards(prev =>
      prev.map(card =>
        card.tempId === tempId ? { ...card, front, back } : card
      )
    );
  };

  // 【カード保存】
  const handleSave = useCallback(async () => {
    const cardsToSave = generatedCards.filter(c => selectedCards.has(c.tempId));
    if (cardsToSave.length === 0) return;

    setIsSaving(true);
    setError(null);

    try {
      // 各カードを個別に保存
      for (const card of cardsToSave) {
        const request: CreateCardRequest = {
          front: card.front,
          back: card.back,
          tags: card.suggested_tags,
        };
        await cardsApi.createCard(request);
      }
      navigate('/cards', { state: { message: `${cardsToSave.length}枚のカードを保存しました` } });
    } catch (err) {
      setError('カードの保存に失敗しました。もう一度お試しください。');
    } finally {
      setIsSaving(false);
    }
  }, [generatedCards, selectedCards, navigate]);

  const selectedCount = selectedCards.size;

  return (
    <div className="flex flex-col min-h-screen pb-20">
      <header className="bg-white shadow-sm p-4 mb-4">
        <h1 className="text-xl font-bold text-gray-800">AIカード生成</h1>
      </header>

      <main className="flex-1 px-4">
        {/* テキスト入力エリア */}
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
            {isOverLimit && (
              <span className="text-sm text-red-500" data-testid="over-limit-error">
                文字数制限を超えています
              </span>
            )}
          </div>
        </section>

        {/* 生成ボタン */}
        <button
          onClick={handleGenerate}
          disabled={!canGenerate}
          className={`w-full py-3 rounded-lg font-medium min-h-[44px] transition-colors ${
            canGenerate
              ? 'bg-green-600 text-white hover:bg-green-700 active:bg-green-800'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
          data-testid="generate-button"
        >
          {isGenerating ? '生成中...' : 'AIでカードを生成'}
        </button>

        {/* ローディング状態 */}
        {isGenerating && (
          <div className="mt-6" data-testid="loading">
            <Loading message="カードを生成中...（最大30秒）" />
          </div>
        )}

        {/* エラー表示 */}
        {error && (
          <div className="mt-6" data-testid="error">
            <Error message={error} onRetry={handleGenerate} />
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
