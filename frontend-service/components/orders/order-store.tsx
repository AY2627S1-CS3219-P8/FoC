import Image from 'next/image';
import { Store } from 'lucide-react';

import type { OrderView } from '@/lib/orders';
import { formatSupplierLocation, supplierImageSrc } from '@/lib/suppliers';
import { cn } from '@/lib/utils';

/** Pickup store name, or a placeholder when Supplier Service has no record. */
export function orderStoreName(order: OrderView) {
  return order.supplier?.name ?? 'Store no longer listed';
}

export function orderPickupLocation(order: OrderView) {
  return order.supplier
    ? formatSupplierLocation(order.supplier)
    : 'Pickup details unavailable';
}

export function OrderStoreThumbnail({
  order,
  className,
}: {
  order: OrderView;
  className?: string;
}) {
  const src = order.supplier && supplierImageSrc(order.supplier);
  if (src) {
    return (
      <Image
        src={src}
        alt=''
        width={44}
        height={44}
        className={cn('size-11 shrink-0 rounded-xl object-cover', className)}
      />
    );
  }
  return (
    <span
      className={cn(
        'bg-courier grid size-11 shrink-0 place-items-center rounded-xl text-white',
        className,
      )}
    >
      <Store className='size-5' aria-hidden />
    </span>
  );
}
