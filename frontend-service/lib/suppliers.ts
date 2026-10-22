import type { Supplier } from '@/lib/supplier-service';

/** Page size for the store directory; Supplier Service allows up to 100. */
export const SUPPLIER_PAGE_SIZE = 20;

/** `COM2 L1`; floor is free text and both parts may be missing. */
export function formatSupplierLocation(supplier: Supplier) {
  const floor = supplier.floor && `L${supplier.floor.replace(/^L/i, '')}`;
  return [supplier.building, floor].filter(Boolean).join(' ') || supplier.area;
}

/** `HH:MM:SS` → `HH:MM`. */
function formatTime(time: string) {
  return time.slice(0, 5);
}

/** Daily Asia/Singapore hours, as Supplier Service defines them. */
export function formatOpeningHours(supplier: Supplier) {
  const { opening_time: opens, closing_time: closes } = supplier;
  if (!opens || !closes) return 'Hours unknown';
  if (opens === closes) return 'Open 24 hours';
  const nextDay = supplier.closing_day_offset === 1 ? ' (next day)' : '';
  return `${formatTime(opens)} – ${formatTime(closes)}${nextDay}`;
}

/** Seed images are bundled with the frontend, keyed by filename. */
export function supplierImageSrc(supplier: Supplier) {
  return supplier.image_key && `/images/suppliers/${supplier.image_key}`;
}
