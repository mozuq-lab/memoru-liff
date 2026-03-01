/**
 * 【テスト概要】: DeckFormModal コンポーネントの差分送信テスト
 * 【テスト対象】: DeckFormModal edit モード - 変更フィールドのみ送信
 * 【関連要件】: REQ-202, REQ-105, REQ-106
 * 【関連タスク】: TASK-0094
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DeckFormModal } from '../DeckFormModal';
import type { Deck } from '@/types';

// ----------------------------------------------------------------
// テストヘルパー
// ----------------------------------------------------------------

const makeDeck = (overrides: Partial<Deck> = {}): Deck => ({
  deck_id: 'deck-1',
  user_id: 'user-1',
  name: '英語',
  description: '基本単語',
  color: '#3B82F6',
  card_count: 10,
  due_count: 3,
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

// ----------------------------------------------------------------
// セットアップ
// ----------------------------------------------------------------

beforeEach(() => {
  // 【テスト前準備】: 各テスト実行前にモック関数をリセット
  // 【環境初期化】: onSubmit / onClose のモック呼び出し履歴をクリア
  vi.clearAllMocks();
});

// ================================================================
// 正常系テストケース
// ================================================================

describe('DeckFormModal - edit モード差分送信', () => {
  // ----------------------------------------------------------------
  // TC-01: name のみ変更時に name のみ送信される
  // ----------------------------------------------------------------
  it('name のみ変更時に name のみ送信される', async () => {
    // 【テスト目的】: edit モードで name だけを変更した場合、payload に name のみが含まれることを確認
    // 【テスト内容】: description と color を初期値のまま、name のみ変更して保存
    // 【期待される動作】: onSubmit が { name: "英単語" } で呼ばれる
    // 🔵 REQ-202・TC-202-01

    // 【テストデータ準備】: 全フィールドが設定されたデッキを用意
    const deck = makeDeck({ name: '英語', description: '基本単語', color: '#3B82F6' });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    // 【初期条件設定】: edit モードでモーダルをレンダリング
    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: name 入力欄を変更して保存
    const nameInput = screen.getByTestId('deck-name-input');
    fireEvent.change(nameInput, { target: { value: '英単語' } });
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: onSubmit の引数が name のみを含むこと
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ name: '英単語' }); // 🔵
    });
    // 【確認ポイント】: payload に description キーと color キーが存在しないこと
    const payload = onSubmit.mock.calls[0][0];
    expect(payload).not.toHaveProperty('description');
    expect(payload).not.toHaveProperty('color');
  });

  // ----------------------------------------------------------------
  // TC-02: description のみ変更時に description のみ送信される
  // ----------------------------------------------------------------
  it('description のみ変更時に description のみ送信される', async () => {
    // 【テスト目的】: edit モードで description だけを変更した場合の payload
    // 【期待される動作】: onSubmit が { description: "応用単語" } で呼ばれる
    // 🔵 REQ-202

    const deck = makeDeck({ name: '英語', description: '基本単語', color: '#3B82F6' });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: description を変更して保存
    const descriptionInput = screen.getByTestId('deck-description-input');
    fireEvent.change(descriptionInput, { target: { value: '応用単語' } });
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: onSubmit の引数が description のみを含むこと
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ description: '応用単語' }); // 🔵
    });
    // 【確認ポイント】: name キーと color キーが存在しないこと
    const payload = onSubmit.mock.calls[0][0];
    expect(payload).not.toHaveProperty('name');
    expect(payload).not.toHaveProperty('color');
  });

  // ----------------------------------------------------------------
  // TC-03: color のみ変更時に color のみ送信される
  // ----------------------------------------------------------------
  it('color のみ変更時に color のみ送信される', async () => {
    // 【テスト目的】: edit モードで color だけを変更した場合の payload
    // 【期待される動作】: onSubmit が { color: "#EF4444" } で呼ばれる
    // 🔵 REQ-202

    const deck = makeDeck({ name: '英語', description: '基本単語', color: '#3B82F6' });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: color パレットで #EF4444 を選択して保存
    fireEvent.click(screen.getByTestId('deck-color-#EF4444'));
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: onSubmit の引数が color のみを含むこと
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ color: '#EF4444' }); // 🔵
    });
    // 【確認ポイント】: name キーと description キーが存在しないこと
    const payload = onSubmit.mock.calls[0][0];
    expect(payload).not.toHaveProperty('name');
    expect(payload).not.toHaveProperty('description');
  });

  // ----------------------------------------------------------------
  // TC-04: 複数フィールド変更時に変更フィールドのみ送信される
  // ----------------------------------------------------------------
  it('複数フィールド変更時に変更フィールドのみ送信される', async () => {
    // 【テスト目的】: name と description を同時に変更した場合、両方が payload に含まれ color は含まれないこと
    // 【期待される動作】: onSubmit が { name: "英単語", description: "応用単語" } で呼ばれる
    // 🔵 REQ-202・要件定義パターン4

    const deck = makeDeck({ name: '英語', description: '基本単語', color: '#3B82F6' });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: name と description を変更して保存
    const nameInput = screen.getByTestId('deck-name-input');
    fireEvent.change(nameInput, { target: { value: '英単語' } });
    const descriptionInput = screen.getByTestId('deck-description-input');
    fireEvent.change(descriptionInput, { target: { value: '応用単語' } });
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: onSubmit の引数が name と description を含むこと
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ name: '英単語', description: '応用単語' }); // 🔵
    });
    // 【確認ポイント】: color キーが存在しないこと
    const payload = onSubmit.mock.calls[0][0];
    expect(payload).not.toHaveProperty('color');
  });

  // ----------------------------------------------------------------
  // TC-05: description をクリアすると null が送信される
  // ----------------------------------------------------------------
  it('description をクリアすると null が送信される', async () => {
    // 【テスト目的】: edit モードで description を空にした場合、description: null が送信されること
    // 【期待される動作】: onSubmit が { description: null } で呼ばれる
    // 🔵 REQ-105・REQ-202・要件定義パターン2

    const deck = makeDeck({ name: '英語', description: '基本単語', color: '#3B82F6' });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: description を空にして保存
    const descriptionInput = screen.getByTestId('deck-description-input');
    fireEvent.change(descriptionInput, { target: { value: '' } });
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: onSubmit の引数に description: null が含まれること
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ description: null }); // 🔵
    });
    // 【確認ポイント】: null であること（undefined や空文字 '' ではないこと）
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.description).toBeNull();
  });

  // ----------------------------------------------------------------
  // TC-06: color を選択解除すると null が送信される
  // ----------------------------------------------------------------
  it('color を選択解除すると null が送信される', async () => {
    // 【テスト目的】: edit モードで color の「なし」ボタンを押した場合、color: null が送信されること
    // 【期待される動作】: onSubmit が { color: null } で呼ばれる
    // 🔵 REQ-106・REQ-202・TC-202-02

    const deck = makeDeck({ name: '英語', description: '基本単語', color: '#3B82F6' });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: color の「カラーなし」ボタンを押下して保存
    fireEvent.click(screen.getByTestId('deck-color-none'));
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: onSubmit の引数に color: null が含まれること
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ color: null }); // 🔵
    });
    // 【確認ポイント】: null であること（undefined ではないこと）
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.color).toBeNull();
  });

  // ----------------------------------------------------------------
  // TC-07: create モードでは全フィールドが送信される（回帰テスト）
  // ----------------------------------------------------------------
  it('create モードでは全フィールドが送信される（回帰テスト）', async () => {
    // 【テスト目的】: create モードでは従来どおり入力フィールドが全て送信されること
    // 【期待される動作】: onSubmit が { name: "新デッキ", description: "説明文", color: "#3B82F6" } で呼ばれる
    // 🔵 制約条件「create モード非破壊」より

    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="create" isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: 各フィールドを入力して保存
    const nameInput = screen.getByTestId('deck-name-input');
    fireEvent.change(nameInput, { target: { value: '新デッキ' } });
    const descriptionInput = screen.getByTestId('deck-description-input');
    fireEvent.change(descriptionInput, { target: { value: '説明文' } });
    fireEvent.click(screen.getByTestId('deck-color-#3B82F6'));
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: 全フィールドが含まれること
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        name: '新デッキ',
        description: '説明文',
        color: '#3B82F6',
      }); // 🔵
    });
  });
});

// ================================================================
// 異常系テストケース
// ================================================================

describe('DeckFormModal - edit モード異常系', () => {
  // ----------------------------------------------------------------
  // TC-E01: 変更なし時に空 payload が送信される
  // ----------------------------------------------------------------
  it('変更なし時に空 payload が送信される', async () => {
    // 【テスト目的】: ユーザーが何も変更せず保存した場合の振る舞い
    // 【期待される動作】: onSubmit が {} で呼ばれる
    // 🔵 TASK-0094 完了条件・要件定義 Edge1 より

    const deck = makeDeck({ name: '英語', description: '基本単語', color: '#3B82F6' });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: 何も変更せず保存ボタン押下
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: onSubmit が空オブジェクトで呼ばれること
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({}); // 🔵
    });
  });
});

// ================================================================
// 境界値テストケース
// ================================================================

describe('DeckFormModal - edit モード境界値', () => {
  // ----------------------------------------------------------------
  // TC-B01: description が null のデッキで空のまま保存すると変更なし
  // ----------------------------------------------------------------
  it('description が null のデッキで空のまま保存すると description は payload に含まれない', async () => {
    // 【テスト目的】: null と空文字の正規化後の比較が一致し、差分なしと判定される境界
    // 【期待される動作】: onSubmit の引数に description キーが含まれない
    // 🟡 要件定義 Edge2 から妥当な推測

    const deck = makeDeck({ name: '英語', description: null, color: '#3B82F6' });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: description を空のまま保存
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: description が payload に含まれないこと
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });
    const payload = onSubmit.mock.calls[0][0];
    expect(payload).not.toHaveProperty('description'); // 🟡
  });

  // ----------------------------------------------------------------
  // TC-B02: color が null のデッキで「なし」のまま保存すると変更なし
  // ----------------------------------------------------------------
  it('color が null のデッキで「なし」のまま保存すると color は payload に含まれない', async () => {
    // 【テスト目的】: null と undefined の正規化後の比較が一致し、差分なしと判定される境界
    // 【期待される動作】: onSubmit の引数に color キーが含まれない
    // 🟡 要件定義 Edge3 から妥当な推測

    const deck = makeDeck({ name: '英語', description: '基本単語', color: null });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: color を「なし」のまま保存（デフォルト状態）
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: color が payload に含まれないこと
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });
    const payload = onSubmit.mock.calls[0][0];
    expect(payload).not.toHaveProperty('color'); // 🟡
  });

  // ----------------------------------------------------------------
  // TC-B03: description に空白のみを入力すると null が送信される
  // ----------------------------------------------------------------
  it('description に空白のみを入力すると null が送信される', async () => {
    // 【テスト目的】: trim() 後に空文字になる入力が null 変換されることの確認
    // 【期待される動作】: onSubmit の引数に description: null が含まれる
    // 🟡 要件定義 Edge4 から妥当な推測

    const deck = makeDeck({ name: '英語', description: '基本単語', color: '#3B82F6' });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: description に空白のみを入力して保存
    const descriptionInput = screen.getByTestId('deck-description-input');
    fireEvent.change(descriptionInput, { target: { value: '   ' } });
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: description: null が送信されること
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ description: null }); // 🟡
    });
  });

  // ----------------------------------------------------------------
  // TC-B04: color を変更してから元に戻すと変更なしとして空 payload が送信される
  // ----------------------------------------------------------------
  it('color を変更してから元に戻すと変更なしとして空 payload が送信される', async () => {
    // 【テスト目的】: 一度変更した値を元に戻した場合に差分検出が正しく「変更なし」と判定すること
    // 【期待される動作】: onSubmit の引数が {}（空オブジェクト）
    // 🟡 要件定義 Edge5 から妥当な推測

    const deck = makeDeck({ name: '英語', description: '基本単語', color: '#3B82F6' });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: color を #EF4444 に変更して → 元の #3B82F6 に戻す → 保存
    fireEvent.click(screen.getByTestId('deck-color-#EF4444'));
    fireEvent.click(screen.getByTestId('deck-color-#3B82F6'));
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: 空オブジェクトで呼ばれること
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({}); // 🟡
    });
  });

  // ----------------------------------------------------------------
  // TC-B05: description と color を同時にクリアすると両方 null が送信される
  // ----------------------------------------------------------------
  it('description と color を同時にクリアすると両方 null が送信される', async () => {
    // 【テスト目的】: 複数フィールドの同時クリアが正しく処理されること（EDGE-102 対応）
    // 【期待される動作】: onSubmit の引数が { description: null, color: null }
    // 🔵 EDGE-102・REQ-105・REQ-106 より

    const deck = makeDeck({ name: '英語', description: '基本単語', color: '#3B82F6' });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
    );

    // 【実際の処理実行】: description を空に、color を「なし」に変更して保存
    const descriptionInput = screen.getByTestId('deck-description-input');
    fireEvent.change(descriptionInput, { target: { value: '' } });
    fireEvent.click(screen.getByTestId('deck-color-none'));
    fireEvent.click(screen.getByTestId('deck-form-submit'));

    // 【結果検証】: 両フィールドが null で送信されること
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ description: null, color: null }); // 🔵
    });
    // 【確認ポイント】: name は未変更のため含まれないこと
    const payload = onSubmit.mock.calls[0][0];
    expect(payload).not.toHaveProperty('name');
  });
});
