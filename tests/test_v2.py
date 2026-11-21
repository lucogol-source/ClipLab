import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from urllib.parse import parse_qs,urlparse
import hashlib

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import captions
import framing
import publishing
import tiktok


class CaptionTests(unittest.TestCase):
    def test_current_word_highlight_and_edit_alignment(self):
        cues=captions.validate_cues([{"start":10,"end":12,"text":"Liberty City","words":[]}],20)
        self.assertEqual(cues[0]["words"][-1]["end"],12)
        srt,ass=captions.render(cues,10,12,1080,1920)
        self.assertIn('00:00:00,000 --> 00:00:02,000',srt)
        events=[l for l in ass.splitlines() if l.startswith('Dialogue:')]
        self.assertEqual(len(events),2)
        self.assertTrue(all(line.count('\\1c&H5fffd3&')==1 for line in events))
        self.assertIn('Liberty City',srt)

    def test_bad_or_overlapping_timings_are_rejected(self):
        with self.assertRaises(ValueError):captions.validate_cues([{"start":0,"end":2,"text":"a"},{"start":1,"end":3,"text":"b"}],10)
        with self.assertRaises(ValueError):captions.validate_cues([{"start":0,"end":float('nan'),"text":"a"}],10)

    def test_long_sentence_is_split_into_readable_cues(self):
        segments=[{"start":0,"end":8,"text":"Una frase molto lunga con tanti termini deve essere divisa per essere leggibile sul telefono."}]
        cues=captions.make_cues(segments,0,8)
        self.assertGreater(len(cues),2)
        self.assertTrue(all(len(c['text'].split())<=5 for c in cues))


class FramingTests(unittest.TestCase):
    def test_crop_never_leaves_source_at_extreme_pan_and_zoom(self):
        for sw,sh in ((1920,1080),(720,1280)):
            for x in (0,50,100):
                for y in (0,50,100):
                    for zoom in (1,2,3):
                        a,b,w,h=framing.crop_rect(sw,sh,1080,1920,{"x":x,"y":y,"zoom":zoom})
                        self.assertGreaterEqual(a,0);self.assertGreaterEqual(b,0)
                        self.assertLessEqual(a+w,sw+.001);self.assertLessEqual(b+h,sh+.001)

    def test_fit_preserves_the_whole_picture_and_split_shows_both_sides(self):
        image=np.zeros((100,200,3),np.uint8);image[:,:100]=(0,0,255);image[:,100:]=(255,0,0)
        split=framing.compose(image,100,200,{"layout":"split","split_left":0,"split_right":100,"zoom":1},0)
        self.assertTrue(np.all(split[40,50]==(0,0,255)))
        self.assertTrue(np.all(split[150,50]==(255,0,0)))
        fit=framing.compose(image,100,200,{"layout":"fit"},0)
        self.assertTrue(np.all(fit[0,0]==0))
        self.assertTrue(np.all(fit[100,5]==(0,0,255)))
        self.assertTrue(np.all(fit[100,95]==(255,0,0)))

    def test_motion_interpolates_without_an_abrupt_center_jump(self):
        points=[{"t":0,"x":0,"y":30,"zoom":1},{"t":2,"x":100,"y":50,"zoom":2}]
        mid=framing.interpolate(points,1,{})
        self.assertAlmostEqual(mid['x'],50);self.assertAlmostEqual(mid['zoom'],1.5)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.db=patch.object(publishing,'DB',Path(self.directory.name)/'queue.db');self.db.start()
        self.project={"id":"p","clips":[{"id":"c","title":"Clip","edit_revision":2,"exports":[{"id":"e","file":"a.mp4","edit_revision":2,"settings":{"start":0,"end":20}}]}]}
        self.meta={"approved":True,"youtube_channel":"ch","youtube_privacy":"private"}
    def tearDown(self):self.db.stop();self.directory.cleanup()

    def enqueue(self):
        with patch('engine.read_project',return_value=self.project),patch('youtube.connection',return_value={"connected":True,"channel":{"id":"ch"}}):
            return publishing.schedule('p',['c'],['youtube'],time.time()+5,6,self.meta)

    def test_queue_persists_and_edited_clip_is_blocked(self):
        self.enqueue();job=publishing.list_jobs()['jobs'][0]
        with publishing.database() as c:c.execute("UPDATE jobs SET scheduled=0")
        self.project['clips'][0]['edit_revision']=3
        with patch('engine.read_project',return_value=self.project),patch('youtube.upload_clip') as upload:
            publishing.tick();upload.assert_not_called()
        self.assertEqual(publishing.list_jobs()['jobs'][0]['status'],'blocked')

    def test_duplicate_schedule_is_rejected_and_pause_survives_reload(self):
        self.enqueue()
        with self.assertRaises(ValueError):self.enqueue()
        publishing.pause(True)
        self.assertTrue(publishing.list_jobs()['paused'])

    def test_overdue_batch_does_not_post_in_a_burst(self):
        self.assertFalse(publishing.eligible({'scheduled':0,'spacing':21600},time.time()-60,time.time()))
        self.assertTrue(publishing.eligible({'scheduled':0,'spacing':21600},None,time.time()))

    def test_tiktok_rejection_stops_polling_and_does_not_reupload(self):
        self.enqueue()
        with publishing.database() as c:
            c.execute("UPDATE jobs SET platform='tiktok',status='processing',result=?",(json.dumps({'publish_id':'post-1'}),))
        with patch('engine.read_project',return_value=self.project),patch('tiktok.request',return_value={'status':'FAILED','fail_reason':'spam_risk'}),patch('tiktok.publish_clip') as upload:
            publishing.tick()
            publishing.tick()
            upload.assert_not_called()
        job=publishing.list_jobs()['jobs'][0]
        self.assertEqual(job['status'],'failed')
        self.assertIn('spam_risk',job['error'])


class TikTokTests(unittest.TestCase):
    def test_desktop_pkce_uses_sha256_hex_and_state(self):
        with tempfile.TemporaryDirectory() as folder:
            client=Path(folder)/'client.json';client.write_text(json.dumps({'client_key':'test'}))
            with patch.object(tiktok,'CLIENT',client):
                url=tiktok.auth_url('http://127.0.0.1:8765')
                query=parse_qs(urlparse(url).query);pending=tiktok.PENDING[query['state'][0]]
                self.assertEqual(query['code_challenge'][0],hashlib.sha256(pending['verifier'].encode()).hexdigest())

    def test_privacy_and_per_video_consent_are_required(self):
        info={'privacy_level_options':['SELF_ONLY'],'max_video_post_duration_sec':60}
        with self.assertRaises(ValueError):tiktok.validate_post(info,{'consent':True,'music_rights':True,'privacy_level':'PUBLIC_TO_EVERYONE'},30)
        with self.assertRaises(ValueError):tiktok.validate_post(info,{'privacy_level':'SELF_ONLY'},30)
        with self.assertRaises(ValueError):tiktok.validate_post(info,{'consent':'false','music_rights':True,'privacy_level':'SELF_ONLY'},30)
        tiktok.validate_post(info,{'consent':True,'music_rights':True,'privacy_level':'SELF_ONLY'},30)


if __name__=='__main__':unittest.main()
