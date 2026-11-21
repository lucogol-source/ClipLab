"""Caption edge cases and shared frontend regression checks."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import captions
import server


class CaptionSlicingTests(unittest.TestCase):
    def test_untimed_caption_is_split_into_text_fragments(self):
        for words in ([],None):
            cue={'start':0,'end':4,'text':'uno due tre sei','words':words}
            left=captions.slice_cue(cue,0,2)
            right=captions.slice_cue(cue,2,4)
            self.assertEqual(left['text'],'uno due')
            self.assertEqual(right['text'],'tre sei')
            self.assertTrue(left['timing_estimated'])
            self.assertTrue(all(0 <= w['start'] < w['end'] <= 2 for w in left['words']))

    def test_unequal_untimed_words_do_not_keep_the_whole_phrase_at_half_cut(self):
        cue={'start':0,'end':10,'text':'Testo corretto.','words':[]}
        self.assertEqual(captions.slice_cue(cue,0,5)['text'],'Testo')
        self.assertEqual(captions.slice_cue(cue,5,10)['text'],'corretto.')

    def test_untrimmed_caption_preserves_its_text(self):
        cue={'start':0,'end':4,'text':'Testo senza tempi per parola.','words':[]}
        full=captions.slice_cue(cue,0,4)
        self.assertEqual(full['text'],cue['text'])
        self.assertEqual(full['words'],[])

    def test_cut_in_word_gap_does_not_resurrect_the_full_sentence(self):
        cue={'start':0,'end':4,'text':'uno due','words':[{'word':'uno','start':0,'end':1},{'word':'due','start':3,'end':4}]}
        self.assertIsNone(captions.slice_cue(cue,1,3))
        changes=captions.store_track({'caption_cues':[cue],'caption_ranges':[[0,4]]},[],0,1)
        self.assertTrue(all(c is not None for c in changes['caption_cues']))

    def test_estimated_timings_survive_save_and_can_be_rendered(self):
        part=captions.slice_cue({'start':0,'end':4,'text':'uno due tre sei'},0,2)
        saved=captions.validate_cues([part],4)
        self.assertTrue(saved[0]['timing_estimated'])
        srt,_=captions.render(saved,0,2,720,1280)
        self.assertIn('uno due',srt)
        self.assertNotIn('tre sei',srt)


class HeaderTests(unittest.TestCase):
    def test_free_badge_and_version_are_present_on_both_platforms(self):
        for windows in (False,True):
            with self.subTest(windows=windows),patch('server.is_windows',return_value=windows):
                html=server.index().body.decode('utf-8')
                self.assertIn('id="free-status">100% gratuito',html)
                self.assertIn('id="app-version">V'+server.VERSION,html)
                self.assertIn('/static/app.js?v='+server.VERSION,html)
                self.assertIn('/static/style.css?v='+server.VERSION,html)
                self.assertIn('Avvia ClipLab.'+('cmd' if windows else 'command'),html)


if __name__=='__main__':unittest.main()
