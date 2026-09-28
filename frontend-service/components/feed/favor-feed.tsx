'use client';

import { useMemo, useState } from 'react';
import { Bell } from 'lucide-react';

import { FavorCard } from '@/components/feed/favor-card';
import { PageContainer, PageHeader } from '@/components/page-header';
import { favors } from '@/lib/mock-data';
import { cn } from '@/lib/utils';

type SortKey = 'nearby' | 'reward' | 'newest';

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'nearby', label: `Nearby (${favors.length})` },
  { key: 'reward', label: 'Highest Reward' },
  { key: 'newest', label: 'Newest First' },
];

export function FavorFeed() {
  const [sort, setSort] = useState<SortKey>('nearby');
  const [accepted, setAccepted] = useState<Set<string>>(new Set());

  const sorted = useMemo(() => {
    const list = [...favors];
    if (sort === 'nearby')
      list.sort((a, b) => a.distanceMeters - b.distanceMeters);
    if (sort === 'reward') list.sort((a, b) => b.credits - a.credits);
    if (sort === 'newest') list.sort((a, b) => a.minutesAgo - b.minutesAgo);
    return list;
  }, [sort]);

  return (
    <PageContainer>
      <PageHeader
        title={
          <>
            <span className='text-brand'>FoC Feed</span>
            <span className='border-brand/50 bg-brand-soft text-brand-strong rounded-md border px-2 py-0.5 text-[10px] font-bold tracking-wide uppercase md:text-xs'>
              Courier view
            </span>
          </>
        }
        actions={
          <button
            type='button'
            aria-label='Notifications'
            className='bg-brand-soft text-brand-strong hover:bg-brand/30 grid size-10 place-items-center rounded-full transition-colors'
          >
            <Bell className='size-5' />
          </button>
        }
      >
        <div
          role='tablist'
          aria-label='Sort favors'
          className='-mx-4 flex gap-2 overflow-x-auto px-4 [scrollbar-width:none] md:mx-0 md:px-0'
        >
          {SORTS.map(({ key, label }) => (
            <button
              key={key}
              type='button'
              role='tab'
              aria-selected={sort === key}
              onClick={() => setSort(key)}
              className={cn(
                'h-9 shrink-0 rounded-full border px-4 text-sm font-semibold transition-colors',
                sort === key
                  ? 'border-courier bg-courier text-white'
                  : 'bg-white text-slate-600 hover:bg-slate-50',
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </PageHeader>

      <div className='grid gap-4 px-4 pt-4 md:grid-cols-2 md:px-0 xl:grid-cols-3'>
        {sorted.map((favor) => (
          <FavorCard
            key={favor.id}
            favor={favor}
            accepted={accepted.has(favor.id)}
            onAccept={(id) => setAccepted((prev) => new Set(prev).add(id))}
          />
        ))}
      </div>
    </PageContainer>
  );
}
