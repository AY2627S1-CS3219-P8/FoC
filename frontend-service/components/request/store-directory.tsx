'use client';

import { useState } from 'react';
import {
  Check,
  Coffee,
  type LucideIcon,
  MapPin,
  Printer,
  Search,
  ShoppingBag,
  UtensilsCrossed,
} from 'lucide-react';

import { type Store, type StoreType, stores } from '@/lib/mock-data';
import { cn } from '@/lib/utils';

const TYPE_META: Record<StoreType, { label: string; icon: LucideIcon }> = {
  Food: { label: 'Food', icon: UtensilsCrossed },
  'Food/Coffee': { label: 'Café', icon: Coffee },
  Shopping: { label: 'Shop', icon: ShoppingBag },
  Printing: { label: 'Print Shop', icon: Printer },
};

export function formatStoreLocation(store: Store) {
  return `${store.building} L${store.floor}`;
}

type StoreDirectoryProps = {
  selectedId?: string;
  onSelect: (store: Store) => void;
  className?: string;
};

export function StoreDirectory({
  selectedId,
  onSelect,
  className,
}: StoreDirectoryProps) {
  const [query, setQuery] = useState('');
  const q = query.trim().toLowerCase();
  const results = q
    ? stores.filter((store) =>
        [
          store.name,
          store.building,
          store.locationDescription,
          TYPE_META[store.type].label,
        ].some((field) => field.toLowerCase().includes(q)),
      )
    : stores;

  return (
    <div className={cn('flex min-h-0 flex-col', className)}>
      <label className='focus-within:ring-brand/40 flex h-11 items-center gap-2 rounded-xl border bg-white px-3 focus-within:ring-2'>
        <Search className='size-4 shrink-0 text-slate-500' aria-hidden />
        <span className='sr-only'>Search stores</span>
        <input
          type='search'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='Search store, food court, print shop...'
          className='w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400'
        />
      </label>

      <ul className='mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto pb-1'>
        {results.map((store) => {
          const { label, icon: Icon } = TYPE_META[store.type];
          const selected = store.id === selectedId;
          return (
            <li key={store.id}>
              <button
                type='button'
                onClick={() => onSelect(store)}
                aria-pressed={selected}
                className={cn(
                  'flex w-full items-center gap-3 rounded-2xl border bg-white p-3 text-left shadow-sm transition-colors hover:border-slate-300',
                  selected && 'border-courier ring-courier/20 ring-2',
                )}
              >
                <span className='bg-courier grid size-11 shrink-0 place-items-center rounded-xl text-white'>
                  <Icon className='size-5' aria-hidden />
                </span>
                <span className='min-w-0 flex-1'>
                  <span className='flex items-start justify-between gap-2'>
                    <span className='truncate font-bold text-slate-900'>
                      {store.name}
                    </span>
                    <span className='bg-brand-soft text-brand-strong shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold'>
                      {label}
                    </span>
                  </span>
                  <span className='mt-1 flex items-center gap-1 text-xs text-slate-500'>
                    <MapPin className='size-3.5 shrink-0' aria-hidden />
                    <span className='truncate'>{formatStoreLocation(store)}</span>
                  </span>
                </span>
                {selected && (
                  <Check className='text-courier size-5 shrink-0' aria-hidden />
                )}
              </button>
            </li>
          );
        })}
        {results.length === 0 && (
          <li className='py-10 text-center text-sm text-slate-500'>
            No stores match “{query}”.
          </li>
        )}
      </ul>
    </div>
  );
}
