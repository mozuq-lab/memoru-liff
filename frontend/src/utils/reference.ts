/**
 * 【機能概要】: 参考情報関連のユーティリティ関数
 * 【実装方針】: 共通関数を集約して重複を排除
 */
import type { ReferenceType } from '@/types/card';

/**
 * 【機能概要】: 参考情報のタイプに応じたアイコン絵文字を返す
 */
export const getTypeIcon = (type: ReferenceType): string => {
  switch (type) {
    case 'url':
      return '\u{1F517}';
    case 'book':
      return '\u{1F4D6}';
    case 'note':
      return '\u{1F4DD}';
  }
};
