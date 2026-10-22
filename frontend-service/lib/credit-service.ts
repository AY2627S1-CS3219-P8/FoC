/**
 * Server-side client for Credit Service's own-account reads. Only import this
 * from Server Actions, Route Handlers or Server Components: every route needs
 * the User Service bearer token. Balances only change through order events,
 * so the frontend never writes to Credit Service.
 */

import { ServiceError, createServiceRequest } from '@/lib/service-request';

const BASE_URL = process.env.CREDIT_SERVICE_URL ?? 'http://localhost:8083';

const request = createServiceRequest(BASE_URL, 'Credit Service');

export type CreditBalance = {
  user_id: string;
  available_balance: number;
  /** Held for the caller's open orders until they complete, cancel or expire. */
  reserved_balance: number;
  total_balance: number;
  created_at: string;
  updated_at: string;
};

export type CreditTransactionType =
  | 'INITIAL_ALLOCATION'
  | 'RESERVATION'
  | 'TRANSFER'
  | 'RELEASE'
  | 'ADMIN_ADJUSTMENT';

export type CreditTransaction = {
  id: string;
  order_id: string | null;
  affected_user_id: string;
  counterparty_user_id: string | null;
  actor_user_id: string | null;
  transaction_type: CreditTransactionType;
  outcome: 'SUCCEEDED' | 'REJECTED';
  amount: number;
  available_delta: number;
  reserved_delta: number;
  reason: string;
  correlation_id: string;
  created_at: string;
};

export type CreditTransactionPage = {
  items: CreditTransaction[];
  total: number;
  limit: number;
  offset: number;
};

/** Credit Service caps a transaction page at 100 items. */
export const MAX_TRANSACTION_PAGE_SIZE = 100;

export const creditService = {
  /**
   * The caller's balance, or null when they have no account yet. Accounts are
   * created with the initial allocation on the user's first order, and reads
   * never create one.
   */
  getMyBalance: async (token: string | undefined) => {
    try {
      return await request<CreditBalance>('/credits/me', { token });
    } catch (error) {
      if (
        error instanceof ServiceError &&
        error.code === 'CREDIT_ACCOUNT_NOT_FOUND'
      ) {
        return null;
      }
      throw error;
    }
  },

  /** The caller's audit trail, newest first. Empty when there is no account. */
  listMyTransactions: (
    token: string | undefined,
    { limit, offset }: { limit?: number; offset?: number } = {},
  ) => {
    const params = new URLSearchParams();
    if (limit !== undefined) params.set('limit', String(limit));
    if (offset !== undefined) params.set('offset', String(offset));
    const query = params.toString();
    return request<CreditTransactionPage>(
      `/credits/me/transactions${query && `?${query}`}`,
      { token },
    );
  },
};
