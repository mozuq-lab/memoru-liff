interface ReviewProgressProps {
  current: number;
  total: number;
}

export const ReviewProgress = ({ current, total }: ReviewProgressProps) => {
  const percentage = Math.round((current / total) * 100);

  return (
    <div className="w-full space-y-1">
      <p className="text-sm text-gray-600 text-center">
        {current} / {total}
      </p>
      <div
        className="w-full bg-gray-200 rounded-full h-2"
        role="progressbar"
        aria-valuenow={current}
        aria-valuemin={1}
        aria-valuemax={total}
      >
        <div
          className="bg-blue-500 rounded-full h-2 transition-all"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};
