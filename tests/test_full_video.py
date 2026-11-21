import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine
import server
from test_audit import ProjectFixture


class FullVideoTests(unittest.TestCase):
    def test_thirty_minutes_produces_thirty_editable_minutes(self):
        clips = engine.split_full_video([], 1800, 60, "Video")
        self.assertEqual(len(clips), 30)
        self.assertEqual([(c["start"],c["end"]) for c in clips], [(i*60,(i+1)*60) for i in range(30)])
        self.assertEqual(len({c["id"] for c in clips}),30)
        for c in clips:
            server.ExportBody(start=c["start"],end=c["end"],title=c["title"])

    def test_covers_silence_remainder_and_long_titles(self):
        for duration in (17,1801,1800.01,7200):
            for target in (30,45,60,90,120,180):
                clips=engine.split_full_video([{"start":80,"end":90,"text":"Parlato"}],duration,target,"x"*150)
                self.assertEqual(clips[0]["start"],0)
                self.assertEqual(clips[-1]["end"],duration)
                self.assertTrue(all(a["end"]==b["start"] for a,b in zip(clips,clips[1:])))
                for c in clips:
                    self.assertLessEqual(c["end"]-c["start"],target)
                    self.assertGreaterEqual(c["end"]-c["start"],.5)
                    server.ExportBody(start=c["start"],end=c["end"],title=c["title"])
        self.assertEqual(engine.split_full_video([],125,60,"Video")[-1]["end"],125)

    def test_mode_is_explicit_and_backwards_compatible(self):
        self.assertEqual(server.Options().mode,"highlights")
        self.assertEqual(server.ImportBody(url="url",mode="full",duration=120).mode,"full")


class FullVideoAnalysisTests(ProjectFixture):
    def test_normal_analysis_uses_full_split_including_silence(self):
        for audio in (False,True):
            engine.update(self.pid,options={**self.options,"mode":"full","duration":60})
            with patch('engine.probe',return_value={"duration":1800,"width":640,"height":360,"has_audio":audio}),patch('engine.run'),patch('engine.transcript',return_value=([{"start":80,"end":90,"text":"Parlato"}],"it")):
                engine.analyze(self.pid)
            project=engine.read_project(self.pid)
            self.assertEqual(project["status"],"ready")
            self.assertEqual(len(project["clips"]),30)
            self.assertEqual(project["clips"][-1]["end"],1800)
            if audio:
                self.assertEqual(project["clips"][1]["text"],"Parlato")
            else:
                self.assertTrue(project["notice"])
