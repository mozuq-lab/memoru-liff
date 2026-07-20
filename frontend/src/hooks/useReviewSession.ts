import { useState, useEffect, useCallback, useRef } from "react";
import { cardsApi, reviewsApi } from "@/services/api";
import type { DueCard, SessionCardResult, ReconfirmCard } from "@/types";

/**
 * 【再確認キュー追加しきい値】: quality 評価がこの値未満（0-2）の場合に
 * 再確認キューへ追加する（SM-2 で最も記憶定着が低い評価帯）。
 */
const RECONFIRM_THRESHOLD = 3;

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

/**
 * 【フック概要】: 復習セッションの状態機械（取得・採点・スキップ・再確認キュー・Undo・再採点）を
 * ReviewPage の描画から分離して集約する。ページ側は本フックが返す状態とハンドラを使って描画する。
 * 【設計方針】: 読み上げ（useSpeech）は描画と密結合のためページ側に残し、カード切替時の
 * `cancel()` のみ引数で受け取る。これによりセッションロジックは読み上げ実装に依存しない。
 *
 * @param deckId - 復習対象デッキ ID（未指定なら全カード）
 * @param cancel - カード切替時に読み上げを停止するためのコールバック（useSpeech の cancel）
 */
export const useReviewSession = (
  deckId: string | undefined,
  cancel: () => void,
) => {
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

  // M-29: アンマウント後の setState を防ぐためのマウントフラグ。
  //   reviewsApi.undoReview / cardsApi.getDueCards などのフライト中リクエストが
  //   アンマウント後に解決した際、連鎖する setState（警告・メモリリーク）を抑止する。
  const isMountedRef = useRef(true);
  // F-3（CardsContext と同パターン）: 最新リクエスト ID を保持し、同一マウント内で
  //   deck_id だけが変わる遷移（/review?deck_id=A → ?deck_id=B）の際に、
  //   古いデッキのレスポンスが後着して cards を上書きするのを防ぐ。
  const fetchRequestIdRef = useRef(0);
  // 前回の取得リクエストを実際に中断するための AbortController
  const fetchAbortRef = useRef<AbortController | null>(null);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      // アンマウント時はフライト中の取得リクエストを中断する
      fetchAbortRef.current?.abort();
    };
  }, []);

  const fetchCards = useCallback(async () => {
    // F-3: このリクエストの ID を採番。完了時に最新でなければ結果を破棄する
    const requestId = ++fetchRequestIdRef.current;
    // 前回リクエストが残っていれば中断してから新しいリクエストを開始する
    fetchAbortRef.current?.abort();
    const controller = new AbortController();
    fetchAbortRef.current = controller;

    setIsLoading(true);
    setError(null);
    try {
      const response = await cardsApi.getDueCards(undefined, deckId, {
        signal: controller.signal,
      });
      // M-29: アンマウント済み / F-3: 後発リクエストありなら state 更新を行わない
      if (!isMountedRef.current || requestId !== fetchRequestIdRef.current)
        return;
      setCards(response.due_cards);
      // deckId 切替（/review?deck_id=A → ?deck_id=B）で cards だけ差し替えると、
      // 前のデッキのセッション進行状態（完了フラグ・採点結果・再確認キュー等）が
      // 残り、完了済み A → B の遷移で isComplete === true のまま復習画面に
      // 戻れなくなる。最新リクエストの成功時にセッション状態を初期化する
      // （fetchCards はマウント時・deckId 変更時・エラーリトライ時のみ呼ばれるため、
      // セッション進行中に走ることはない）。
      setCurrentIndex(0);
      setIsFlipped(false);
      setReviewedCount(0);
      setIsComplete(false);
      setReviewResults([]);
      setRegradeCardIndex(null);
      setReconfirmQueue([]);
      setIsReconfirmMode(false);
    } catch {
      // 中断（アンマウント・デッキ切替）起因のエラーは requestId / mount ガードで除外される
      if (!isMountedRef.current || requestId !== fetchRequestIdRef.current)
        return;
      setError("復習カードの取得に失敗しました");
    } finally {
      // F-3: 最新リクエストのときのみローディング解除
      if (isMountedRef.current && requestId === fetchRequestIdRef.current) {
        setIsLoading(false);
      }
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

  // 【現在表示中カードの表面テキスト】: 自動読み上げ判定にページ側で使用する。
  // regradeCardIndex は Undo 後の手動再採点フローのため autoPlay 対象外（ページ側で制御）。
  const currentCardFront = isReconfirmMode
    ? reconfirmQueue[0]?.front
    : cards[currentIndex]?.front;

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
          // M-29: アンマウント済みなら以降の state 更新を行わない
          if (!isMountedRef.current) return;

          // 【再確認キュー追加判定】: quality 0-2 の場合のみキューに追加
          if (grade < RECONFIRM_THRESHOLD) {
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
          if (grade < RECONFIRM_THRESHOLD) {
            setIsFlipped(false);
            setIsReconfirmMode(true);
          } else {
            setIsComplete(true);
          }
        } catch {
          // M-29: アンマウント済みなら state 更新を行わない
          if (!isMountedRef.current) return;
          setError("再採点の送信に失敗しました");
          setRegradeCardIndex(null);
          setIsComplete(true);
        } finally {
          if (isMountedRef.current) {
            setIsSubmitting(false);
          }
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
        // M-29: アンマウント済みなら以降の state 更新を行わない
        if (!isMountedRef.current) return;

        // 【再確認キュー追加判定】: quality 0-2 の場合のみキューに追加
        // W-17 fix: setReconfirmQueue を updater 関数パターンに統一し、
        // 最新の state を参照する。moveToNext には updater で計算した値と
        // 同一のローカル変数を渡すことで整合性を保つ。
        let newReconfirmQueue = reconfirmQueue;
        if (grade < RECONFIRM_THRESHOLD) {
          const newCard = buildReconfirmCard(
            currentCard.card_id,
            currentCard.front,
            currentCard.back,
            grade,
          );
          newReconfirmQueue = [...reconfirmQueue, newCard];
          setReconfirmQueue((prev) => [...prev, newCard]);
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
        // M-29: アンマウント済みなら state 更新を行わない
        if (!isMountedRef.current) return;
        setError("採点の送信に失敗しました");
      } finally {
        if (isMountedRef.current) {
          setIsSubmitting(false);
        }
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
      // High-4: 再入ガード — Undo 実行中に別行の Undo が発火しても無視する。
      //   ガードなしだと regradeCardIndex / undoingIndex（単一値）が競合し、
      //   片方の再採点機会が失われたり reviewedCount が二重減算されたりする。
      if (isUndoing) return;
      const result = reviewResults[index];
      setIsUndoing(true);
      setUndoingIndex(index);
      setError(null);
      try {
        await reviewsApi.undoReview(result.cardId);
        // M-29: アンマウント済みなら以降の state 更新を行わない
        if (!isMountedRef.current) return;

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
        // M-29: アンマウント済みなら state 更新を行わない
        if (!isMountedRef.current) return;
        setError("取り消しに失敗しました");
      } finally {
        if (isMountedRef.current) {
          setIsUndoing(false);
          setUndoingIndex(null);
        }
      }
    },
    [reviewResults, isUndoing],
  );

  const handleFlip = useCallback(() => {
    setIsFlipped((prev) => !prev);
  }, []);

  return {
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
  };
};
