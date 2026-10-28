'use client';

import { useRef, useState, useTransition } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ChevronRight, MapPin } from 'lucide-react';

import { ErrorBanner } from '@/components/list-controls';
import {
  DropOffFields,
  dropOffFieldIds,
} from '@/components/orders/drop-off-fields';
import { PageContainer, PageHeader } from '@/components/page-header';
import { CreditOffer } from '@/components/request/credit-offer';
import { OrderConfirmation } from '@/components/request/order-confirmation';
import { Button } from '@/components/ui/button';
import { fieldClass } from '@/components/ui/field';
import type { CreditBalanceResult } from '@/lib/credit-actions';
import { offerLimits } from '@/lib/credits';
import { EMPTY_DROP_OFF, toDeliveryLocation } from '@/lib/drop-off';
import { newIdempotencyKey } from '@/lib/idempotency';
import { createOrder } from '@/lib/order-actions';
import {
  DUPLICATE_SUBMISSION,
  MAX_ITEM_DESCRIPTION_LENGTH,
  type OrderView,
} from '@/lib/orders';
import type { Supplier } from '@/lib/supplier-service';
import { formatOpeningHours, formatSupplierLocation } from '@/lib/suppliers';
import { cn } from '@/lib/utils';

function RequiredTag() {
  return (
    <span className='ml-2 rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-600'>
      Required
    </span>
  );
}

function FieldLabel({
  htmlFor,
  missing = false,
  children,
}: {
  htmlFor?: string;
  missing?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className='mb-2 block text-sm font-bold text-slate-900'
    >
      {children}
      {missing && <RequiredTag />}
    </label>
  );
}

const STORE_FIELD_ID = 'request-store';
const DESCRIPTION_FIELD_ID = 'description';
const DROP_OFF_PREFIX = 'request-drop-off';
const DROP_OFF_IDS = dropOffFieldIds(DROP_OFF_PREFIX);

/** A field that still blocks posting, and the control to focus for it. */
type MissingField = { label: string; fieldId?: string };

/** Lists what still blocks posting, so the disabled button can say why. */
function MissingFields({ fields }: { fields: MissingField[] }) {
  return (
    <p aria-live='polite' className='text-center text-sm text-slate-500'>
      To post, fill in:{' '}
      {fields.map(({ label, fieldId }, i) => (
        <span key={label}>
          {i > 0 && ', '}
          {fieldId ? (
            <button
              type='button'
              onClick={() => document.getElementById(fieldId)?.focus()}
              className='font-semibold text-red-600 underline-offset-2 hover:underline'
            >
              {label}
            </button>
          ) : (
            <span className='font-semibold text-red-600'>{label}</span>
          )}
        </span>
      ))}
    </p>
  );
}

type RequestErrandProps = {
  /** Store chosen in the directory, loaded from Supplier Service. */
  initialStore: Supplier | null;
  storeError: string | null;
  credit: CreditBalanceResult;
  /** What a user without a credit account will have once their first errand opens it. */
  initialAllocation: number;
};

export function RequestErrand({
  initialStore,
  storeError,
  credit,
  initialAllocation,
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

  const limits = offerLimits(credit, initialAllocation);
  const [credits, setCredits] = useState(limits.initial);
  const delivery = toDeliveryLocation(dropOff);

  const missing = {
    store: store === null,
    description: !description.trim(),
    point: !dropOff.pointId,
    credit: !limits.hasCredit,
  };
  const missingFields: MissingField[] = [
    missing.store && { label: 'Store', fieldId: STORE_FIELD_ID },
    missing.description && {
      label: 'Item description',
      fieldId: DESCRIPTION_FIELD_ID,
    },
    missing.point && { label: 'Drop-off point', fieldId: DROP_OFF_IDS.point },
    missing.credit && { label: 'Available credit' },
  ].filter((field): field is MissingField => Boolean(field));

  const canSubmit =
    missingFields.length === 0 && credits >= 1 && credits <= limits.max;

  function reset() {
    setStore(null);
    setDescription('');
    setDropOff(EMPTY_DROP_OFF);
    setCredits(limits.initial);
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
      // Other failures keep the key so a retry can't post a duplicate. This
      // one means an earlier attempt with the key was posted with other
      // details, so the next attempt needs a new key.
      if (result.code === DUPLICATE_SUBMISSION) idempotencyKey.current = null;
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
              {/* The store control is a link, which a label can't point to. */}
              <FieldLabel missing={missing.store}>
                1. Select Store or Facility
              </FieldLabel>
              <Link
                id={STORE_FIELD_ID}
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
              <FieldLabel
                htmlFor={DESCRIPTION_FIELD_ID}
                missing={missing.description}
              >
                2. Item Description
              </FieldLabel>
              <textarea
                id={DESCRIPTION_FIELD_ID}
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
                    {[
                      formatSupplierLocation(store) || store.area,
                      store.description,
                    ]
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
                idPrefix={DROP_OFF_PREFIX}
                value={dropOff}
                onChange={setDropOff}
                renderLabel={(htmlFor, text, fieldMissing) => (
                  <label
                    htmlFor={htmlFor}
                    className='mb-1.5 block text-xs font-semibold text-slate-600'
                  >
                    {text}
                    {fieldMissing && <RequiredTag />}
                  </label>
                )}
              />
            </fieldset>

            <CreditOffer
              value={credits}
              onChange={setCredits}
              max={limits.max}
              credit={credit}
              initialAllocation={initialAllocation}
            />

            {error && <ErrorBanner>{error}</ErrorBanner>}

            <Button
              type='submit'
              disabled={!canSubmit || isSubmitting}
              className='bg-brand hover:bg-brand-strong h-12 w-full rounded-xl text-base font-bold text-white'
            >
              {isSubmitting ? 'Posting…' : 'Post Request'}
            </Button>
            {missingFields.length > 0 && (
              <MissingFields fields={missingFields} />
            )}
          </form>
        )}
      </div>
    </PageContainer>
  );
}
