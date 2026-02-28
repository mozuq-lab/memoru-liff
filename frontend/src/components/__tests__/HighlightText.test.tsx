/**
 * 【テスト概要】: HighlightText コンポーネントのテスト
 * 【テスト対象】: HighlightText コンポーネント
 * 【テスト対応】: HT-001〜HT-006
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HighlightText } from '../HighlightText';

describe('HighlightText', () => {
  // HT-001: query が空のとき、テキストがそのまま表示される
  it('HT-001: query が空のとき、テキストがそのまま表示される', () => {
    render(<HighlightText text="テストテキスト" query="" />);
    expect(screen.getByText('テストテキスト')).toBeInTheDocument();
    expect(document.querySelector('mark')).toBeNull();
  });

  // HT-002: query がマッチした箇所は <mark> タグで囲まれる
  it('HT-002: query がマッチした箇所は <mark> タグで囲まれる', () => {
    render(<HighlightText text="こんにちは世界" query="世界" />);
    const mark = document.querySelector('mark');
    expect(mark).toBeInTheDocument();
    expect(mark?.textContent).toBe('世界');
  });

  // HT-003: マッチは大文字・小文字を区別しない
  it('HT-003: マッチは大文字・小文字を区別しない', () => {
    render(<HighlightText text="Hello World" query="hello" />);
    const mark = document.querySelector('mark');
    expect(mark).toBeInTheDocument();
    expect(mark?.textContent).toBe('Hello');
  });

  // HT-004: マッチは全角・半角を区別しない
  it('HT-004: マッチは全角・半角を区別しない', () => {
    render(<HighlightText text="ｈｅｌｌｏ world" query="hello" />);
    const mark = document.querySelector('mark');
    expect(mark).toBeInTheDocument();
    expect(mark?.textContent).toBe('ｈｅｌｌｏ');
  });

  // HT-005: XSS を引き起こす特殊文字が安全にエスケープされる
  it('HT-005: XSS を引き起こす特殊文字が安全にエスケープされる', () => {
    render(<HighlightText text="<script>alert('xss')</script>" query="script" />);
    // dangerouslySetInnerHTML を使っていないので HTML インジェクションは起きない
    // テキストとして表示される（エスケープされる）
    expect(document.querySelector('script')).toBeNull();
  });

  // HT-006: 複数箇所マッチの場合、すべての箇所がハイライトされる
  it('HT-006: 複数箇所マッチの場合、すべての箇所がハイライトされる', () => {
    render(<HighlightText text="cat and cat" query="cat" />);
    const marks = document.querySelectorAll('mark');
    expect(marks).toHaveLength(2);
    marks.forEach((mark) => expect(mark.textContent).toBe('cat'));
  });
});
