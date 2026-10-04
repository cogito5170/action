import unittest

from action import AUTHOR_KINDS, ActionIntent, ContractError
from tests.test_forms import intent


def peer(**kw):
    d = dict(author_kind="peer", msg_id="msg-0123456789abcdef")
    d.update(kw)
    return intent(**d)


class PeerIntent(unittest.TestCase):
    def test_kind_exists(self):
        self.assertIn("peer", AUTHOR_KINDS)

    def test_refused_without_msg_id(self):
        for bad in (None, "", " "):
            with self.assertRaises(ContractError):
                peer(msg_id=bad)

    def test_refused_without_dc_id(self):
        for bad in ("", None):
            with self.assertRaises(ContractError):
                peer(dc_id=bad)

    def test_refused_without_used_keys(self):
        with self.assertRaises(ContractError):
            peer(used_keys=[])

    def test_accepted_and_roundtrips(self):
        p = peer()
        self.assertEqual(p.to_dict()["msg_id"], "msg-0123456789abcdef")
        self.assertEqual(ActionIntent.from_dict(p.to_dict()), p)
        self.assertNotEqual(p.id, peer(msg_id="msg-other").id)

    def test_msg_id_only_for_peer(self):
        with self.assertRaises(ContractError):
            intent(msg_id="msg-1")

    def test_old_intents_unchanged(self):
        self.assertNotIn("msg_id", intent().to_dict())


if __name__ == "__main__":
    unittest.main()
