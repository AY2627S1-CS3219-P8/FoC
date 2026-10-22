'use server';

import {
  type DeliveryLocation,
  type Order,
  type OrderCreate,
  type OrderRole,
  orderService,
} from '@/lib/order-service';
import { withSuppliers } from '@/lib/order-views';
import {
  ORDER_PAGE_SIZE,
  type OrderActionResult,
  type OrderPageResult,
} from '@/lib/orders';
import { ServiceError } from '@/lib/service-request';
import { getSessionToken } from '@/lib/session-token';

/** Service errors become results; anything else is a bug and is rethrown. */
function failure(error: unknown) {
  if (error instanceof ServiceError) {
    return { ok: false as const, status: error.status, message: error.message };
  }
  throw error;
}

async function act(
  run: (token: string | undefined) => Promise<Order>,
): Promise<OrderActionResult> {
  try {
    const [order] = await withSuppliers([await run(await getSessionToken())]);
    return { ok: true, order };
  } catch (error) {
    return failure(error);
  }
}

/**
 * The browser keeps one idempotency key per form submission, so a retry after
 * a timeout returns the original order instead of posting a second one.
 */
export async function createOrder(
  idempotencyKey: string,
  order: OrderCreate,
): Promise<OrderActionResult> {
  return act((token) => orderService.createOrder(token, idempotencyKey, order));
}

export async function loadOrder(id: string): Promise<OrderActionResult> {
  return act((token) => orderService.getOrder(token, id));
}

export async function loadOpenOrders(offset = 0): Promise<OrderPageResult> {
  try {
    const page = await orderService.listOpenOrders(await getSessionToken(), {
      limit: ORDER_PAGE_SIZE,
      offset,
    });
    return {
      ok: true,
      items: await withSuppliers(page.items),
      total: page.total,
      loadedAt: Date.now(),
    };
  } catch (error) {
    return failure(error);
  }
}

export async function loadMyOrders(
  role: OrderRole,
  offset = 0,
): Promise<OrderPageResult> {
  try {
    const page = await orderService.listMyOrders(
      await getSessionToken(),
      role,
      { limit: ORDER_PAGE_SIZE, offset },
    );
    return {
      ok: true,
      items: await withSuppliers(page.items),
      total: page.total,
      loadedAt: Date.now(),
    };
  } catch (error) {
    return failure(error);
  }
}

export async function acceptOrder(id: string) {
  return act((token) => orderService.acceptOrder(token, id));
}

export async function pickUpOrder(id: string) {
  return act((token) => orderService.pickUpOrder(token, id));
}

export async function completeOrder(id: string) {
  return act((token) => orderService.completeOrder(token, id));
}

export async function cancelOrder(id: string) {
  return act((token) => orderService.cancelOrder(token, id));
}

export async function changeDelivery(id: string, delivery: DeliveryLocation) {
  return act((token) => orderService.changeDelivery(token, id, delivery));
}
