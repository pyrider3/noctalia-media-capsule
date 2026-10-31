# Media Capsule

适用于 Noctalia 5.4.0 或更新版本（插件 API 43）的播放状态栏插件。在同一个圆角胶囊中显示封面、曲名、实时音频背景和底部播放进度。

## 功能

- 真实 PipeWire 音频驱动的连续背景波形，曲名叠在上方，暂停时平滑收拢。
- 胶囊根据内容平滑伸缩，最大宽度可设 180–720 px，默认 360 px。
- 长标题可选不滚动、悬停滚动、始终滚动，速度可调。
- 点击打开播放面板：大封面、播放／暂停、前后曲、可拖动进度和播放器音量。
- 多播放器选择器显示名称、曲目和播放状态；手动选择后固定控制该来源。
- 自动模式优先播放中的来源，尽量保持当前来源；固定来源关闭后自动回退。
- 控制命令通过本机 Unix socket 直接发送，按钮立即反馈，再同步实际状态。

| 操作 | 功能 |
| --- | --- |
| 左键 | 打开／关闭播放面板 |
| 右键 | 播放／暂停当前选中的播放器 |
| 中键 | 下一首 |
| 悬停 | 完整信息；按设置滚动长标题 |

## 安装

需要 Python 3.11+、`python-cairo`、`python-dbus`、`python-pillow`，以及运行中的 Noctalia、PipeWire 和支持 MPRIS 的播放器。

```sh
git clone https://github.com/pyrider3/noctalia-media-capsule.git
cd noctalia-media-capsule
python3 install.py
noctalia msg plugins update local
noctalia msg plugins enable pyrider3/media-capsule
noctalia msg config-reload
```

安装器会备份 Noctalia 配置，将顶栏原来的 `media` 与 `audio_visualizer` 替换成 `media-capsule`，保留其他组件。请先确保已有 Noctalia 配置。

## 设置

打开 **Noctalia 设置 → 插件 → Media Capsule 齿轮**，可调整：

- 最大宽度：180–720 px。宽度是上限，短曲名会自动缩窄。
- 长标题：不滚动／悬停滚动／始终滚动。
- 滚动速度：8–60 px/秒，默认 22。

默认悬停约半秒后开始滚动，端点减速、停留并往返。关闭滚动时显示省略号。

## 多播放器

点击播放面板右上角的来源按钮，选择“自动选择”或某个播放器。固定选择在暂停时保留，退出该播放器后恢复自动选择。所有控制指令指定具体播放器，目标已关闭时不会误发给另一个来源。

## 本机数据与限制

- 插件：`~/.config/noctalia/plugins/media-capsule/`
- 状态、socket 和固定来源：`~/.local/state/media-capsule/`
- 固定来源保存在 `selection.json`，重启后保留。
- 封面支持播放器提供的本机 `file://` 地址；远端地址使用音乐图标，不下载远端封面。
- 波形反映系统总音频，不是单个播放器的独立音频。
- 浏览器按其公开的 MPRIS 来源显示，不能分别控制未公开独立来源的标签页。
- 无播放器时隐藏；无时长的直播只显示进度底轨。播放控制能力取决于播放器。

不需要账号或密钥，不读取 Notion 凭证及日程。仓库不包含本机媒体缓存或播放器选择记录。

## 验证

```sh
python3 -m unittest test_media
lua test_widget.lua
noctalia plugins lint .
```

13 项 Python 测试和 Luau 回调检查通过；插件 lint 无警告。测试覆盖频谱平滑、暂停回落、画布透明圆角、播放器选择与目标隔离、保存失败、进度交互、即时命令传递，以及实际滚动的像素变化。

## 许可证

MIT
