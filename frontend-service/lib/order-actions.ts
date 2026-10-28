'use server';

import { revalidatePath } from 'next/cache';

import {
  type ActionResult,
  type FailureOverrides,
  type PageResult,
  toResult,
} from '@/lib/action-result';
import {
  type DeliveryLocation,
  type Order,
  type OrderCreate,
  type OrderRole,
  orderService,
} from '@/lib/order-service';
import { withSuppliers } from '@/lib/order-views';
import { DUPLICATE_SUBMISSION, type OrderView } from '@/lib/orders';
import { FIRST_PAGE, type PageWindow, clampPageWindow } from '@/lib/paging';
import type { Page } from '@/lib/service-request';
import { getSessionToken } from '@/lib/session';

export type OrderActionResult = ActionResult<{ order: OrderView }>;

async function act(
  run: (token: string | undefined) => Promise<Order>,
  overrides?: FailureOverrides,
): Promise<OrderActionResult> {
  return toResult(async () => {
    const [order] = await withSuppliers([await run(await getSessionToken())]);
    return { order };
  }, overrides);
}

async function loadPage(
  read: (token: string | undefined, window: PageWindow) => Promise<Page<Order>>,
  window: PageWindow,
): Promise<PageResult<OrderView>> {
  return toResult(async () => {
    const page = await read(await getSessionToken(), clampPageWindow(window));
    return {
      items: await withSuppliers(page.items),
      total: page.total,
      loadedAt: Date.now(),
    };
  });
}

/**
 * The browser keeps one idempotency key per form submission, so a retry after
 * a timeout returns the original order instead of posting a second one.
 */
export async function createOrder(
  idempotencyKey: string,
  order: OrderCreate,
): Promise<OrderActionResult> {
  return act(
    (token) => orderService.createOrder(token, idempotencyKey, order),
    {
      // The key was used before with different details.
      409: {
        message:
          'An earlier attempt was already posted. Check My Errands before posting again.',
        code: DUPLICATE_SUBMISSION,
      },
    },
  );
}

export async function loadOrder(id: string): Promise<OrderActionResult> {
  return act((token) => orderService.getOrder(token, id));
}

export async function loadOpenOrders(
  window: PageWindow = FIRST_PAGE,
): Promise<PageResult<OrderView>> {
  return loadPage(orderService.listOpenOrders, window);
}

export async function loadMyOrders(
  role: OrderRole,
  window: PageWindow = FIRST_PAGE,
): Promise<PageResult<OrderView>> {
  return loadPage(
    (token, page) => orderService.listMyOrders(token, role, page),
    window,
  );
}

export async function acceptOrder(id: string) {
  return act((token) => orderService.acceptOrder(token, id), {
    409: { message: 'Another courier accepted this errand first.' },
    // Order Service hides orders that left OPEN from non-participants.
    404: { message: 'This errand is no longer available.' },
  });
}

export async function pickUpOrder(id: string) {
  return act((token) => orderService.pickUpOrder(token, id));
}

/**
 * Completing or cancelling moves credit, so re-render the layout's balance.
 * Credit Service applies the change from Kafka shortly after, so the refreshed
 * balance can still be one event behind.
 */
async function refreshingBalance(result: Promise<OrderActionResult>) {
  const settled = await result;
  if (settled.ok) revalidatePath('/', 'layout');
  return settled;
}

export async function completeOrder(id: string) {
  return refreshingBalance(
    act((token) => orderService.completeOrder(token, id)),
  );
}

export async function cancelOrder(id: string) {
  return refreshingBalance(act((token) => orderService.cancelOrder(token, id)));
}

export async function changeDelivery(id: string, delivery: DeliveryLocation) {
  return act((token) => orderService.changeDelivery(token, id, delivery));
}
