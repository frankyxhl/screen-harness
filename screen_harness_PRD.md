# PRD：AI Screen SOP Harness

**版本**：v0.1  
**日期**：2026-05-06  
**状态**：Draft  
**产品代号**：`screen-harness`  
**目标用户**：需要把桌面操作流程沉淀成标准化 SOP 的团队、运营、客服、实施、培训、QA、工程支持人员。

---

## 1. 一句话概述

`screen-harness` 是一个面向 AI agent 的 macOS 录屏与 SOP 生成工具。它通过底层录屏能力、结构化时间线、字幕/标注渲染、动态 Python helper 机制，把“人手动录屏”升级为“AI 辅助生成标准化流程视频与文档”。

核心理念：

> 录屏只是底层能力；真正的产品价值是让 AI 在录制前、录制中、录制后参与流程标准化，并把重复经验沉淀成可复用 helper。

---

## 2. 背景与问题

团队内部经常需要录制 SOP 视频，例如：

- 如何在内部系统中新建客户、创建工单、提交报销、配置权限。
- 如何完成某个软件安装、账号初始化、数据导入、审批流程。
- 如何演示客服、实施、运营、财务、HR 等部门的标准操作流程。
- 如何给新同事、外包伙伴、跨国团队同步操作步骤。

当前常见方式是：

1. 打开普通录屏软件。
2. 边操作边讲解。
3. 手动剪辑视频。
4. 手动加字幕或导出逐字稿。
5. 手动整理文档。
6. 后续流程变更后又重新录制。

痛点包括：

- 视频里有大量口误、等待、重复操作。
- 字幕逐字稿不等于 SOP，口语化内容不适合培训。
- 操作步骤没有结构化记录，后续难以自动生成文档。
- 敏感信息容易被录进去，例如姓名、邮箱、客户名、Token、内部 URL。
- 不同人录出来的标准不一致，难以沉淀团队统一模板。
- 录一次只是一个视频，不能变成可复用的流程知识。

`screen-harness` 的目标是把录制过程结构化，让 AI 把原始录屏、语音、点击、窗口信息、人工打点整理成可复用 SOP。

---

## 3. 产品目标

### 3.1 核心目标

1. **快速录制 macOS 屏幕操作**  
   支持屏幕、窗口、区域录制，并能录制麦克风音频。

2. **生成标准化 SOP 字幕**  
   不只是语音逐字稿，而是将口语讲解转成简洁、正式、可培训的步骤说明。

3. **生成结构化时间线**  
   记录步骤、字幕、点击、高亮、打码、章节等事件，形成可编辑 `timeline.json`。

4. **支持后期渲染**  
   使用时间线生成最终视频：字幕、步骤标题、点击高亮、局部放大、敏感信息打码。

5. **支持 agent 动态 helper**  
   允许 AI agent 在任务过程中编写 Python helper，将特定流程、特定系统、特定样式沉淀为可复用代码。

6. **默认保护隐私和安全**  
   本地优先，敏感信息标记和打码优先，云端 AI 能力可配置、可关闭。

### 3.2 成功标准

MVP 成功的判断标准：

- 用户可以在 10 分钟内完成一次 SOP 录制、生成带字幕的最终视频。
- 用户可以通过简单命令或快捷键添加步骤、字幕、标注。
- 生成的 SOP 字幕比原始口语逐字稿更简洁、更正式。
- 最终产物至少包括：`raw.mp4`、`timeline.json`、`sop.ass` 或 `sop.srt`、`final.mp4`。
- agent 能将复用逻辑写入 `agent-workspace/agent_helpers.py`，下一次运行自动可用。

---

## 4. 非目标

MVP 阶段不追求：

- 完整替代专业视频剪辑软件。
- 全自动识别所有 UI 元素并完全无人工干预生成完美 SOP。
- 一开始就支持 Windows、Linux、移动端。
- 一开始就支持多人协作云端编辑。
- 一开始就支持复杂实时视频合成和直播级字幕。
- 一开始就支持所有内部系统的专用识别能力。

MVP 的重点是：

> 用尽可能薄的技术栈打通“录屏 → 时间线 → AI SOP 字幕 → 后期渲染 → 可复用 helper”的闭环。

---

## 5. 用户画像

### 5.1 SOP 制作者

典型角色：运营、实施、客服主管、财务、HR、产品运营。  
需求：快速录制流程，生成清晰培训视频和文字步骤。  
痛点：不想学复杂剪辑，不想手工加字幕，不想反复重录。

### 5.2 新员工 / 学习者

典型角色：新同事、外包人员、跨部门协作者。  
需求：通过视频和文档快速学会标准操作。  
痛点：普通录屏太长、废话多、重点不清楚。

### 5.3 AI / Coding Agent 用户

典型角色：工程师、AI 工具开发者、自动化爱好者。  
需求：通过 Python helper 扩展录制流程，让 agent 能控制录屏、字幕、标注和后期渲染。  
痛点：普通录屏工具没有可编程接口，无法沉淀成自动化工作流。

### 5.4 管理者 / 培训负责人

典型角色：团队负责人、培训负责人、流程 Owner。  
需求：统一 SOP 规范，降低培训成本，保证流程更新及时。  
痛点：不同人录的视频风格不统一，内容难审查，难维护。

---

## 6. 核心使用场景

### 场景 A：录制报销系统 SOP

用户打开工具，开始录制屏幕和麦克风。用户一边操作报销系统，一边口头说明。录制时用户按快捷键标记“新步骤”。录制结束后，AI 自动将语音和步骤打点整理成正式 SOP 字幕，并生成最终视频。

输出：

- `final.mp4`：带步骤字幕和高亮的视频。
- `sop.md`：文字版操作手册。
- `timeline.json`：结构化编辑记录。
- `transcript.srt`：原始语音转写，可选。

### 场景 B：agent 生成专用流程 helper

用户经常录制某个内部 CRM 的流程。agent 发现这些流程经常重复，于是在 `agent-workspace/agent_helpers.py` 中写入：

```python
def crm_step_open_customer_page():
    step("打开客户管理页面")
    caption("在左侧菜单点击「客户管理」，进入客户列表。")
    highlight_text("客户管理")
```

下一次录制 CRM SOP 时，agent 可以直接调用这个 helper，保证字幕风格和标注一致。

### 场景 C：后期统一打码和剪辑

用户录制时不小心出现了客户邮箱和内部 Token。录制后 AI 根据 OCR、窗口标题、用户手动标记或规则检测到敏感区域，在时间线里添加 `redact` 事件。最终渲染时自动打码。

### 场景 D：从视频生成文档

用户只想录一次视频，但最终需要发给同事 Markdown 文档。系统根据视频关键帧、字幕和步骤时间线生成 `sop.md`，每一步附带截图。

---

## 7. 产品原则

1. **本地优先**  
   默认在本地录制、保存、渲染。上传音频或视频到云端 AI 之前必须有明确配置。

2. **原始素材不可破坏**  
   `raw.mp4` 永远保留，不直接覆盖。所有修改都写入 `timeline.json`，最终视频由渲染器生成。

3. **结构化优先于直接剪视频**  
   字幕、步骤、标注、打码都先写进 timeline，再统一渲染。

4. **后期字幕优先于实时字幕**  
   MVP 以高质量后期 SOP 字幕为主；实时字幕可作为预览或高级功能。

5. **agent 可扩展，但要有安全边界**  
   允许 agent 写 Python helper，但必须让用户知道这些代码有本地执行权限。

6. **少抽象，多暴露底层能力**  
   借鉴 browser-harness：核心 helper 简洁，底层能力直接暴露给 agent，复杂能力通过 workspace 积累。

---

## 8. MVP 范围

### 8.1 P0 功能

#### P0.1 开始/停止录屏

用户可以通过 CLI 开始和停止录屏：

```bash
screen-harness -c '
start_recording("expense_create_request")
wait(10)
stop_recording()
'
```

要求：

- 支持 macOS 主屏录制。
- 支持麦克风录音。
- 支持录制鼠标指针。
- 生成 `raw.mp4`。
- 录制文件放在独立 recording 目录。

#### P0.2 时间线记录

录制过程中可以记录：

- `step`：步骤标题。
- `caption`：字幕文本。
- `highlight`：区域高亮。
- `click`：点击位置。
- `redact`：打码区域。
- `chapter`：章节。

示例：

```python
step("创建报销申请")
caption("点击右上角「新建申请」，进入申请表单。")
highlight_region(1240, 88, 180, 64, text="新建申请")
```

#### P0.3 生成 SOP 字幕

录制后生成面向培训的 SOP 字幕。

输入：

- 原始语音转写。
- 用户手动添加的 `step` 和 `caption`。
- 时间线事件。

输出：

- `sop.srt`：基础字幕。
- `sop.ass`：带样式字幕，优先用于最终渲染。

#### P0.4 后期渲染最终视频

使用 FFmpeg 或同类 renderer 生成 `final.mp4`。

渲染内容：

- 底部字幕。
- 步骤标题。
- 点击高亮。
- 简单打码。

#### P0.5 动态 helper

支持 `agent-workspace/agent_helpers.py`。

规则：

- CLI 启动时自动加载该文件。
- 公开函数自动注入 helper 命名空间。
- agent 可以修改该文件。
- 文件修改会保存在本地。
- 修改不会自动 commit 或 push。

#### P0.6 生成 Markdown SOP

录制后输出 `sop.md`：

- 标题。
- 步骤列表。
- 每步说明。
- 可选关键帧截图。
- 对应视频时间点。

---

### 8.2 P1 功能

- 快捷键打点。
- 实时字幕预览浮窗。
- 系统音频录制。
- 选择窗口录制，而不是全屏录制。
- 自动删除长时间等待片段。
- 自动识别敏感信息并建议打码。
- 自动生成视频章节。
- 多语言字幕翻译。
- 导出 Notion / Confluence / Markdown。

---

### 8.3 P2 功能

- 基于 ScreenCaptureKit 的原生采集内核。
- 可视化 timeline 编辑器。
- 多人协作审阅。
- SOP 模板库。
- 根据 SOP 自动校验用户是否按步骤操作。
- 与浏览器自动化、桌面自动化、RPA 工具联动。
- 私有化部署 AI 转写和总结模型。

---

## 9. 用户体验流程

### 9.1 CLI-first 流程

```bash
screen-harness init
screen-harness doctor
screen-harness -c '
start_recording("expense_create_request")
step("打开报销系统")
caption("进入公司后台，打开报销系统。")
wait_for_user("完成登录后继续")
step("新建申请")
caption("点击右上角「新建申请」。")
stop_recording()
render()
'
```

输出目录：

```text
recordings/expense_create_request_20260506_153012/
  raw.mp4
  timeline.json
  audio.wav
  transcript.srt
  sop.srt
  sop.ass
  sop.md
  final.mp4
  metadata.json
```

### 9.2 人工录制 + 快捷键打点流程

1. 用户运行：

```bash
screen-harness record "报销系统 - 创建申请"
```

2. 用户开始操作和讲解。
3. 用户按快捷键：

```text
⌘⇧1：新步骤
⌘⇧2：添加重点说明
⌘⇧3：标记敏感区域
⌘⇧4：添加高亮
⌘⇧5：结束录制
```

4. 录制结束后，系统自动生成 SOP 字幕和最终视频。
5. 用户可以手动编辑 `timeline.json` 或 `sop.md` 后重新渲染。

### 9.3 Agent 辅助流程

用户让 agent 录制一条 SOP：

```text
帮我录一条“CRM 新建客户”的 SOP。录制时请把每一步整理成正式字幕，并把客户手机号打码。
```

agent 执行：

```python
start_recording("crm_create_customer")
step("进入客户管理")
caption("在左侧菜单点击「客户管理」。")
# 用户实际操作
step("新建客户")
caption("点击「新建客户」，填写客户基本信息。")
mark_sensitive("phone_number")
stop_recording()
transcribe()
generate_sop_captions()
render()
```

---

## 10. 信息架构与文件结构

建议项目结构：

```text
screen-harness/
  screen_harness/
    __init__.py
    run.py              # CLI 入口，执行 -c Python
    helpers.py          # 对 agent 暴露的核心函数
    recorder.py         # FFmpeg / ScreenCaptureKit wrapper
    timeline.py         # 时间线事件模型
    captions.py         # SRT / ASS 生成
    transcribe.py       # ASR 转写接口
    render.py           # 后期渲染
    admin.py            # doctor、权限检查、设备检查
    ipc.py              # 可选：长期 daemon 的本地 IPC
  agent-workspace/
    agent_helpers.py    # agent 可编辑 helper
  domain-skills/
    crm.py
    expense.py
    onboarding.py
  recordings/
    .gitkeep
  PRD.md
```

单条 recording 的目录结构：

```text
recordings/<recording_id>/
  raw.mp4               # 原始录屏，不覆盖
  audio.wav             # 抽取或单独录制的音频
  timeline.json         # 核心结构化事件
  transcript.srt        # 原始逐字稿
  sop.srt               # 简洁 SOP 字幕
  sop.ass               # 带样式字幕
  sop.md                # 文档版 SOP
  final.mp4             # 最终视频
  screenshots/
    step_001.png
    step_002.png
  metadata.json
```

---

## 11. 核心数据模型

### 11.1 `timeline.json`

```json
{
  "recording_id": "expense_create_request_20260506_153012",
  "title": "报销系统 - 创建申请",
  "created_at": "2026-05-06T15:30:12+09:00",
  "source_video": "raw.mp4",
  "duration": 128.4,
  "canvas": {
    "width": 1920,
    "height": 1080,
    "fps": 30
  },
  "events": [
    {
      "id": "evt_001",
      "t": 0.0,
      "type": "chapter",
      "title": "创建报销申请"
    },
    {
      "id": "evt_002",
      "t": 4.2,
      "type": "step",
      "title": "打开报销系统"
    },
    {
      "id": "evt_003",
      "t": 5.0,
      "type": "caption",
      "text": "进入公司后台，在左侧菜单打开「报销系统」。",
      "duration": 4.0,
      "style": "sop_default"
    },
    {
      "id": "evt_004",
      "t": 9.8,
      "type": "highlight",
      "rect": [80, 240, 260, 64],
      "duration": 3.0,
      "text": "报销系统"
    },
    {
      "id": "evt_005",
      "t": 20.5,
      "type": "redact",
      "rect": [1120, 80, 300, 48],
      "duration": 8.0,
      "reason": "用户名"
    }
  ]
}
```

### 11.2 Event 类型

| 类型 | 用途 | MVP |
|---|---|---|
| `chapter` | 视频章节 | 是 |
| `step` | SOP 步骤 | 是 |
| `caption` | 字幕 | 是 |
| `click` | 点击位置 | 是 |
| `highlight` | 区域高亮 | 是 |
| `redact` | 敏感信息打码 | 是 |
| `zoom` | 局部放大 | 否，P1 |
| `pause` | 暂停或等待 | 否，P1 |
| `cut` | 剪辑片段 | 否，P1 |
| `speed` | 变速 | 否，P1 |

---

## 12. 核心 API / Helper 设计

### 12.1 录制控制

```python
start_recording(name: str, *, screen: str | None = None, mic: str | None = None) -> Recording
stop_recording() -> Recording
pause_recording() -> None
resume_recording() -> None
```

### 12.2 时间线事件

```python
step(title: str, *, t: float | None = None) -> None
chapter(title: str, *, t: float | None = None) -> None
caption(text: str, *, duration: float | None = None, t: float | None = None) -> None
click(x: int, y: int, *, label: str | None = None, t: float | None = None) -> None
highlight_region(x: int, y: int, w: int, h: int, *, text: str | None = None, duration: float = 3.0) -> None
redact_region(x: int, y: int, w: int, h: int, *, reason: str | None = None, duration: float | None = None) -> None
```

### 12.3 后期处理

```python
extract_audio() -> Path
transcribe() -> Path
generate_sop_captions(style: str = "concise") -> Path
generate_markdown_sop() -> Path
render(output: str = "final.mp4") -> Path
```

### 12.4 Agent helper 示例

```python
# agent-workspace/agent_helpers.py

from screen_harness.helpers import step, caption, highlight_region


def explain_click(label: str, x: int, y: int):
    """为一次标准点击生成字幕和高亮。"""
    step(f"点击{label}")
    caption(f"点击「{label}」，进入下一步。")
    highlight_region(x - 120, y - 40, 240, 80, text=label)


def sop_wait_for_page_load(seconds: float = 2.0):
    """记录页面加载等待说明。"""
    caption("等待页面加载完成。")
    wait(seconds)
```

---

## 13. 动态 helper 机制

### 13.1 机制说明

借鉴 browser-harness，`screen-harness` 在启动时加载：

```text
agent-workspace/agent_helpers.py
```

加载后，将其中公开函数注入到 `helpers.py` 的可调用命名空间。agent 可以在任务过程中编辑该文件，沉淀新的 SOP helper。

### 13.2 生效规则

MVP 推荐规则：

- 每次 `screen-harness -c ...` 启动时加载一次。
- 修改 `agent_helpers.py` 后，下一次命令运行自动生效。
- 不做同一 Python 进程内热更新，避免复杂状态问题。
- helper 文件保存为本地普通文件。
- 不自动 commit，不自动 push。

### 13.3 安全提示

由于 helper 是 Python 代码，它具备本地执行权限。必须在文档和 CLI 中明确提示：

- helper 可以读写文件。
- helper 可以调用系统命令。
- helper 可以访问本地录屏和音频。
- helper 可以调用 AI API 或网络请求。
- 默认只允许受信任 agent 编辑。

MVP 至少提供：

```bash
screen-harness helpers diff
screen-harness helpers open
screen-harness helpers reset
```

---

## 14. 字幕策略

### 14.1 字幕类型

系统支持两类字幕：

1. **逐字稿字幕**  
   基于语音转写，尽量保留用户原话。适合审查和回溯。

2. **SOP 字幕**  
   基于语音、步骤、上下文重写，删除口语、废话、重复内容。适合最终视频。

最终视频默认使用 SOP 字幕。

### 14.2 字幕格式

MVP 支持：

- `SRT`：简单、兼容性好。
- `ASS`：支持位置、字号、样式、背景框，更适合 SOP 视频。

推荐最终渲染使用 ASS。

### 14.3 SOP 字幕风格

默认风格：

- 简洁。
- 使用动词开头。
- 一次只讲一个动作。
- 避免口语词，例如“嗯”“然后呢”“大概就是”。
- 保留关键按钮、字段、页面名称。
- 必要时补充等待、确认、保存等关键动作。

示例：

原始语音：

```text
然后我们这里点一下这个新建，嗯，等它加载出来，然后这里填一下金额和这个事由。
```

SOP 字幕：

```text
点击「新建申请」，等待表单加载完成。
填写报销金额、费用类型和申请事由。
```

---

## 15. 实时字幕方案

MVP 不把实时字幕作为核心交付，但预留能力。

### 15.1 MVP：后期字幕

优点：

- 准确度更高。
- 可以消除口误。
- 可以统一风格。
- 可以避免实时识别错误进入最终视频。

### 15.2 P1：实时预览字幕

录制时显示透明浮窗，展示当前 AI 理解的步骤或临时字幕。

要求：

- 可开启/关闭。
- 可选择是否录入视频。
- 不作为最终字幕真相。

### 15.3 P1/P2：实时烧录字幕

可通过 FFmpeg `drawtext`、动态文本文件、filtergraph 命令或原生渲染层实现。仅作为高级功能，不作为 MVP 依赖。

---

## 16. 渲染方案

### 16.1 MVP 渲染能力

- 将 `sop.ass` 烧录到视频。
- 绘制点击高亮。
- 绘制矩形高亮。
- 绘制打码区域。
- 输出 `final.mp4`。

### 16.2 渲染原则

- 原始视频不覆盖。
- 每次渲染生成新文件或覆盖 `final.mp4` 前确认。
- timeline 是唯一真相。
- 渲染失败不影响原始素材。

### 16.3 后续高级渲染

- 局部放大。
- 鼠标路径强调。
- 自动跳过等待。
- 章节卡片。
- 品牌模板。
- 多语言字幕版本。

---

## 17. 技术架构

### 17.1 MVP 架构

```text
CLI / Agent
  |
  | screen-harness -c "Python code"
  v
run.py
  |
  | loads helpers + agent_helpers
  v
helpers.py
  |
  | recording / timeline / caption / render APIs
  v
recorder.py --------> FFmpeg subprocess
  |
  v
timeline.py --------> timeline.json
  |
  v
transcribe.py ------> local or cloud ASR
  |
  v
captions.py --------> sop.srt / sop.ass
  |
  v
render.py ----------> final.mp4
```

### 17.2 为什么先用 FFmpeg

MVP 阶段使用 FFmpeg 的原因：

- 命令行能力成熟。
- 方便由 Python subprocess 控制。
- 适合录制、抽音频、烧字幕、转码。
- 能快速验证产品闭环。

### 17.3 为什么后续考虑 ScreenCaptureKit

产品化阶段可以考虑原生 macOS 采集内核：

- 更好地控制窗口选择。
- 更好地处理权限、音频和性能。
- 更适合实时预览、窗口排除、系统音频等高级需求。

MVP 决策：

> FFmpeg 负责打通闭环；ScreenCaptureKit 作为 P1/P2 技术演进方向。

---

## 18. 权限与安全

### 18.1 macOS 权限

工具需要处理：

- 屏幕录制权限。
- 麦克风权限。
- 可选：辅助功能权限，用于快捷键、鼠标或窗口信息。
- 可选：文件访问权限。

`screen-harness doctor` 应检查权限状态，并给出清晰指引。

### 18.2 隐私保护

默认策略：

- 原始视频和音频保存在本地。
- 不自动上传。
- AI 转写和总结必须明确配置 provider。
- 提供敏感信息打码事件。
- 提供本地清理命令。

命令：

```bash
screen-harness doctor
screen-harness recordings list
screen-harness recordings clean --older-than 30d
screen-harness redact scan <recording_id>
```

### 18.3 Agent 执行安全

由于 `-c` 和 `agent_helpers.py` 都执行 Python，必须明确：

- 仅在可信环境中使用。
- 对外部 agent 代码保持审查。
- 提供 helper diff 和 reset。
- 后续可加入 allowlist 或 sandbox 模式。

---

## 19. 非功能性需求

### 19.1 性能

MVP 目标：

- 1080p 30fps 录制稳定。
- 录制过程中 CPU 占用可接受，不明显影响业务系统操作。
- 10 分钟视频的基础渲染可在可接受时间内完成。

### 19.2 可靠性

- 录制异常中断时尽量保留已录素材。
- FFmpeg 进程状态可检测。
- 时间线事件写入使用 append 或安全写入，避免数据损坏。
- 渲染失败时输出错误日志。

### 19.3 可维护性

- helper API 简洁。
- timeline schema 稳定。
- 渲染器可替换。
- ASR provider 可替换。
- agent helper 与核心代码隔离。

### 19.4 可解释性

- 最终视频中的每个字幕、标注、打码都能追溯到 timeline 事件。
- AI 生成内容应可人工编辑和重新渲染。

---

## 20. 关键命令设计

```bash
# 初始化项目目录
screen-harness init

# 检查 FFmpeg、权限、设备、录制路径
screen-harness doctor

# 列出设备
screen-harness devices

# 录制
screen-harness record "报销系统 - 创建申请"

# 执行 agent 生成的 Python
screen-harness -c 'start_recording("demo"); wait(5); stop_recording(); render()'

# 转写
screen-harness transcribe <recording_id>

# 生成 SOP 字幕
screen-harness captions generate <recording_id>

# 渲染最终视频
screen-harness render <recording_id>

# 生成文档
screen-harness sop generate <recording_id>

# 查看 helper 修改
screen-harness helpers diff

# 重置 helper
screen-harness helpers reset
```

---

## 21. 验收标准

### 21.1 录制验收

- 用户可以成功录制 1080p 屏幕和麦克风。
- 停止录制后生成 `raw.mp4`。
- 中途异常时不丢失已录素材。

### 21.2 时间线验收

- `step()`、`caption()`、`highlight_region()`、`redact_region()` 可以写入 `timeline.json`。
- 时间戳与视频时间基本对齐。
- 手动修改 `timeline.json` 后可重新渲染。

### 21.3 字幕验收

- 能生成 `sop.srt` 和 `sop.ass`。
- SOP 字幕比逐字稿更简洁。
- 字幕时间与视频画面基本匹配。

### 21.4 渲染验收

- 能生成 `final.mp4`。
- 字幕可见且不遮挡关键 UI。
- 高亮和打码按时间线出现。
- 原始视频不被覆盖。

### 21.5 动态 helper 验收

- agent 可以写入 `agent-workspace/agent_helpers.py`。
- 下一次运行 CLI 时新 helper 可用。
- `helpers diff` 能展示修改。
- `helpers reset` 能恢复到空 helper 或默认模板。

---

## 22. 里程碑

### Milestone 0：技术验证

目标：打通最小录屏和渲染链路。

交付：

- FFmpeg 录屏 wrapper。
- 录制开始/停止。
- 生成 `raw.mp4`。
- 手写 `sop.ass` 后能烧录到 `final.mp4`。

### Milestone 1：MVP CLI

目标：形成可用 CLI-first 产品。

交付：

- `screen-harness -c`。
- `helpers.py`。
- `timeline.json`。
- `step`、`caption`、`highlight`、`redact`。
- 后期渲染。
- `agent-workspace/agent_helpers.py`。

### Milestone 2：AI SOP 生成

目标：从语音和时间线生成正式 SOP。

交付：

- 音频抽取。
- 转写接口。
- SOP 字幕生成。
- Markdown SOP 生成。
- 基础敏感信息提示。

### Milestone 3：交互体验增强

目标：让非工程用户也能顺畅使用。

交付：

- 快捷键打点。
- 简单菜单栏入口或轻量 GUI。
- 实时字幕预览。
- recording 管理。

### Milestone 4：产品化能力

目标：面向团队 SOP 规模化使用。

交付：

- 模板库。
- 多语言字幕。
- 自动打码增强。
- ScreenCaptureKit 采集内核评估或替换。
- 文档平台导出。

---

## 23. 风险与应对

### 风险 1：macOS 权限和录制兼容性复杂

应对：

- MVP 先提供 `doctor`。
- 明确支持范围，例如 macOS 版本、主屏录制、麦克风录制。
- 产品化阶段再升级原生采集。

### 风险 2：实时字幕准确度不稳定

应对：

- MVP 不依赖实时字幕。
- 最终视频使用后期 SOP 字幕。
- 实时字幕仅作为预览。

### 风险 3：AI 生成内容不可靠

应对：

- 输出可编辑 `timeline.json` 和 `sop.md`。
- 支持重新生成和重新渲染。
- 保留逐字稿供人工核对。

### 风险 4：敏感信息泄露

应对：

- 本地优先。
- 不自动上传。
- 提供打码事件。
- 提供清理命令。
- 录制前显示提醒。

### 风险 5：agent helper 权限过大

应对：

- 明确安全提示。
- 仅信任 agent 可写。
- 提供 diff、reset。
- 后续增加 sandbox 或 allowlist。

---

## 24. 成功指标

### 产品指标

- 单条 SOP 从录制到最终视频的平均耗时。
- 用户手动编辑字幕的次数和时长。
- 生成视频被团队查看或复用的次数。
- SOP 文档导出的次数。
- 同一 helper 被复用的次数。

### 质量指标

- 字幕时间对齐准确率。
- 用户对 SOP 字幕质量评分。
- 敏感信息漏打码率。
- 录制失败率。
- 渲染失败率。

### 开发者指标

- agent helper 新增数量。
- domain skill 新增数量。
- CLI 调用成功率。
- 平均从新流程到可复用 helper 的时间。

---

## 25. 开放问题

1. MVP 是否只支持全屏录制，还是必须支持窗口录制？
2. 是否需要录制系统声音？如果需要，MVP 是否接受虚拟声卡方案？
3. 转写默认使用本地模型还是云端 API？
4. 公司内部使用时，是否允许上传音频到第三方 AI 服务？
5. timeline 编辑优先做 JSON 手工编辑，还是轻量 UI？
6. 是否需要从第一版开始支持快捷键打点？
7. SOP 文档导出优先支持 Markdown、Notion 还是 Confluence？
8. helper 是否允许 agent 自动修改，还是每次修改前都要用户确认？
9. 最终视频是否需要统一品牌样式，例如 logo、字体、片头片尾？
10. 是否要支持多人审阅和版本管理？

---

## 26. MVP 示例脚本

```python
# examples/expense_sop.py

start_recording("expense_create_request")

chapter("创建报销申请")

step("打开报销系统")
caption("进入公司后台，在左侧菜单打开「报销系统」。")
wait_for_user("打开报销系统后继续")

step("新建申请")
caption("点击右上角「新建申请」，进入申请表单。")
highlight_region(1240, 88, 180, 64, text="新建申请")
wait_for_user("进入申请表单后继续")

step("填写申请信息")
caption("填写报销金额、费用类型、申请事由和附件。")
wait_for_user("填写完成后继续")

step("提交申请")
caption("确认信息无误后，点击「提交」完成申请。")
highlight_region(1320, 920, 160, 64, text="提交")
wait_for_user("提交完成后继续")

stop_recording()
transcribe()
generate_sop_captions()
generate_markdown_sop()
render()
```

---

## 27. 总结

`screen-harness` 的核心不是做一个更复杂的录屏软件，而是做一个 AI 可编程的 SOP 生成工作台。

它借鉴 browser-harness 的设计：

```text
底层能力由成熟工具提供
核心代码保持薄封装
agent 通过 Python helper 扩展能力
经验沉淀在 workspace
每次运行都可以复用之前积累的 helper
```

第一版应该优先打通：

```text
录屏 → timeline → 转写 → SOP 字幕 → 渲染 → 文档 → helper 复用
```

只要这个闭环成立，后续实时字幕、自动打码、窗口录制、模板库、团队协作都可以在此基础上逐步增强。
