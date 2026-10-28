import type { Order, OrderStatus } from '@/lib/order-service';
import type { Supplier } from '@/lib/supplier-service';
import { formatSupplierLocation } from '@/lib/suppliers';

/** An order with its pickup store, which Order Service only references by id. */
export type OrderView = Order & {
  /** Null when the store was deleted or Supplier Service is unavailable. */
  supplier: Supplier | null;
  /** True when the lookup failed, as opposed to the store being deleted. */
  supplierUnavailable: boolean;
};

/** Failure code from `createOrder` when the idempotency key was already used. */
export const DUPLICATE_SUBMISSION = 'DUPLICATE_SUBMISSION';

/** Order Service limits, from `order-service/app/schemas.py`. */
export const MAX_CREDIT_AMOUNT = 1000;
export const MAX_ITEM_DESCRIPTION_LENGTH = 500;
export const MAX_DELIVERY_DETAILS_LENGTH = 500;

/**
 * Requesters may cancel or move the drop-off until the courier picks up.
 * Mirrors `REQUESTER_CANCELLABLE` and `DESTINATION_MUTABLE` in
 * `order-service/app/services/orders.py`.
 */
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
 * True in the second half of an open errand's lifetime. Uses the order's own
 * `expires_at`, so it follows Order Service if the expiry window changes.
 */
export function isNearExpiry(order: Order, now: number) {
  const created = new Date(order.created_at).getTime();
  const expires = new Date(order.expires_at).getTime();
  return now >= created + (expires - created) / 2;
}

/** Pickup store name, or a placeholder when Supplier Service has no record. */
export function orderStoreName(order: OrderView) {
  if (order.supplier) return order.supplier.name;
  return order.supplierUnavailable
    ? 'Store details unavailable'
    : 'Store no longer listed';
}

export function orderPickupLocation(order: OrderView) {
  return order.supplier
    ? formatSupplierLocation(order.supplier) || order.supplier.area
    : 'Pickup details unavailable';
}
