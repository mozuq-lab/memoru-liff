/**
 * 【テスト概要】: 日付ユーティリティのテスト
 * 【テスト対象】: formatDueDate, getDueStatus
 * 【テスト対応】: TASK-0016 テストケース2〜4
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { formatDueDate, getDueStatus } from '../date';

describe('date utilities', () => {
  beforeEach(() => {
    // 2024年1月15日を「今日」として固定
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-15T00:00:00'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('formatDueDate', () => {
    it('日付を日本語フォーマットで表示する', () => {
      const result = formatDueDate('2024-01-15');
      expect(result).toBe('1月15日(月)');
    });

    it('月末の日付を正しくフォーマットする', () => {
      const result = formatDueDate('2024-01-31');
      expect(result).toBe('1月31日(水)');
    });

    it('異なる月の日付を正しくフォーマットする', () => {
      const result = formatDueDate('2024-03-20');
      expect(result).toBe('3月20日(水)');
    });
  });

  describe('getDueStatus', () => {
    describe('期限切れ', () => {
      it('昨日の日付は期限切れと判定される', () => {
        const result = getDueStatus('2024-01-14');
        expect(result.status).toBe('overdue');
        expect(result.label).toBe('期限切れ');
      });

      it('過去の日付は期限切れと判定される', () => {
        const result = getDueStatus('2024-01-01');
        expect(result.status).toBe('overdue');
        expect(result.label).toBe('期限切れ');
      });
    });

    describe('今日', () => {
      it('今日の日付は今日と判定される', () => {
        const result = getDueStatus('2024-01-15');
        expect(result.status).toBe('today');
        expect(result.label).toBe('今日');
      });
    });

    describe('もうすぐ', () => {
      it('明日の日付はもうすぐと判定される', () => {
        const result = getDueStatus('2024-01-16');
        expect(result.status).toBe('upcoming');
        expect(result.label).toBe('もうすぐ');
      });

      it('2日後の日付はもうすぐと判定される', () => {
        const result = getDueStatus('2024-01-17');
        expect(result.status).toBe('upcoming');
        expect(result.label).toBe('もうすぐ');
      });
    });

    describe('それ以降', () => {
      it('3日後の日付は日付表示となる', () => {
        const result = getDueStatus('2024-01-18');
        expect(result.status).toBe('future');
        expect(result.label).toBe('1月18日(木)');
      });

      it('1週間後の日付は日付表示となる', () => {
        const result = getDueStatus('2024-01-22');
        expect(result.status).toBe('future');
        expect(result.label).toBe('1月22日(月)');
      });
    });
  });
});
