/**
 * 【機能概要】: 日付関連のユーティリティ関数
 * 【実装方針】: date-fnsを使用して日付フォーマットとステータス判定
 * 【テスト対応】: TASK-0016 テストケース2〜4
 * 🔵 青信号: architecture.mdより
 */
import { format, isToday, isBefore, addDays, parseISO } from 'date-fns';
import { ja } from 'date-fns/locale';

/**
 * 【機能概要】: 日付文字列を M/DD 形式にフォーマット（予測バー用）
 * @param dateStr - ISO 8601形式の日付文字列
 * @returns M/DD 形式の文字列（例: 1/05）
 */
export const formatShortDate = (dateStr: string): string => {
  const date = parseISO(dateStr);
  return format(date, 'M/dd');
};

/**
 * 【機能概要】: 日付文字列を日時表示にフォーマット（セッション履歴用）
 * @param dateStr - ISO 8601形式の日付文字列
 * @returns 日本語ロケールの短い月日+時分（例: 1月5日 14:30）
 */
export const formatDateTime = (dateStr: string): string => {
  const date = parseISO(dateStr);
  return format(date, 'M月d日 HH:mm', { locale: ja });
};

/**
 * 【型定義】: 復習日ステータス
 */
export interface DueStatus {
  status: 'overdue' | 'today' | 'upcoming' | 'future';
  label: string;
}

/**
 * 【機能概要】: 復習日を日本語フォーマットで表示
 * 【実装方針】: date-fnsのformat関数を使用
 * @param due - ISO 8601形式の日付文字列
 * @returns フォーマットされた日付文字列（例: 1月5日(日)）
 */
export const formatDueDate = (due: string): string => {
  const date = parseISO(due);
  return format(date, 'M月d日(E)', { locale: ja });
};

/**
 * 【機能概要】: 復習日のステータスを判定
 * 【実装方針】: 今日からの日数差に基づいてステータスを返す
 * @param due - ISO 8601形式の日付文字列
 * @returns ステータスオブジェクト
 */
export const getDueStatus = (due: string): DueStatus => {
  const dueDate = parseISO(due);
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // 期限切れ（今日より前）
  if (isBefore(dueDate, today)) {
    return { status: 'overdue', label: '期限切れ' };
  }

  // 今日
  if (isToday(dueDate)) {
    return { status: 'today', label: '今日' };
  }

  // もうすぐ（3日以内）
  const threeDaysLater = addDays(today, 3);
  if (isBefore(dueDate, threeDaysLater)) {
    return { status: 'upcoming', label: 'もうすぐ' };
  }

  // それ以降
  return { status: 'future', label: formatDueDate(due) };
};
