'use client';

import { useEffect, useRef, useState, useTransition } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Award,
  ChevronRight,
  CircleCheck,
  CircleX,
  Clock,
  LoaderCircle,
  MapPin,
  Minus,
  Plus,
} from 'lucide-react';

import {
  DropOffFields,
  EMPTY_DROP_OFF,
  fieldClass,
  toDeliveryLocation,
} from '@/components/orders/drop-off-fields';
import { PageContainer, PageHeader } from '@/components/page-header';
import { Button } from '@/components/ui/button';
import type { CreditBalanceResult } from '@/lib/credit-actions';
import { createOrder, loadOrder } from '@/lib/order-actions';
import {
  MAX_CREDIT_AMOUNT,
  MAX_ITEM_DESCRIPTION_LENGTH,
  type OrderView,
  formatRejectionReason,
} from '@/lib/orders';
import type { Supplier } from '@/lib/supplier-service';
import { formatOpeningHours, formatSupplierLocation } from '@/lib/suppliers';
import { cn } from '@/lib/utils';

const DEFAULT_CREDITS = 10;

// Credit Service reserves asynchronously over Kafka, usually within seconds.
const STATUS_POLL_MS = 1500;
const STATUS_POLL_ATTEMPTS = 20;

function FieldLabel({
  htmlFor,
  children,
}: {
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className='mb-2 block text-sm font-bold text-slate-900'
    >
      {children}
    </label>
  );
}

/**
 * A random UUID v4. `crypto.randomUUID()` only exists in secure contexts, so
 * it fails when the app is served over plain http on a non-localhost host.
 */
function newIdempotencyKey() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/**
 * Polls a new order until Credit Service has reserved its credit (`OPEN`) or
 * refused it (`REJECTED`). `stalled` turns true when polling gives up, after
 * a failed read or too many attempts, while the order is still pending.
 */
function useSettledOrder(order: OrderView) {
  const [settled, setSettled] = useState(order);
  const [stalled, setStalled] = useState(false);
  const orderId = order.id;
  const initiallyPending = order.status === 'PENDING_CREDIT';

  useEffect(() => {
    if (!initiallyPending) return;

    let attempts = 0;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      const result = await loadOrder(orderId);
      if (cancelled) return;
      if (!result.ok) {
        setStalled(true);
        return;
      }
      setSettled(result.order);
      if (result.order.status !== 'PENDING_CREDIT') return;
      if (++attempts < STATUS_POLL_ATTEMPTS) {
        timer = setTimeout(poll, STATUS_POLL_MS);
      } else {
        setStalled(true);
      }
    };
    timer = setTimeout(poll, STATUS_POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [orderId, initiallyPending]);

  return { settled, stalled };
}

function OrderConfirmation({
  order,
  onReset,
}: {
  order: OrderView;
  onReset: () => void;
}) {
  const router = useRouter();
  const { settled, stalled } = useSettledOrder(order);
  const storeName = settled.supplier?.name ?? 'the store';

  // Refresh the layout so the side nav shows the reserved balance.
  useEffect(() => {
    if (settled.status !== 'PENDING_CREDIT') router.refresh();
  }, [settled.status, router]);

  const content = {
    STALLED: {
      icon: <Clock className='mx-auto size-12 text-slate-400' />,
      title: 'Still reserving credit',
      body: 'This is taking longer than usual. My Errands shows the latest status.',
    },
    PENDING_CREDIT: {
      icon: (
        <LoaderCircle className='mx-auto size-12 animate-spin text-slate-400' />
      ),
      title: 'Reserving credit…',
      body: `Holding ${settled.credit_amount} cr so couriers can see your errand.`,
    },
    OPEN: {
      icon: <CircleCheck className='mx-auto size-12 text-emerald-600' />,
      title: 'Request posted!',
      body: `Couriers can now see your errand from ${storeName}. ${settled.credit_amount} cr is held until it is done.`,
    },
    REJECTED: {
      icon: <CircleX className='mx-auto size-12 text-red-600' />,
      title: 'Request not posted',
      body: formatRejectionReason(settled.rejection_reason),
    },
  }[
    settled.status === 'PENDING_CREDIT'
      ? stalled
        ? 'STALLED'
        : 'PENDING_CREDIT'
      : settled.status === 'REJECTED'
        ? 'REJECTED'
        : 'OPEN'
  ];

  return (
    <div
      aria-live='polite'
      className='rounded-2xl border bg-white p-6 text-center shadow-sm'
    >
      {content.icon}
      <h2 className='mt-3 text-xl font-bold text-slate-900'>{content.title}</h2>
      <p className='mt-1 text-sm text-slate-500'>{content.body}</p>
      <div className='mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center'>
        <Button
          asChild
          className='bg-courier hover:bg-courier/90 h-11 rounded-xl px-6 font-semibold text-white'
        >
          <Link href='/orders'>View my errands</Link>
        </Button>
        <Button
          variant='outline'
          onClick={onReset}
          className='h-11 rounded-xl px-6 font-semibold'
        >
          Post another
        </Button>
      </div>
    </div>
  );
}

function BalanceHint({ credit }: { credit: CreditBalanceResult }) {
  let text: string;
  if (!credit.ok) text = 'Balance unavailable';
  else if (!credit.balance)
    text = 'Starting credit is added with your first errand';
  else text = `Available: ${credit.balance.available_balance} cr`;

  return (
    <Link
      href='/credits'
      className='text-brand-strong text-xs font-semibold hover:underline'
    >
      {text}
    </Link>
  );
}

type RequestErrandProps = {
  /** Store chosen in the directory, loaded from Supplier Service. */
  initialStore: Supplier | null;
  storeError: string | null;
  credit: CreditBalanceResult;
};

export function RequestErrand({
  initialStore,
  storeError,
  credit,
}: RequestErrandProps) {
  const router = useRouter();
  const [store, setStore] = useState(initialStore);
  const [description, setDescription] = useState('');
  const [dropOff, setDropOff] = useState(EMPTY_DROP_OFF);
  const [order, setOrder] = useState<OrderView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, startSubmitting] = useTransition();
  // One key per errand: resubmitting after a failure cannot post it twice.
  const idempotencyKey = useRef<string | null>(null);

  // Credit Service decides at reservation time; this cap only avoids offers
  // that are sure to be rejected.
  const available =
    credit.ok && credit.balance ? credit.balance.available_balance : null;
  const maxCredits = Math.min(
    MAX_CREDIT_AMOUNT,
    available ?? MAX_CREDIT_AMOUNT,
  );
  const hasCredit = maxCredits >= 1;
  const defaultCredits = Math.max(1, Math.min(DEFAULT_CREDITS, maxCredits));
  const [credits, setCredits] = useState(defaultCredits);
  const delivery = toDeliveryLocation(dropOff);

  const canSubmit =
    store !== null &&
    description.trim().length > 0 &&
    delivery !== null &&
    credits >= 1 &&
    credits <= maxCredits;

  function reset() {
    setStore(null);
    setDescription('');
    setDropOff(EMPTY_DROP_OFF);
    setCredits(defaultCredits);
    setOrder(null);
    setError(null);
    idempotencyKey.current = null;
    router.replace('/request');
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || !store || !delivery) return;
    idempotencyKey.current ??= newIdempotencyKey();
    const key = idempotencyKey.current;

    setError(null);
    startSubmitting(async () => {
      const result = await createOrder(key, {
        pickup_supplier_id: store.id,
        delivery,
        item_description: description.trim(),
        credit_amount: credits,
      });
      if (result.ok) {
        setOrder(result.order);
        return;
      }
      // Other failures keep the key so a retry can't post a duplicate. A 409
      // means an earlier attempt with this key was posted with other details.
      if (result.status === 409) {
        idempotencyKey.current = null;
        setError(
          'An earlier attempt was already posted. Check My Errands before posting again.',
        );
        return;
      }
      setError(result.message);
    });
  }

  return (
    <PageContainer>
      <PageHeader title='Request an Errand' />

      <div className='px-4 pt-4 md:px-0'>
        {order ? (
          <OrderConfirmation order={order} onReset={reset} />
        ) : (
          <form onSubmit={handleSubmit} className='space-y-6'>
            <div className='flex items-center gap-3'>
              <span className='bg-brand rounded-full px-3 py-1 text-xs font-bold text-white'>
                Step 1 of 3
              </span>
              <span className='text-sm font-medium text-slate-600'>
                Errand Details
              </span>
            </div>

            <div>
              <FieldLabel>1. Select Store or Facility</FieldLabel>
              <Link
                href='/request/store'
                className={cn(
                  fieldClass,
                  'flex h-12 items-center justify-between text-left',
                )}
              >
                <span className={cn(!store && 'text-slate-400')}>
                  {store?.name ?? 'Choose a location'}
                </span>
                <ChevronRight
                  className='size-5 shrink-0 text-slate-500'
                  aria-hidden
                />
              </Link>
              {storeError && !store && (
                <p role='alert' className='mt-2 text-sm text-red-600'>
                  {storeError}
                </p>
              )}
            </div>

            <div>
              <FieldLabel htmlFor='description'>2. Item Description</FieldLabel>
              <textarea
                id='description'
                rows={4}
                value={description}
                maxLength={MAX_ITEM_DESCRIPTION_LENGTH}
                onChange={(e) => setDescription(e.target.value)}
                placeholder='e.g. Iced Vanilla Latte (oat milk, less ice) and one chocolate croissant please!'
                className={cn(fieldClass, 'resize-none py-3')}
              />
              <p className='mt-1 text-right text-xs text-slate-400'>
                {description.length}/{MAX_ITEM_DESCRIPTION_LENGTH}
              </p>
            </div>

            <div>
              <FieldLabel>Pickup Location (Auto-filled)</FieldLabel>
              <p
                className={cn(
                  'bg-courier-soft flex min-h-12 items-center gap-2 rounded-xl px-4 py-3 text-sm',
                  store ? 'text-courier font-semibold' : 'text-slate-400',
                )}
              >
                <MapPin className='text-courier size-4 shrink-0' aria-hidden />
                {store ? (
                  <span>
                    {[formatSupplierLocation(store), store.description]
                      .filter(Boolean)
                      .join(', ')}
                    <span className='block text-xs font-medium'>
                      {formatOpeningHours(store)}
                    </span>
                  </span>
                ) : (
                  'Select a store to fill this in'
                )}
              </p>
            </div>

            <fieldset>
              <legend className='mb-2 text-sm font-bold text-slate-900'>
                3. Delivery Destination
              </legend>
              <DropOffFields
                idPrefix='request-drop-off'
                value={dropOff}
                onChange={setDropOff}
                renderLabel={(htmlFor, text) => (
                  <label
                    htmlFor={htmlFor}
                    className='mb-1.5 block text-xs font-semibold text-slate-600'
                  >
                    {text}
                  </label>
                )}
              />
            </fieldset>

            <div className='rounded-2xl border bg-white p-4 shadow-xs'>
              <div className='flex flex-wrap items-center justify-between gap-2'>
                <span className='text-sm font-bold text-slate-900'>
                  Credit Reward Offer
                </span>
                <BalanceHint credit={credit} />
              </div>
              <div className='mt-3 flex flex-wrap items-center gap-4'>
                <div className='border-brand/40 bg-brand-soft flex items-center rounded-xl border'>
                  <button
                    type='button'
                    aria-label='Decrease credits'
                    disabled={!hasCredit || credits <= 1}
                    onClick={() =>
                      setCredits((c) =>
                        Math.max(1, Math.min(c - 1, maxCredits)),
                      )
                    }
                    className='text-brand-strong grid size-11 place-items-center disabled:opacity-40'
                  >
                    <Minus className='size-4' />
                  </button>
                  <span
                    aria-live='polite'
                    className='text-brand-strong flex min-w-16 items-center justify-center gap-1 text-base font-bold'
                  >
                    <Award className='size-4' aria-hidden />
                    {credits} cr
                  </span>
                  <button
                    type='button'
                    aria-label='Increase credits'
                    disabled={!hasCredit || credits >= maxCredits}
                    onClick={() =>
                      setCredits((c) => Math.min(c + 1, maxCredits))
                    }
                    className='text-brand-strong grid size-11 place-items-center disabled:opacity-40'
                  >
                    <Plus className='size-4' />
                  </button>
                </div>
                <p className='flex-1 text-xs text-slate-500'>
                  Held from your balance until the errand is done, and returned
                  if it is cancelled or expires after an hour.
                </p>
              </div>
              {!hasCredit && (
                <p role='alert' className='mt-2 text-xs text-red-600'>
                  You have no available credit to offer.
                </p>
              )}
            </div>

            {error && (
              <p
                role='alert'
                className='rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700'
              >
                {error}
              </p>
            )}

            <Button
              type='submit'
              disabled={!canSubmit || isSubmitting}
              className='bg-brand hover:bg-brand-strong h-12 w-full rounded-xl text-base font-bold text-white'
            >
              {isSubmitting ? 'Posting…' : 'Post Request'}
            </Button>
          </form>
        )}
      </div>
    </PageContainer>
  );
}
