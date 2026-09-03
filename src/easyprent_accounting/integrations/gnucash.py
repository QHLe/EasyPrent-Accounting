from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from urllib.parse import quote


class GnuCashIntegrationError(ValueError):
    """Raised when the configured GnuCash book cannot be read."""


@dataclass(frozen=True, slots=True)
class GnuCashAccount:
    guid: str
    name: str
    full_name: str
    parent_guid: str | None


@dataclass(frozen=True, slots=True)
class GnuCashPayment:
    split_guid: str
    transaction_guid: str
    account_guid: str
    booking_date: date
    amount: Decimal
    description: str


class GnuCashReader(Protocol):
    def list_accounts(self, settings: dict) -> list[GnuCashAccount]: ...

    def list_payments(
        self,
        settings: dict,
        account_guids: set[str],
        period_start: date,
        period_end: date,
    ) -> list[GnuCashPayment]: ...


class PiecashGnuCashReader:
    """Read a remote PostgreSQL-backed GnuCash book without changing it."""

    def _open_book(self, settings: dict):
        try:
            import piecash
        except ImportError as error:  # pragma: no cover - exercised in deployment
            raise GnuCashIntegrationError(
                "piecash is not installed; install the server dependencies first"
            ) from error

        required = ("host", "port", "database", "username", "password")
        if any(not settings.get(field) for field in required):
            raise GnuCashIntegrationError("GnuCash connection is not configured")

        sslmode = str(settings.get("sslmode") or "require")
        uri = (
            "postgresql+psycopg2://"
            f"{quote(str(settings['username']), safe='')}:{quote(str(settings['password']), safe='')}@"
            f"{settings['host']}:{int(settings['port'])}/{quote(str(settings['database']), safe='')}"
            f"?sslmode={quote(sslmode, safe='')}"
        )
        try:
            return piecash.open_book(uri_conn=uri, readonly=True)
        except Exception as error:  # piecash exposes several exception classes
            raise GnuCashIntegrationError(f"GnuCash connection failed: {error}") from error

    def list_accounts(self, settings: dict) -> list[GnuCashAccount]:
        book = self._open_book(settings)
        try:
            return sorted(
                [
                    GnuCashAccount(
                        guid=str(account.guid),
                        name=str(account.name),
                        full_name=str(account.fullname),
                        parent_guid=(str(account.parent.guid) if account.parent is not None else None),
                    )
                    for account in book.accounts
                ],
                key=lambda account: account.full_name.casefold(),
            )
        finally:
            book.close()

    def list_payments(
        self,
        settings: dict,
        account_guids: set[str],
        period_start: date,
        period_end: date,
    ) -> list[GnuCashPayment]:
        if not account_guids:
            return []
        bank_account_guid = str(settings.get("bank_account_guid") or "").strip()
        if not bank_account_guid:
            raise GnuCashIntegrationError("GnuCash bank account is not configured")
        book = self._open_book(settings)
        try:
            payments: list[GnuCashPayment] = []
            for account in book.accounts:
                if str(account.guid) not in account_guids:
                    continue
                if account.parent is None:
                    raise GnuCashIntegrationError(
                        "the selected GnuCash NK account must be a subaccount"
                    )
                for split in account.splits:
                    transaction = split.transaction
                    booking_date = transaction.post_date
                    if not period_start <= booking_date <= period_end:
                        continue
                    bank_splits = [
                        transaction_split
                        for transaction_split in transaction.splits
                        if str(transaction_split.account.guid) == bank_account_guid
                    ]
                    if not bank_splits:
                        continue
                    payments.append(
                        GnuCashPayment(
                            split_guid=str(split.guid),
                            transaction_guid=str(transaction.guid),
                            account_guid=str(account.guid),
                            booking_date=booking_date,
                            # The bank split determines the economic direction:
                            # incoming bank money is positive; refunds are negative.
                            amount=sum(
                                (Decimal(str(bank_split.value)) for bank_split in bank_splits),
                                start=Decimal("0"),
                            ),
                            description=str(transaction.description or ""),
                        )
                    )
            return payments
        finally:
            book.close()
