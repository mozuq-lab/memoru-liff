interface LoadingProps {
  message?: string;
}

export const Loading = ({ message = '読み込み中...' }: LoadingProps) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[200px]">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
      <p className="mt-4 text-gray-600">{message}</p>
    </div>
  );
};
