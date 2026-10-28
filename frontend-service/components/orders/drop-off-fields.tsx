'use client';

import { ArrowRight, ChevronDown } from 'lucide-react';

import { fieldClass } from '@/components/ui/field';
import { DROP_OFF_POINTS, type DropOffValue } from '@/lib/drop-off';
import { MAX_DELIVERY_DETAILS_LENGTH } from '@/lib/orders';
import { cn } from '@/lib/utils';

type DropOffFieldsProps = {
  idPrefix: string;
  value: DropOffValue;
  onChange: (value: DropOffValue) => void;
  /**
   * Rendered before each control, so callers keep their own label style.
   * `missing` is true when a required control is still empty.
   */
  renderLabel: (
    htmlFor: string,
    text: string,
    missing: boolean,
  ) => React.ReactNode;
};

/** Element ids of the two controls, so callers can link to or focus them. */
export function dropOffFieldIds(idPrefix: string) {
  return { point: `${idPrefix}-point`, details: `${idPrefix}-details` };
}

export function DropOffFields({
  idPrefix,
  value,
  onChange,
  renderLabel,
}: DropOffFieldsProps) {
  const { point: pointId, details: detailsId } = dropOffFieldIds(idPrefix);

  return (
    <div className='space-y-4'>
      <div>
        {renderLabel(pointId, 'Drop-off Point', !value.pointId)}
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
        {renderLabel(detailsId, 'Where exactly? (optional)', false)}
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
