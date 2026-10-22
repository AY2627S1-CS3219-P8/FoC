'use server';

import {
  type CreditBalance,
  type CreditTransactionPage,
  creditService,
} from '@/lib/credit-service';
import { ServiceError } from '@/lib/service-request';
import { getSessionToken } from '@/lib/session-token';

/** `balance` is null until the user's first order opens an account. */
export type CreditBalanceResult =
  | { ok: true; balance: CreditBalance | null }
  | { ok: false; message: string };

export type CreditTransactionPageResult =
  | { ok: true; page: CreditTransactionPage }
  | { ok: false; message: string };

/** Page size for the credit history; Credit Service allows up to 100. */
const TRANSACTION_PAGE_SIZE = 20;

function failure(error: unknown) {
  if (error instanceof ServiceError) {
    return { ok: false as const, message: error.message };
  }
  throw error;
}

export async function loadBalance(): Promise<CreditBalanceResult> {
  try {
    const balance = await creditService.getMyBalance(await getSessionToken());
    return { ok: true, balance };
  } catch (error) {
    return failure(error);
  }
}

export async function loadTransactions(
  offset = 0,
): Promise<CreditTransactionPageResult> {
  try {
    const page = await creditService.listMyTransactions(
      await getSessionToken(),
      { limit: TRANSACTION_PAGE_SIZE, offset },
    );
    return { ok: true, page };
  } catch (error) {
    return failure(error);
  }
}
