import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GradeButtons } from '../GradeButtons';

const defaultProps = {
  onGrade: vi.fn(),
  onSkip: vi.fn(),
  disabled: false,
};

const renderGradeButtons = (props = {}) => {
  return render(<GradeButtons {...defaultProps} {...props} />);
};

describe('GradeButtons', () => {
  describe('ボタン表示', () => {
    it('0-5 の6つの採点ボタンが表示される', () => {
      renderGradeButtons();
      for (let i = 0; i <= 5; i++) {
        expect(screen.getByRole('button', { name: new RegExp(`${i}`) })).toBeInTheDocument();
      }
    });

    it('スキップボタンが表示される', () => {
      renderGradeButtons();
      expect(screen.getByRole('button', { name: /スキップ/ })).toBeInTheDocument();
    });
  });

  describe('採点ボタンクリック', () => {
    it('グレード0のボタンをクリックすると onGrade(0) が呼ばれる', async () => {
      const onGrade = vi.fn();
      renderGradeButtons({ onGrade });

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /^0/ }));

      expect(onGrade).toHaveBeenCalledWith(0);
    });

    it('グレード3のボタンをクリックすると onGrade(3) が呼ばれる', async () => {
      const onGrade = vi.fn();
      renderGradeButtons({ onGrade });

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /^3/ }));

      expect(onGrade).toHaveBeenCalledWith(3);
    });

    it('グレード5のボタンをクリックすると onGrade(5) が呼ばれる', async () => {
      const onGrade = vi.fn();
      renderGradeButtons({ onGrade });

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /^5/ }));

      expect(onGrade).toHaveBeenCalledWith(5);
    });
  });

  describe('スキップボタンクリック', () => {
    it('スキップボタンをクリックすると onSkip が呼ばれる', async () => {
      const onSkip = vi.fn();
      renderGradeButtons({ onSkip });

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /スキップ/ }));

      expect(onSkip).toHaveBeenCalledTimes(1);
    });
  });

  describe('disabled 状態', () => {
    it('disabled=true の場合、採点ボタンが無効化される', () => {
      renderGradeButtons({ disabled: true });
      for (let i = 0; i <= 5; i++) {
        expect(screen.getByRole('button', { name: new RegExp(`^${i}`) })).toBeDisabled();
      }
    });

    it('disabled=true の場合、スキップボタンも無効化される', () => {
      renderGradeButtons({ disabled: true });
      expect(screen.getByRole('button', { name: /スキップ/ })).toBeDisabled();
    });

    it('disabled=true の場合、クリックしても onGrade が呼ばれない', async () => {
      const onGrade = vi.fn();
      renderGradeButtons({ onGrade, disabled: true });

      const user = userEvent.setup();
      await user.click(screen.getByRole('button', { name: /^3/ }));

      expect(onGrade).not.toHaveBeenCalled();
    });
  });

  describe('アクセシビリティ', () => {
    it('各採点ボタンに aria-label が設定されている', () => {
      renderGradeButtons();
      for (let i = 0; i <= 5; i++) {
        const button = screen.getByRole('button', { name: new RegExp(`^${i}`) });
        expect(button).toHaveAttribute('aria-label');
      }
    });
  });

  describe('再確認モード', () => {
    // 【テスト目的】: 再確認モード（isReconfirmMode=true）で正しいUIが表示されることを確認
    // 【テスト内容】: 2択ボタン表示、6段階ボタン非表示、スキップボタン非表示
    // 【期待される動作】: 早期リターンパターンにより再確認専用UIがレンダリングされる
    // 🔵 受け入れ基準 TC-002-01, TC-102-01 に対応

    // 【テストデータ準備】: 再確認モード用の共通 Props
    const reconfirmProps = {
      onGrade: vi.fn(),
      disabled: false,
      isReconfirmMode: true as const,
      onReconfirmRemembered: vi.fn(),
      onReconfirmForgotten: vi.fn(),
    };

    describe('正常系', () => {
      it('isReconfirmMode=true で「覚えた」「覚えていない」ボタンが表示される (TC-GB-001)', () => {
        // 【実際の処理実行】: 再確認モード Props で GradeButtons をレンダリング
        render(<GradeButtons {...reconfirmProps} />);

        // 【結果検証】: 2択ボタンの存在確認
        // 【検証項目】: 「覚えた」ボタンがDOMに存在すること 🔵
        expect(screen.getByRole('button', { name: '覚えた' })).toBeInTheDocument();
        // 【検証項目】: 「覚えていない」ボタンがDOMに存在すること 🔵
        expect(screen.getByRole('button', { name: '覚えていない' })).toBeInTheDocument();
      });

      it('isReconfirmMode=true で6段階評価ボタンが非表示になる (TC-GB-002)', () => {
        // 【実際の処理実行】: 再確認モードでレンダリング
        render(<GradeButtons {...reconfirmProps} />);

        // 【結果検証】: grade 0-5 のボタンが全て非表示であること
        // 【検証項目】: 早期リターンにより6段階UIブロックが到達不能 🔵
        for (let i = 0; i <= 5; i++) {
          expect(screen.queryByRole('button', { name: new RegExp(`^${i}`) })).toBeNull();
        }
      });

      it('isReconfirmMode=true でスキップボタンが非表示になる (TC-GB-003)', () => {
        // 【実際の処理実行】: onSkip が渡されていても再確認モードではスキップボタン非表示
        render(<GradeButtons {...reconfirmProps} onSkip={vi.fn()} />);

        // 【結果検証】: スキップボタンが存在しないこと
        // 【検証項目】: 要件定義書 REQ-102「再確認モードでスキップボタン非表示」 🔵
        expect(screen.queryByRole('button', { name: /スキップ/ })).toBeNull();
      });

      it('isReconfirmMode=false で6段階評価ボタンとスキップボタンが従来通り表示される (TC-GB-004)', () => {
        // 【実際の処理実行】: 通常モード（再確認モード無効）でレンダリング
        render(<GradeButtons onGrade={vi.fn()} onSkip={vi.fn()} disabled={false} isReconfirmMode={false} />);

        // 【結果検証】: 通常モードのUIが表示されること
        // 【検証項目】: grade 0-5 ボタン6つが全て存在する 🔵
        for (let i = 0; i <= 5; i++) {
          expect(screen.getByRole('button', { name: new RegExp(`^${i}`) })).toBeInTheDocument();
        }
        // 【検証項目】: スキップボタンが存在する 🔵
        expect(screen.getByRole('button', { name: /スキップ/ })).toBeInTheDocument();
        // 【検証項目】: 再確認用ボタンが存在しない 🔵
        expect(screen.queryByRole('button', { name: '覚えた' })).toBeNull();
        expect(screen.queryByRole('button', { name: '覚えていない' })).toBeNull();
      });

      it('「覚えた」ボタンクリックで onReconfirmRemembered が呼ばれる (TC-GB-005)', async () => {
        // 【テスト前準備】: モック関数を作成
        const onReconfirmRemembered = vi.fn();
        // 【実際の処理実行】: 「覚えた」ボタンをクリック
        render(<GradeButtons {...reconfirmProps} onReconfirmRemembered={onReconfirmRemembered} />);

        const user = userEvent.setup();
        await user.click(screen.getByRole('button', { name: '覚えた' }));

        // 【結果検証】: onReconfirmRemembered が1回だけ呼ばれること 🔵
        expect(onReconfirmRemembered).toHaveBeenCalledOnce();
      });

      it('「覚えていない」ボタンクリックで onReconfirmForgotten が呼ばれる (TC-GB-006)', async () => {
        // 【テスト前準備】: モック関数を作成
        const onReconfirmForgotten = vi.fn();
        // 【実際の処理実行】: 「覚えていない」ボタンをクリック
        render(<GradeButtons {...reconfirmProps} onReconfirmForgotten={onReconfirmForgotten} />);

        const user = userEvent.setup();
        await user.click(screen.getByRole('button', { name: '覚えていない' }));

        // 【結果検証】: onReconfirmForgotten が1回だけ呼ばれること 🔵
        expect(onReconfirmForgotten).toHaveBeenCalledOnce();
      });
    });

    describe('異常系', () => {
      it('disabled=true で再確認モード両ボタンが disabled 状態になる (TC-GB-007)', () => {
        // 【実際の処理実行】: disabled=true で再確認モードをレンダリング
        render(<GradeButtons {...reconfirmProps} disabled={true} />);

        // 【結果検証】: 両ボタンが disabled 属性を持つこと
        // 【検証項目】: 「覚えた」ボタンが無効化されていること 🔵
        expect(screen.getByRole('button', { name: '覚えた' })).toBeDisabled();
        // 【検証項目】: 「覚えていない」ボタンが無効化されていること 🔵
        expect(screen.getByRole('button', { name: '覚えていない' })).toBeDisabled();
      });

      it('disabled=true でクリックしても onReconfirmRemembered が呼ばれない (TC-GB-008)', async () => {
        // 【テスト前準備】: モック関数を作成
        const onReconfirmRemembered = vi.fn();
        // 【実際の処理実行】: disabled 状態で「覚えた」ボタンのクリックを試みる
        render(<GradeButtons {...reconfirmProps} disabled={true} onReconfirmRemembered={onReconfirmRemembered} />);

        const user = userEvent.setup();
        await user.click(screen.getByRole('button', { name: '覚えた' }));

        // 【結果検証】: disabled ボタンのクリックはイベントをブロックする 🔵
        expect(onReconfirmRemembered).not.toHaveBeenCalled();
      });

      it('disabled=true でクリックしても onReconfirmForgotten が呼ばれない (TC-GB-009)', async () => {
        // 【テスト前準備】: モック関数を作成
        const onReconfirmForgotten = vi.fn();
        // 【実際の処理実行】: disabled 状態で「覚えていない」ボタンのクリックを試みる
        render(<GradeButtons {...reconfirmProps} disabled={true} onReconfirmForgotten={onReconfirmForgotten} />);

        const user = userEvent.setup();
        await user.click(screen.getByRole('button', { name: '覚えていない' }));

        // 【結果検証】: disabled ボタンのクリックはイベントをブロックする 🔵
        expect(onReconfirmForgotten).not.toHaveBeenCalled();
      });
    });

    describe('境界値', () => {
      it('isReconfirmMode が未指定の場合に従来モードで表示される (TC-GB-010)', () => {
        // 【実際の処理実行】: isReconfirmMode を渡さない（undefined）
        render(<GradeButtons onGrade={vi.fn()} onSkip={vi.fn()} disabled={false} />);

        // 【結果検証】: 通常モードの6段階ボタンが表示される
        // 【検証項目】: undefined は falsy なので通常ブランチに入る 🔵
        for (let i = 0; i <= 5; i++) {
          expect(screen.getByRole('button', { name: new RegExp(`^${i}`) })).toBeInTheDocument();
        }
        // 【検証項目】: 再確認ボタンは存在しない 🔵
        expect(screen.queryByRole('button', { name: '覚えた' })).toBeNull();
        expect(screen.queryByRole('button', { name: '覚えていない' })).toBeNull();
      });

      it('再確認ボタンに min-h-[44px] クラスが適用されている (TC-GB-011)', () => {
        // 【実際の処理実行】: 再確認モードでレンダリング
        render(<GradeButtons {...reconfirmProps} />);

        // 【結果検証】: 両ボタンの className に min-h-[44px] が含まれること
        // 【検証項目】: WCAG 2.1 Level AAA のタップ領域最小値（44px x 44px）NFR-201 🟡
        const rememberedButton = screen.getByRole('button', { name: '覚えた' });
        const forgottenButton = screen.getByRole('button', { name: '覚えていない' });
        expect(rememberedButton.className).toContain('min-h-[44px]');
        expect(forgottenButton.className).toContain('min-h-[44px]');
      });
    });
  });
});
