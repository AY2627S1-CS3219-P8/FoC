import { BottomNav, SideNav } from '@/components/app-nav';
import { getCreditBalance } from '@/lib/credit-balance';
import { requireCurrentUser } from '@/lib/session';

export default async function MainLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // `proxy.ts` only checks that the cookie exists; this confirms with User
  // Service that the session is still valid before any private page renders.
  // The balance loads alongside; an invalid session redirects before it shows.
  const [, credit] = await Promise.all([
    requireCurrentUser(),
    getCreditBalance(),
  ]);

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
