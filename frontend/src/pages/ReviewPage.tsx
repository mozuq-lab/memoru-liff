import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { FlipCard } from '@/components/FlipCard';
import { GradeButtons } from '@/components/GradeButtons';
import { ReviewProgress } from '@/components/ReviewProgress';
import { ReviewComplete } from '@/components/ReviewComplete';
import { Loading } from '@/components/common/Loading';
import { Error } from '@/components/common/Error';
import { cardsApi, reviewsApi } from '@/services/api';
import type { DueCard, SessionCardResult } from '@/types';

export const ReviewPage = () => {
  const navigate = useNavigate();

  const [cards, setCards] = useState<DueCard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [reviewedCount, setReviewedCount] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  const [reviewResults, setReviewResults] = useState<SessionCardResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCards = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await cardsApi.getDueCards();
      setCards(response.due_cards);
    } catch {
      setError('復習カードの取得に失敗しました');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCards();
  }, [fetchCards]);

  const moveToNext = useCallback(() => {
    setIsFlipped(false);
    if (currentIndex >= cards.length - 1) {
      setIsComplete(true);
    } else {
      setCurrentIndex((prev) => prev + 1);
    }
  }, [currentIndex, cards.length]);

  const handleGrade = useCallback(async (grade: number) => {
    const currentCard = cards[currentIndex];
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await reviewsApi.submitReview(currentCard.card_id, grade);
      setReviewResults((prev) => [
        ...prev,
        {
          cardId: currentCard.card_id,
          front: currentCard.front,
          grade,
          nextReviewDate: response.updated.due_date,
          type: 'graded' as const,
        },
      ]);
      setReviewedCount((prev) => prev + 1);
      moveToNext();
    } catch {
      setError('採点の送信に失敗しました');
    } finally {
      setIsSubmitting(false);
    }
  }, [cards, currentIndex, moveToNext]);

  const handleSkip = useCallback(() => {
    const currentCard = cards[currentIndex];
    setReviewResults((prev) => [
      ...prev,
      {
        cardId: currentCard.card_id,
        front: currentCard.front,
        type: 'skipped' as const,
      },
    ]);
    moveToNext();
  }, [cards, currentIndex, moveToNext]);

  const handleFlip = useCallback(() => {
    setIsFlipped((prev) => !prev);
  }, []);

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
          <button
            type="button"
            onClick={handleBack}
            className="text-gray-600 min-h-[44px] min-w-[44px] flex items-center"
            aria-label="戻る"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
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
          <button
            type="button"
            onClick={handleBack}
            className="text-gray-600 min-h-[44px] min-w-[44px] flex items-center"
            aria-label="戻る"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        </header>
        <div className="flex-1 flex items-center justify-center px-6 text-center">
          <div>
            <p className="text-lg text-gray-600 mb-4">復習対象のカードはありません</p>
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
        <ReviewComplete reviewedCount={reviewedCount} results={reviewResults} />
      </div>
    );
  }

  const currentCard = cards[currentIndex];

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      <header className="p-4 flex items-center justify-between">
        <button
          type="button"
          onClick={handleBack}
          className="text-gray-600 min-h-[44px] min-w-[44px] flex items-center"
          aria-label="戻る"
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
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
            />
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
