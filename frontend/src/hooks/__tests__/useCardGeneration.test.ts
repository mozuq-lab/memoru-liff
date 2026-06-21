import { describe, it, expect } from 'vitest';
import { resolveTimeoutMs } from '@/hooks/useCardGeneration';

describe('resolveTimeoutMs', () => {
  it('正の数値文字列を数値(ms)として解決する', () => {
    expect(resolveTimeoutMs('180000', 30000)).toBe(180000);
  });

  it('未設定(undefined)は fallback を使う', () => {
    expect(resolveTimeoutMs(undefined, 30000)).toBe(30000);
  });

  it('空文字は fallback を使う', () => {
    expect(resolveTimeoutMs('', 30000)).toBe(30000);
  });

  it('非数値は fallback を使う', () => {
    expect(resolveTimeoutMs('abc', 30000)).toBe(30000);
  });

  it('0 や負値は fallback を使う', () => {
    expect(resolveTimeoutMs('0', 30000)).toBe(30000);
    expect(resolveTimeoutMs('-5', 30000)).toBe(30000);
  });

  it('Infinity など非有限値は fallback を使う', () => {
    expect(resolveTimeoutMs('Infinity', 30000)).toBe(30000);
  });
});
