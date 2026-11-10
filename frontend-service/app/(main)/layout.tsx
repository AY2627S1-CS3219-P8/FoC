import { BottomNav, SideNav } from '@/components/app-nav';
import { CreditBalanceProvider } from '@/components/credit-balance-provider';
import { getCreditBalance } from '@/lib/credit-balance';
import { isAdminView, requireCurrentUser } from '@/lib/session';

export default async function MainLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // `proxy.ts` only checks that the cookie exists; this confirms with User
  // Service that the session is still valid before any private page renders.
  // The balance loads alongside; an invalid session redirects before it shows.
  const [, credit, adminView] = await Promise.all([
    requireCurrentUser(),
    getCreditBalance(),
    isAdminView(),
  ]);
  const view = adminView ? 'admin' : 'user';

  return (
    <CreditBalanceProvider initial={credit}>
      <div className='bg-surface min-h-dvh md:pl-64'>
        <SideNav view={view} />
        <main className='pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-10'>
          {children}
        </main>
        <BottomNav view={view} />
      </div>
    </CreditBalanceProvider>
  );
}
