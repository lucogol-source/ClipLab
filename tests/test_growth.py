import io
import json
import sys
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundles
import engine
import promotion
import publishing
import server
import tiktok
from test_audit import ProjectFixture

SNAPSHOT = {"status":"fresh","checked_at":1000,"topics":["GTA 6","Champions League"],
            "source":promotion.FEED}


class PromotionTests(unittest.TestCase):
    def test_titles_and_tags_stay_related_and_bounded(self):
        project={"title":"GTA 6: Tommy Vercetti", "options":{"mode":"full"}}
        clip={"start":0,"end":30,"text":"Tommy Vercetti arriva a Vice City. Ecco perché GTA 6 cambia la storia."}
        result=promotion.generate(project,clip,SNAPSHOT,12)
        self.assertIn("Parte 13",result["title"])
        self.assertLessEqual(len(result["title"]),100)
        self.assertIn("#GTA6",result["hashtags"])
        self.assertNotIn("#ChampionsLeague",result["hashtags"])
        self.assertEqual(result["promotion"]["trending_hashtags"],["#GTA6"])
        self.assertIn("#GTA6",result["description"])
        different=promotion.generate({"title":"GTA 5","options":{}},{"text":"GTA 5: un gioco interessante","start":0,"end":30},SNAPSHOT)
        self.assertNotIn("#GTA6",different["hashtags"])
        self.assertLessEqual(len(result["hashtags"]),6)

    def test_rss_age_limit_caching_and_offline_status(self):
        stamp="Thu, 01 Jan 1970 00:16:40 GMT"
        rss=f"<rss><channel><item><title>GTA 6</title><pubDate>{stamp}</pubDate></item><item><title>Vecchio</title><pubDate>Wed, 01 Jan 1969 00:00:00 GMT</pubDate></item></channel></rss>".encode()
        response=Mock(status_code=200)
        response.iter_content.return_value=[rss]
        with patch.object(promotion,"CACHE",None),patch.object(promotion,"RETRY_AT",0),patch.object(promotion.time,"time",return_value=1100),patch.object(promotion.requests,"get") as get:
            get.return_value.__enter__=Mock(return_value=response)
            get.return_value.__exit__=Mock(return_value=False)
            got=promotion.trends()
            self.assertEqual(got["topics"],["GTA 6"])
            self.assertEqual(promotion.trends(),got)
            self.assertEqual(get.call_count,1)
        with patch.object(promotion,"CACHE",None),patch.object(promotion,"RETRY_AT",0),patch.object(promotion.requests,"get",side_effect=promotion.requests.ConnectionError):
            result=promotion.generate({"title":"Podcasts","options":{}},{"text":"Un ospite racconta la sua storia","start":0,"end":30})
            self.assertEqual(result["promotion"]["trend_status"],"unavailable")
            self.assertEqual(result["promotion"]["trending_hashtags"],[])
            self.assertTrue(result["hashtags"])

    def test_description_adds_hashtags_once_within_platform_limits(self):
        result=promotion.description("Titolo #shorts",["#Shorts","#GTA6"])
        self.assertEqual(result.casefold().count("#shorts"),1)
        self.assertTrue(result.endswith("#GTA6"))
        self.assertLessEqual(len(promotion.description("x"*5000,["#Shorts","#GTA6"])),5000)


class BulkDownloadTests(ProjectFixture):
    def setUp(self):
        super().setUp()
        self.filename="clip-"+"a"*12+".mp4"
        folder=engine.project_dir(self.pid)
        (folder/self.filename).write_bytes(b"video")
        (folder/self.filename.replace(".mp4",".srt")).write_text("Sottotitoli")
        engine.update_clip(self.pid,self.cid,title="Titolo #1",description="Descrizione",hashtags=["#Shorts"],
                           edit_revision=0,exports=[{"file":self.filename,"id":"export","settings":{"start":0,"end":20}}])

    def test_zip_contains_selected_video_and_metadata_and_releases_lock(self):
        with bundles.create(self.pid,[self.cid]) as file:
            with zipfile.ZipFile(file) as archive:
                self.assertEqual(archive.testzip(),None)
                names=archive.namelist()
                self.assertEqual(len(names),4)
                self.assertEqual(archive.read(next(n for n in names if n.endswith(".mp4"))),b"video")
                meta=json.loads(archive.read(next(n for n in names if n.endswith(".json"))))
                self.assertIn("#Shorts",meta["description"])
                self.assertEqual(meta["title"],"Titolo #1")
        self.assertNotIn((self.pid,self.cid),engine.BUSY)

    def test_stale_exports_busy_clips_duplicate_ids_and_paths_are_rejected(self):
        with self.assertRaises(ValueError):bundles.create(self.pid,[self.cid,self.cid])
        engine.update_clip(self.pid,self.cid,edit_revision=1)
        with self.assertRaises(ValueError):bundles.create(self.pid,[self.cid])
        engine.update_clip(self.pid,self.cid,edit_revision=0)
        engine.claim_clip(self.pid,self.cid)
        with self.assertRaises(engine.ClipBusy):bundles.create(self.pid,[self.cid])
        engine.release_clip(self.pid,self.cid)
        engine.update_clip(self.pid,self.cid,exports=[{"file":"../project.json","settings":{}}])
        with self.assertRaises(ValueError):bundles.create(self.pid,[self.cid])

    def test_metadata_is_pinned_in_scheduled_payload(self):
        with patch("youtube.connection",return_value={"connected":True,"channel":{"id":"channel"}}):
            publishing.schedule(self.pid,[self.cid],["youtube"],time.time()+60,6,
                                {"approved":True,"youtube_channel":"channel","youtube_privacy":"private","description":"Messaggio"})
        payload=publishing.list_jobs()["jobs"][0]["payload"]
        self.assertEqual(payload["description"],"Messaggio\n\n#Shorts")
        self.assertEqual(payload["hashtags"],["#Shorts"])

    def test_manual_youtube_publish_includes_tags(self):
        with patch("youtube.upload_clip"),patch("server.task") as task:
            server.publish(self.pid,self.cid,server.PublishBody(channel_id="channel",title="Titolo",description="Testo"))
        self.assertEqual(task.call_args.args[-1],"Testo\n\n#Shorts")

    def test_tiktok_caption_includes_selected_hashtags(self):
        response=Mock(status_code=201)
        data={"consent":True,"music_rights":True,"privacy_level":"SELF_ONLY","title":"Titolo forte","hashtags":["#Shorts","#GTA6"]}
        with patch("tiktok.creator_info",return_value={"privacy_level_options":["SELF_ONLY"],"max_video_post_duration_sec":60}),patch("tiktok.request",return_value={"publish_id":"tt","upload_url":"https://upload.tiktokapis.com/file"}) as request,patch("tiktok.requests.put",return_value=response):
            tiktok.publish_clip(self.pid,self.cid,"export",data)
        self.assertEqual(request.call_args.args[1]["post_info"]["title"],"Titolo forte\n\n#Shorts #GTA6")

    def test_editing_description_can_remove_generated_hashtags(self):
        server.save_metadata(self.pid,self.cid,server.MetadataBody(description="Testo #GTA6"))
        saved=engine.read_project(self.pid)["clips"][0]
        self.assertEqual(saved["hashtags"],["#GTA6"])
        with patch("server.task") as task:
            server.publish(self.pid,self.cid,server.PublishBody(channel_id="channel",title="Titolo",description=saved["description"]))
        self.assertNotIn("#Shorts",task.call_args.args[-1])
