# Stripe setup

What you need to do once to take real money. Steps apply to **test mode**; flip to live keys once the test flow is solid end-to-end.

---

## 1. Create a Stripe account

1. Sign up at https://stripe.com — free, no card required for test mode.
2. Stay in **test mode** (toggle in top-right of the dashboard). All the keys and prices below should be test-mode versions.

## 2. Create a Price per product

hero-proto's `ShopProduct` rows need a `stripe_price_id`. Each seeded SKU needs a matching Price in Stripe:

| SKU | Display | Amount (USD) |
|---|---|---|
| `starter_pack` | Starter Pack | $1.99 |
| `gems_small` | Pocket Change | $4.99 |
| `gems_medium` | Slush Fund | $19.99 |
| `gems_large` | Off-the-Books Budget | $49.99 |
| `shards_pack` | Summoning Cache | $9.99 |
| `access_cards_pack` | Keymaster's Bundle | $9.99 |
| `weekly_bundle` | Weekly Ops Kit | $9.99 |

In the dashboard: **Products → Add product**. For each one:
- Name = the `title` from the table
- Pricing model = "One-time"
- Price = USD, matching above
- Save → copy the Price ID (starts with `price_...`)

Then apply them to the DB:

```sql
UPDATE shop_products SET stripe_price_id = 'price_ABCxxx' WHERE sku = 'gems_small';
-- repeat per SKU
```

Or from a Python shell:
```python
from app.db import SessionLocal
from app.models import ShopProduct

MAPPING = {
    "gems_small": "price_abc123",
    # ...
}
with SessionLocal() as db:
    for sku, pid in MAPPING.items():
        p = db.query(ShopProduct).filter_by(sku=sku).one()
        p.stripe_price_id = pid
    db.commit()
```

Products without a `stripe_price_id` won't show a "Buy" button for Stripe checkout — they remain available through the mock-payment path in dev.

## 3. Get API keys

**Dashboard → Developers → API keys.**

- **Publishable key** (`pk_test_...`) — exposed to the client. Not strictly required yet; future checkout.js integration will use it.
- **Secret key** (`sk_test_...`) — **never commit this.** Set via env var.

Add to your `.env` (local) or secret store (prod):

```
HEROPROTO_STRIPE_API_KEY=sk_test_...
HEROPROTO_STRIPE_PUBLISHABLE_KEY=pk_test_...
```

## 4. Set up the webhook listener

In development, use the Stripe CLI to forward events to your local server:

```bash
# install: https://stripe.com/docs/stripe-cli
stripe login
stripe listen --forward-to http://127.0.0.1:8000/shop/webhooks/stripe
```

On startup the CLI prints a signing secret:

```
> Ready! Your webhook signing secret is whsec_abc123... (^C to quit)
```

Copy it into `.env`:

```
HEROPROTO_STRIPE_WEBHOOK_SECRET=whsec_abc123...
```

In production, create a webhook endpoint at **Dashboard → Developers → Webhooks → Add endpoint**:
- URL: `https://your-domain.com/shop/webhooks/stripe`
- Events: `checkout.session.completed`, `charge.refunded`
- Copy the endpoint's signing secret into the same env var.

## 5. Configure redirect URLs

```
HEROPROTO_STRIPE_SUCCESS_URL=http://127.0.0.1:8000/app/shop?checkout=success
HEROPROTO_STRIPE_CANCEL_URL=http://127.0.0.1:8000/app/shop?checkout=cancel
```

In production use the real domain.

## 6. Test end-to-end in test mode

1. Start the server: `uv run uvicorn app.main:app`
2. Start the listener: `stripe listen --forward-to http://127.0.0.1:8000/shop/webhooks/stripe`
3. From the HTMX shop tab, click Buy on any Stripe-enabled product. You'll get redirected to the Stripe-hosted checkout page.
4. Use any Stripe **test card**: `4242 4242 4242 4242`, any future date, any CVC, any ZIP.
5. After submission, Stripe redirects to the success URL and fires `checkout.session.completed`.
6. The `/shop/webhooks/stripe` handler completes the Purchase, grants the currency, writes the ledger.
7. Verify on `/me` that balances updated.

## 7. Safety checklist before going live

- [ ] All products have `stripe_price_id` populated — one per SKU.
- [ ] Webhook signing secret is set and rotates independently of the API key.
- [ ] `HEROPROTO_ENVIRONMENT=prod` — the server refuses to start if `mock_payments_enabled=true` while env is prod (see `app/main.py:_check_secrets`).
- [ ] Real Stripe live keys (`sk_live_`, `pk_live_`, `whsec_`) — not test keys.
- [ ] Webhook endpoint is HTTPS-only. Stripe refuses plain-HTTP webhook URLs in live mode.
- [ ] Monitoring: watch `PurchaseState.FAILED` rows and unhandled webhook event types (logged at INFO).
- [ ] Tax configuration: if you're in the US and registered for sales tax, set up **Stripe Tax**. Outside US, check VAT / GST requirements.
- [ ] Refund policy written and linked from the app.

## Data model recap

- `ShopProduct.stripe_price_id` — links our SKU to a Stripe Price object.
- `Purchase.processor = "stripe"` and `processor_ref = <session_id>` — Stripe Checkout Session id.
- `Purchase.state` — PENDING during checkout, COMPLETED on webhook, REFUNDED on chargeback.
- `(processor, processor_ref)` is UNIQUE → the webhook is naturally idempotent even if Stripe retries.
- `PurchaseLedger` rows are written on every grant and refund — never exposed to players, used for CS and reconciliation.

## Troubleshooting

**Checkout returns 503 "Stripe is not configured"**
→ `HEROPROTO_STRIPE_API_KEY` is empty or malformed. Check env loading.

**Checkout returns 409 "has no Stripe price configured"**
→ `stripe_price_id` is empty for that SKU. Update the DB.

**Webhook returns 400 "invalid Stripe signature"**
→ `HEROPROTO_STRIPE_WEBHOOK_SECRET` doesn't match the signing secret printed by `stripe listen` (or by the live webhook endpoint). The secret changes every time you restart `stripe listen` in dev.

**Balance didn't update after a successful test payment**
→ Check the `stripe listen` output: it logs every forwarded event and shows the response. If it shows a 4xx/5xx from our handler, check logs and `Purchase.state` for that session id.
