/**
 * AIカード生成画面 - テキスト入力 / URL入力の2モード対応
 */
import { CardPreview } from '@/components/CardPreview';
import { DeckSelector } from '@/components/DeckSelector';
import { Navigation } from '@/components/Navigation';
import { Loading } from '@/components/common/Loading';
import { Error as ErrorMessage } from '@/components/common/Error';
import { UrlInput } from '@/components/UrlInput';
import { GenerateProgress } from '@/components/GenerateProgress';
import { GenerateOptions } from '@/components/GenerateOptions';
// NOTE: BrowserProfileSettings は AgentCore Browser 連携の再有効化時に復活させる。
//       現状バックエンドが profile_id 付きリクエストに 501 を返すため import を一時停止。
// import { BrowserProfileSettings } from '@/components/BrowserProfileSettings';
import { useCardGeneration, MIN_CHARS, MAX_CHARS } from '@/hooks/useCardGeneration';

export const GeneratePage = () => {
  const {
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
    charCount,
    isUnderLimit,
    isOverLimit,
    canGenerateText,
    canGenerateUrl,
    selectedCount,
    setInputUrl,
    setSelectedDeckId,
    setCardType,
    setTargetCount,
    setDifficulty,
    handleInputChange,
    handleTabSwitch,
    handleGenerateFromText,
    handleGenerateFromUrl,
    handleToggleCard,
    handleEditCard,
    handleSave,
  } = useCardGeneration();

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

            {/*
              【認証プロファイル UI 一時無効化】:
              AgentCore Browser 連携（認証付きページ取得 / SPA フォールバック）は
              バックエンドで意図的に無効化済み（profile_id 付きリクエストは 501 を返す）。
              そのため BrowserProfileSettings の描画を「準備中」お知らせに置き換えている。
              バックエンド再有効化時は、以下のお知らせを削除し、下記の元コードに戻すこと:

                <section className="mb-6" aria-label="認証プロファイル">
                  <BrowserProfileSettings
                    selectedProfileId={selectedProfileId}
                    onProfileSelect={setSelectedProfileId}
                    disabled={isGenerating}
                  />
                </section>

              （BrowserProfileSettings コンポーネントと API クライアントは温存している）
            */}
            <section className="mb-6" aria-label="認証プロファイル">
              <div
                className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-600"
                data-testid="browser-profile-coming-soon"
              >
                🔒 ログインが必要なページの取得は準備中です
              </div>
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
            <ErrorMessage
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
