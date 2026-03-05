import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { FlipCard } from "@/components/FlipCard";
import { GradeButtons } from "@/components/GradeButtons";
import { ReviewProgress } from "@/components/ReviewProgress";
import { ReviewComplete } from "@/components/ReviewComplete";
import { Loading } from "@/components/common/Loading";
import { Error } from "@/components/common/Error";
import { cardsApi, reviewsApi } from "@/services/api";
import { useSpeech } from "@/hooks/useSpeech";
import { useSpeechSettings } from "@/hooks/useSpeechSettings";
import { useAuth } from "@/hooks/useAuth";
import type { DueCard, SessionCardResult, ReconfirmCard } from "@/types";

/**
 * 【ヘルパー関数】: ReconfirmCard オブジェクトを生成する
 * 【再利用性】: handleGrade の通常モードと再採点モードの両方で同一ロジックが必要なため共通化
 * 【単一責任】: カードデータと評価グレードから ReconfirmCard を構築する責任のみを持つ
 * 🔵 信頼性レベル: architecture.md の ReconfirmCard 型定義より
 * @param cardId - カード ID
 * @param front - カード表面テキスト
 * @param back - カード裏面テキスト（見つからない場合は空文字）
 * @param grade - quality 評価値（0, 1, or 2）
 * @returns ReconfirmCard オブジェクト
 */
const buildReconfirmCard = (
  cardId: string,
  front: string,
  back: string,
  grade: number,
): ReconfirmCard => ({
  cardId,
  front,
  back,
  originalGrade: grade,
});

export const ReviewPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const deckId = searchParams.get("deck_id") || undefined;

  const [cards, setCards] = useState<DueCard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [reviewedCount, setReviewedCount] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  const [reviewResults, setReviewResults] = useState<SessionCardResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [regradeCardIndex, setRegradeCardIndex] = useState<number | null>(null);
  const [isUndoing, setIsUndoing] = useState(false);
  const [undoingIndex, setUndoingIndex] = useState<number | null>(null);
  const [reconfirmQueue, setReconfirmQueue] = useState<ReconfirmCard[]>([]);
  const [isReconfirmMode, setIsReconfirmMode] = useState(false);

  // 読み上げ機能 (US1: 手動読み上げ、US2: 自動読み上げ、US3: 速度設定)
  const { user: authUser } = useAuth();
  const userId = authUser?.profile?.sub;
  const { settings } = useSpeechSettings(userId);
  const { isSpeaking, isSupported, speak, cancel } = useSpeech({
    rate: settings.rate,
  });

  const fetchCards = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await cardsApi.getDueCards(undefined, deckId);
      setCards(response.due_cards);
    } catch {
      setError("復習カードの取得に失敗しました");
    } finally {
      setIsLoading(false);
    }
  }, [deckId]);

  useEffect(() => {
    fetchCards();
  }, [fetchCards]);

  // 【再採点モードガード】: regradeCardIndex が指すカードが cards に存在しない場合、
  // 再採点を中止して完了画面に遷移する（render 内の setState を回避）
  useEffect(() => {
    if (regradeCardIndex !== null) {
      const regradeResult = reviewResults[regradeCardIndex];
      const regradeCard = cards.find((c) => c.card_id === regradeResult.cardId);
      if (!regradeCard) {
        setRegradeCardIndex(null);
        setIsComplete(true);
      }
    }
  }, [regradeCardIndex, reviewResults, cards]);

  // 【自動読み上げ (US2)】: カードが切り替わった際に autoPlay が有効なら表面テキストを自動再生
  // 現在表示中カードの表面テキストをモードに応じて導出し、変化したときのみ speak を呼ぶ。
  // regradeCardIndex は Undo 後の手動再採点フローのため autoPlay をスキップする。
  const currentCardFront = isReconfirmMode
    ? reconfirmQueue[0]?.front
    : cards[currentIndex]?.front;
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

  /**
   * 【機能概要】: 採点またはスキップ後に次のカードへ進む、またはセッションを完了する
   * 【設計方針】: 通常カードを優先して消化し、全消化後に再確認キューへ遷移する
   *              引数として最新のキュー状態とインデックスを受け取ることで
   *              setState の非同期性による古い値参照を回避する
   * 【状態遷移】:
   *   通常カードが残る → currentIndex をインクリメント
   *   通常カード全消化 + キュー非空 → isReconfirmMode = true
   *   通常カード全消化 + キュー空  → isComplete = true
   * 🔵 信頼性レベル: 要件定義書 REQ-502・dataflow.md より
   * @param currentReconfirmQueue - 最新の再確認キュー（setState の非同期性回避のため引数で受け取る）
   * @param currentCardIndex - 現在のカードインデックス
   * @param currentCardsLength - 通常カードの総数
   */
  const moveToNext = useCallback(
    (
      currentReconfirmQueue: ReconfirmCard[],
      currentCardIndex: number,
      currentCardsLength: number,
    ) => {
      cancel();
      setIsFlipped(false);
      if (currentCardIndex >= currentCardsLength - 1) {
        // 【通常カード全消化】: 再確認キューの有無でセッション継続か完了かを決定
        if (currentReconfirmQueue.length > 0) {
          setIsReconfirmMode(true);
        } else {
          setIsComplete(true);
        }
      } else {
        // 【次の通常カードへ】: インデックスをインクリメント
        setCurrentIndex((prev) => prev + 1);
      }
    },
    [cancel],
  );

  /**
   * 【機能概要】: カードの採点を送信し、結果に応じて次のカードへ進む
   * 【設計方針】: 再採点モード (regradeCardIndex !== null) と通常モードで処理を分岐
   * 【再確認キュー判定】: quality 0-2 の場合のみ reconfirmQueue にカードを追加する
   *                       (SM-2 アルゴリズムで最も記憶定着が低い評価に対応)
   * 【保守性】: ReconfirmCard 作成ロジックは buildReconfirmCard ヘルパーに集約
   * 🔵 信頼性レベル: 要件定義書 REQ-001, REQ-103・dataflow.md より
   * @param grade - quality 評価値（0-5）
   */
  const handleGrade = useCallback(
    async (grade: number) => {
      // 【再採点モード】: Undo された採点を再送信する
      if (regradeCardIndex !== null) {
        const result = reviewResults[regradeCardIndex];
        setIsSubmitting(true);
        setError(null);
        try {
          const response = await reviewsApi.submitReview(result.cardId, grade);

          // 【再確認キュー追加判定】: quality 0-2 の場合のみキューに追加
          if (grade < 3) {
            const back =
              cards.find((c) => c.card_id === result.cardId)?.back ?? "";
            setReconfirmQueue((prev) => [
              ...prev,
              buildReconfirmCard(result.cardId, result.front, back, grade),
            ]);
          }

          setReviewResults((prev) =>
            prev.map((r, i) =>
              i === regradeCardIndex
                ? {
                    ...r,
                    grade,
                    nextReviewDate: response.updated.due_date,
                    type: "graded" as const,
                  }
                : r,
            ),
          );
          setReviewedCount((prev) => prev + 1);

          // 【再採点後の遷移判定】: grade < 3 → 再確認モードに遷移、grade >= 3 → 完了画面に遷移
          setRegradeCardIndex(null);
          if (grade < 3) {
            setIsFlipped(false);
            setIsReconfirmMode(true);
          } else {
            setIsComplete(true);
          }
        } catch {
          setError("再採点の送信に失敗しました");
          setRegradeCardIndex(null);
          setIsComplete(true);
        } finally {
          setIsSubmitting(false);
        }
        return;
      }

      // 【通常モード】: 現在表示中のカードを採点する
      const currentCard = cards[currentIndex];
      setIsSubmitting(true);
      setError(null);
      try {
        const response = await reviewsApi.submitReview(
          currentCard.card_id,
          grade,
        );

        // 【再確認キュー追加判定】: quality 0-2 の場合のみキューに追加
        let newReconfirmQueue = reconfirmQueue;
        if (grade < 3) {
          const newCard = buildReconfirmCard(
            currentCard.card_id,
            currentCard.front,
            currentCard.back,
            grade,
          );
          newReconfirmQueue = [...reconfirmQueue, newCard];
          setReconfirmQueue(newReconfirmQueue);
        }

        setReviewResults((prev) => [
          ...prev,
          {
            cardId: currentCard.card_id,
            front: currentCard.front,
            grade,
            nextReviewDate: response.updated.due_date,
            type: "graded" as const,
          },
        ]);
        setReviewedCount((prev) => prev + 1);
        moveToNext(newReconfirmQueue, currentIndex, cards.length);
      } catch {
        setError("採点の送信に失敗しました");
      } finally {
        setIsSubmitting(false);
      }
    },
    [
      cards,
      currentIndex,
      moveToNext,
      regradeCardIndex,
      reviewResults,
      reconfirmQueue,
    ],
  );

  /**
   * 【機能概要】: 現在のカードをスキップして次のカードへ進む
   * 【設計方針】: スキップカードは reconfirmQueue に追加しない（SM-2 評価なし）
   *              結果には 'skipped' type で記録する
   * 🔵 信頼性レベル: 既存実装パターンより
   */
  const handleSkip = useCallback(() => {
    const currentCard = cards[currentIndex];
    setReviewResults((prev) => [
      ...prev,
      {
        cardId: currentCard.card_id,
        front: currentCard.front,
        type: "skipped" as const,
      },
    ]);
    moveToNext(reconfirmQueue, currentIndex, cards.length);
  }, [cards, currentIndex, moveToNext, reconfirmQueue]);

  /**
   * 【機能概要】: 再確認モードで「覚えた」を選択したときの処理
   * 【改善内容】: setState updater 関数内でのネストされた setState 呼び出しを分離し、
   *              React の推奨パターンに沿った実装に変更
   * 【設計方針】: currentReconfirmCard を先頭から取り出し、残りキューの状態に応じて
   *              セッション完了 or 次の再確認カードへ遷移
   * 【API呼び出し】: なし（フロントエンド state のみで管理）
   * 🔵 信頼性レベル: 要件定義書 REQ-003・architecture.md より
   */
  const handleReconfirmRemembered = useCallback(() => {
    if (reconfirmQueue.length === 0) return;

    const [current, ...rest] = reconfirmQueue;

    // 【先頭カードをキューから除外】: スライスした残りキューをセット
    setReconfirmQueue(rest);

    // 【結果を「再確認済み＝覚えた」に更新】: API 呼び出しなし
    // 【ガード条件】: type === 'graded' のカードのみ更新対象とし、undone 等の誤更新を防止
    setReviewResults((results) =>
      results.map((r) =>
        r.cardId === current.cardId && r.type === "graded"
          ? {
              ...r,
              type: "reconfirmed" as const,
              reconfirmResult: "remembered" as const,
            }
          : r,
      ),
    );

    // 【セッション進行判定】: 残りキューが空なら完了、まだあれば再確認モード継続
    if (rest.length === 0) {
      setIsReconfirmMode(false);
      setIsComplete(true);
    }

    setIsFlipped(false);
  }, [reconfirmQueue]);

  /**
   * 【機能概要】: 再確認モードで「覚えていない」を選択したときの処理
   * 【設計方針】: 先頭カードをキュー末尾に再追加することで、他のカードを先に表示してから
   *              再度このカードに戻るサイクルを実現する
   * 【API呼び出し】: なし（SM-2 の next_review_at は最初の quality 0-2 評価時に設定済み）
   * 🔵 信頼性レベル: 要件定義書 REQ-004・dataflow.md より
   */
  const handleReconfirmForgotten = useCallback(() => {
    // 【キュー先頭カードを末尾に再追加】: slice(1) で先頭を除いた残りに末尾追加
    setReconfirmQueue((prev) => {
      const [current, ...rest] = prev;
      return [...rest, current];
    });
    setIsFlipped(false);
  }, []);

  /**
   * 【機能概要】: 完了画面から特定カードの採点を取り消す（Undo）
   * 【設計方針】: Undo 後は再採点モードに移行し、評価のやり直しを可能にする
   * 【再確認キュー連携】: Undo 対象カードが reconfirmQueue に存在する場合は除去する
   *                       (quality 3-5 の Undo の場合はキューにないため filter が空振りするが安全)
   * 【isReconfirmMode リセット】: 再採点は通常の6段階評価のため、再確認2択UI にしない
   * 🔵 信頼性レベル: 要件定義書 REQ-404・ヒアリング Q4 回答より
   * @param index - reviewResults 内の対象カードのインデックス
   */
  const handleUndo = useCallback(
    async (index: number) => {
      const result = reviewResults[index];
      setIsUndoing(true);
      setUndoingIndex(index);
      setError(null);
      try {
        await reviewsApi.undoReview(result.cardId);

        // 【再確認キューから除去】: 対象カードが存在しない場合も filter は安全に空振りする
        setReconfirmQueue((prev) =>
          prev.filter((c) => c.cardId !== result.cardId),
        );

        setReviewResults((prev) =>
          prev.map((r, i) =>
            i === index
              ? { ...r, type: "undone" as const, reconfirmResult: undefined }
              : r,
          ),
        );
        setReviewedCount((prev) => Math.max(0, prev - 1));

        // 【再採点モードへ移行】: isReconfirmMode をリセットして通常の採点 UI を表示
        setRegradeCardIndex(index);
        setIsComplete(false);
        setIsReconfirmMode(false);
        setIsFlipped(false);
      } catch {
        setError("取り消しに失敗しました");
      } finally {
        setIsUndoing(false);
        setUndoingIndex(null);
      }
    },
    [reviewResults],
  );

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
            <svg
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
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
            <svg
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>
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
          <button
            type="button"
            onClick={handleBack}
            className="text-gray-600 min-h-[44px] min-w-[44px] flex items-center"
            aria-label="戻る"
          >
            <svg
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>
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
        <button
          type="button"
          onClick={handleBack}
          className="text-gray-600 min-h-[44px] min-w-[44px] flex items-center"
          aria-label="戻る"
        >
          <svg
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
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
              speechProps={{
                speechState: { isSpeaking, isSupported },
                onSpeakFront: () => (isSpeaking ? cancel() : speak(currentCard.front)),
                onSpeakBack: () => (isSpeaking ? cancel() : speak(currentCard.back)),
              }}
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
