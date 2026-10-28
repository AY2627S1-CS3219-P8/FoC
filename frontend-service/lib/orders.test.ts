import { describe, expect, it } from 'vitest';

import {
  deliveryDetailsOf,
  dropOffValueOf,
  toDeliveryLocation,
} from '@/lib/drop-off';
import { newIdempotencyKey } from '@/lib/idempotency';
import type { Order } from '@/lib/order-service';
import { isNearExpiry } from '@/lib/orders';

describe('isNearExpiry', () => {
  const order = {
    created_at: '2026-10-28T10:00:00Z',
    expires_at: '2026-10-28T11:00:00Z',
  } as Order;

  it('turns true halfway through the order’s own lifetime', () => {
    expect(isNearExpiry(order, Date.parse('2026-10-28T10:29:00Z'))).toBe(false);
    expect(isNearExpiry(order, Date.parse('2026-10-28T10:30:00Z'))).toBe(true);
  });
});

describe('drop-off', () => {
  it('round-trips a preset point and trims the details', () => {
    const value = dropOffValueOf('COM1', '  Level 2  ');
    expect(value.pointId).toBe('com1');
    expect(toDeliveryLocation(value)).toEqual({
      label: 'COM1',
      latitude: 1.2949,
      longitude: 103.7737,
      details: 'Level 2',
    });
  });

  it('is incomplete without a known point', () => {
    expect(dropOffValueOf('Somewhere else', 'x').pointId).toBe('');
    expect(toDeliveryLocation({ pointId: '', details: 'x' })).toBeNull();
  });

  it('sends the label as details when none are given, and hides it again', () => {
    const location = toDeliveryLocation({ pointId: 'com1', details: '  ' });
    expect(location?.details).toBe('COM1');
    expect(deliveryDetailsOf('COM1', 'COM1')).toBeNull();
    expect(dropOffValueOf('COM1', 'COM1').details).toBe('');
  });
});

describe('newIdempotencyKey', () => {
  it('returns distinct v4 UUIDs', () => {
    const key = newIdempotencyKey();
    expect(key).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
    expect(newIdempotencyKey()).not.toBe(key);
  });
});
