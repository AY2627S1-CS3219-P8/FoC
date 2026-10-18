'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Award,
  CirclePlus,
  House,
  type LucideIcon,
  MessageSquare,
  ShoppingBag,
  User,
} from 'lucide-react';

import { CREDIT_BALANCE } from '@/lib/mock-data';
import { cn } from '@/lib/utils';

type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  disabled?: boolean;
};

// Order matches the mobile tab bar; Request sits in the middle.
const NAV_ITEMS: NavItem[] = [
  { label: 'Feed', href: '/home', icon: House },
  { label: 'Orders', href: '/orders', icon: ShoppingBag },
  { label: 'Request', href: '/request', icon: CirclePlus },
  { label: 'Chat', href: '/chat', icon: MessageSquare, disabled: true },
  { label: 'Profile', href: '/profile', icon: User, disabled: true },
];

function useIsActive() {
  const pathname = usePathname();
  return (href: string) => pathname === href || pathname.startsWith(`${href}/`);
}

export function BottomNav() {
  const isActive = useIsActive();

  return (
    <nav
      aria-label='Primary'
      className='fixed inset-x-0 bottom-0 z-40 border-t bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden'
    >
      <ul className='mx-auto grid h-16 max-w-md grid-cols-5'>
        {NAV_ITEMS.map(({ label, href, icon: Icon, disabled }) => {
          const active = isActive(href);
          const content = (
            <>
              <Icon
                className={cn('size-6', active && 'stroke-[2.25]')}
                aria-hidden
              />
              <span className='text-[11px] font-medium'>{label}</span>
            </>
          );
          const base =
            'flex h-full flex-col items-center justify-center gap-1 transition-colors';

          return (
            <li key={href}>
              {disabled ? (
                <span
                  aria-disabled
                  title='Coming soon'
                  className={cn(base, 'text-slate-300')}
                >
                  {content}
                </span>
              ) : (
                <Link
                  href={href}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    base,
                    active
                      ? 'text-brand-strong'
                      : 'text-slate-400 hover:text-slate-600',
                  )}
                >
                  {content}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function SideNav() {
  const isActive = useIsActive();

  return (
    <aside className='fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r bg-white px-4 py-6 md:flex'>
      <Link href='/home' className='flex items-center gap-2 px-2'>
        <span className='bg-brand grid size-9 place-items-center rounded-xl text-sm font-extrabold text-white'>
          FoC
        </span>
        <span className='text-lg leading-tight font-bold text-slate-900'>
          Friend on Campus
        </span>
      </Link>

      <nav aria-label='Primary' className='mt-8'>
        <ul className='space-y-1'>
          {NAV_ITEMS.map(({ label, href, icon: Icon, disabled }) => {
            const active = isActive(href);
            const base =
              'flex h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors';

            return (
              <li key={href}>
                {disabled ? (
                  <span
                    aria-disabled
                    className={cn(base, 'cursor-not-allowed text-slate-300')}
                  >
                    <Icon className='size-5' aria-hidden />
                    {label}
                    <span className='ml-auto rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-400 uppercase'>
                      Soon
                    </span>
                  </span>
                ) : (
                  <Link
                    href={href}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      base,
                      active
                        ? 'bg-brand-tint text-brand-strong'
                        : 'text-slate-600 hover:bg-slate-50',
                    )}
                  >
                    <Icon className='size-5' aria-hidden />
                    {label}
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      </nav>

      <div className='border-brand-soft bg-brand-tint mt-auto rounded-2xl border p-4'>
        <p className='text-xs font-medium text-slate-500'>Credit balance</p>
        <p className='text-brand-strong mt-1 flex items-center gap-1.5 text-2xl font-bold'>
          <Award className='size-5' aria-hidden />
          {CREDIT_BALANCE} cr
        </p>
      </div>
    </aside>
  );
}
