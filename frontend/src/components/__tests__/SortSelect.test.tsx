/**
 * 【テスト概要】: SortSelect コンポーネントのテスト
 * 【テスト対象】: SortSelect コンポーネント
 * 【テスト対応】: SS-001〜SS-006
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SortSelect } from '../SortSelect';

describe('SortSelect', () => {
  const defaultProps = {
    sortBy: 'created_at' as const,
    sortOrder: 'desc' as const,
    onSortByChange: vi.fn(),
    onSortOrderChange: vi.fn(),
  };

  // SS-001: ソートキー選択ドロップダウンが表示される
  it('SS-001: ソートキー選択ドロップダウンが表示される', () => {
    render(<SortSelect {...defaultProps} />);
    expect(screen.getByTestId('sort-by-select')).toBeInTheDocument();
  });

  // SS-002: ソート方向トグルボタンが表示される
  it('SS-002: ソート方向トグルボタンが表示される', () => {
    render(<SortSelect {...defaultProps} />);
    expect(screen.getByTestId('sort-order-toggle')).toBeInTheDocument();
  });

  // SS-003: data-testid="sort-by-select" が付与されている
  it('SS-003: data-testid="sort-by-select" が付与されている', () => {
    render(<SortSelect {...defaultProps} />);
    const select = screen.getByTestId('sort-by-select');
    expect(select.tagName.toLowerCase()).toBe('select');
  });

  // SS-004: data-testid="sort-order-toggle" が付与されている
  it('SS-004: data-testid="sort-order-toggle" が付与されている', () => {
    render(<SortSelect {...defaultProps} />);
    const toggle = screen.getByTestId('sort-order-toggle');
    expect(toggle.tagName.toLowerCase()).toBe('button');
  });

  // SS-005: ソートキー変更で onSortByChange が呼ばれる
  it('SS-005: ソートキー変更で onSortByChange が呼ばれる', () => {
    const onSortByChange = vi.fn();
    render(<SortSelect {...defaultProps} onSortByChange={onSortByChange} />);
    fireEvent.change(screen.getByTestId('sort-by-select'), {
      target: { value: 'ease_factor' },
    });
    expect(onSortByChange).toHaveBeenCalledWith('ease_factor');
  });

  // SS-006: 方向トグルで onSortOrderChange が呼ばれる
  it('SS-006: 方向トグルで onSortOrderChange が呼ばれる', () => {
    const onSortOrderChange = vi.fn();
    render(<SortSelect {...defaultProps} onSortOrderChange={onSortOrderChange} />);
    fireEvent.click(screen.getByTestId('sort-order-toggle'));
    // desc → asc に切り替え
    expect(onSortOrderChange).toHaveBeenCalledWith('asc');
  });

  // ソートキーのオプションが3つ表示されるか確認
  it('ソートキーのオプションが3つ表示される', () => {
    render(<SortSelect {...defaultProps} />);
    const select = screen.getByTestId('sort-by-select') as HTMLSelectElement;
    expect(select.options).toHaveLength(3);
  });

  // sortOrder='asc' のとき、トグルで 'desc' を呼ぶ
  it("sortOrder='asc' のとき、トグルで 'desc' を呼ぶ", () => {
    const onSortOrderChange = vi.fn();
    render(
      <SortSelect {...defaultProps} sortOrder="asc" onSortOrderChange={onSortOrderChange} />
    );
    fireEvent.click(screen.getByTestId('sort-order-toggle'));
    expect(onSortOrderChange).toHaveBeenCalledWith('desc');
  });
});
