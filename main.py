#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电子书语音朗读器 - Android Kivy 版
支持格式: TXT / EPUB / PDF
TTS引擎: Android原生TTS + gTTS(在线) + edge-tts(在线)
"""

import os, re, sys, json, queue, asyncio, threading, tempfile, time, shutil
from pathlib import Path
from typing import Optional, List

import kivy
kivy.require('2.1.0')
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.progressbar import ProgressBar
from kivy.uix.spinner import Spinner
from kivy.utils import platform

# ─── Android 权限 ──
if platform == 'android':
    from android.permissions import request_permissions, Permission
    from android.content import Context
    from jnius import autoclass, PythonJavaClass, java_method
    import android.activity
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
    DocumentsContract = autoclass('android.provider.DocumentsContract')
    ContentResolver = autoclass('android.content.ContentResolver')
    OpenableColumns = autoclass('android.provider.OpenableColumns')

# ─── 文本解析 ──
try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
except ImportError:
    ebooklib = None
    BeautifulSoup = None

# ─── 在线TTS ──
try:
    from gtts import gTTS
except ImportError:
    gTTS = None

try:
    import edge_tts
except ImportError:
    edge_tts = None


# ══════════════════════════════════════════
#  文本提取
# ══════════════════════════════════════════

def extract_text(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    if ext == '.txt': return extract_txt(filepath)
    elif ext == '.epub': return extract_epub(filepath)
    elif ext == '.pdf': return extract_pdf(filepath)
    else: raise ValueError(f"不支持: {ext}")

def extract_txt(filepath: str) -> str:
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

def extract_epub(filepath: str) -> str:
    if ebooklib is None or BeautifulSoup is None:
        raise RuntimeError("需安装 ebooklib + beautifulsoup4")
    book = epub.read_epub(filepath)
    texts = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            for tag in soup(['script', 'style', 'nav']): tag.decompose()
            text = soup.get_text(separator='\n')
            texts.append(re.sub(r'\n{3,}', '\n\n', text).strip())
    return '\n'.join(texts)

def extract_pdf(filepath: str) -> str:
    if pypdf is None: raise RuntimeError("需安装 pypdf")
    reader = pypdf.PdfReader(filepath)
    return '\n'.join([p.extract_text() or '' for p in reader.pages])

def chunk_text(text: str, max_chars: int = 600) -> List[str]:
    paras = re.split(r'\n\s*\n', text)
    chunks, cur = [], ""
    for p in paras:
        p = p.strip()
        if not p: continue
        if len(cur) + len(p) < max_chars:
            cur += p + "。"
        else:
            if cur: chunks.append(cur)
            if len(p) > max_chars:
                for s in re.split(r'(?<=[。！？!?])', p):
                    if len(cur) + len(s) < max_chars: cur += s
                    else:
                        if cur: chunks.append(cur)
                        cur = s
            else:
                cur = p + "。"
    if cur: chunks.append(cur)
    return chunks


# ══════════════════════════════════════════
#  TTS 引擎
# ══════════════════════════════════════════

class AndroidTTS:
    def __init__(self):
        self.tts = None
        self._is_init = False
        self._stop_flag = threading.Event()

    def init(self):
        if self._is_init or platform != 'android': return
        TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
        ctx = PythonActivity.mActivity

        class OnInit(PythonJavaClass):
            __javainterfaces__ = ['android/speech/tts/TextToSpeech$OnInitListener']
            def __init__(self, tts, event):
                super().__init__()
                self.tts = tts; self.event = event
            @java_method('(I)V')
            def onInit(self, status):
                if status == TextToSpeech.SUCCESS:
                    self.tts.setLanguage(autoclass('java.util.Locale').CHINESE)
                self.event.set()

        evt = threading.Event()
        self.tts = TextToSpeech(ctx, OnInit(self, evt))
        evt.wait(timeout=5)
        self._is_init = True

    def stop(self):
        self._stop_flag.set()
        if self.tts: self.tts.stop()

    def reset(self): self._stop_flag.clear()
    def is_stopped(self): return self._stop_flag.is_set()

    def speak(self, text: str, rate: int = 0):
        if not text.strip() or not self._is_init: return False
        self.tts.setSpeechRate(max(0.1, 3.0, 1.0 + rate / 100))
        self.tts.speak(text, 0, None, "chunk")
        while self.tts.isSpeaking():
            if self.is_stopped(): self.tts.stop(); return False
            time.sleep(0.1)
        return True


class TTS_gTTS:
    def __init__(self): self._stop = threading.Event()
    def stop(self): self._stop.set()
    def reset(self): self._stop.clear()
    def is_stopped(self): return self._stop.is_set()
    def synth(self, text, path, rate=0):
        if not text.strip() or self.is_stopped(): return False
        try:
            gTTS(text, lang='zh-CN', slow=(rate < 0)).save(path)
            return True
        except: return False


class TTS_Edge:
    def __init__(self, voice='zh-CN-XiaoxiaoNeural'):
        self._stop = threading.Event(); self.voice = voice
    def stop(self): self._stop.set()
    def reset(self): self._stop.clear()
    def is_stopped(self): return self._stop.is_set()
    def synth(self, text, path, rate=0):
        if not text.strip() or self.is_stopped(): return False
        try:
            r = f"{'+' if rate >= 0 else ''}{rate}%"
            asyncio.run(edge_tts.Communicate(text, self.voice, rate=r).save(path))
            return True
        except: return False


# ══════════════════════════════════════════
#  Kivy 主界面
# ══════════════════════════════════════════

class EbookTTSApp(App):
    def __init__(self):
        super().__init__()
        self.title = "电子书朗读器"
        self.full_text = ""
        self.chunks: List[str] = []
        self.chunk_idx = 0
        self.is_playing = False
        self.is_paused = False
        self.speed_val = 0
        self.speed_factor = 1.0
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._queue = queue.Queue()
        self.temp = tempfile.mkdtemp(prefix="et_")

        self.android_tts = AndroidTTS() if platform == 'android' else None
        self.gtts_eng = TTS_gTTS() if gTTS else None
        self.edge_eng = TTS_Edge() if edge_tts else None
        self.cur_engine = "Android TTS"

    def build(self):
        if platform == 'android':
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
            Clock.schedule_once(lambda dt: self.android_tts.init() if self.android_tts else None, 1)

        root = BoxLayout(orientation='vertical', spacing=4, padding=6)

        # ── 工具栏 ──
        tb = BoxLayout(size_hint_y=0.08, spacing=6)
        btn_open = Button(text='📂 打开', size_hint_x=0.15)
        btn_open.bind(on_release=lambda b: self.open_file())
        tb.add_widget(btn_open)

        self.eng_spin = Spinner(text='Android TTS', values=self._engines(), size_hint_x=0.25)
        self.eng_spin.bind(text=lambda s, v: setattr(self, 'cur_engine', v))
        tb.add_widget(self.eng_spin)

        btn_save = Button(text='💾 保存', size_hint_x=0.12)
        btn_save.bind(on_release=lambda b: self.save_audio())
        tb.add_widget(btn_save)

        # 语速
        sp = BoxLayout(size_hint_x=0.3, spacing=4)
        sp.add_widget(Label(text='语速:', size_hint_x=0.15))
        self.sl = Slider(min=0.5, max=2.0, value=1.0, size_hint_x=0.55)
        self.sl.bind(value=self._on_speed)
        sp.add_widget(self.sl)
        self.sl_lb = Label(text='1.0x', size_hint_x=0.15)
        sp.add_widget(self.sl_lb)
        tb.add_widget(sp)
        root.add_widget(tb)

        # ── 文本区 ──
        sv = ScrollView(size_hint_y=0.6)
        self.txt = Label(text='点击"打开"选择电子书\n支持 TXT / EPUB / PDF', markup=True,
                         size_hint_y=None, text_size=(self.width*0.9, None), padding=(12,12), font_size=16)
        self.txt.bind(width=lambda w,v: setattr(self.txt, 'text_size', (v*0.9, None)))
        self.txt.bind(texture_size=lambda w,v: setattr(w, 'height', v[1]))
        sv.add_widget(self.txt)
        root.add_widget(sv)

        # ── 进度 ──
        pl = BoxLayout(orientation='vertical', size_hint_y=0.06, spacing=2)
        self.pb = ProgressBar(max=100, value=0, size_hint_y=0.5)
        pl.add_widget(self.pb)
        self.plb = Label(text='未加载', size_hint_y=0.5, font_size=13)
        pl.add_widget(self.plb)
        root.add_widget(pl)

        # ── 控制栏 ──
        cl = BoxLayout(size_hint_y=0.12, spacing=10, padding=(20, 4))
        self.b_play = Button(text='▶ 播放', font_size=18)
        self.b_play.bind(on_release=lambda b: self.play())
        cl.add_widget(self.b_play)

        self.b_pause = Button(text='⏸ 暂停', font_size=18, disabled=True)
        self.b_pause.bind(on_release=lambda b: self.toggle_pause())
        cl.add_widget(self.b_pause)

        self.b_stop = Button(text='⏹ 停止', font_size=18, disabled=True)
        self.b_stop.bind(on_release=lambda b: self.stop())
        cl.add_widget(self.b_stop)

        self.b_sgen = Button(text='停止生成', font_size=14, disabled=True)
        self.b_sgen.bind(on_release=lambda b: self.stop())
        cl.add_widget(self.b_sgen)
        root.add_widget(cl)

        # ── 状态 ──
        self.st = Label(text='就绪', size_hint_y=0.04, font_size=14, halign='left')
        root.add_widget(self.st)

        Clock.schedule_interval(lambda dt: self._poll(), 0.1)
        return root

    def _engines(self):
        e = []
        if platform == 'android': e.append('Android TTS')
        if self.gtts_eng: e.append('gTTS')
        if self.edge_eng: e.append('edge-tts')
        return e or ['无引擎']

    def _on_speed(self, s, v):
        self.speed_factor = v
        self.sl_lb.text = f'{v:.1f}x'
        self.speed_val = int((v - 1.0) * 100)

    def _poll(self):
        try:
            while True:
                m = self._queue.get_nowait()
                t = m.get('type','')
                if t == 'progress':
                    self.pb.value = m['pct']
                    self.plb.text = m['info']
                elif t == 'status':
                    self.st.text = m['text']
                elif t == 'done':
                    self.is_playing = False; self._upd_btns()
                    self.st.text = '播放完成'; self.pb.value = 100
                elif t == 'error':
                    self.is_playing = False; self._upd_btns()
                    self.st.text = f'错误: {m["text"]}'
        except queue.Empty: pass

    # ── 文件 ──
    def open_file(self):
        if platform == 'android':
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType('*/*')
            intent.putExtra(Intent.EXTRA_MIME_TYPES, ['text/plain','application/epub+zip','application/pdf'])
            PythonActivity.mActivity.startActivityForResult(intent, 1001)
            android.activity.bind(on_activity_result=self._on_file)
        else:
            self._toast('桌面版请输入路径')

    def _on_file(self, req, res, data):
        if req != 1001 or res != -1: return
        try:
            uri = data.getData()
            cr = PythonActivity.mActivity.getContentResolver()
            ins = cr.openInputStream(uri)
            cur = cr.query(uri, None, None, None, None)
            name = 'book'
            if cur and cur.moveToFirst():
                idx = cur.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if idx >= 0: name = cur.getString(idx)
            tmp = os.path.join(self.temp, name)
            with open(tmp, 'wb') as f: f.write(ins.read())
            ins.close()
            if cur: cur.close()
            self._load(tmp)
        except Exception as e:
            self._toast(f'打开失败: {e}')

    def _load(self, path):
        try:
            self.stop()
            raw = extract_text(path)
            if not raw.strip(): raise ValueError('无内容')
            self.full_text = raw
            self.chunks = chunk_text(raw)
            self.chunk_idx = 0
            display = raw[:2000] + ('\n\n...(省略)' if len(raw)>2000 else '')
            self.txt.text = display
            fn = Path(path).name
            self.plb.text = f'{fn} | {len(self.chunks)} 段'
            self.st.text = f'已加载: {fn} ({len(self.chunks)}段)'
            self.pb.value = 0; self._upd_btns()
        except Exception as e:
            self._toast(f'加载失败: {e}')

    # ── 播放 ──
    def _eng(self):
        n = self.cur_engine
        if 'Android' in n: return self.android_tts
        if 'gTTS' in n: return self.gtts_eng
        if 'edge' in n: return self.edge_eng
        return None

    def play(self):
        if not self.chunks: return
        eng = self._eng()
        if not eng: self._toast('引擎不可用'); return
        if self.is_paused and self.is_playing:
            self._pause.clear(); self.is_paused = False
            self.b_pause.text = '⏸ 暂停'; self.st.text = '继续'; return
        if self.is_playing: return
        self._stop.clear(); self._pause.clear()
        self.is_playing = True; self.is_paused = False; self._upd_btns()
        self.st.text = '播放中...'
        threading.Thread(target=self._loop, args=(eng,), daemon=True).start()

    def _loop(self, eng):
        total = len(self.chunks)
        if hasattr(eng, 'reset'): eng.reset()
        for idx in range(self.chunk_idx, total):
            if self._stop.is_set(): return
            while self._pause.is_set():
                if self._stop.is_set(): return; time.sleep(0.1)
            chunk = self.chunks[idx]
            if not chunk.strip(): continue
            pct = int((idx+1)/total*100)
            self._queue.put({'type':'progress','pct':pct,'info':f'{idx+1}/{total}({pct}%)'})
            self._queue.put({'type':'status','text':f'播放: {idx+1}/{total}'})
            if hasattr(eng, 'speak'):
                eng.speak(chunk, self.speed_val)
            else:
                out = os.path.join(self.temp, f'c{idx:05d}.mp3')
                try: eng.synth(chunk, out, self.speed_val)
                except: continue
                if self._stop.is_set(): return
                self._play_file(out)
            self.chunk_idx = idx + 1
        self._queue.put({'type':'done'}); self.chunk_idx = 0

    def _play_file(self, path):
        if not os.path.exists(path): return
        from jnius import autoclass
        mp = autoclass('android.media.MediaPlayer')()
        mp.setDataSource(path); mp.prepare(); mp.start()
        while mp.isPlaying():
            if self._stop.is_set(): mp.stop(); return
            while self._pause.is_set():
                if self._stop.is_set(): mp.stop(); return; time.sleep(0.1)
            time.sleep(0.1)
        mp.release()

    def toggle_pause(self):
        if not self.is_playing: return
        if self.is_paused:
            self._pause.clear(); self.is_paused = False
            self.b_pause.text = '⏸ 暂停'; self.st.text = '继续'
        else:
            self._pause.set(); self.is_paused = True
            self.b_pause.text = '▶ 继续'; self.st.text = '已暂停'

    def stop(self):
        self._stop.set(); self._pause.clear()
        self.is_playing = False; self.is_paused = False
        eng = self._eng()
        if eng and hasattr(eng, 'stop'): eng.stop()
        self._upd_btns(); self.st.text = '已停止'

    def _toast(self, msg):
        self.st.text = msg

    # ── 保存 ──
    def save_audio(self):
        if not self.chunks: self._toast('请先打开电子书'); return
        self.st.text = '正在生成音频...'
        threading.Thread(target=self._save_worker, daemon=True).start()

    def _save_worker(self):
        eng = self._eng()
        if not eng: self._queue.put({'type':'status','text':'引擎不可用'}); return
        if hasattr(eng, 'reset'): eng.reset()
        self._stop.clear()
        total = len(self.chunks)
        sd = tempfile.mkdtemp(prefix='es_')
        files = []
        for idx, chunk in enumerate(self.chunks):
            if self._stop.is_set(): break
            if not chunk.strip(): continue
            out = os.path.join(sd, f'{idx:05d}.mp3')
            try:
                if hasattr(eng, 'synth'): eng.synth(chunk, out, self.speed_val)
                if os.path.exists(out): files.append(out)
            except: continue
            pct = int((idx+1)/total*100)
            self._queue.put({'type':'progress','pct':pct,'info':f'生成: {idx+1}/{total}'})
        if not files: return
        import android.os.Environment as Env
        dn = Env.getExternalStoragePublicDirectory(Env.DIRECTORY_DOWNLOADS).getAbsolutePath()
        sp = os.path.join(dn, '电子书音频.mp3')
        with open(sp, 'wb') as f:
            for fp in files:
                with open(fp, 'rb') as cf: f.write(cf.read())
        shutil.rmtree(sd, ignore_errors=True)
        self._queue.put({'type':'status','text':f'已保存到下载目录'})
        if platform == 'android':
            try:
                Toast = autoclass('android.widget.Toast')
                ctx = PythonActivity.mActivity
                Toast.makeText(ctx, f'已保存: 电子书音频.mp3', Toast.LENGTH_LONG).show()
            except: pass

    def _upd_btns(self):
        ok = bool(self.chunks)
        self.b_play.disabled = not ok or self.is_playing
        self.b_pause.disabled = not self.is_playing
        self.b_stop.disabled = not self.is_playing
        self.b_sgen.disabled = not self.is_playing

    def on_stop(self):
        self.stop()
        try: shutil.rmtree(self.temp)
        except: pass


if __name__ == '__main__':
    EbookTTSApp().run()
