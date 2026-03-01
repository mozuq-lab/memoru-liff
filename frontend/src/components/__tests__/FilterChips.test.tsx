/**
 * 【テスト概要】: FilterChips コンポーネントのテスト
 * 【テスト対象】: FilterChips コンポーネント
 * 【テスト対応】: FC-001〜FC-004
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FilterChips } from '../FilterChips';

describe('FilterChips', () => {
  // FC-001: 4つのチップが表示される（all, due, learning, new）
  it('FC-001: 4つのチップが表示される（all, due, learning, new）', () => {
    render(<FilterChips value="all" onChange={vi.fn()} />);
    expect(screen.getByTestId('filter-chip-all')).toBeInTheDocument();
    expect(screen.getByTestId('filter-chip-due')).toBeInTheDocument();
    expect(screen.getByTestId('filter-chip-learning')).toBeInTheDocument();
    expect(screen.getByTestId('filter-chip-new')).toBeInTheDocument();
  });

  // FC-002: 選択中のチップが視覚的に区別される (aria-pressed="true")
  it('FC-002: 選択中のチップが aria-pressed="true" を持つ', () => {
    render(<FilterChips value="due" onChange={vi.fn()} />);
    const dueChip = screen.getByTestId('filter-chip-due');
    expect(dueChip).toHaveAttribute('aria-pressed', 'true');
    // 選択されていないチップは aria-pressed="false"
    expect(screen.getByTestId('filter-chip-all')).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByTestId('filter-chip-learning')).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByTestId('filter-chip-new')).toHaveAttribute('aria-pressed', 'false');
  });

  // FC-003: チップ押下で onChange が対応する ReviewStatusFilter 値で呼ばれる
  it('FC-003: チップ押下で onChange が対応する値で呼ばれる', () => {
    const onChange = vi.fn();
    render(<FilterChips value="all" onChange={onChange} />);
    fireEvent.click(screen.getByTestId('filter-chip-new'));
    expect(onChange).toHaveBeenCalledWith('new');
  });

  // FC-004: value='due' のとき「期日（due）」チップが selected 状態になる
  it('FC-004: value="due" のとき due チップが selected 状態になる', () => {
    render(<FilterChips value="due" onChange={vi.fn()} />);
    const dueChip = screen.getByTestId('filter-chip-due');
    expect(dueChip).toHaveAttribute('aria-pressed', 'true');
  });

  // すべてのチップラベルが表示されるか確認
  it('すべてのチップのラベルが表示される', () => {
    render(<FilterChips value="all" onChange={vi.fn()} />);
    expect(screen.getByText('すべて')).toBeInTheDocument();
    expect(screen.getByText('期日（due）')).toBeInTheDocument();
    expect(screen.getByText('学習中')).toBeInTheDocument();
    expect(screen.getByText('新規')).toBeInTheDocument();
  });

  // value='all' が初期状態
  it('value="all" のとき all チップが selected 状態になる', () => {
    render(<FilterChips value="all" onChange={vi.fn()} />);
    expect(screen.getByTestId('filter-chip-all')).toHaveAttribute('aria-pressed', 'true');
  });
});
