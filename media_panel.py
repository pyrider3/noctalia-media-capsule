#!/usr/bin/env python3
"""Native rounded playback panel, sharing the bar's selected MPRIS player."""
import math
import time
import cairo
from media_canvas import STATE,read,save,rgba,cover_surface,deliver
from stream_server import serve

WIDTH,HEIGHT,SCALE=368,460,2


def clock(seconds):
    seconds=max(0,int(seconds));return f'{seconds//60}:{seconds%60:02d}'


class Controls:
    def __init__(self):
        self.data={};self.skin={};self.cover=None;self.art=None
        self.session=None;self.sequence=-1;self.down=0;self.released=0
        self.pointer=(0,0);self.pressed=False;self.drag=None;self.preview=0
        self.changed=time.monotonic();self.hitboxes=[];self.identity=None
        self.content_changed=self.changed;self.pending={}
        self.players=[];self.selection="";self.chooser=False;self.chooser_page=0
        self.chooser_progress=0.0;self.selection_pending=None

    def command(self,action,value=None):
        deliver(dict(id=str(time.time_ns()),action=action,value=value,target=self.data.get("bus"),sent=time.monotonic()))
        if action=='PlayPause':
            self.pending[action]=(not self.data.get('playing',False),time.monotonic())
            self.data['playing']=not self.data.get('playing',False)
        if action in ('SetPosition','Volume'):self.pending[action]=(value,time.monotonic())

    def action(self,action):
        if action=='chooser:toggle':self.chooser=not self.chooser;return
        if action=='chooser:close':self.chooser=False;return
        if action=='chooser:next':self.chooser_page+=1;return
        if action=='chooser:previous':self.chooser_page=max(0,self.chooser_page-1);return
        if action.startswith('chooser:select:'):
            selected=action[len('chooser:select:'):]
            self.command('SelectPlayer',selected)
            self.selection=selected;self.selection_pending=(selected,time.monotonic())
            chosen=next((p for p in self.players if p['bus']==selected),None)
            if chosen:self.data=chosen.copy()
            self.pending.clear();self.chooser=False;return
        self.command(action)

    def input(self,event):
        if not isinstance(event.get('seq'),int) or event['seq']==self.sequence:return
        self.sequence=event['seq']
        self.pointer=(float(event.get('x',0))*WIDTH,float(event.get('y',0))*HEIGHT)
        if event.get('session')!=self.session:
            self.session=event.get('session');self.down=event.get('down_serial',0);self.released=event.get('released_serial',0)
            self.drag=None;self.pressed=False;self.changed=time.monotonic()
        if event.get('down_serial',0)!=self.down:
            self.down=event['down_serial'];self.pressed=True
            x=float(event.get('down_x',0))*WIDTH;y=float(event.get('down_y',0))*HEIGHT
            if self.chooser:pass
            elif 24<=x<=344 and 292<=y<=318 and self.data.get('can_seek') and self.data.get('length',0)>0:self.drag='SetPosition'
            elif 60<=x<=308 and 414<=y<=438 and self.data.get('volume') is not None:self.drag='Volume'
        if self.pressed and self.drag:
            x=self.pointer[0]
            self.preview=max(0,min(1,(x-(24 if self.drag=='SetPosition' else 60))/(320 if self.drag=='SetPosition' else 248)))
        if event.get('released_serial',0)!=self.released:
            self.released=event['released_serial']
            x=float(event.get('up_x',event.get('x',0)))*WIDTH;y=float(event.get('up_y',event.get('y',0)))*HEIGHT
            if self.pressed and not event.get('cancelled'):
                if self.drag:
                    fraction=max(0,min(1,(x-(24 if self.drag=='SetPosition' else 60))/(320 if self.drag=='SetPosition' else 248)))
                    self.command(self.drag,fraction*self.data.get('length',0) if self.drag=='SetPosition' else fraction)
                else:
                    for bx,by,bw,bh,action,enabled in reversed(self.hitboxes):
                        if enabled and bx<=x<=bx+bw and by<=y<=by+bh:self.action(action);break
            self.pressed=False;self.drag=None

    def step(self,delta,now):
        status=read(STATE/'status.json');data=status.get('player',{})
        if status:
            self.data=data.copy();self.players=status.get('players',[]);self.selection=status.get('selection','')
        if self.selection_pending:
            selected,sent=self.selection_pending
            if self.selection==selected or time.monotonic()-sent>.8:self.selection_pending=None
            else:
                self.selection=selected
                chosen=next((p for p in self.players if p['bus']==selected),None)
                if chosen:self.data=chosen.copy()
        target=1 if self.chooser else 0
        self.chooser_progress+=(target-self.chooser_progress)*(1-math.exp(-24*min(delta,.05)))
        if abs(self.chooser_progress-target)<.001:self.chooser_progress=float(target)
        for action,(value,sent) in list(self.pending.items()):
            if time.monotonic()-sent>.8:self.pending.pop(action);continue
            if action=='SetPosition':self.data.update(position=value,stamp=sent)
            elif action=='Volume':self.data['volume']=value
            elif action=='PlayPause':self.data['playing']=value
        value=read(STATE/'input.json')
        if value:self.skin=value
        identity=(self.data.get('bus'),self.data.get('title'),self.data.get('artist'))
        if identity!=self.identity:self.identity=identity;self.content_changed=time.monotonic();self.drag=None;self.pending.clear()
        url=self.data.get('art_url','')
        if url!=self.art:self.art=url;self.cover=cover_surface(url,320)
        old_sequence=self.sequence
        self.input(read(STATE/'panel-input.json'))
        return abs(self.chooser_progress-int(self.chooser))>.001 or self.sequence!=old_sequence or bool(self.pending) or bool(self.data.get('playing')) or self.pressed or time.monotonic()-self.changed<.4 or time.monotonic()-self.content_changed<.25

    def paint(self):
        surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,WIDTH*SCALE,HEIGHT*SCALE)
        c=cairo.Context(surface);c.scale(SCALE,SCALE)
        accent=self.skin.get('accent','#edb69b');fg=self.skin.get('text','#e9e9e6');muted='#9da5b0'
        def rect(x,y,w,h,color,r=0,alpha=1):
            r=min(r,w/2,h/2);c.new_sub_path()
            for cx,cy,a in [(x+w-r,y+r,-math.pi/2),(x+w-r,y+h-r,0),(x+r,y+h-r,math.pi/2),(x+r,y+r,math.pi)]:c.arc(cx,cy,r,a,a+math.pi/2)
            c.close_path();c.set_source_rgba(*rgba(color,alpha));c.fill()
        def text(label,x,y,size=13,color=None,limit=None,bold=False):
            c.select_font_face('Noto Sans CJK SC',cairo.FONT_SLANT_NORMAL,cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL);c.set_font_size(size)
            label=str(label)
            if limit and c.text_extents(label).x_advance>limit:
                while label and c.text_extents(label+'…').x_advance>limit:label=label[:-1]
                label+='…'
            c.set_source_rgba(*rgba(color or fg));c.move_to(x,y);c.show_text(label)
        def stroke(x1,y1,x2,y2,color,width=2):
            c.set_source_rgba(*rgba(color));c.set_line_width(width);c.set_line_cap(cairo.LINE_CAP_ROUND);c.move_to(x1,y1);c.line_to(x2,y2);c.stroke()
        rect(0,0,WIDTH,HEIGHT,'#171a1f',28)
        # Muted cover glow and restrained content entrance.
        ease=min(1,max(0,(time.monotonic()-self.changed)/.24));ease=1-(1-ease)**3
        c.save();c.translate(0,6*(1-ease));c.push_group()
        data=self.data;playing=data.get('playing',False)
        text('正在播放' if playing else '已暂停' if data else '暂无播放',24,32,12,accent)
        rect(164,12,180,28,'#2b323c',14,.7)
        source=('固定 · ' if self.selection else '自动 · ')+data.get('name',data.get('bus','').replace('org.mpris.MediaPlayer2.',''))
        text(source,176,31,11,fg,142)
        stroke(326,23,330,27,muted,1.3);stroke(330,27,334,23,muted,1.3)
        rect(96,48,176,176,accent,26,.07)
        c.save()
        # Rounded clipping for the large cover.
        x,y,w,h,r=104,56,160,160,20
        c.new_sub_path()
        for cx,cy,a in [(x+w-r,y+r,-math.pi/2),(x+w-r,y+h-r,0),(x+r,y+h-r,math.pi/2),(x+r,y+r,math.pi)]:c.arc(cx,cy,r,a,a+math.pi/2)
        c.close_path();c.clip()
        if self.cover:c.translate(x,y);c.scale(.5,.5);c.set_source_surface(self.cover);c.paint()
        else:rect(x,y,w,h,'#262c35',20);text('♪',165,158,42,accent)
        c.restore()
        text(data.get('title','打开播放器开始聆听'),24,248,18,fg,320,True)
        text(data.get('artist',''),24,272,13,muted,320)
        length=data.get('length',0);position=data.get('position',0)
        if playing:position+=max(0,time.monotonic()-data.get('stamp',time.monotonic()))
        fraction=max(0,min(1,position/length)) if length>0 else 0
        if self.drag=='SetPosition':fraction=self.preview;position=fraction*length
        rect(24,303,320,4,'#343c47',2);rect(24,303,320*fraction,4,accent,2)
        if data.get('can_seek'):
            c.arc(24+320*fraction,305,5 if self.drag!='SetPosition' else 7,0,2*math.pi);c.set_source_rgba(*rgba(accent));c.fill()
        text(clock(position),24,332,11,muted)
        text(clock(length) if length else '直播',308,332,11,muted)
        self.hitboxes=[(164,12,180,28,"chooser:toggle",True)]
        for x,y,size,action,enabled in [(92,351,40,'Previous',data.get('can_previous',False)),(156,343,56,'PlayPause',bool(data)),(236,351,40,'Next',data.get('can_next',False))]:
            bright=action=='PlayPause';hover=x<=self.pointer[0]<=x+size and y<=self.pointer[1]<=y+size
            rect(x,y,size,size,accent if bright else '#2b323c',size/2,1 if bright else .9 if hover else .45)
            color='#171a1f' if bright else fg if enabled else '#59616c'
            cx=x+size/2;cy=y+size/2
            c.set_source_rgba(*rgba(color));c.set_line_width(2)
            if bright and playing:
                rect(cx-7,cy-9,4,18,color,1);rect(cx+3,cy-9,4,18,color,1)
            else:
                direction=-1 if action=='Previous' else 1
                c.move_to(cx-5*direction,cy-8);c.line_to(cx+7*direction,cy);c.line_to(cx-5*direction,cy+8);c.close_path();c.fill()
                if not bright:stroke(cx+8*direction,cy-8,cx+8*direction,cy+8,color)
            self.hitboxes.append((x,y,size,size,action,enabled))
        volume=data.get('volume')
        text('音量',24,431,11,muted)
        if volume is not None:
            volume=self.preview if self.drag=='Volume' else max(0,min(1,volume))
            rect(60,423,248,3,'#343c47',1.5);rect(60,423,248*volume,3,accent,1.5)
            c.arc(60+248*volume,424.5,4,0,2*math.pi);c.set_source_rgba(*rgba(accent));c.fill()
            text(str(round(volume*100)),320,431,11,muted)
        else:text('播放器不支持',260,431,11,muted)
        if self.chooser_progress>0:
            progress=self.chooser_progress
            rect(0,0,WIDTH,HEIGHT,'#080a0e',28,.65*progress)
            self.hitboxes=[(0,0,WIDTH,HEIGHT,'chooser:close',True)]
            c.save();c.translate(0,-7*(1-progress));c.push_group()
            page_count=max(1,math.ceil(len(self.players)/5))
            self.chooser_page=min(self.chooser_page,page_count-1)
            rows=self.players[self.chooser_page*5:(self.chooser_page+1)*5]
            card_height=116+len(rows)*48+(34 if page_count>1 else 0)
            rect(16,44,336,card_height,'#222831',22)
            text('选择播放器',32,73,16,fg,bold=True)
            text('×',322,73,16,muted)
            self.hitboxes.append((310,52,32,30,'chooser:close',True))
            rect(28,87,312,42,accent if not self.selection else '#303844',12,.2 if not self.selection else .4)
            text('自动选择',40,105,12,fg)
            text('优先播放中，保持当前来源',40,122,10,muted)
            if not self.selection:text('✓',316,111,14,accent)
            self.hitboxes.append((28,87,312,42,'chooser:select:',True))
            for index,item in enumerate(rows):
                y=139+index*48;chosen=self.selection==item['bus']
                rect(28,y,312,44,accent if chosen else '#303844',12,.22 if chosen else .36)
                state='播放中' if item.get('playing') else '已暂停' if item.get('status')=='Paused' else '已停止'
                text(item.get('name',item['bus'].replace('org.mpris.MediaPlayer2.','')),40,y+17,12,fg,210)
                text(state,286,y+17,10,accent if item.get('playing') else muted)
                text(item.get('title') or '暂无曲目',40,y+35,10,muted,270)
                self.hitboxes.append((28,y,312,44,'chooser:select:'+item['bus'],True))
            if not rows:text('尚未发现播放器',40,155,12,muted)
            if page_count>1:
                y=139+len(rows)*48
                text('‹ 上一页',40,y+20,11,muted);text(str(self.chooser_page+1)+' / '+str(page_count),168,y+20,11,muted);text('下一页 ›',275,y+20,11,muted)
                self.hitboxes.extend([(28,y,100,30,'chooser:previous',self.chooser_page>0),(246,y,94,30,'chooser:next',self.chooser_page<page_count-1)])
            c.pop_group_to_source();c.paint_with_alpha(progress);c.restore()
        c.pop_group_to_source();c.paint_with_alpha(ease);c.restore()
        surface.flush();raw=memoryview(surface.get_data()).cast('B');out=bytearray(raw);out[0::4]=raw[2::4];out[2::4]=raw[0::4]
        return WIDTH,bytes(out)

if __name__=='__main__':serve(Controls,STATE,'panel',WIDTH,HEIGHT)
