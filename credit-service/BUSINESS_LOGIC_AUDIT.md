# Credit business-logic audit map

## Layer boundary

`app/services/credits.py` contains transport-independent Credit rules. Its
operations accept UUIDs, amounts, and domain reasons; it does not import event
envelopes, RabbitMQ code, HTTP schemas, or outbox helpers.

`app/services/event_handlers.py` is the application-layer adapter. It translates
incoming events into domain calls and translates domain results into outbox
events. `app/worker.py` owns retry, commit, acknowledgement, and dead lettering.

## Account creation

1. Validate and normalize domain inputs.
2. Lock and compare the User UUID and NUS student number.
3. Create a zero-balance account only when neither identifier exists.
4. Use `initial_allocation_granted_at` as the durable allocation marker.
5. Grant and ledger the allocation in the caller-owned transaction.

## Reservation

1. Lock any existing reservation by its unique Order UUID.
2. Lock the requester account.
3. Ledger expected rejection instead of raising a system failure.
4. Move the amount from available to reserved without changing total credit.
5. Record the signed balance movement.

Stable rejection codes are `ACCOUNT_NOT_FOUND`, `ACCOUNT_NOT_ACTIVE`, and
`INSUFFICIENT_CREDIT`.

## Transfer

1. Lock and validate the active reservation.
2. Lock requester and courier accounts in UUID order.
3. Move requester reserved credit to courier available credit.
4. Record one signed ledger row for each side with the settlement reason.

The same Credit operation supports two domain reasons:

- `ORDER_COMPLETED`
- `ORDER_CANCELLED_AFTER_PICKUP`

The courier must be active. The requester need not remain active because the
credit was already reserved and is owed to the courier.

## Release

1. Lock and validate the active reservation.
2. Lock its requester account.
3. Reverse the hold without changing requester total credit.
4. Record the release ledger row.

Release is used for expiry and cancellation before pickup. Cancellation after
pickup uses transfer, not release.

## Administrator adjustment

1. Validate non-zero amount and non-blank reason. Authentication is enforced at
   the HTTP boundary rather than coupled into the domain function.
2. Lock the target account and enforce a non-negative available balance.
3. Apply the signed adjustment.
4. Record actor, absolute amount, signed delta, reason, and correlation UUID.

## Event adaptation

- `order.created` calls reservation and emits `credit.reserved` or
  `credit.reservation_failed`.
- `order.completed` calls transfer with `ORDER_COMPLETED` and emits
  `credit.transferred`.
- `order.cancelled` from `PICKED_UP` calls transfer with
  `ORDER_CANCELLED_AFTER_PICKUP` and emits `credit.transferred`.
- Other `order.cancelled` events and `order.expired` call release and emit
  `credit.released`.
- `user.created` calls account creation and initial allocation.

The adapter stages the inbox marker and outbox event in the same transaction as
the domain mutation and ledger rows. It does not modify Order state.
