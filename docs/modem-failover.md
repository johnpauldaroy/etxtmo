# Cross-branch modem failover

TextBlast keeps campaign ownership separate from modem execution. Contacts, opt-outs,
campaign totals, and audit records remain under the source branch even when a backup
branch modem sends the SMS.

## Configure

1. Keep every branch agent configured with its own permanent `BRANCH_ID`.
2. Confirm each modem reports a recent heartbeat on the **Modems** page.
3. Select the source branch in the application header.
4. Open **Modems**, enable automatic failover, and set:
   - **Offline after**: how old the newest local modem heartbeat may be.
   - **Failover delay**: how long queued work waits before a backup may claim it.
   - **Stuck delivery after**: the review threshold for an unreported modem claim.
5. Add backup branches in priority order.

The server selects the first configured backup branch that has a healthy modem. Agents
cannot request another branch's work directly.

## Delivery safety

- A queue item is atomically claimed by one modem.
- Delivery results are accepted only from the modem that claimed the item.
- Failed attempts release their modem assignment so routing is recalculated.
- Stale `sending` items are never automatically resent. Use **Review stale deliveries**
  to mark them failed, investigate the modem/Gammu database, and retry manually only
  when duplicate delivery has been ruled out.
- Recipients see the phone number of the backup modem's SIM.

## Production rollout

Run `alembic upgrade head` in `api-core` before restarting the API, then deploy the
updated branch agent at every branch. Existing agents must be upgraded because queue
result uploads now include the registered `modem_id`.
