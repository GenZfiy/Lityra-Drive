import unittest
import os
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

# Importing the service package constructs its app. Keep that import isolated
# from any developer or production database URL.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from app import events


class Bus:
    def __init__(self):
        self.handlers = {}

    def on(self, name, handler):
        self.handlers[name] = handler


class Db:
    @contextmanager
    def session(self):
        yield object()


class NotificationService:
    def __init__(self):
        self.inapp = []
        self.email = []

    def notify_inapp(self, session, **kwargs):
        self.inapp.append(kwargs)

    def notify_email(self, session, **kwargs):
        self.email.append(kwargs)


class InvitationDeliveryTests(unittest.TestCase):
    def test_invitation_fans_out_to_company_staff_with_deduplicated_channels(self):
        bus = Bus()
        service = NotificationService()
        auth = SimpleNamespace(post=lambda *_args, **_kwargs: {"data": [
            {"id": "staff-1", "email": "staff1@example.test", "full_name": "Staff One"},
            {"id": "staff-2", "email": "staff2@example.test", "full_name": "Staff Two"},
        ]})
        with patch.object(events, "ServiceClient", return_value=auth):
            events.register_handlers(bus, Db(), service)
        event = SimpleNamespace(id="event-1", type="drive.participant.invited")
        bus.handlers["drive.participant.invited"]({
            "drive_id": "drive-1", "kind": "company", "participant_ids": ["company-1"],
            "drive_title": "Campus hiring", "organizer_name": "North College",
        }, event)
        self.assertEqual([row["user_id"] for row in service.inapp], ["staff-1", "staff-2"])
        self.assertEqual([row["user_id"] for row in service.email], ["staff-1", "staff-2"])
        self.assertEqual(len({row["dedupe_key"] for row in service.inapp}), 2)
        self.assertEqual(len({row["dedupe_key"] for row in service.email}), 2)
        self.assertTrue(all("Campus hiring" in row["body"] for row in service.email))

    def test_unknown_organization_kind_is_ignored(self):
        bus = Bus()
        service = NotificationService()
        auth = SimpleNamespace(post=lambda *_args, **_kwargs: self.fail("auth should not be queried"))
        with patch.object(events, "ServiceClient", return_value=auth):
            events.register_handlers(bus, Db(), service)
        bus.handlers["drive.participant.invited"]({"kind": "unknown", "participant_ids": ["x"]},
                                                    SimpleNamespace(id="event-2"))
        self.assertEqual(service.inapp, [])
        self.assertEqual(service.email, [])


if __name__ == "__main__":
    unittest.main()
