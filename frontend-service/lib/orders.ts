import type { DeliveryLocation, Order, OrderStatus } from '@/lib/order-service';
import type { Supplier } from '@/lib/supplier-service';

/** An order with its pickup store, which Order Service only references by id. */
export type OrderView = Order & {
  /** Null when the store was deleted or Supplier Service is unavailable. */
  supplier: Supplier | null;
};

export type OrderActionResult =
  | { ok: true; order: OrderView }
  | { ok: false; status: number; message: string };

export type OrderPageResult =
  | {
      ok: true;
      items: OrderView[];
      total: number;
      /**
       * Server time the page was read, in ms. Relative times are computed
       * from it so the server render and hydration produce the same text.
       */
      loadedAt: number;
    }
  | { ok: false; status: number; message: string };

/** Page size for the feed and order lists; Order Service allows up to 100. */
export const ORDER_PAGE_SIZE = 20;

/** Order Service limits, from `order-service/app/schemas.py`. */
export const MAX_CREDIT_AMOUNT = 1000;
export const MAX_ITEM_DESCRIPTION_LENGTH = 500;
export const MAX_DELIVERY_DETAILS_LENGTH = 500;

/** Requesters may cancel or move the drop-off until the courier picks up. */
export const PRE_PICKUP_STATUSES: readonly OrderStatus[] = [
  'PENDING_CREDIT',
  'OPEN',
  'ACCEPTED',
];

export const STATUS_LABELS: Record<OrderStatus, string> = {
  PENDING_CREDIT: 'Reserving credit',
  OPEN: 'Open',
  ACCEPTED: 'Accepted',
  PICKED_UP: 'Picked Up',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
  EXPIRED: 'Expired',
  REJECTED: 'Rejected',
};

const REJECTION_REASONS: Record<string, string> = {
  INSUFFICIENT_CREDIT: 'You did not have enough available credit.',
  ACCOUNT_NOT_FOUND: 'Your credit account could not be found.',
};

export function formatRejectionReason(reason: string | null) {
  return (
    (reason && REJECTION_REASONS[reason]) ?? 'Credit could not be reserved.'
  );
}

/**
 * Campus drop-off points. Order Service needs coordinates inside latitude
 * 1.288–1.310 and longitude 103.750–103.788, so the requester picks a point
 * and describes the exact spot in the details field.
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

/** The preset an order's drop-off came from, matched by label. */
export function findDropOffPoint(label: string) {
  return DROP_OFF_POINTS.find((point) => point.label === label);
}

export function minutesSince(iso: string, now = Date.now()) {
  return Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000));
}

const dateFormat = new Intl.DateTimeFormat('en-SG', {
  day: 'numeric',
  month: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZone: 'Asia/Singapore',
});

export function formatDateTime(iso: string) {
  return dateFormat.format(new Date(iso));
}
