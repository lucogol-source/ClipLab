"""Regression cases for the correctness audit. No remote uploads or model downloads."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import captions
import engine
import launch
import prepare_models
import publishing
import server
import tiktok
import youtube
from version import VERSION


class CaptionAudit(unittest.TestCase):
    def setUp(self):
        self.project={'segments':[{'start':0,'end':10,'text':'Vecchio testo.'},{'start':10,'end':20,'text':'Nuovo testo.'}]}
        self.cue={'id':'edited','start':0,'end':10,'text':'Testo corretto.','words':[]}

    def test_longer_cut_gets_source_captions_without_losing_corrections(self):
        for metadata in ({},{'caption_ranges':[[0,10]]}):
            with self.subTest(metadata=metadata):
                clip={'start':0,'end':20,'caption_cues':[self.cue],**metadata}
                cues=captions.track(self.project,clip,0,20)
                srt,_=captions.render(cues,0,20,1080,1920)
                self.assertIn('Testo corretto.',srt)
                self.assertIn('Nuovo testo.',' '.join(c['text'] for c in cues))
                self.assertIn('00:00:10,000',srt)
                self.assertNotIn('Vecchio testo.',srt)

    def test_intentionally_deleted_captions_stay_deleted_in_reviewed_range(self):
        clip={'start':0,'end':20,'caption_cues':[],'caption_ranges':[[0,10]]}
        cues=captions.track(self.project,clip,0,20)
        self.assertTrue(cues)
        self.assertTrue(all(c['start']>=10 for c in cues))

    def test_save_after_extending_does_not_mark_unseen_part_as_deleted(self):
        clip={'start':0,'end':20,'caption_cues':[self.cue],'caption_ranges':[[0,10]]}
        changes=captions.store_track(clip,[dict(self.cue,text='Ulteriore correzione.')],0,10)
        clip.update(changes)
        result=captions.track(self.project,clip,0,20)
        self.assertEqual(result[0]['text'],'Ulteriore correzione.')
        self.assertIn('Nuovo testo.',' '.join(c['text'] for c in result))

    def test_editing_shorter_range_retains_saved_text_outside_it(self):
        clip={'start':0,'end':20,'caption_cues':[self.cue],'caption_ranges':[[0,10]]}
        track=captions.store_track(clip,[],5,10)
        self.assertEqual(track['caption_cues'][0]['end'],5)
        self.assertEqual(track['caption_ranges'],[[0,10]])


class ProjectFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name)
        projects=self.folder/'projects';projects.mkdir()
        for target,value in (('engine.PROJECTS',projects),('engine.DATA',self.folder),('publishing.DB',self.folder/'queue.sqlite3')):
            p=patch(target,value);p.start();self.addCleanup(p.stop)
        self.addCleanup(self.temp.cleanup)
        engine.BUSY.clear();engine.EVENTS.clear();engine.ANALYZING.clear()
        self.addCleanup(engine.BUSY.clear);self.addCleanup(engine.EVENTS.clear);self.addCleanup(engine.ANALYZING.clear)
        self.options={'duration':30,'count':2,'format':'9:16','captions':'karaoke','auto_publish':False,'channel_id':'channel','privacy':'private'}
        self.p=engine.new_project(self.options,'Test audit')
        self.pid=self.p['id'];self.cid='auditclip'
        self.clip={'id':self.cid,'title':'Clip','start':0,'end':20,'status':'exported','exports':[{'id':'export','file':'test.mp4','edit_revision':0,'settings':{'start':0,'end':20}}],'edit_revision':0}
        engine.update(self.pid,status='ready',duration=60,source_file='source.mp4',clips=[self.clip])

    def current(self):return engine.read_project(self.pid)['clips'][0]
    def enqueue(self):
        with patch('youtube.connection',return_value={'connected':True,'channel':{'id':'channel'}}):
            publishing.schedule(self.pid,[self.cid],['youtube'],__import__('time').time()+5,6,{'approved':True,'youtube_channel':'channel','youtube_privacy':'private'})
        with publishing.database() as c:c.execute('UPDATE jobs SET scheduled=0')


class AnalysisAudit(ProjectFixture):
    def test_cancelled_analysis_clears_cancellation_before_later_tasks(self):
        engine.EVENTS[self.pid].set()
        engine.analyze(self.pid)
        self.assertEqual(engine.read_project(self.pid)['status'],'cancelled')
        self.assertNotIn(self.pid,engine.EVENTS)
        engine.check_cancel(self.pid)

    def test_success_and_failure_clear_cancellation_and_bound_silent_title(self):
        for failure in (False,True):
            with self.subTest(failure=failure):
                engine.EVENTS[self.pid]=threading.Event()
                engine.update(self.pid,title='a'*150)
                meta={'duration':60,'width':640,'height':360,'has_audio':False}
                with patch('engine.probe',side_effect=RuntimeError('bad video') if failure else None,return_value=meta),patch('engine.run'):
                    engine.analyze(self.pid)
                p=engine.read_project(self.pid)
                self.assertEqual(p['status'],'error' if failure else 'ready')
                self.assertNotIn(self.pid,engine.EVENTS)
                if not failure:
                    self.assertEqual(len(p['clips'][0]['title']),100)
                    server.ExportBody(start=0,end=30,title=p['clips'][0]['title'])

    def test_automatic_flow_continues_after_each_clip_failure(self):
        for failing_stage in ('render','upload'):
            with self.subTest(stage=failing_stage):
                clips=[dict(self.clip,id='first'),dict(self.clip,id='second')]
                engine.update(self.pid,options=dict(self.options,auto_publish=True))
                counters={'render':0,'upload':0}
                def render(pid,cid,settings):
                    counters['render']+=1
                    if failing_stage=='render' and cid=='first':raise RuntimeError('render failed')
                def upload(pid,cid,*args):
                    counters['upload']+=1
                    if failing_stage=='upload' and cid=='first':raise RuntimeError('upload failed')
                    engine.update_clip(pid,cid,status='published')
                with patch('engine.probe',return_value={'duration':60,'width':640,'height':360,'has_audio':False}),patch('engine.run'),patch('engine.propose_clips',return_value=clips),patch('engine.render',side_effect=render),patch('youtube.upload_clip',side_effect=upload):
                    engine.analyze(self.pid)
                result=engine.read_project(self.pid)
                self.assertEqual(result['status'],'ready')
                self.assertEqual(result['clips'][1]['status'],'published')
                self.assertEqual(counters['render'],2)
                self.assertEqual(counters['upload'],2 if failing_stage=='upload' else 1)
                self.assertEqual(result['auto_publish_errors'][0]['clip_id'],'first')

    def test_cancelled_automatic_upload_does_not_continue(self):
        engine.update(self.pid,options=dict(self.options,auto_publish=True))
        def upload(*args):
            engine.EVENTS[self.pid].set()
            raise RuntimeError('wrapped cancellation')
        clips=[dict(self.clip,id='first'),dict(self.clip,id='second')]
        with patch('engine.probe',return_value={'duration':60,'width':640,'height':360,'has_audio':False}),patch('engine.run'),patch('engine.propose_clips',return_value=clips),patch('engine.render') as render,patch('youtube.upload_clip',side_effect=upload):
            engine.analyze(self.pid)
        self.assertEqual(engine.read_project(self.pid)['status'],'cancelled')
        self.assertEqual(render.call_count,1)
        self.assertNotIn(self.pid,engine.EVENTS)


class PublishingAudit(ProjectFixture):
    def test_republish_is_rejected_before_queueing(self):
        engine.update_clip(self.pid,self.cid,status='published',youtube={'id':'remote'})
        body=server.PublishBody(channel_id='channel',title='Clip')
        with patch.object(server.POOL,'submit') as submit:
            with self.assertRaises(server.HTTPException) as error:server.publish(self.pid,self.cid,body)
            self.assertEqual(error.exception.status_code,409)
            submit.assert_not_called()
        self.assertEqual(self.current()['status'],'published')

    def test_idle_stop_and_old_cancellation_do_not_poison_scheduled_upload(self):
        self.enqueue();engine.cancel_project(self.pid)
        engine.EVENTS[self.pid]=threading.Event();engine.EVENTS[self.pid].set()
        def upload(pid,cid,*args):
            engine.check_cancel(pid)
            engine.update_clip(pid,cid,status='published')
            return {'id':'remote'}
        with patch('youtube.upload_clip',side_effect=upload):publishing.tick()
        self.assertEqual(publishing.list_jobs()['jobs'][0]['status'],'published')
        self.assertFalse(engine.BUSY)
        self.assertNotIn(self.pid,engine.EVENTS)

    def test_scheduler_waits_for_export_then_uploads(self):
        self.enqueue();engine.claim_clip(self.pid,self.cid)
        engine.update_clip(self.pid,self.cid,status='rendering')
        with patch('youtube.upload_clip',return_value={'id':'remote'}) as upload:
            publishing.tick();upload.assert_not_called()
            self.assertEqual(publishing.list_jobs()['jobs'][0]['status'],'queued')
            engine.update_clip(self.pid,self.cid,status='exported');engine.release_clip(self.pid,self.cid)
            publishing.tick();upload.assert_called_once()
        self.assertFalse(engine.BUSY)

    def test_upload_reservation_blocks_editor_and_duplicate_worker(self):
        self.enqueue();entered=threading.Event();finish=threading.Event()
        def upload(*args):
            entered.set()
            if not finish.wait(3):raise RuntimeError('test timed out')
            return {'id':'remote'}
        with patch('youtube.upload_clip',side_effect=upload) as uploader:
            worker=threading.Thread(target=publishing.tick);worker.start()
            try:
                self.assertTrue(entered.wait(2))
                with self.assertRaises(server.HTTPException) as error:
                    server.draft(self.pid,self.cid,server.ExportBody(start=0,end=20,title='Changed'))
                self.assertEqual(error.exception.status_code,409)
                with self.assertRaises(engine.ClipBusy):server.task(self.pid,self.cid,lambda *args:None)
                publishing.tick()
            finally:finish.set();worker.join(3)
            self.assertFalse(worker.is_alive());uploader.assert_called_once()
        self.assertEqual(self.current()['title'],'Clip')
        self.assertFalse(engine.BUSY)

    def test_rejected_transcription_does_not_invalidate_schedule(self):
        self.enqueue()
        with patch.object(server.POOL,'submit',side_effect=RuntimeError('executor stopped')):
            with self.assertRaises(RuntimeError):server.transcribe_clip(self.pid,self.cid,server.TranscribeBody())
        self.assertEqual(publishing.list_jobs()['jobs'][0]['status'],'queued')
        self.assertEqual(self.current()['status'],'exported')
        self.assertFalse(engine.BUSY)

    def test_sibling_task_does_not_clear_in_progress_cancellation(self):
        other=dict(self.clip,id='other')
        engine.update(self.pid,clips=[self.clip,other])
        engine.claim_clip(self.pid,self.cid);engine.EVENTS[self.pid].set()
        engine.claim_clip(self.pid,'other')
        with self.assertRaises(engine.Cancelled):engine.check_cancel(self.pid)
        engine.release_clip(self.pid,self.cid)
        with self.assertRaises(engine.Cancelled):engine.check_cancel(self.pid)
        engine.release_clip(self.pid,'other');engine.check_cancel(self.pid)

    def test_tiktok_success_preserves_youtube_published_state(self):
        engine.update_clip(self.pid,self.cid,status='published',youtube={'id':'yt'})
        (engine.project_dir(self.pid)/'test.mp4').write_bytes(b'video')
        metadata={'consent':True,'music_rights':True,'privacy_level':'SELF_ONLY'}
        response=MagicMock(status_code=201)
        with patch('tiktok.creator_info',return_value={'privacy_level_options':['SELF_ONLY'],'max_video_post_duration_sec':60}),patch('tiktok.request',return_value={'publish_id':'tt','upload_url':'https://upload.tiktokapis.com/file'}),patch('tiktok.requests.put',return_value=response):
            result=tiktok.publish_clip(self.pid,self.cid,'export',metadata)
        self.assertEqual(result['status'],'processing')
        self.assertEqual(self.current()['status'],'published')


class DownloadAudit(unittest.TestCase):
    def response(self,status,data=b'',headers=None):
        r=MagicMock(status_code=status,headers=headers or {})
        r.__enter__.return_value=r;r.iter_content.return_value=[data]
        return r

    def download(self,partial,expected,responses,sha=True):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'model.bin';path.with_suffix('.bin.part').write_bytes(partial)
            session=MagicMock();session.get.side_effect=responses
            with patch('prepare_models.requests.Session',return_value=session),patch('prepare_models.time.sleep'):
                prepare_models.download('https://example.test/model',path,hashlib.sha256(expected).hexdigest() if sha else None)
            self.assertEqual(path.read_bytes(),expected)
            self.assertFalse(path.with_suffix('.bin.part').exists())
            return session

    def test_complete_part_after_416_is_promoted_with_checksum(self):
        self.download(b'complete',b'complete',[self.response(416,headers={'Content-Range':'bytes */8'})])

    def test_corrupt_or_oversize_part_after_416_restarts_without_range(self):
        session=self.download(b'bad file!',b'correct',[self.response(416,headers={'Content-Range':'bytes */9'}),self.response(200,b'correct',{'Content-Length':'7'})])
        self.assertEqual(session.get.call_args_list[1].kwargs['headers'],{})

    def test_complete_part_without_checksum_uses_total_size(self):
        self.download(b'complete',b'complete',[self.response(416,headers={'Content-Range':'bytes */8'})],sha=False)

    def test_model_paths_follow_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            for extra,expected in (({},str(Path(temp)/'models')),({'CLIPLAB_MODELS_DIR':str(Path(temp)/'custom')},str(Path(temp)/'custom'))):
                env=dict(os.environ,CLIPLAB_DATA_DIR=temp,**extra)
                if not extra:env.pop('CLIPLAB_MODELS_DIR',None)
                output=subprocess.check_output([sys.executable,'-c','import prepare_models; print(prepare_models.MODELS)'],env=env,cwd=Path(__file__).resolve().parents[1],text=True)
                self.assertEqual(output.strip(),str(Path(expected).resolve()))


class VersionAndLaunchAudit(unittest.TestCase):
    def test_frontend_and_health_use_single_version(self):
        self.assertEqual(server.health()['version'],VERSION)
        html=server.index().body.decode()
        self.assertIn('V'+VERSION,html)
        self.assertNotIn('__CLIPLAB_VERSION__',html)

    def test_other_copy_on_8765_uses_free_alternate(self):
        other={'application':'cliplab','app_root':'/other/copy','version':'2.0','instance_id':'other'}
        self.select({8765:other},8768)

    def test_owned_future_version_is_reused_at_existing_port(self):
        own={'application':'cliplab','app_root':str(launch.ROOT),'data_dir':str(launch.DATA),'version':'9.5.1','instance_id':'ours'}
        for port in range(8768,8779):
            with self.subTest(port=port):self.select({8765:{'application':'other'},port:own},port)

    def test_same_installation_with_other_data_directory_is_not_owned(self):
        info={'application':'cliplab','app_root':str(launch.ROOT),'data_dir':str(launch.DATA/'other'),'instance_id':'other'}
        self.assertFalse(launch.owns_server(info))

    def select(self,states,expected):
        with patch.dict(os.environ),patch.object(launch,'PORT',8765),patch.object(launch,'URL',''),patch.object(launch,'RECORD',Path('/tmp/unused')),patch.object(launch,'health',side_effect=lambda port:states.get(port)),patch.object(launch,'port_available',return_value=True):
            launch.select_port()
            self.assertEqual(launch.PORT,expected)
            self.assertEqual(launch.RECORD.name,f'server-{expected}.json')


if __name__=='__main__':unittest.main()
