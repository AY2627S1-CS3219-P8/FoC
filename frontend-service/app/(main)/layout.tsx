import { BottomNav, SideNav } from '@/components/app-nav';

export default function MainLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className='bg-surface min-h-dvh md:pl-64'>
      <SideNav />
      <main className='pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-10'>
        {children}
      </main>
      <BottomNav />
    </div>
  );
}
