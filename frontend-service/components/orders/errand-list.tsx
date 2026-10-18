'use client';

import { useState } from 'react';
import { Store } from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/page-header';
import {
  type Errand,
  type ErrandRole,
  type ErrandStatus,
  errands,
} from '@/lib/mock-data';
import { cn } from '@/lib/utils';

const STATUS_STYLES: Record<
  ErrandStatus,
  { label: string; className: string }
> = {
  open: { label: 'Open', className: 'bg-amber-50 text-amber-700' },
  accepted: {
    label: 'Accepted',
    className: 'bg-courier-soft text-courier',
  },
  picked_up: { label: 'Picked Up', className: 'bg-sky-50 text-sky-700' },
  completed: {
    label: 'Completed',
    className: 'bg-emerald-50 text-emerald-700',
  },
  cancelled: { label: 'Cancelled', className: 'bg-red-50 text-red-600' },
  expired: { label: 'Expired', className: 'bg-slate-100 text-slate-500' },
};

const ROLE_TABS: { role: ErrandRole; label: string }[] = [
  { role: 'requester', label: 'As Requester' },
  { role: 'courier', label: 'As Courier' },
];

function ErrandCard({ errand }: { errand: Errand }) {
  const status = STATUS_STYLES[errand.status];

  return (
    <article className='rounded-2xl border bg-white p-4 shadow-sm'>
      <div className='flex items-center justify-between gap-3 border-b pb-3'>
        <p className='text-xs font-semibold tracking-wide text-slate-400 uppercase'>
          <span
            className={
              errand.role === 'requester' ? 'text-brand-strong' : 'text-courier'
            }
          >
            {errand.role}
          </span>{' '}
          · #{errand.id}
        </p>
        <span
          className={cn(
            'rounded-full px-2.5 py-1 text-xs font-semibold',
            status.className,
          )}
        >
          {status.label}
        </span>
      </div>
      <h2 className='mt-3 font-bold text-slate-900'>{errand.title}</h2>
      <p className='mt-1 flex items-center gap-1.5 text-sm text-slate-500'>
        <Store className='size-4 shrink-0' aria-hidden />
        {errand.store}
      </p>
      <div className='mt-3 flex items-center justify-between'>
        <span className='text-xs text-slate-400'>{errand.date}</span>
        <span className='text-brand-strong font-bold'>{errand.credits} cr</span>
      </div>
    </article>
  );
}

export function ErrandList() {
  const [role, setRole] = useState<ErrandRole>('requester');
  const visible = errands.filter((errand) => errand.role === role);

  return (
    <PageContainer>
      <PageHeader title='My Campus Errands'>
        <div
          role='tablist'
          aria-label='Errand role'
          className='bg-brand-soft grid grid-cols-2 gap-1 rounded-xl p-1 md:max-w-sm'
        >
          {ROLE_TABS.map((tab) => {
            const count = errands.filter((e) => e.role === tab.role).length;
            const active = role === tab.role;
            return (
              <button
                key={tab.role}
                type='button'
                role='tab'
                aria-selected={active}
                onClick={() => setRole(tab.role)}
                className={cn(
                  'h-10 rounded-lg text-sm font-semibold transition-colors',
                  active
                    ? 'bg-brand text-white shadow-sm'
                    : 'text-brand-strong hover:bg-brand/20',
                )}
              >
                {tab.label} ({count})
              </button>
            );
          })}
        </div>
      </PageHeader>

      <div className='grid gap-4 px-4 pt-4 md:grid-cols-2 md:px-0 xl:grid-cols-3'>
        {visible.map((errand) => (
          <ErrandCard key={errand.id} errand={errand} />
        ))}
        {visible.length === 0 && (
          <p className='col-span-full py-12 text-center text-sm text-slate-500'>
            No errands yet.
          </p>
        )}
      </div>
    </PageContainer>
  );
}
