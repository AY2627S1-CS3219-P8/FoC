import { ArrowRight, Check, Clock, MapPin, Star } from 'lucide-react';

import { CreditBadge } from '@/components/credit-badge';
import { Button } from '@/components/ui/button';
import type { Favor } from '@/lib/mock-data';
import { cn } from '@/lib/utils';

const AVATAR_COLOURS = [
  'bg-rose-100 text-rose-700',
  'bg-sky-100 text-sky-700',
  'bg-emerald-100 text-emerald-700',
  'bg-violet-100 text-violet-700',
  'bg-amber-100 text-amber-700',
];

// Orders still OPEN after this long expire (FR13.5.1).
export const EXPIRY_MINUTES = 60;
// Visual hint only, not a lifecycle state
const STALE_MINUTES = EXPIRY_MINUTES / 2;

function initials(name: string) {
  return name
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

function avatarColour(name: string) {
  const hash = [...name].reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
  return AVATAR_COLOURS[hash % AVATAR_COLOURS.length];
}

type FavorCardProps = {
  favor: Favor;
  accepted: boolean;
  onAccept: (id: string) => void;
};

export function FavorCard({ favor, accepted, onAccept }: FavorCardProps) {
  const { requester } = favor;
  const stale = favor.minutesAgo >= STALE_MINUTES;

  return (
    <article className='flex flex-col rounded-2xl border bg-white p-4 shadow-sm'>
      <div className='flex items-start justify-between gap-3'>
        <div className='flex min-w-0 items-center gap-3'>
          <span
            aria-hidden
            className={cn(
              'grid size-11 shrink-0 place-items-center rounded-full text-sm font-bold',
              avatarColour(requester.name),
            )}
          >
            {initials(requester.name)}
          </span>
          <div className='min-w-0'>
            <p className='truncate font-bold text-slate-900'>
              {requester.name}
            </p>
            <p className='flex items-center gap-1 text-xs text-slate-500'>
              <Star
                className='size-3 fill-amber-400 text-amber-400'
                aria-hidden
              />
              {requester.rating.toFixed(1)} ({requester.favors} favors)
            </p>
          </div>
        </div>
        <CreditBadge credits={favor.credits} />
      </div>

      <dl className='mt-4 space-y-2 text-sm'>
        <div className='flex items-start gap-2'>
          <MapPin
            className='text-brand-strong mt-0.5 size-4 shrink-0'
            aria-hidden
          />
          <dt className='font-semibold text-slate-900'>Pickup:</dt>
          <dd className='text-slate-600'>{favor.pickup}</dd>
        </div>
        <div className='flex items-start gap-2'>
          <ArrowRight
            className='text-courier mt-0.5 size-4 shrink-0'
            aria-hidden
          />
          <dt className='font-semibold text-slate-900'>Deliver:</dt>
          <dd className='text-slate-600'>{favor.deliverTo}</dd>
        </div>
      </dl>

      <p className='border-brand-soft bg-brand-tint text-brand-strong mt-4 rounded-lg border px-3 py-2.5 text-sm font-medium'>
        {favor.items}
      </p>

      <div className='mt-auto flex items-center justify-between gap-3 pt-4'>
        <span
          className={cn(
            'inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-semibold',
            stale ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-700',
          )}
        >
          <Clock className='size-3.5' aria-hidden />
          {favor.minutesAgo} mins ago
        </span>
        <Button
          onClick={() => onAccept(favor.id)}
          disabled={accepted}
          className={cn(
            'h-10 rounded-lg px-5 font-semibold',
            accepted
              ? 'bg-emerald-600 text-white disabled:opacity-100'
              : 'bg-courier hover:bg-courier/90 text-white',
          )}
        >
          {accepted ? (
            <>
              <Check aria-hidden /> Accepted
            </>
          ) : (
            'Accept Favor'
          )}
        </Button>
      </div>
    </article>
  );
}
