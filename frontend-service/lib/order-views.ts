import type { Order } from '@/lib/order-service';
import type { OrderView } from '@/lib/orders';
import { type Supplier, supplierService } from '@/lib/supplier-service';

/**
 * Attaches each order's pickup store. Order Service only stores the supplier
 * id, so look up each distinct store once. A missing store does not hide the
 * order: the card falls back to a placeholder.
 */
export async function withSuppliers(orders: Order[]): Promise<OrderView[]> {
  const ids = [...new Set(orders.map((order) => order.pickup_supplier_id))];
  const suppliers = new Map<string, Supplier | null>(
    await Promise.all(
      ids.map(
        async (id) =>
          [
            id,
            await supplierService.getSupplier(id).catch(() => null),
          ] as const,
      ),
    ),
  );
  return orders.map((order) => ({
    ...order,
    supplier: suppliers.get(order.pickup_supplier_id) ?? null,
  }));
}
