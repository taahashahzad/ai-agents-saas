"""Firestore transaction helper.

`fn(transaction)` must do ALL reads (`ref.get(transaction=transaction)`) before any writes
(`transaction.set/update/delete/create`) and must not have side effects outside Firestore,
because Firestore may re-run it when it detects contention.
"""
from typing import Callable, TypeVar

from google.cloud import firestore

T = TypeVar("T")


def run_in_transaction(db: firestore.Client, fn: Callable[[firestore.Transaction], T]) -> T:
    @firestore.transactional
    def _run(transaction: firestore.Transaction) -> T:
        return fn(transaction)

    return _run(db.transaction())
