/**
 * GenerateOptions コンポーネントテスト (T028)
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GenerateOptions } from '../GenerateOptions';

describe('GenerateOptions', () => {
  const defaultProps = {
    cardType: 'qa' as const,
    targetCount: 10,
    difficulty: 'medium' as const,
    onCardTypeChange: vi.fn(),
    onTargetCountChange: vi.fn(),
    onDifficultyChange: vi.fn(),
    disabled: false,
  };

  it('renders card type selector with all options', () => {
    render(<GenerateOptions {...defaultProps} />);

    expect(screen.getByTestId('card-type-qa')).toBeInTheDocument();
    expect(screen.getByTestId('card-type-definition')).toBeInTheDocument();
    expect(screen.getByTestId('card-type-cloze')).toBeInTheDocument();
  });

  it('highlights selected card type', () => {
    render(<GenerateOptions {...defaultProps} cardType="definition" />);

    const definitionBtn = screen.getByTestId('card-type-definition');
    expect(definitionBtn.className).toContain('bg-blue');
  });

  it('calls onCardTypeChange when card type clicked', () => {
    const onCardTypeChange = vi.fn();
    render(<GenerateOptions {...defaultProps} onCardTypeChange={onCardTypeChange} />);

    fireEvent.click(screen.getByTestId('card-type-cloze'));
    expect(onCardTypeChange).toHaveBeenCalledWith('cloze');
  });

  it('renders target count slider', () => {
    render(<GenerateOptions {...defaultProps} targetCount={15} />);

    const slider = screen.getByTestId('target-count-slider') as HTMLInputElement;
    expect(slider).toBeInTheDocument();
    expect(slider.value).toBe('15');
  });

  it('calls onTargetCountChange when slider changes', () => {
    const onTargetCountChange = vi.fn();
    render(<GenerateOptions {...defaultProps} onTargetCountChange={onTargetCountChange} />);

    const slider = screen.getByTestId('target-count-slider');
    fireEvent.change(slider, { target: { value: '20' } });
    expect(onTargetCountChange).toHaveBeenCalledWith(20);
  });

  it('displays target count value', () => {
    render(<GenerateOptions {...defaultProps} targetCount={15} />);

    expect(screen.getByTestId('target-count-display')).toHaveTextContent('15');
  });

  it('renders difficulty selector', () => {
    render(<GenerateOptions {...defaultProps} />);

    expect(screen.getByTestId('difficulty-easy')).toBeInTheDocument();
    expect(screen.getByTestId('difficulty-medium')).toBeInTheDocument();
    expect(screen.getByTestId('difficulty-hard')).toBeInTheDocument();
  });

  it('calls onDifficultyChange when difficulty clicked', () => {
    const onDifficultyChange = vi.fn();
    render(<GenerateOptions {...defaultProps} onDifficultyChange={onDifficultyChange} />);

    fireEvent.click(screen.getByTestId('difficulty-hard'));
    expect(onDifficultyChange).toHaveBeenCalledWith('hard');
  });

  it('disables all controls when disabled prop is true', () => {
    render(<GenerateOptions {...defaultProps} disabled={true} />);

    const slider = screen.getByTestId('target-count-slider') as HTMLInputElement;
    expect(slider.disabled).toBe(true);

    // Card type buttons should have disabled styling
    const qaBtn = screen.getByTestId('card-type-qa');
    expect(qaBtn).toHaveAttribute('disabled');
  });
});
