'use client';

import { ArrowRight, ChevronDown } from 'lucide-react';

import type { DeliveryLocation } from '@/lib/order-service';
import {
  DROP_OFF_POINTS,
  MAX_DELIVERY_DETAILS_LENGTH,
  findDropOffPoint,
} from '@/lib/orders';
import { cn } from '@/lib/utils';

export type DropOffValue = { pointId: string; details: string };

export const EMPTY_DROP_OFF: DropOffValue = { pointId: '', details: '' };

/** An order's current drop-off as form state, if it came from a preset. */
export function dropOffValueOf(label: string, details: string): DropOffValue {
  return { pointId: findDropOffPoint(label)?.id ?? '', details };
}

/** The Order Service body for a complete drop-off, or null if incomplete. */
export function toDeliveryLocation({
  pointId,
  details,
}: DropOffValue): DeliveryLocation | null {
  const point = DROP_OFF_POINTS.find((p) => p.id === pointId);
  if (!point || !details.trim()) return null;
  const { label, latitude, longitude } = point;
  return { label, latitude, longitude, details: details.trim() };
}

export const fieldClass =
  'w-full rounded-xl border bg-white px-4 text-sm text-slate-900 shadow-xs outline-none transition-shadow placeholder:text-slate-400 focus:border-courier focus:ring-2 focus:ring-courier/20';

type DropOffFieldsProps = {
  idPrefix: string;
  value: DropOffValue;
  onChange: (value: DropOffValue) => void;
  /** Rendered before each control, so callers keep their own label style. */
  renderLabel: (htmlFor: string, text: string) => React.ReactNode;
};

export function DropOffFields({
  idPrefix,
  value,
  onChange,
  renderLabel,
}: DropOffFieldsProps) {
  const pointId = `${idPrefix}-point`;
  const detailsId = `${idPrefix}-details`;

  return (
    <div className='space-y-4'>
      <div>
        {renderLabel(pointId, 'Drop-off Point')}
        <div className='relative'>
          <ArrowRight
            className='text-courier pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2'
            aria-hidden
          />
          <select
            id={pointId}
            value={value.pointId}
            onChange={(e) => onChange({ ...value, pointId: e.target.value })}
            className={cn(
              fieldClass,
              'h-12 appearance-none pr-11 pl-10',
              !value.pointId && 'text-slate-400',
            )}
          >
            <option value='' disabled>
              Choose a campus building
            </option>
            {DROP_OFF_POINTS.map((point) => (
              <option
                key={point.id}
                value={point.id}
                className='text-slate-900'
              >
                {point.label}
              </option>
            ))}
          </select>
          <ChevronDown
            className='pointer-events-none absolute top-1/2 right-4 size-4 -translate-y-1/2 text-slate-500'
            aria-hidden
          />
        </div>
      </div>
      <div>
        {renderLabel(detailsId, 'Where exactly?')}
        <input
          id={detailsId}
          value={value.details}
          maxLength={MAX_DELIVERY_DETAILS_LENGTH}
          onChange={(e) => onChange({ ...value, details: e.target.value })}
          placeholder='e.g. Level 2 study area, table by the window'
          className={cn(fieldClass, 'h-12')}
        />
      </div>
    </div>
  );
}
