'use client';

import { useMemo, useState, useTransition } from 'react';
import { RefreshCw } from 'lucide-react';

import { type AcceptState, FavorCard } from '@/components/feed/favor-card';
import { PageContainer, PageHeader } from '@/components/page-header';
import { Button } from '@/components/ui/button';
import { acceptOrder, loadOpenOrders } from '@/lib/order-actions';
import type { OrderPageResult, OrderView } from '@/lib/orders';
import { cn } from '@/lib/utils';

type SortKey = 'newest' | 'reward';

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'newest', label: 'Newest First' },
  { key: 'reward', label: 'Highest Reward' },
];

const IDLE: AcceptState = { kind: 'idle' };

/**
 * Open errands from Order Service, which already excludes the caller's own
 * orders and anything that is no longer OPEN (FR12.1.2, FR13.5.1).
 */
export function FavorFeed({ initial }: { initial: OrderPageResult }) {
  const [orders, setOrders] = useState<OrderView[]>(
    initial.ok ? initial.items : [],
  );
  const [total, setTotal] = useState(initial.ok ? initial.total : 0);
  const [error, setError] = useState(initial.ok ? null : initial.message);
  const [sort, setSort] = useState<SortKey>('newest');
  const [accepts, setAccepts] = useState<Record<string, AcceptState>>({});
  const [now, setNow] = useState(initial.ok ? initial.loadedAt : 0);
  const [isLoading, startLoading] = useTransition();

  // Order Service returns newest first, so that order needs no re-sort.
  const sorted = useMemo(
    () =>
      sort === 'reward'
        ? [...orders].sort((a, b) => b.credit_amount - a.credit_amount)
        : orders,
    [orders, sort],
  );

  function load(offset: number) {
    startLoading(async () => {
      const result = await loadOpenOrders(offset);
      if (!result.ok) {
        setError(result.message);
        return;
      }
      setError(null);
      setTotal(result.total);
      setNow(result.loadedAt);
      if (offset === 0) {
        setOrders(result.items);
        setAccepts({});
      } else {
        // A page can shift while orders are accepted, so skip repeats.
        setOrders((prev) => {
          const seen = new Set(prev.map((order) => order.id));
          return [...prev, ...result.items.filter((o) => !seen.has(o.id))];
        });
      }
    });
  }

  async function accept(id: string) {
    setAccepts((prev) => ({ ...prev, [id]: { kind: 'pending' } }));
    const result = await acceptOrder(id);
    setAccepts((prev) => ({
      ...prev,
      [id]: result.ok
        ? { kind: 'accepted' }
        : {
            kind: 'failed',
            message:
              result.status === 409
                ? 'Another courier accepted this errand first.'
                : result.message,
          },
    }));
  }

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
            aria-label='Refresh feed'
            onClick={() => load(0)}
            disabled={isLoading}
            className='bg-brand-soft text-brand-strong hover:bg-brand/30 grid size-10 place-items-center rounded-full transition-colors disabled:opacity-60'
          >
            <RefreshCw className={cn('size-5', isLoading && 'animate-spin')} />
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
              {key === 'newest' && ` (${total})`}
            </button>
          ))}
        </div>
      </PageHeader>

      {error && (
        <p
          role='alert'
          className='mx-4 mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 md:mx-0'
        >
          {error}
        </p>
      )}

      <div className='grid gap-4 px-4 pt-4 md:grid-cols-2 md:px-0 xl:grid-cols-3'>
        {sorted.map((order) => (
          <FavorCard
            key={order.id}
            order={order}
            state={accepts[order.id] ?? IDLE}
            now={now}
            onAccept={accept}
          />
        ))}
        {!error && orders.length === 0 && (
          <p className='col-span-full py-12 text-center text-sm text-slate-500'>
            No open errands right now. Check back soon!
          </p>
        )}
      </div>

      {orders.length < total && (
        <div className='flex justify-center px-4 pt-6 md:px-0'>
          <Button
            variant='outline'
            onClick={() => load(orders.length)}
            disabled={isLoading}
            className='h-11 rounded-xl px-6 font-semibold'
          >
            {isLoading ? 'Loading…' : 'Load more'}
          </Button>
        </div>
      )}
    </PageContainer>
  );
}
