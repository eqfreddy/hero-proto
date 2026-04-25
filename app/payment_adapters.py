"""PaymentAdapter abstraction.

Three processors today: Stripe (web checkout — already wired in stripe_ext.py),
Apple StoreKit (iOS in-app purchases), Google Play Billing (Android IAP).
Each adapter takes a raw receipt + claimed product SKU, validates the
receipt with the processor, and returns a normalized VerifiedReceipt.

The Apple + Google verifiers ship in two modes:
  - "real": calls the real verification API. Requires credentials in
    settings (HEROPROTO_APPLE_BUNDLE_ID, HEROPROTO_GOOGLE_SERVICE_ACCOUNT).
    Wrapped behind try/except so we degrade to clear errors, not 500s.
  - "sandbox": validates only structural fields. Used for dev/CI without
    real Apple/Google credentials. Receipts must be a known fake-receipt
    shape produced by tests/_iap_fakes.py.

The actual third-party SDKs (app-store-server-library,
google-play-billing-validator) are imported lazily inside the real-mode
verifier so they're optional dependencies — the codebase still imports
even if they're not installed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from app.config import settings


# --- Result type ------------------------------------------------------------


@dataclass(frozen=True)
class VerifiedReceipt:
    """Normalized result returned by every adapter.

    processor_ref is the unique transaction id for idempotency — duplicate
    webhooks (same id) find the existing Purchase row and no-op rather than
    double-grant.
    """
    processor: str          # "apple" | "google" | "stripe"
    processor_ref: str      # transaction_id / order_id / charge_id
    sku: str                # product identifier — must match a ShopProduct.sku
    raw: dict               # parsed receipt for audit
    sandbox: bool = False


class ReceiptError(ValueError):
    """Raised when a receipt fails validation. Router maps to 400."""


# --- Protocol ---------------------------------------------------------------


class PaymentAdapter(Protocol):
    name: str

    def verify(self, receipt: str, claimed_sku: str | None = None) -> VerifiedReceipt: ...


# --- Apple StoreKit 2 -------------------------------------------------------
#
# Real-mode: app-store-server-library decodes the JWS receipt, verifies the
# Apple-signed JWT chain, and returns the transaction. We pull bundle_id +
# transaction_id + product_id out as our normalized fields.
#
# Sandbox-mode: receipt must be a JSON object with the same shape as the
# real result. Used by CI + tests without Apple sandbox creds.


_FAKE_PREFIX_APPLE = "fake-apple:"


@dataclass
class AppleAdapter:
    name: str = "apple"

    def verify(self, receipt: str, claimed_sku: str | None = None) -> VerifiedReceipt:
        if not receipt:
            raise ReceiptError("empty receipt")

        # Sandbox shortcut for tests / CI with no Apple credentials.
        if receipt.startswith(_FAKE_PREFIX_APPLE):
            try:
                payload = json.loads(receipt[len(_FAKE_PREFIX_APPLE):])
            except json.JSONDecodeError as e:
                raise ReceiptError(f"fake-apple receipt malformed: {e}") from e
            sku = payload.get("productId")
            tx = payload.get("transactionId")
            if not sku or not tx:
                raise ReceiptError("fake-apple receipt missing productId/transactionId")
            if claimed_sku and claimed_sku != sku:
                raise ReceiptError(f"sku mismatch: claimed {claimed_sku!r}, receipt {sku!r}")
            return VerifiedReceipt(
                processor="apple", processor_ref=str(tx), sku=str(sku),
                raw=payload, sandbox=True,
            )

        # Real mode. Lazy-import so the SDK stays optional.
        try:
            from appstoreserverlibrary.signed_data_verifier import (  # type: ignore[import-not-found]
                SignedDataVerifier,
            )
        except ImportError as e:
            raise ReceiptError(
                "Apple receipt verification SDK not installed — "
                "add app-store-server-library to dependencies"
            ) from e

        bundle_id = (settings.apple_bundle_id or "").strip()
        if not bundle_id:
            raise ReceiptError("HEROPROTO_APPLE_BUNDLE_ID not set")
        try:
            verifier = SignedDataVerifier(
                root_certificates=[],   # caller wires real Apple roots in production
                enable_online_checks=False,
                bundle_id=bundle_id,
                app_apple_id=settings.apple_app_id or 0,
                environment="Production" if not settings.apple_sandbox else "Sandbox",
            )
            decoded = verifier.verify_and_decode_signed_transaction(receipt)
        except Exception as e:
            raise ReceiptError(f"apple verify failed: {e}") from e

        sku = getattr(decoded, "productId", None) or decoded.get("productId") if hasattr(decoded, "get") else None
        tx = getattr(decoded, "transactionId", None) or (decoded.get("transactionId") if hasattr(decoded, "get") else None)
        if not sku or not tx:
            raise ReceiptError("apple receipt missing productId / transactionId")
        if claimed_sku and claimed_sku != sku:
            raise ReceiptError(f"sku mismatch: claimed {claimed_sku!r}, receipt {sku!r}")
        return VerifiedReceipt(
            processor="apple", processor_ref=str(tx), sku=str(sku),
            raw=dict(decoded) if hasattr(decoded, "items") else {"transactionId": tx, "productId": sku},
            sandbox=settings.apple_sandbox,
        )


# --- Google Play Billing ----------------------------------------------------
#
# Real-mode: google-play-billing-validator hits the Play Developer API with
# a service-account JSON to verify the purchase token. We extract orderId +
# productId.
#
# Sandbox-mode: receipt is JSON with productId + orderId fields.


_FAKE_PREFIX_GOOGLE = "fake-google:"


@dataclass
class GoogleAdapter:
    name: str = "google"

    def verify(self, receipt: str, claimed_sku: str | None = None) -> VerifiedReceipt:
        if not receipt:
            raise ReceiptError("empty receipt")

        if receipt.startswith(_FAKE_PREFIX_GOOGLE):
            try:
                payload = json.loads(receipt[len(_FAKE_PREFIX_GOOGLE):])
            except json.JSONDecodeError as e:
                raise ReceiptError(f"fake-google receipt malformed: {e}") from e
            sku = payload.get("productId")
            order = payload.get("orderId")
            if not sku or not order:
                raise ReceiptError("fake-google receipt missing productId/orderId")
            if claimed_sku and claimed_sku != sku:
                raise ReceiptError(f"sku mismatch: claimed {claimed_sku!r}, receipt {sku!r}")
            return VerifiedReceipt(
                processor="google", processor_ref=str(order), sku=str(sku),
                raw=payload, sandbox=True,
            )

        # Real mode.
        try:
            # The lib's import path varies by version; both shapes seen in the wild.
            try:
                from google_play_billing_validator import Validator  # type: ignore[import-not-found]
            except ImportError:
                from inapppy import GooglePlayValidator as Validator  # type: ignore[import-not-found]
        except ImportError as e:
            raise ReceiptError(
                "Google Play receipt SDK not installed — add google-play-billing-validator "
                "or inapppy to dependencies"
            ) from e

        sa_json = (settings.google_service_account_json or "").strip()
        package = (settings.google_package_name or "").strip()
        if not sa_json or not package:
            raise ReceiptError(
                "HEROPROTO_GOOGLE_SERVICE_ACCOUNT_JSON + HEROPROTO_GOOGLE_PACKAGE_NAME required"
            )
        try:
            payload = json.loads(receipt)
        except json.JSONDecodeError as e:
            raise ReceiptError(f"google receipt is not JSON: {e}") from e
        token = payload.get("purchaseToken")
        sku = payload.get("productId")
        if not token or not sku:
            raise ReceiptError("google receipt missing purchaseToken / productId")

        try:
            v = Validator(bundle_id=package, service_account_json=sa_json)
            ok, info = v.verify(token, sku)
        except Exception as e:
            raise ReceiptError(f"google verify failed: {e}") from e
        if not ok:
            raise ReceiptError(f"google verify rejected: {info}")
        order = payload.get("orderId") or info.get("orderId") or token
        if claimed_sku and claimed_sku != sku:
            raise ReceiptError(f"sku mismatch: claimed {claimed_sku!r}, receipt {sku!r}")
        return VerifiedReceipt(
            processor="google", processor_ref=str(order), sku=str(sku),
            raw=info, sandbox=False,
        )


# --- Adapter registry -------------------------------------------------------


_ADAPTERS: dict[str, PaymentAdapter] = {
    "apple": AppleAdapter(),
    "google": GoogleAdapter(),
}


def get_adapter(processor: str) -> PaymentAdapter:
    a = _ADAPTERS.get(processor.lower().strip())
    if a is None:
        raise ReceiptError(f"unknown processor {processor!r}")
    return a


def list_supported_processors() -> list[str]:
    return list(_ADAPTERS.keys())
