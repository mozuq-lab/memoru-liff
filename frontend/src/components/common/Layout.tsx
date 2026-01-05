import type { ReactNode } from 'react';

interface LayoutProps {
  children: ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  return (
    <div className="min-h-screen bg-gray-50">
      <main className="container mx-auto px-4 py-6 max-w-md">
        {children}
      </main>
    </div>
  );
};
