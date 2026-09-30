'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowRight,
  Award,
  ChevronRight,
  CircleCheck,
  Map as MapIcon,
  MapPin,
  Minus,
  Plus,
} from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/page-header';
import { formatStoreLocation } from '@/components/request/store-directory';
import { Button } from '@/components/ui/button';
import { CREDIT_BALANCE, type Store, stores } from '@/lib/mock-data';
import { cn } from '@/lib/utils';

const ETA_OPTIONS = [
  { value: 'asap', label: 'Asap (30m)' },
  { value: '1h', label: 'Within 1h' },
  { value: '2h', label: 'Within 2h' },
] as const;

type Eta = (typeof ETA_OPTIONS)[number]['value'];

const DEFAULT_CREDITS = 10;

const fieldClass =
  'w-full rounded-xl border bg-white px-4 text-sm text-slate-900 shadow-xs outline-none transition-shadow placeholder:text-slate-400 focus:border-courier focus:ring-2 focus:ring-courier/20';

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

export function RequestErrand() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [store, setStore] = useState<Store | null>(null);
  const [description, setDescription] = useState('');
  const [destination, setDestination] = useState('');
  const [credits, setCredits] = useState(DEFAULT_CREDITS);
  const [eta, setEta] = useState<Eta>('asap');
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    const storeId = searchParams.get('store');
    if (!storeId) return;
    const selected = stores.find((s) => s.id === storeId);
    if (selected) setStore(selected);
    router.replace('/request');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const canSubmit =
    store !== null &&
    description.trim().length > 0 &&
    destination.trim().length > 0;

  function reset() {
    setStore(null);
    setDescription('');
    setDestination('');
    setCredits(DEFAULT_CREDITS);
    setEta('asap');
    setSubmitted(false);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    // TODO: POST to order-service once it exposes a create-order endpoint.
    setSubmitted(true);
  }

  return (
    <PageContainer>
      <PageHeader title='Request an Errand' />

      <div className='px-4 pt-4 md:px-0'>
        {submitted && store ? (
          <div className='rounded-2xl border bg-white p-6 text-center shadow-sm'>
            <CircleCheck
              className='mx-auto size-12 text-emerald-600'
              aria-hidden
            />
            <h2 className='mt-3 text-xl font-bold text-slate-900'>
              Request posted!
            </h2>
            <p className='mt-1 text-sm text-slate-500'>
              Couriers nearby can now see your errand from {store.name}.
            </p>
            <div className='mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center'>
              <Button
                asChild
                className='bg-courier hover:bg-courier/90 h-11 rounded-xl px-6 font-semibold text-white'
              >
                <Link href='/orders'>View my errands</Link>
              </Button>
              <Button
                variant='outline'
                onClick={reset}
                className='h-11 rounded-xl px-6 font-semibold'
              >
                Post another
              </Button>
            </div>
          </div>
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
            </div>

            <div>
              <FieldLabel htmlFor='description'>2. Item Description</FieldLabel>
              <textarea
                id='description'
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder='e.g. Iced Vanilla Latte (oat milk, less ice) and one chocolate croissant please!'
                className={cn(fieldClass, 'resize-none py-3')}
              />
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
                {store
                  ? `${formatStoreLocation(store)}, ${store.locationDescription}`
                  : 'Select a store to fill this in'}
              </p>
            </div>

            <div>
              <FieldLabel htmlFor='destination'>
                3. Delivery Destination
              </FieldLabel>
              <div className='relative'>
                <ArrowRight
                  className='text-courier pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2'
                  aria-hidden
                />
                <input
                  id='destination'
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  placeholder='e.g. PGP Foyer Block 12, Lounge Area'
                  className={cn(fieldClass, 'h-12 pr-11 pl-10')}
                />
                <MapIcon
                  className='pointer-events-none absolute top-1/2 right-4 size-4 -translate-y-1/2 text-slate-500'
                  aria-hidden
                />
              </div>
            </div>

            <div className='rounded-2xl border bg-white p-4 shadow-xs'>
              <div className='flex items-center justify-between'>
                <span className='text-sm font-bold text-slate-900'>
                  Credit Reward Offer
                </span>
                <span className='text-brand-strong text-xs font-semibold'>
                  Balance: {CREDIT_BALANCE} cr
                </span>
              </div>
              <div className='mt-3 flex flex-wrap items-center gap-4'>
                <div className='border-brand/40 bg-brand-soft flex items-center rounded-xl border'>
                  <button
                    type='button'
                    aria-label='Decrease credits'
                    disabled={credits <= 1}
                    onClick={() => setCredits((c) => c - 1)}
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
                    disabled={credits >= CREDIT_BALANCE}
                    onClick={() => setCredits((c) => c + 1)}
                    className='text-brand-strong grid size-11 place-items-center disabled:opacity-40'
                  >
                    <Plus className='size-4' />
                  </button>
                </div>
                <p className='flex-1 text-xs text-slate-500'>
                  Higher credits attract couriers faster!
                </p>
              </div>
            </div>

            <fieldset>
              <legend className='mb-2 text-sm font-bold text-slate-900'>
                Estimated Delivery Time
              </legend>
              <div className='grid grid-cols-3 gap-2'>
                {ETA_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className={cn(
                      'has-focus-visible:ring-brand/40 flex h-11 cursor-pointer items-center justify-center rounded-xl border text-sm font-semibold transition-colors has-focus-visible:ring-2',
                      eta === option.value
                        ? 'border-brand bg-brand text-white'
                        : 'bg-white text-slate-700 hover:bg-slate-50',
                    )}
                  >
                    <input
                      type='radio'
                      name='eta'
                      value={option.value}
                      checked={eta === option.value}
                      onChange={() => setEta(option.value)}
                      className='sr-only'
                    />
                    {option.label}
                  </label>
                ))}
              </div>
            </fieldset>

            <Button
              type='submit'
              disabled={!canSubmit}
              className='bg-brand hover:bg-brand-strong h-12 w-full rounded-xl text-base font-bold text-white'
            >
              Post Request
            </Button>
          </form>
        )}
      </div>
    </PageContainer>
  );
}
