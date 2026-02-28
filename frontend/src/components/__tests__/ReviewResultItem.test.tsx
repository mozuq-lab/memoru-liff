import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReviewResultItem } from '../ReviewResultItem';
import type { SessionCardResult } from '@/types';

describe('ReviewResultItem', () => {
  describe('再確認結果表示', () => {
    // 【テスト目的】: type='reconfirmed' のカードが正しい表示で結果リストに表示されることを確認
    // 【テスト内容】: 元の評価バッジ、「覚えた✔」サブラベル、Undoボタンの表示
    // 【期待される動作】: 通常 graded とは異なるサブラベルで再確認結果が区別できる
    // 🔵 受け入れ基準 TC-501-01, TC-501-02 に対応

    describe('正常系', () => {
      it('type="reconfirmed" で元の評価バッジ（grade=2）が表示される (TC-RRI-001)', () => {
        // 【テストデータ準備】: quality 2 で評価後に再確認で「覚えた」と回答したカード
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: 'テスト問題',
          grade: 2,
          type: 'reconfirmed',
          reconfirmResult: 'remembered',
        };
        // 【実際の処理実行】: 再確認結果のカードをレンダリング
        render(<ReviewResultItem result={result} index={0} />);

        // 【結果検証】: 元の評価値「2」のバッジが表示されること
        // 【検証項目】: grade=2 のラベルテキストがDOM内に存在すること 🔵
        expect(screen.getByText('2')).toBeInTheDocument();
        // 【確認内容】: バッジの色が amber であること（GRADE_DISPLAY_CONFIGS[2] = bg-amber-100）
        const badge = screen.getByText('2');
        expect(badge.className).toContain('bg-amber-100');
        expect(badge.className).toContain('text-amber-700');
      });

      it('type="reconfirmed" で「覚えた✔」サブラベルが表示される (TC-RRI-002)', () => {
        // 【テストデータ準備】: 再確認で「覚えた」として確認済みのカード
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: 'テスト問題',
          grade: 1,
          type: 'reconfirmed',
          reconfirmResult: 'remembered',
        };
        // 【実際の処理実行】: 再確認結果のカードをレンダリング
        render(<ReviewResultItem result={result} index={0} />);

        // 【結果検証】: 「覚えた✔」サブラベルが表示されること
        // 【検証項目】: reconfirm-ui-requirements.md セクション2.4「サブラベル: 覚えた✔, text-xs text-green-600」 🔵
        expect(screen.getByText('覚えた✔')).toBeInTheDocument();
      });

      it('type="reconfirmed" で「次回:」が表示されない (TC-RRI-003)', () => {
        // 【テストデータ準備】: nextReviewDate が設定されていても type='reconfirmed' では非表示
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: 'テスト問題',
          grade: 2,
          type: 'reconfirmed',
          nextReviewDate: '2026-03-01',
          reconfirmResult: 'remembered',
        };
        // 【実際の処理実行】: 再確認結果のカードをレンダリング
        render(<ReviewResultItem result={result} index={0} />);

        // 【結果検証】: 次回復習日が表示されないこと
        // 【検証項目】: type='reconfirmed' では nextReviewDate は非表示 🔵
        expect(screen.queryByText(/次回/)).toBeNull();
      });

      it('type="graded"（grade=4）で従来通りのバッジと次回復習日が表示される (TC-RRI-004)', () => {
        // 【テストデータ準備】: quality 4 で採点された通常の復習カード
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: 'テスト問題',
          grade: 4,
          type: 'graded',
          nextReviewDate: '2026-03-01',
        };
        // 【実際の処理実行】: 通常の graded カードをレンダリング
        render(<ReviewResultItem result={result} index={0} />);

        // 【結果検証】: 通常表示が維持されていること（リグレッション防止）
        // 【検証項目】: grade=4 ラベルが存在すること 🔵
        expect(screen.getByText('4')).toBeInTheDocument();
        // 【検証項目】: 次回復習日が表示されること 🔵
        expect(screen.getByText(/次回: 2026-03-01/)).toBeInTheDocument();
        // 【検証項目】: 「覚えた✔」は表示されないこと 🔵
        expect(screen.queryByText('覚えた✔')).toBeNull();
      });

      it('type="graded"（grade=1）で従来通りの表示（低評価）(TC-RRI-005)', () => {
        // 【テストデータ準備】: quality 1 で採点された低評価カード
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: 'テスト問題',
          grade: 1,
          type: 'graded',
          nextReviewDate: '2026-03-01',
        };
        // 【実際の処理実行】: 低評価の graded カードをレンダリング
        render(<ReviewResultItem result={result} index={0} />);

        // 【結果検証】: type='graded' なら低評価でも従来通りの表示 🔵
        expect(screen.getByText('1')).toBeInTheDocument();
        expect(screen.getByText(/次回: 2026-03-01/)).toBeInTheDocument();
        // 【検証項目】: 「覚えた✔」は表示されないこと 🔵
        expect(screen.queryByText('覚えた✔')).toBeNull();
      });

      it('type="reconfirmed" で Undo ボタンが表示される (TC-RRI-006)', () => {
        // 【テストデータ準備】: 再確認カードに Undo 機能が有効なケース
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: 'テスト問題',
          grade: 2,
          type: 'reconfirmed',
          reconfirmResult: 'remembered',
        };
        const onUndo = vi.fn();
        // 【実際の処理実行】: onUndo ハンドラ付きで再確認カードをレンダリング
        render(<ReviewResultItem result={result} index={0} onUndo={onUndo} />);

        // 【結果検証】: Undo ボタンが表示されること
        // 【検証項目】: 要件定義書 REQ-404「Undo 機能は再確認カードにも使用可能」 🔵
        expect(screen.getByRole('button', { name: /取り消す/ })).toBeInTheDocument();
      });

      it('type="reconfirmed" で Undo ボタンクリックが onUndo(index) を呼ぶ (TC-RRI-007)', async () => {
        // 【テストデータ準備】: 再確認カードの Undo 操作
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: 'テスト問題',
          grade: 2,
          type: 'reconfirmed',
          reconfirmResult: 'remembered',
        };
        const onUndo = vi.fn();
        // 【実際の処理実行】: Undo ボタンをクリック
        render(<ReviewResultItem result={result} index={0} onUndo={onUndo} />);

        const user = userEvent.setup();
        await user.click(screen.getByRole('button', { name: /取り消す/ }));

        // 【結果検証】: onUndo に index=0 が渡されること 🔵
        expect(onUndo).toHaveBeenCalledWith(0);
      });

      it('type="reconfirmed" でカード表面テキストが表示される (TC-RRI-010)', () => {
        // 【テストデータ準備】: カードの表面テキスト確認
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: '日本語の単語テスト',
          grade: 0,
          type: 'reconfirmed',
          reconfirmResult: 'remembered',
        };
        // 【実際の処理実行】: 再確認カードをレンダリング
        render(<ReviewResultItem result={result} index={0} />);

        // 【結果検証】: front テキストが表示されること
        // 【検証項目】: reconfirm-ui-requirements.md「カード表面テキスト: result.front（truncate）」 🔵
        expect(screen.getByText('日本語の単語テスト')).toBeInTheDocument();
      });
    });

    describe('リグレッション防止', () => {
      it('type="skipped" で従来通りの表示（ダッシュバッジ + スキップ）(TC-RRI-008)', () => {
        // 【テストデータ準備】: スキップされたカードの結果表示
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: 'テスト問題',
          type: 'skipped',
        };
        // 【実際の処理実行】: スキップカードをレンダリング
        render(<ReviewResultItem result={result} index={0} />);

        // 【結果検証】: 従来の skipped 表示が変わっていないこと 🔵
        expect(screen.getByText('—')).toBeInTheDocument();
        expect(screen.getByText('スキップ')).toBeInTheDocument();
        // 【検証項目】: Undo ボタンは非表示（onUndo なし）
        expect(screen.queryByRole('button', { name: /取り消す/ })).toBeNull();
      });

      it('type="undone" で従来通りの表示（戻るバッジ + 取り消し済み）(TC-RRI-009)', () => {
        // 【テストデータ準備】: 取り消されたカードの結果表示
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: 'テスト問題',
          type: 'undone',
        };
        // 【実際の処理実行】: undone カードをレンダリング
        render(<ReviewResultItem result={result} index={0} />);

        // 【結果検証】: 従来の undone 表示が変わっていないこと 🔵
        expect(screen.getByText('↩')).toBeInTheDocument();
        expect(screen.getByText('取り消し済み')).toBeInTheDocument();
        // 【検証項目】: Undo ボタンは非表示（onUndo なし）
        expect(screen.queryByRole('button', { name: /取り消す/ })).toBeNull();
      });
    });

    describe('境界値', () => {
      it('type="reconfirmed" かつ grade=undefined でグレードバッジが非表示 (TC-RRI-011)', () => {
        // 【テストデータ準備】: grade が未定義の再確認カード（オプショナルフィールドのエッジケース）
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: 'テスト問題',
          type: 'reconfirmed',
          reconfirmResult: 'remembered',
        };
        // 【実際の処理実行】: grade なしでレンダリング
        render(<ReviewResultItem result={result} index={0} />);

        // 【結果検証】: グレード数値が表示されないこと（グレースフルデグラデーション）
        // 【検証項目】: gradeConfig = null となりバッジがレンダリングされない 🟡
        // 「覚えた✔」のみ表示される（またはバッジなしで正常に動作する）
        expect(screen.getByText('テスト問題')).toBeInTheDocument();
        // 数値ラベルが存在しないことを確認（0,1,2,3,4,5 どれも表示されない）
        for (let i = 0; i <= 5; i++) {
          expect(screen.queryByText(String(i))).toBeNull();
        }
      });

      it('type="reconfirmed" かつ grade=0 で正しいバッジが表示される (TC-RRI-012)', () => {
        // 【テストデータ準備】: grade の最小値（0）での表示確認
        const result: SessionCardResult = {
          cardId: 'card-1',
          front: 'テスト問題',
          grade: 0,
          type: 'reconfirmed',
          reconfirmResult: 'remembered',
        };
        // 【実際の処理実行】: grade=0 の再確認カードをレンダリング
        render(<ReviewResultItem result={result} index={0} />);

        // 【結果検証】: grade=0 のバッジが正しく表示されること
        // 【検証項目】: GRADE_DISPLAY_CONFIGS[0] = { label: '0', bgClass: 'bg-red-100', textClass: 'text-red-700' } 🔵
        expect(screen.getByText('0')).toBeInTheDocument();
        const badge = screen.getByText('0');
        expect(badge.className).toContain('bg-red-100');
        expect(badge.className).toContain('text-red-700');
        // 「覚えた✔」も表示される
        expect(screen.getByText('覚えた✔')).toBeInTheDocument();
      });
    });
  });
});
