/**
 * 【テスト概要】: SearchBar コンポーネントのテスト
 * 【テスト対象】: SearchBar コンポーネント
 * 【テスト対応】: SB-001〜SB-008
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SearchBar } from '../SearchBar';

describe('SearchBar', () => {
  // SB-001: 入力フィールドが表示される
  it('SB-001: 入力フィールドが表示される', () => {
    render(<SearchBar value="" onChange={vi.fn()} />);
    expect(screen.getByRole('searchbox')).toBeInTheDocument();
  });

  // SB-002: テキスト入力により onChange が呼ばれる
  it('SB-002: テキスト入力により onChange が呼ばれる', () => {
    const onChange = vi.fn();
    render(<SearchBar value="" onChange={onChange} />);
    const input = screen.getByRole('searchbox');
    fireEvent.change(input, { target: { value: 'test' } });
    expect(onChange).toHaveBeenCalledWith('test');
  });

  // SB-003: value が空でないとき、クリアボタン（✕）が表示される
  it('SB-003: value が空でないとき、クリアボタンが表示される', () => {
    render(<SearchBar value="hello" onChange={vi.fn()} />);
    expect(screen.getByTestId('search-bar-clear')).toBeInTheDocument();
  });

  // SB-004: クリアボタン押下で onChange('') が呼ばれる
  it('SB-004: クリアボタン押下で onChange("") が呼ばれる', () => {
    const onChange = vi.fn();
    render(<SearchBar value="hello" onChange={onChange} />);
    fireEvent.click(screen.getByTestId('search-bar-clear'));
    expect(onChange).toHaveBeenCalledWith('');
  });

  // SB-005: value が空のときクリアボタンは表示されない
  it('SB-005: value が空のときクリアボタンは表示されない', () => {
    render(<SearchBar value="" onChange={vi.fn()} />);
    expect(screen.queryByTestId('search-bar-clear')).toBeNull();
  });

  // SB-006: maxLength による入力制限が機能する
  it('SB-006: maxLength による入力制限が機能する', () => {
    render(<SearchBar value="" onChange={vi.fn()} maxLength={10} />);
    const input = screen.getByRole('searchbox');
    expect(input).toHaveAttribute('maxLength', '10');
  });

  // SB-007: data-testid="search-bar-input" が付与されている
  it('SB-007: data-testid="search-bar-input" が付与されている', () => {
    render(<SearchBar value="" onChange={vi.fn()} />);
    expect(screen.getByTestId('search-bar-input')).toBeInTheDocument();
  });

  // SB-008: data-testid="search-bar-clear" がクリアボタンに付与されている
  it('SB-008: data-testid="search-bar-clear" がクリアボタンに付与されている', () => {
    render(<SearchBar value="text" onChange={vi.fn()} />);
    const clearBtn = screen.getByTestId('search-bar-clear');
    expect(clearBtn).toBeInTheDocument();
  });

  // デフォルト placeholder
  it('デフォルトの placeholder が表示される', () => {
    render(<SearchBar value="" onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText('カードを検索...')).toBeInTheDocument();
  });

  // カスタム placeholder
  it('カスタム placeholder が設定できる', () => {
    render(<SearchBar value="" onChange={vi.fn()} placeholder="検索" />);
    expect(screen.getByPlaceholderText('検索')).toBeInTheDocument();
  });
});
