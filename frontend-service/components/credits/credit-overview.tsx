'use client';

import { useState, useTransition } from 'react';
import { Award } from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/page-header';
import { Button } from '@/components/ui/button';
import {
  type CreditBalanceResult,
  type CreditTransactionPageResult,
  loadTransactions,
} from '@/lib/credit-actions';
import type { CreditTransaction } from '@/lib/credit-service';
import { formatDateTime } from '@/lib/orders';
import { cn } from '@/lib/utils';

/** Credit Service reason codes for settlements, from `event_handlers.py`. */
const SETTLEMENT_LABELS: Record<string, string> = {
  ORDER_COMPLETED_REQUESTER_DEBIT: 'Paid to your courier',
  ORDER_COMPLETED_COURIER_CREDIT: 'Earned from an errand',
  ORDER_CANCELLED_AFTER_PICKUP_REQUESTER_DEBIT:
    'Paid to your courier (cancelled after pickup)',
  ORDER_CANCELLED_AFTER_PICKUP_COURIER_CREDIT:
    'Earned from an errand (cancelled after pickup)',
};

function describe({ transaction_type, outcome, reason }: CreditTransaction) {
  switch (transaction_type) {
    case 'INITIAL_ALLOCATION':
      return 'Starting credit';
    case 'RESERVATION':
      if (outcome === 'SUCCEEDED') return 'Held for your errand';
      return reason === 'INSUFFICIENT_CREDIT'
        ? 'Errand refused: not enough credit'
        : 'Errand refused: credit could not be reserved';
    case 'TRANSFER':
      return SETTLEMENT_LABELS[reason] ?? 'Errand settlement';
    case 'RELEASE':
      return reason === 'ORDER_EXPIRED'
        ? 'Returned: errand expired'
        : 'Returned: errand cancelled';
    case 'ADMIN_ADJUSTMENT':
      return `Adjusted by an administrator: ${reason}`;
  }
}

/**
 * Holds and releases move credit between available and reserved without
 * changing the total, so show those as movements rather than gains or losses.
 */
function formatChange({ available_delta, reserved_delta }: CreditTransaction) {
  const net = available_delta + reserved_delta;
  if (net > 0) return { text: `+${net} cr`, className: 'text-emerald-700' };
  if (net < 0) return { text: `${net} cr`, className: 'text-red-600' };
  if (reserved_delta > 0)
    return { text: `${reserved_delta} cr held`, className: 'text-slate-500' };
  if (reserved_delta < 0)
    return {
      text: `${-reserved_delta} cr returned`,
      className: 'text-slate-500',
    };
  return { text: 'No change', className: 'text-slate-400' };
}

function BalanceTile({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: number;
  emphasis?: boolean;
}) {
  return (
    <div
      className={cn(
        'rounded-2xl border p-4',
        emphasis ? 'border-brand-soft bg-brand-tint' : 'bg-white',
      )}
    >
      <p className='text-xs font-medium text-slate-500'>{label}</p>
      <p
        className={cn(
          'mt-1 flex items-center gap-1.5 text-2xl font-bold',
          emphasis ? 'text-brand-strong' : 'text-slate-900',
        )}
      >
        {emphasis && <Award className='size-5' aria-hidden />}
        {value} cr
      </p>
    </div>
  );
}

type CreditOverviewProps = {
  credit: CreditBalanceResult;
  initialTransactions: CreditTransactionPageResult;
};

export function CreditOverview({
  credit,
  initialTransactions,
}: CreditOverviewProps) {
  const [transactions, setTransactions] = useState<CreditTransaction[]>(
    initialTransactions.ok ? initialTransactions.page.items : [],
  );
  const [total, setTotal] = useState(
    initialTransactions.ok ? initialTransactions.page.total : 0,
  );
  const [error, setError] = useState(
    initialTransactions.ok ? null : initialTransactions.message,
  );
  const [isLoading, startLoading] = useTransition();

  function loadMore() {
    startLoading(async () => {
      const result = await loadTransactions(transactions.length);
      if (!result.ok) {
        setError(result.message);
        return;
      }
      setError(null);
      setTotal(result.page.total);
      setTransactions((prev) => [...prev, ...result.page.items]);
    });
  }

  return (
    <PageContainer>
      <PageHeader title='Credits' />

      <div className='space-y-6 px-4 pt-4 md:px-0'>
        {!credit.ok ? (
          <p
            role='alert'
            className='rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700'
          >
            {credit.message}
          </p>
        ) : credit.balance ? (
          <div className='grid gap-3 sm:grid-cols-3'>
            <BalanceTile
              label='Available'
              value={credit.balance.available_balance}
              emphasis
            />
            <BalanceTile
              label='Held for open errands'
              value={credit.balance.reserved_balance}
            />
            <BalanceTile label='Total' value={credit.balance.total_balance} />
          </div>
        ) : (
          <p className='rounded-2xl border bg-white p-4 text-sm text-slate-600'>
            You don&apos;t have a credit account yet. Your starting credit is
            added when you post or deliver your first errand.
          </p>
        )}

        <section>
          <h2 className='text-lg font-bold text-slate-900'>History</h2>
          {error && (
            <p role='alert' className='mt-2 text-sm text-red-600'>
              {error}
            </p>
          )}
          <ul className='mt-3 divide-y rounded-2xl border bg-white'>
            {transactions.map((transaction) => {
              const change = formatChange(transaction);
              return (
                <li
                  key={transaction.id}
                  className='flex items-center justify-between gap-3 px-4 py-3'
                >
                  <div className='min-w-0'>
                    <p className='text-sm font-semibold break-words text-slate-900'>
                      {describe(transaction)}
                    </p>
                    <p className='text-xs text-slate-400'>
                      {formatDateTime(transaction.created_at)}
                    </p>
                  </div>
                  <span
                    className={cn(
                      'shrink-0 text-sm font-bold whitespace-nowrap',
                      change.className,
                    )}
                  >
                    {change.text}
                  </span>
                </li>
              );
            })}
            {!error && transactions.length === 0 && (
              <li className='px-4 py-10 text-center text-sm text-slate-500'>
                No credit activity yet.
              </li>
            )}
          </ul>
          {transactions.length < total && (
            <div className='flex justify-center pt-4'>
              <Button
                variant='outline'
                onClick={loadMore}
                disabled={isLoading}
                className='h-11 rounded-xl px-6 font-semibold'
              >
                {isLoading ? 'Loading…' : 'Load more'}
              </Button>
            </div>
          )}
        </section>
      </div>
    </PageContainer>
  );
}
