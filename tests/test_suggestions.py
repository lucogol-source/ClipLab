import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import approval
import requests
import suggestions as box

KEY = "a" * 32
META = dict(id=KEY, title="Sottotitoli", description="Sposta più righe.", version="2.2.0", platform="Windows")


def issue():
    return {**approval.issue_content(META), "number":7, "state":"open", "user":{"id":approval.OWNER_ID},
            "url":approval.API+"/issues/7"}


def owner_comment(body, n=1):
    return {"id":n, "body":body, "user":{"id":approval.OWNER_ID,"type":"User","login":"lucogol-source"},
            "author_association":"OWNER","created_at":"2026-11-20T20:00:00Z","updated_at":"2026-11-20T20:00:00Z",
            "issue_url":approval.API+"/issues/7"}


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.issue = issue()
        self.comment = owner_comment(self.issue["body"].split(approval.FOOTER)[-1].strip("`"))

    def test_exact_owner_approval(self):
        result = approval.approved(self.issue, [self.comment])
        self.assertEqual((result["issue"],result["approval_id"]),(7,1))

    def test_proposal_is_never_approval(self):
        self.assertIsNone(approval.approved(self.issue, []))
        for change in ({"user":{"id":33,"type":"User","login":"lucogol-source"}},{"author_association":"MEMBER"},
                       {"performed_via_github_app":{"id":123}},{"updated_at":"changed"},
                       {"issue_url":approval.API+"/issues/8"},{"body":"> " + self.comment["body"]}):
            with self.subTest(change=change):
                self.assertIsNone(approval.approved(self.issue,[{**self.comment,**change}]))

    def test_changed_issue_cannot_reuse_approval(self):
        for change in ({"title":self.issue["title"]+"!"},{"body":"extra\n"+self.issue["body"]},
                       {"pull_request":{}},{"state":"closed"},{"url":"https://api.github.com/repos/other/repo/issues/7"}):
            self.assertIsNone(approval.approved({**self.issue,**change}, [self.comment]))
        rewritten = approval.issue_content({**META, "description":"Proposta diversa"})
        self.assertIsNone(approval.approved({**self.issue, **rewritten}, [self.comment]))

    def test_owner_can_revoke_then_reapprove(self):
        revoked=owner_comment("/cliplab revoca",2)
        self.assertIsNone(approval.approved(self.issue,[revoked,self.comment]))
        result=approval.approved(self.issue,[revoked,self.comment,{**self.comment,"id":3}])
        self.assertEqual(result["approval_id"],3)


class OutboxTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db=Path(tmp.name)/"outbox.sqlite3"
        fake=patch.object(box,"DB",self.db)
        fake.start()
        self.addCleanup(fake.stop)

    def save(self):
        return box.save(KEY,META["title"],META["description"])

    def test_save_once_after_lost_response(self):
        self.save()
        self.save()
        self.assertEqual(len(box.list_items()),1)
        with self.assertRaises(ValueError):
            box.save(KEY,"Diverso","Descrizione")
        with self.assertRaises(ValueError):
            box.save("b"*32,"   ","Descrizione")

    def test_private_submission_platforms(self):
        for win in (True,False):
            key=("c" if win else "d")*32
            with patch.object(box,"is_windows",return_value=win):
                row=box.save(key,"Titolo","Testo")
            self.assertEqual(row["platform"], "Windows" if win else "macOS")
            with patch.object(box,"credentials",return_value={}), patch.object(box.requests,"get") as get, patch.object(box.requests,"post") as post:
                get.return_value.json.return_value={"login":"collaborator"}
                post.return_value=Mock(status_code=201)
                post.return_value.json.return_value={"number":12}
                box.deliver(row)
                self.assertEqual(post.call_args.args,(approval.API+"/issues",))
                self.assertFalse(post.call_args.kwargs["allow_redirects"])
                self.assertEqual(set(post.call_args.kwargs["json"]),{"title","body"})
        self.assertTrue(all(row["number"]==12 and row["state"]=="sent" for row in box.list_items()))

    def test_uncertain_delivery_only_checks_then_recovers(self):
        row=self.save()
        with patch.object(box,"credentials",return_value={}), patch.object(box.requests,"get") as get, patch.object(box.requests,"post",side_effect=requests.Timeout) as post:
            get.return_value.json.return_value={"login":"collaborator"}
            box.deliver(row)
            check=box.list_items()[0]
            self.assertEqual(check["state"],"checking")
            with self.assertRaises(ValueError):
                box.resend(KEY)
            get.return_value.json.return_value={"items":[{**issue(),"repository_url":approval.API,
                                                        "user":{"login":"collaborator"}}]}
            box.deliver(check)
            self.assertEqual(post.call_count,1)
            self.assertEqual(box.list_items()[0]["number"],7)

    def test_rejected_and_disconnected_preserve_submission(self):
        row=self.save()
        with patch.object(box,"credentials",side_effect=ValueError(box.AUTH_HELP)):
            box.tick()
        self.assertEqual(box.list_items()[0]["detail"],box.AUTH_HELP)
        with patch.object(box,"credentials",return_value={}), patch.object(box.requests,"get") as get, patch.object(box.requests,"post",return_value=Mock(status_code=403)):
            get.return_value.json.return_value={"login":"reader"}
            box.deliver(row)
        self.assertEqual(box.list_items()[0]["state"],"queued")

    def test_bridge_claim_and_confirm(self):
        (self.db.parent/"suggestions-via-codex").touch()
        self.assertEqual(self.save()["state"],"handoff")
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs=[job for job in pool.map(lambda _:box.bridge_next(), range(3)) if job]
        self.assertEqual([j["action"] for j in jobs],["create"])
        self.assertFalse(box.tick())
        box.retry(KEY)
        self.assertEqual(box.bridge_next()["action"],"find")
        with self.assertRaises(ValueError):
            box.bridge_confirm(KEY,{**issue(),"url":"https://other.example/issues/7"})
        box.bridge_confirm(KEY,issue())
        self.assertEqual(box.list_items()[0]["state"],"sent")
        self.assertIsNone(box.bridge_next())

    def test_only_explicit_retry_can_repost_after_missing_receipt(self):
        self.save()
        box.update(KEY,"checking",box.NO_RECEIPT)
        self.assertFalse(box.via_codex())
        box.resend(KEY)
        self.assertEqual(box.list_items()[0]["state"],"queued")
