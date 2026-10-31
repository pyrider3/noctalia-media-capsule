#!/usr/bin/env python3
"""Install the media capsule and replace the two built-in bar entries."""
from pathlib import Path
import datetime
import re
import shutil
import subprocess
import tomllib

source=Path(__file__).resolve().parent
target=Path.home()/'.config/noctalia/plugins/media-capsule'
target.mkdir(parents=True,exist_ok=True)
for name in ['plugin.toml','widget.luau','media_canvas.py','motion.py','stream_server.py','panel.luau','media_panel.py']:
    shutil.copy2(source/name,target/name)
shutil.copytree(source/'translations',target/'translations',dirs_exist_ok=True)
path=Path.home()/'.local/state/noctalia/settings.toml'
text=path.read_text();tomllib.loads(text)
backup=path.with_name('settings.toml.bak-media-capsule-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
shutil.copy2(path,backup)
def replace_entries(match):
    import json
    values=tomllib.loads('items = '+match[2])['items']
    updated=[]
    for name in values:
        if name in ('media','audio_visualizer','media-capsule'):
            if 'media-capsule' not in updated:updated.append('media-capsule')
        else:updated.append(name)
    return match[1]+json.dumps(updated,ensure_ascii=False)
text=re.sub(r'(?m)^((?:start|center|end)\s*=\s*)(\[[^\]]*\])',replace_entries,text)
if '[widget.media-capsule]' not in text:
    text+='\n[widget.media-capsule]\ntype = "pyrider3/media-capsule:player"\n'
tomllib.loads(text);path.write_text(text)
print('Installed. Backup:',backup)
print('Reload with: noctalia msg plugins update local; noctalia msg plugins enable pyrider3/media-capsule; noctalia msg config-reload')
