import type { DeliveryLocation } from '@/lib/order-service';

/**
 * Campus drop-off points. Order Service needs coordinates inside latitude
 * 1.288–1.310 and longitude 103.750–103.788, so the requester picks a point
 * and can describe the exact spot in the details field.
 */
export type DropOffPoint = Omit<DeliveryLocation, 'details'> & { id: string };

export const DROP_OFF_POINTS: DropOffPoint[] = [
  { id: 'com1', label: 'COM1', latitude: 1.2949, longitude: 103.7737 },
  { id: 'com2', label: 'COM2', latitude: 1.2938, longitude: 103.7745 },
  {
    id: 'clb',
    label: 'Central Library',
    latitude: 1.2966,
    longitude: 103.773,
  },
  {
    id: 'yih',
    label: 'Yusof Ishak House',
    latitude: 1.2984,
    longitude: 103.7726,
  },
  {
    id: 'hssml',
    label: 'Hon Sui Sen Memorial Library',
    latitude: 1.2931,
    longitude: 103.772,
  },
  {
    id: 'e4',
    label: 'Engineering Block E4',
    latitude: 1.2992,
    longitude: 103.7691,
  },
  {
    id: 'medsci',
    label: 'Medicine+Science Library',
    latitude: 1.2968,
    longitude: 103.7794,
  },
  {
    id: 'pgp',
    label: "Prince George's Park Residences",
    latitude: 1.2909,
    longitude: 103.7771,
  },
  {
    id: 'utown',
    label: 'University Town',
    latitude: 1.3048,
    longitude: 103.7727,
  },
];

/** Drop-off form state: the chosen point's id and the free-text details. */
export type DropOffValue = { pointId: string; details: string };

export const EMPTY_DROP_OFF: DropOffValue = { pointId: '', details: '' };

/**
 * The requester's own drop-off details, or null when they gave none. Order
 * Service requires non-blank details, so an order without any stores the
 * label again (see `toDeliveryLocation`).
 */
export function deliveryDetailsOf(label: string, details: string) {
  return details === label ? null : details;
}

/**
 * An order's current drop-off as form state. Orders only store the label, so
 * the point is matched by it; a label that is no longer a preset leaves the
 * point unselected.
 */
export function dropOffValueOf(label: string, details: string): DropOffValue {
  const point = DROP_OFF_POINTS.find((p) => p.label === label);
  return {
    pointId: point?.id ?? '',
    details: deliveryDetailsOf(label, details) ?? '',
  };
}

/**
 * The Order Service body for a drop-off, or null until a point is chosen.
 * Details are optional here but required by Order Service, so blank details
 * fall back to the point's label.
 */
export function toDeliveryLocation({
  pointId,
  details,
}: DropOffValue): DeliveryLocation | null {
  const point = DROP_OFF_POINTS.find((p) => p.id === pointId);
  if (!point) return null;
  const { label, latitude, longitude } = point;
  return { label, latitude, longitude, details: details.trim() || label };
}
