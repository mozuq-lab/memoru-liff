/**
 * 【機能概要】: 再確認モード中であることを示すピル型バッジコンポーネント
 * 【設計方針】: props を持たないプレゼンテーションコンポーネントとして設計し、
 *              再確認モードのヘッダーに配置して現在のモードをユーザーに伝える
 * 【スタイリング】: bg-blue-100 / text-blue-700 / rounded-full（ピル型）
 * 🔵 信頼性レベル: reconfirm-ui-requirements.md セクション2.2 より
 */
export const ReconfirmBadge = () => {
  return (
    <span className="inline-flex items-center bg-blue-100 text-blue-700 rounded-full px-2 py-0.5 text-xs font-medium">
      再確認
    </span>
  );
};
