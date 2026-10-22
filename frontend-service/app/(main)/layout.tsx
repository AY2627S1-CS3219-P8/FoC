import { BottomNav, SideNav } from '@/components/app-nav';
import { requireCurrentUser } from '@/lib/session';

export default async function MainLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // `proxy.ts` only checks that the cookie exists; this confirms with User
  // Service that the session is still valid before any private page renders.
  await requireCurrentUser();

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
