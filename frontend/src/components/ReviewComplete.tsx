import { Link } from 'react-router-dom';
import type { SessionCardResult } from '@/types';

interface ReviewCompleteProps {
  reviewedCount: number;
  results?: SessionCardResult[];
}

export const ReviewComplete = ({ reviewedCount }: ReviewCompleteProps) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 text-center">
      <h2 className="text-2xl font-bold text-gray-800 mb-4">
        復習完了!
      </h2>
      <p className="text-lg text-gray-600 mb-8">
        {reviewedCount}枚のカードを復習しました
      </p>
      <Link
        to="/"
        className="inline-block py-3 px-8 bg-blue-600 text-white rounded-lg font-medium min-h-[44px] hover:bg-blue-700 active:bg-blue-800 transition-colors"
      >
        ホームに戻る
      </Link>
    </div>
  );
};
