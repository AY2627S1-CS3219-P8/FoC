import { BottomNav, SideNav } from '@/components/app-nav';
import { getCreditBalance } from '@/lib/credit-balance';

export default async function MainLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const credit = await getCreditBalance();

  return (
    <div className='bg-surface min-h-dvh md:pl-64'>
      <SideNav credit={credit} />
      <main className='pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-10'>
        {children}
      </main>
      <BottomNav />
    </div>
  );
}
