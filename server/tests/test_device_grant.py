from __future__ import annotations

from autodoc_server.logic.device_grant import DeviceGrantStore, approve_registration
from autodoc_server.logic.storage import Storage


def test_create_returns_a_pending_registration_with_unique_codes():
    store = DeviceGrantStore()

    a = store.create("cluster-a")
    b = store.create("cluster-b")

    assert a.status == "pending"
    assert a.cluster_name == "cluster-a"
    assert a.device_code != b.device_code
    assert a.user_code != b.user_code


def test_get_by_device_code_and_user_code_find_the_same_registration():
    store = DeviceGrantStore()
    registration = store.create("cluster-a")

    assert store.get_by_device_code(registration.device_code) == registration
    assert store.get_by_user_code(registration.user_code) == registration


def test_get_by_unknown_code_returns_none():
    store = DeviceGrantStore()

    assert store.get_by_device_code("nope") is None
    assert store.get_by_user_code("NOPE-NOPE") is None


def test_approve_sets_status_and_push_token():
    store = DeviceGrantStore()
    registration = store.create("cluster-a")

    updated = store.approve(registration.user_code, push_token="token-123")

    assert updated.status == "approved"
    assert updated.push_token == "token-123"
    assert store.get_by_device_code(registration.device_code).status == "approved"


def test_deny_sets_status_denied_without_a_token():
    store = DeviceGrantStore()
    registration = store.create("cluster-a")

    updated = store.deny(registration.user_code)

    assert updated.status == "denied"
    assert updated.push_token is None


def test_approve_and_deny_unknown_user_code_return_none():
    store = DeviceGrantStore()

    assert store.approve("NOPE-NOPE", push_token="x") is None
    assert store.deny("NOPE-NOPE") is None


def test_is_expired_uses_the_injected_clock():
    clock = {"now": 1000.0}
    store = DeviceGrantStore(ttl_seconds=60, clock=lambda: clock["now"])
    registration = store.create("cluster-a")

    assert store.is_expired(registration) is False

    clock["now"] = 1061.0

    assert store.is_expired(registration) is True


def test_approve_registration_mints_and_persists_a_push_token(tmp_path):
    store = DeviceGrantStore()
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")
    registration = store.create("homelab")

    updated = approve_registration(store, storage, registration.user_code)

    assert updated.status == "approved"
    assert storage.verify_push_token("homelab", updated.push_token)
    assert not storage.verify_push_token("homelab", "wrong-token")


def test_approve_registration_unknown_user_code_returns_none(tmp_path):
    store = DeviceGrantStore()
    storage = Storage(data_dir=tmp_path / "data", docs_dir=tmp_path / "docs_src")

    assert approve_registration(store, storage, "NOPE-NOPE") is None


def test_list_pending_excludes_expired_and_non_pending_registrations():
    clock = {"now": 0.0}
    store = DeviceGrantStore(ttl_seconds=60, clock=lambda: clock["now"])

    to_expire = store.create("to-expire")
    to_approve = store.create("to-approve")
    store.approve(to_approve.user_code, push_token="x")

    clock["now"] = 61.0  # to_expire's TTL (created at t=0) has now passed
    still_pending = store.create("still-pending")  # created after the jump, still fresh

    pending = store.list_pending()

    assert [r.cluster_name for r in pending] == [still_pending.cluster_name]
    assert to_expire.user_code not in {r.user_code for r in pending}
