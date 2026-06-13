import { useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { FlipCard } from "@/components/FlipCard";
import { ReferenceDisplay } from "@/components/ReferenceDisplay";
import { GradeButtons } from "@/components/GradeButtons";
import { ReviewProgress } from "@/components/ReviewProgress";
import { ReviewComplete } from "@/components/ReviewComplete";
import { Loading } from "@/components/common/Loading";
import { Error } from "@/components/common/Error";
import { BackButton } from "@/components/common/BackButton";
import { useSpeech } from "@/hooks/useSpeech";
import { useSpeechSettings } from "@/hooks/useSpeechSettings";
import { useReviewSession } from "@/hooks/useReviewSession";
import { useAuthContext } from "@/contexts/AuthContext";

export const ReviewPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const deckId = searchParams.get("deck_id") || undefined;

  // 読み上げ機能 (US1: 手動読み上げ、US2: 自動読み上げ、US3: 速度設定)
  const { user: authUser } = useAuthContext();
  const userId = authUser?.profile?.sub;
  const { settings } = useSpeechSettings(userId);
  const { isSpeaking, isSupported, speak, cancel } = useSpeech({
    rate: settings.rate,
  });

  // 復習セッションの状態機械はフックへ集約。読み上げの cancel のみ橋渡しする。
  const {
    cards,
    currentIndex,
    isFlipped,
    isSubmitting,
    reviewedCount,
    isComplete,
    reviewResults,
    isLoading,
    error,
    regradeCardIndex,
    isUndoing,
    undoingIndex,
    reconfirmQueue,
    isReconfirmMode,
    currentCardFront,
    fetchCards,
    handleGrade,
    handleSkip,
    handleReconfirmRemembered,
    handleReconfirmForgotten,
    handleUndo,
    handleFlip,
  } = useReviewSession(deckId, cancel);

  // 【自動読み上げ (US2)】: カードが切り替わった際に autoPlay が有効なら表面テキストを自動再生
  // 現在表示中カードの表面テキストをモードに応じて導出し、変化したときのみ speak を呼ぶ。
  // regradeCardIndex は Undo 後の手動再採点フローのため autoPlay をスキップする。
  useEffect(() => {
    if (
      !settings.autoPlay ||
      isLoading ||
      isComplete ||
      regradeCardIndex !== null
    )
      return;
    if (currentCardFront) {
      speak(currentCardFront);
    }
  }, [
    settings.autoPlay,
    currentCardFront,
    isComplete,
    isLoading,
    regradeCardIndex,
    speak,
  ]);

  const handleBack = useCallback(() => {
    navigate(-1);
  }, [navigate]);

  if (isLoading) {
    return (
      <div className="flex flex-col min-h-screen bg-gray-50">
        <div className="flex-1 flex items-center justify-center">
          <Loading message="復習カードを読み込み中..." />
        </div>
      </div>
    );
  }

  if (error && cards.length === 0) {
    return (
      <div className="flex flex-col min-h-screen bg-gray-50">
        <header className="p-4">
          <BackButton onClick={handleBack} />
        </header>
        <div className="flex-1 flex items-center justify-center p-4">
          <Error message={error} onRetry={fetchCards} />
        </div>
      </div>
    );
  }

  if (cards.length === 0) {
    return (
      <div className="flex flex-col min-h-screen bg-gray-50">
        <header className="p-4">
          <BackButton onClick={handleBack} />
        </header>
        <div className="flex-1 flex items-center justify-center px-6 text-center">
          <div>
            <p className="text-lg text-gray-600 mb-4">
              {deckId
                ? "このデッキに復習対象のカードはありません"
                : "復習対象のカードはありません"}
            </p>
            <button
              type="button"
              onClick={handleBack}
              className="py-3 px-8 bg-blue-600 text-white rounded-lg font-medium min-h-[44px] hover:bg-blue-700 active:bg-blue-800 transition-colors"
            >
              戻る
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (isComplete) {
    return (
      <div className="flex flex-col min-h-screen bg-gray-50">
        {error && (
          <p
            className="text-red-500 text-sm text-center mt-4 px-4"
            role="alert"
          >
            {error}
          </p>
        )}
        <ReviewComplete
          reviewedCount={reviewedCount}
          results={reviewResults}
          onUndo={handleUndo}
          isUndoing={isUndoing}
          undoingIndex={undoingIndex}
        />
      </div>
    );
  }

  // 【再採点モード】: Undo されたカードを再採点UI で表示する（再確認モードより優先）
  if (regradeCardIndex !== null) {
    const regradeResult = reviewResults[regradeCardIndex];
    const regradeCard = cards.find((c) => c.card_id === regradeResult.cardId);
    if (!regradeCard) {
      // useEffect で状態更新を行うため、ここでは null を返すのみ
      return null;
    }
    return (
      <div className="flex flex-col min-h-screen bg-gray-50">
        <header className="p-4 flex items-center">
          <p className="text-sm text-gray-600">再採点</p>
        </header>

        <main className="flex-1 flex flex-col px-4">
          <div className="flex-1 flex items-center justify-center">
            <div className="w-full max-w-md">
              <FlipCard
                front={regradeCard.front}
                back={regradeCard.back}
                isFlipped={isFlipped}
                onFlip={handleFlip}
                speechProps={{
                  speechState: { isSpeaking, isSupported },
                  onSpeakFront: () => (isSpeaking ? cancel() : speak(regradeCard.front)),
                  onSpeakBack: () => (isSpeaking ? cancel() : speak(regradeCard.back)),
                }}
              />
              {isFlipped && (
                <ReferenceDisplay references={regradeCard.references ?? []} />
              )}
            </div>
          </div>

          {error && (
            <p className="text-red-500 text-sm text-center mb-2" role="alert">
              {error}
            </p>
          )}

          <div className="pb-6 min-h-[200px]">
            {isFlipped && (
              <GradeButtons onGrade={handleGrade} disabled={isSubmitting} />
            )}
          </div>
        </main>
      </div>
    );
  }

  // 【再確認モード】: reconfirmQueue の先頭カードを再確認UI で表示する
  if (isReconfirmMode && reconfirmQueue.length > 0) {
    const reconfirmCard = reconfirmQueue[0];
    return (
      <div className="flex flex-col min-h-screen bg-gray-50">
        <header className="p-4 flex items-center gap-3">
          <BackButton onClick={handleBack} />
          <span className="inline-flex items-center bg-amber-100 text-amber-700 rounded-full px-2 py-0.5 text-xs font-medium">
            再確認
          </span>
          <span className="text-xs text-gray-500">
            残り {reconfirmQueue.length} 枚
          </span>
        </header>
        <main className="flex-1 flex flex-col px-4">
          <div className="flex-1 flex items-center justify-center">
            <div className="w-full max-w-md">
              <FlipCard
                front={reconfirmCard.front}
                back={reconfirmCard.back}
                isFlipped={isFlipped}
                onFlip={handleFlip}
                speechProps={{
                  speechState: { isSpeaking, isSupported },
                  onSpeakFront: () => (isSpeaking ? cancel() : speak(reconfirmCard.front)),
                  onSpeakBack: () => (isSpeaking ? cancel() : speak(reconfirmCard.back)),
                }}
              />
              {isFlipped && (
                <ReferenceDisplay references={cards.find((c) => c.card_id === reconfirmCard.cardId)?.references ?? []} />
              )}
            </div>
          </div>

          <div className="pb-6 min-h-[200px]">
            <GradeButtons
              onGrade={handleGrade}
              disabled={isSubmitting}
              isReconfirmMode={true}
              onReconfirmRemembered={handleReconfirmRemembered}
              onReconfirmForgotten={handleReconfirmForgotten}
            />
          </div>
        </main>
      </div>
    );
  }

  const currentCard = cards[currentIndex];

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      <header className="p-4 flex items-center justify-between">
        <BackButton onClick={handleBack} />
        <div className="flex-1 mx-4">
          <ReviewProgress current={currentIndex + 1} total={cards.length} />
        </div>
      </header>

      <main className="flex-1 flex flex-col px-4">
        <div className="flex-1 flex items-center justify-center">
          <div className="w-full max-w-md">
            <FlipCard
              front={currentCard.front}
              back={currentCard.back}
              isFlipped={isFlipped}
              onFlip={handleFlip}
              speechProps={{
                speechState: { isSpeaking, isSupported },
                onSpeakFront: () => (isSpeaking ? cancel() : speak(currentCard.front)),
                onSpeakBack: () => (isSpeaking ? cancel() : speak(currentCard.back)),
              }}
            />
            {isFlipped && (
              <ReferenceDisplay references={currentCard.references ?? []} />
            )}
          </div>
        </div>

        {error && (
          <p className="text-red-500 text-sm text-center mb-2" role="alert">
            {error}
          </p>
        )}

        <div className="pb-6 min-h-[200px]">
          {isFlipped && (
            <GradeButtons
              onGrade={handleGrade}
              onSkip={handleSkip}
              disabled={isSubmitting}
            />
          )}
        </div>
      </main>
    </div>
  );
};
