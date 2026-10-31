import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from media_canvas import Media,cover_surface

class FakePlayer:
    def __init__(self):
        self.data=dict(bus='test',title='歌名',artist='歌手',playing=True,position=40,length=100,stamp=time.monotonic())
        self.commands=[]
    def command(self,value):self.commands.append(value)

class MediaTests(unittest.TestCase):
    def test_real_spectrum_smoothing_pause_decay_and_commands(self):
        p=FakePlayer();m=Media(p);now=time.time()
        value={'spectrum':[.8]*20,'stamp':now,'command_serial':0}
        with patch('media_canvas.read',return_value=value):
            m.step(.016,now)
            self.assertTrue(all(0<x<.8 for x in m.bands))
            value['command_serial']=1;value['command']='PlayPause'
            m.step(.016,now);m.step(.016,now)
            self.assertEqual(p.commands,['PlayPause'])
            p.data['playing']=False
            for _ in range(100):m.step(.016,now)
            self.assertLess(max(m.bands),.001)

    def test_native_frame_bounds_and_metadata_transition(self):
        p=FakePlayer();m=Media(p)
        with patch('media_canvas.read',return_value={}):m.step(.016,time.time())
        with patch('media_canvas.save'):
            width,pixels=m.paint()
        self.assertEqual(len(pixels),width*2*28*2*4)
        self.assertEqual(pixels[3],0) # corner stays transparent
        old=m.current
        p.data=p.data|{'title':'新歌标题特别长'*20}
        with patch('media_canvas.read',return_value={}):m.step(.016,time.time())
        self.assertEqual(m.previous,old)
        self.assertLessEqual(m.motion.target,360)
        self.assertIsNone(cover_surface('https://example.com/cover.jpg'))

if __name__=='__main__':unittest.main()

class PanelTests(unittest.TestCase):
    def test_seek_is_normalized_clamped_and_only_commits_on_release(self):
        from media_panel import Controls
        p=Controls();p.data=dict(can_seek=True,length=100)
        base=dict(session=1,seq=1,down_serial=0,released_serial=0,pressed=False,x=0,y=0)
        p.input(base)
        with patch('media_panel.deliver') as save:
            p.input(base|dict(seq=2,down_serial=1,down_x=24/368,down_y=305/460,pressed=True,x=.5,y=305/460))
            self.assertEqual(save.call_count,0)
            self.assertAlmostEqual(p.preview,.5)
            p.input(base|dict(seq=3,down_serial=1,released_serial=1,up_x=1,up_y=305/460))
            self.assertEqual(save.call_args.args[0]['action'],'SetPosition')
            self.assertEqual(save.call_args.args[0]['value'],100)
            p.input(base|dict(seq=4,down_serial=1,released_serial=1))
            self.assertEqual(save.call_count,1)

    def test_cancelled_drag_and_unseekable_live_do_not_send(self):
        from media_panel import Controls
        p=Controls();p.data=dict(can_seek=True,length=100)
        base=dict(session=1,seq=1,down_serial=0,released_serial=0,pressed=False,x=0,y=0)
        p.input(base)
        with patch('media_panel.deliver') as save:
            p.input(base|dict(seq=2,down_serial=1,down_x=.5,down_y=305/460,pressed=True))
            p.input(base|dict(seq=3,down_serial=1,released_serial=1,cancelled=True))
            self.assertEqual(save.call_count,0)

    def test_panel_image_bounds_rounding_and_control_targets(self):
        from media_panel import Controls
        p=Controls();p.changed-=1;p.content_changed-=1
        p.data=dict(title='真实播放标题',artist='歌手',playing=False,length=100,position=20,volume=.5,can_seek=True)
        width,pixels=p.paint()
        self.assertEqual(len(pixels),368*2*460*2*4)
        self.assertEqual(pixels[3],0)
        self.assertEqual([box[4] for box in p.hitboxes],['chooser:toggle','Previous','PlayPause','Next'])

class ResponsivenessTests(unittest.TestCase):
    def test_play_button_feedback_does_not_wait_for_player_poll(self):
        from media_panel import Controls
        p=Controls();p.data={'playing':False}
        with patch('media_panel.deliver') as send:
            p.command('PlayPause')
            self.assertTrue(p.data['playing'])
            p.command('PlayPause')
            self.assertFalse(p.data['playing'])
            self.assertEqual(send.call_count,2)

    def test_control_datagram_is_delivered_without_render_or_poll(self):
        import socket,json
        from media_canvas import deliver
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            server=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
            self.addCleanup(server.close)
            server.bind(str(root/'commands.sock'));server.settimeout(.2)
            with patch('media_canvas.STATE',root):deliver({'id':'one','action':'PlayPause'})
            self.assertEqual(json.loads(server.recv(4096)),{'id':'one','action':'PlayPause'})
            self.assertFalse((root/'control.json').exists())


class PlayerSelectionTests(unittest.TestCase):
    def setUp(self):
        self.players=[dict(bus='a',name='音乐',title='歌曲',status='Playing',playing=True),dict(bus='b',name='浏览器',title='视频',status='Playing',playing=True),dict(bus='c',name='暂停来源',title='播客',status='Paused',playing=False)]

    def test_auto_is_stable_and_manual_paused_source_stays_selected(self):
        from media_canvas import choose_player
        self.assertEqual(choose_player(self.players,'','b')[0]['bus'],'b')
        chosen,selected=choose_player(self.players,'c','a')
        self.assertEqual((chosen['bus'],selected),('c','c'))
        chosen,selected=choose_player(self.players,'closed','b')
        self.assertEqual((chosen['bus'],selected),('b',''))
        self.assertEqual(choose_player([], 'closed'),(None,''))

    def test_explicit_target_never_falls_back_to_different_player(self):
        from media_canvas import control_target
        self.assertEqual(control_target(self.players,self.players[0],'b')['bus'],'b')
        self.assertEqual(control_target(self.players,self.players[0],'closed'),{})

    def test_selector_sends_selection_and_routes_followup_control(self):
        from media_panel import Controls
        p=Controls();p.players=self.players;p.chooser=True
        with patch('media_panel.deliver') as send:
            p.action('chooser:select:b')
            self.assertFalse(p.chooser)
            self.assertEqual(p.data['bus'],'b')
            self.assertEqual(send.call_args.args[0]['value'],'b')
            p.command('PlayPause')
            self.assertEqual(send.call_args.args[0]['target'],'b')
        p.chooser=True;p.chooser_progress=1;p.changed-=1
        width,pixels=p.paint()
        self.assertTrue(any(h[4]=='chooser:select:b' for h in p.hitboxes))
        self.assertTrue(all(h[4].startswith('chooser:') for h in p.hitboxes))

    def test_selection_persists_and_write_failure_keeps_old_choice(self):
        import threading
        from media_canvas import Player,read,choose_player
        p=Player.__new__(Player);p.players=self.players;p.selection='';p.data=self.players[0].copy();p.refresh=threading.Event()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch('media_canvas.STATE',root):
                self.assertTrue(p.select('b'))
                saved=read(root/'selection.json')['bus']
                self.assertEqual(choose_player(self.players,saved)[0]['bus'],'b')
                with patch('media_canvas.save',side_effect=OSError('disk full')):
                    with self.assertRaises(OSError):p.select('c')
                self.assertEqual((p.selection,p.data['bus']),('b','b'))

class DisplaySettingsTests(unittest.TestCase):
    def test_width_limit_and_scroll_modes_apply_live(self):
        p=FakePlayer();p.data['title']='很长的曲目名称'*60;p.data['playing']=False
        m=Media(p);settings={'max_width':200,'title_scroll':'never'}
        with patch('media_canvas.read',return_value=settings):
            m.step(.016,time.time());self.assertEqual(m.motion.target,200)
            m.motion.width=200;m.motion.velocity=0;m.change_at-=1
            self.assertFalse(m.step(.016,time.time()))
            settings['title_scroll']='always'
            self.assertTrue(m.step(.016,time.time()))
            settings.update(title_scroll='hover',hovered=False,max_width=720)
            m.step(.016,time.time());self.assertEqual(m.motion.target,720)
            settings['max_width']=9999
            m.step(.016,time.time());self.assertEqual(m.motion.target,720)

class MarqueeRenderingTests(unittest.TestCase):
    def test_long_title_pixels_actually_move_and_never_mode_stays_still(self):
        m=Media(FakePlayer());m.current=m.player.data|{'title':'Long title for actual scrolling verification '*4,'playing':False}
        m.previous={};m.change_at=0;m.scroll_started=100;m.motion.width=200
        m.input={'title_scroll':'hover','hovered':True}
        with patch('media_canvas.save'),patch('media_canvas.time.monotonic',return_value=100):
            _,first=m.paint();self.assertEqual(m.scroll_offset,0)
        with patch('media_canvas.save'),patch('media_canvas.time.monotonic',return_value=102):
            _,second=m.paint();self.assertGreater(m.scroll_offset,0)
        self.assertNotEqual(first,second)
        m.input['hovered']=False
        with patch('media_canvas.save'),patch('media_canvas.time.monotonic',return_value=102):
            m.paint();self.assertEqual(m.scroll_offset,0)
        m.input.update(title_scroll='always')
        with patch('media_canvas.save'),patch('media_canvas.time.monotonic',return_value=102):
            m.paint();self.assertGreater(m.scroll_offset,0)
        m.input.update(title_scroll='never',hovered=True)
        with patch('media_canvas.save'),patch('media_canvas.time.monotonic',return_value=102):
            m.paint();self.assertEqual(m.scroll_offset,0)
