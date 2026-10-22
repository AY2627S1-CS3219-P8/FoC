/**
 * Server-side client for Order Service. Only import this from Server Actions,
 * Route Handlers or Server Components: every route needs the User Service
 * bearer token, and Order Service does not allow browser origins.
 *
 * Request bodies are built field by field because Order Service rejects any
 * field it doesn't expect.
 */

import { createServiceRequest } from '@/lib/service-request';

const BASE_URL = process.env.ORDER_SERVICE_URL ?? 'http://localhost:8082';

const request = createServiceRequest(BASE_URL, 'Order Service');

export type OrderStatus =
  | 'PENDING_CREDIT'
  | 'OPEN'
  | 'ACCEPTED'
  | 'PICKED_UP'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'EXPIRED'
  | 'REJECTED';

export type OrderRole = 'requester' | 'courier';

export type DeliveryLocation = {
  label: string;
  latitude: number;
  longitude: number;
  details: string;
};

export type OrderCreate = {
  pickup_supplier_id: string;
  delivery: DeliveryLocation;
  item_description: string;
  credit_amount: number;
};

export type Order = {
  id: string;
  requester_id: string;
  courier_id: string | null;
  pickup_supplier_id: string;
  delivery_label: string;
  delivery_latitude: number;
  delivery_longitude: number;
  delivery_details: string;
  item_description: string;
  credit_amount: number;
  status: OrderStatus;
  /** Credit Service reason, e.g. `INSUFFICIENT_CREDIT`, when `REJECTED`. */
  rejection_reason: string | null;
  accepted_at: string | null;
  picked_up_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  cancelled_by: string | null;
  expired_at: string | null;
  expires_at: string;
  created_at: string;
  updated_at: string;
};

export type OrderPage = {
  items: Order[];
  total: number;
  limit: number;
  offset: number;
};

type PageParams = { limit?: number; offset?: number };

function pageQuery({ limit, offset }: PageParams, extra: string[][] = []) {
  const params = new URLSearchParams(extra);
  if (limit !== undefined) params.set('limit', String(limit));
  if (offset !== undefined) params.set('offset', String(offset));
  const query = params.toString();
  return query && `?${query}`;
}

function delivery({ label, latitude, longitude, details }: DeliveryLocation) {
  return { label, latitude, longitude, details };
}

const orderPath = (id: string) => `/orders/${encodeURIComponent(id)}`;

export const orderService = {
  /** 201 for a new order, 200 when the same key and body are retried. */
  createOrder: (
    token: string | undefined,
    idempotencyKey: string,
    {
      pickup_supplier_id,
      delivery: location,
      item_description,
      credit_amount,
    }: OrderCreate,
  ) =>
    request<Order>('/orders', {
      method: 'POST',
      token,
      headers: { 'Idempotency-Key': idempotencyKey },
      body: {
        pickup_supplier_id,
        delivery: delivery(location),
        item_description,
        credit_amount,
      },
    }),

  /** `OPEN` errands posted by other users, newest first. */
  listOpenOrders: (token: string | undefined, page: PageParams = {}) =>
    request<OrderPage>(`/orders/open${pageQuery(page)}`, { token }),

  /** The caller's own orders in one role, newest first. */
  listMyOrders: (
    token: string | undefined,
    role: OrderRole,
    page: PageParams = {},
  ) =>
    request<OrderPage>(`/orders${pageQuery(page, [['role', role]])}`, {
      token,
    }),

  getOrder: (token: string | undefined, id: string) =>
    request<Order>(orderPath(id), { token }),

  /** Requester only, before pickup. */
  changeDelivery: (
    token: string | undefined,
    id: string,
    location: DeliveryLocation,
  ) =>
    request<Order>(`${orderPath(id)}/delivery`, {
      method: 'PATCH',
      token,
      body: delivery(location),
    }),

  /** First committed accept wins; the others get 409. */
  acceptOrder: (token: string | undefined, id: string) =>
    request<Order>(`${orderPath(id)}/accept`, { method: 'POST', token }),

  /** Assigned courier only. */
  pickUpOrder: (token: string | undefined, id: string) =>
    request<Order>(`${orderPath(id)}/pickup`, { method: 'POST', token }),

  /** Requester only, after pickup. */
  completeOrder: (token: string | undefined, id: string) =>
    request<Order>(`${orderPath(id)}/complete`, { method: 'POST', token }),

  /** Requester before pickup. */
  cancelOrder: (token: string | undefined, id: string) =>
    request<Order>(`${orderPath(id)}/cancel`, { method: 'POST', token }),
};
