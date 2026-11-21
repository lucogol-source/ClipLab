import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine
import youtube


class MediaTests(unittest.TestCase):
    def test_accepts_normalized_video_links_and_rejects_external_hosts(self):
        for url in ("https://youtu.be/abcdefghijk?t=4", "https://www.youtube.com/shorts/abcdefghijk", "https://m.youtube.com/watch?v=abcdefghijk&list=abc"):
            self.assertEqual(engine.normalize_youtube(url), "https://www.youtube.com/watch?v=abcdefghijk")
        for url in ("http://127.0.0.1/secret", "https://youtube.com.evil.test/watch?v=abcdefghijk", "file:///etc/passwd", "https://youtube.com@evil.test/watch?v=abcdefghijk", "https://youtube.com/playlist?list=abc", "https://youtube.com:443/watch?v=abcdefghijk"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                engine.normalize_youtube(url)

    def test_timestamps_carry_and_subtitles_stay_inside_the_cut(self):
        self.assertEqual(engine.stamp(59.9999), "00:01:00,000")
        segments = [{"start": 5, "end": 9, "text": "Hello world.", "words": [{"start": 5, "end": 6, "word": "Hello"}, {"start": 6, "end": 9, "word": "world."}]}]
        srt, ass = engine.subtitles(segments, 5.5, 8, "karaoke", 720, 1280)
        self.assertIn("00:00:00,000 --> 00:00:02,500", srt)
        self.assertIn("Hello world.", srt)
        self.assertIn("PlayResY: 1280", ass)
        self.assertNotIn("00:00:09", srt)

    def test_proposals_are_bounded_and_dont_duplicate_the_same_passage(self):
        segments = [{"start": i * 5, "end": i * 5 + 4.8, "text": f"Why does idea {i} matter?", "words": []} for i in range(36)]
        clips = engine.propose_clips(segments, 180, 30, 4)
        self.assertGreaterEqual(len(clips), 2)
        for c in clips:
            self.assertGreaterEqual(c["start"], 0)
            self.assertLessEqual(c["end"], 180)
            self.assertGreater(c["end"], c["start"])
        for i, c in enumerate(clips):
            for d in clips[i + 1:]:
                overlap = max(0, min(c["end"], d["end"]) - max(c["start"], d["start"]))
                self.assertLessEqual(overlap, min(c["end"]-c["start"], d["end"]-d["start"]) * .25)


class YouTubeTests(unittest.TestCase):
    def test_upload_uses_explicit_channel_privacy_and_is_idempotent(self):
        clip = {"id": "abc", "exports": [{"file": "sample.mp4"}], "status": "exported"}
        service = MagicMock()
        request = service.videos.return_value.insert.return_value
        request.next_chunk.return_value = (None, {"id": "video123", "status": {"privacyStatus": "private"}})
        with patch.object(youtube, "read_project", return_value={"clips": [clip]}), patch.object(youtube, "project_dir", return_value=Path("/tmp")), patch.object(youtube, "client_for_channel", return_value=service) as channel, patch.object(youtube, "MediaFileUpload"), patch.object(youtube, "check_cancel"), patch.object(youtube, "update_clip"):
            result = youtube.upload_clip("pid", "abc", "channel123", "private", False, "A title", "#Shorts")
            channel.assert_called_once_with("channel123")
            body = service.videos.return_value.insert.call_args.kwargs["body"]
            self.assertEqual(body["status"]["privacyStatus"], "private")
            self.assertIs(body["status"]["selfDeclaredMadeForKids"], False)
            self.assertEqual(result["id"], "video123")
        clip["youtube"] = result
        with patch.object(youtube, "read_project", return_value={"clips": [clip]}), patch.object(youtube, "client_for_channel") as channel, patch.object(youtube,'update_clip') as update:
            self.assertEqual(youtube.upload_clip("pid", "abc", "channel123", "public", False, "Title", ""), result)
            channel.assert_not_called()
            update.assert_called_once_with('pid','abc',status='published',error=None)

    def test_uncertain_upload_is_not_retried(self):
        clip = {"id": "abc", "exports": [{"file": "x.mp4"}], "upload_uncertain": True}
        with patch.object(youtube, "read_project", return_value={"clips": [clip]}), patch.object(youtube, "client_for_channel") as client:
            with self.assertRaisesRegex(ValueError, "incerto"):
                youtube.upload_clip("p", "abc", "c", "private", False, "Title", "")
            client.assert_not_called()

    def test_oauth_does_not_accept_arbitrary_token_servers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "client.json"
            with patch.object(youtube, "CLIENT", path), patch.object(youtube, "TOKEN", Path(folder)/"token.json"):
                youtube.configure({"installed": {"client_id": "abc.apps.googleusercontent.com", "client_secret": "not-a-real-secret", "token_uri": "http://evil.test"}})
                saved = json.loads(path.read_text())
                self.assertEqual(saved["installed"]["token_uri"], "https://oauth2.googleapis.com/token")
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
