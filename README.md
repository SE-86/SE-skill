# ai-builder-guide · AI 工程规范库

> **39 份面向 AI 的工程规范文档 · 约 26.4 万字 · 9 类路由 · 一条命令装进 15 种 AI 工具**
>
> 让 Claude / Cursor / Codex / Gemini / Copilot / Windsurf / WorkBuddy 等任意 AI 在写代码前，
> **按需**读取你沉淀的工程规范——而不是每次从头解释，也不会一次性把 26 万字灌爆上下文。

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-39%20%E4%BB%B6-orange.svg)]()
[![Size](https://img.shields.io/badge/corpus-264%20KB-informational.svg)]()

---

## 这是什么

一个**渐进式披露（progressive disclosure）**的知识库。

市面上的"AI 规则库"大多是把整份规范塞进系统提示，结果是每次对话都烧掉几万 token、
且 AI 往往只用到其中一小部分。这个项目换了个思路：

| 层级 | 文件 | 体量 | 何时加载 |
|---|---|---|---|
| **L1 总表** | `SKILL.md` | ~3 KB | **每次都载**，仅用于分类定向 |
| **L2 路由** | `routes/X-*.md` | ~2–6 KB | 确定分类后加载**一个** |
| **L3 正文** | 源文档的某几十行 | 通常 1–8 KB | **只读命中的那个章节** |

**单次任务典型消耗 ≈ 12 KB，而不是全库 464 KB。**

核心约束写在 `CORE.md` 里，作为三条铁律：

1. **禁止全量读取** —— 全读会导致上下文溢出、输出截断、API 限流。这不是效率问题，是正确性问题。
2. **按需精确到"章节"** —— 每份文档都切好锚点，标注起止行号，只读那几十行。
3. **先读 CLASSIFY，再读内容** —— 文件名有歧义（本库就有 3 组同名/近名文档），必须先查路由表。

---

## 快速开始

### 方式一：图形界面（推荐，零门槛）

下载 `AI工程规范库安装器.exe`，**双击即用，对方不需要装 Python**。

它会扫描本机装了哪些 AI 工具，勾选后一键安装，卸载时精准摘除、绝不弄脏你原有的配置文件。

### 方式二：命令行

```bash
python install.py scan                  # 扫描本机 AI 工具，只读不动
python install.py install               # 交互式选择安装
python install.py install --all         # 装到所有检测到的工具
python install.py status                # 查看安装状态
python install.py uninstall claude      # 卸载
```

### 方式三：发给朋友（便携套件）

```bash
python install.py bundle --zip          # 生成自包含 zip，直接发过去
```

对方解压后双击 exe 即可，**不依赖你机器上的任何绝对路径**。

---

## 它支持哪些 AI

安装器会自动探测本机环境，并**按每种工具的官方约定**选择正确的落点。

### 关键：装一次，多端生效

`~/.agents/skills/` 是 **Agent Skills 标准的跨端互操作目录**，
Codex / Cursor / Copilot / Gemini CLI / Windsurf **全部**会扫描它。

| 工具 | 读取 `~/.agents/skills/` | 落点 |
|---|---|---|
| Codex CLI | ✅ 原生扫描 | `~/.agents/skills/` |
| Cursor | ✅ 还额外读 `.claude/skills/`、`.codex/skills/` | `~/.cursor/skills/` |
| GitHub Copilot | ✅ | `~/.copilot/skills/` |
| Gemini CLI | ✅（优先级高于 `.gemini/skills/`） | `~/.gemini/skills/` |
| Windsurf | ✅ 跨代理兼容扫描 | `~/.codeium/windsurf/skills/` |
| **Claude Code** | ❌ **只读自己的目录** | `~/.claude/skills/` |
| **WorkBuddy** | ❌ | `~/.workbuddy/skills/` |

> 所以**最优解是装两处**：通用目录 + Claude Code。
> （Cursor 会顺带从 `~/.claude/skills/` 读取，装了 Claude 就等于也装了 Cursor。）

支持列表：WorkBuddy、Claude Code、CodeBuddy、Cursor、Windsurf、Trae、Codex CLI、
Gemini CLI、Aider、OpenHands、Continue、Cline / Roo Code、GitHub Copilot、Zed、VS Code。

### 各种落点形态

| 形态 | 说明 |
|---|---|
| **技能目录** | 复制完整技能包到 `~/.<工具>/skills/ai-builder-guide/`，原生支持 skills 的工具走这条 |
| **桥接块** | 往 `AGENTS.md` / `GEMINI.md` / `user_rules.md` 追加带标记的内容，卸载时精准摘除 |
| **项目规则** | 需 `--project <路径>`，写 `.cursor/rules/*.mdc`、`.clinerules/` 等 |

---

## 知识库内容

### 9 类路由

| 分类 | 覆盖内容 |
|---|---|
| **A · 协作与 AI 行为** | 多 AI 接力、角色扮演、拟真聊天、**无联网时的信息获取** |
| **B · 工具·素材·文档生成** | 图片/视频生成、PPT/Word/表格规范、**Fab/Quixel/CC0 素材与授权**、Blender、MCP 配置 |
| **C · 安全与稳定（P0）** | 备份恢复、日志脱敏、环境隔离、回滚、限流熔断、认证授权、防 XSS/CSRF/注入、密钥管理 |
| **D · 工程化与后端** | Git 流程、CI/CD、测试、监控可观测、性能；后端 API、数据库迁移、**报错处理** |
| **E · 网页前端工程** | 技术栈选型、组件/路由/状态管理、表单、国际化、无障碍、应用框架 |
| **F · 网页视觉风格** | 苹果风、简约风、植物风、杂志/报纸/手绘风；**登录页 / 社区页 / 游戏宣传页** |
| **G · 跨端与底层** | 移动端适配、Electron/Tauri、小程序、Flutter/RN、图形学、物理引擎、网络同步 |
| **H · 游戏开发** | 2D/3D、引擎选型、联机多人、游戏 UI、存档/经济/匹配/反作弊、数值关卡 |
| **I · UE5 与 UI 页面** | **UE5.8 实验性 MCP**、蓝图/C++/渲染/动画/打包；**跨端应用类 UI 页面**规范 |

### 部分文档

<details>
<summary><b>展开查看全部 39 份文档</b></summary>

**安全与工程化**
- `P0 安全与稳定性规范.md`
- `工程化与可观测性协作规范.md`
- `文件储存和数据迁移.md`
- `无联网能力时的信息获取与下载规范.md`
- `开发/报错处理.md` · `开发/补充规范.md`
- `开发/安全与协作基础规范.md` · `开发/安全与协作基础实现规范.md`

**网页与前端**
- `开发/开发：网页前后端/开发前端.md` · `开发后端.md`
- `开发/开发：网页前后端/网页开发教程（万能）.md`
- 风格专项：苹果风 / 简约风 / 植物风 / 杂志报纸手绘风
- 页面专项：登录与社区 · 游戏宣传页 · 聊天页面（网页版）
- `开发/前端进阶系统实现规范.md` · `开发/UI 页面通用实现规范.md`

**游戏与引擎**（均在 `开发/编程：游戏制作/`）
- `2d.md` · `3d.md` · `引擎怎么用.md` · `全自动开发.md`
- 游戏 UI：`游戏ui页面.md` · `聊天页面实现.md`（**游戏版**，与网页版同名不同物）
- 联机：`联机实现.md`（用现成平台） · `联机实现2.md`（从零手写，**原文原则与前者相反**）
- `游戏系统与引擎进阶实现规范.md` · `开发/游戏系统深度实现规范.md`
- `UE5 MCP 深度教程.md` · `UE5 引擎使用知识手册.md`

**素材与工具**
- `开发/素材获取.md` · `开发/Blender 建模与 MCP 使用规范.md`
- `图片或视频生成.md` · `PPT  DOCX  表格 文件生成规范.md`

**跨端与 AI 协作**
- `开发/跨端与底层系统实现规范.md`
- `多ai怎么办.md` · `仅仅面向聊天或角色扮演的教程！.md`

</details>

---

## 目录结构

```
Universal-AI-Skills/
├── AI工程规范库安装器.exe   # 图形安装器（双击即用，无需 Python）
├── gui.py                   # 图形界面源码
├── install.py               # 命令行安装器：扫描 + 一键部署
├── AGENTS.md                # 通用桥接入口（给无 Skill 机制的框架）
├── SKILL.md                 # 总入口：分类路由表
├── CORE.md                  # 通用执行协议（三条铁律 + 读取方法）
├── INDEX.md                 # 全库 39 份文档 × 全部章节的行号锚点
├── manifest.json            # 同上，机器可读
├── routes/                  # 9 个分类路由（二级）
│   ├── A-协作与AI行为.md    ├── B-工具与素材.md
│   ├── C-安全与稳定.md      ├── D-工程化与后端.md
│   ├── E-网页前端工程.md    ├── F-网页视觉风格.md
│   ├── G-跨端与底层.md      ├── H-游戏开发.md
│   └── I-UE5与UI页面.md
└── tools/                   # 维护脚本
    ├── rebuild_manifest.py  # 重建行号锚点
    ├── gen_index.py         # 重新生成 INDEX.md
    └── build_exe.bat        # 打包图形安装器
```

### 为什么用"行号锚点"而不是物理拆分

一个自然的做法是把 39 份文档按章节切成上百个碎片文件。我们没有这么做：

- `Read(file, offset, limit)` 与读一个独立文件的**上下文成本完全相同**，但粒度更细（能精确到单个组件）
- 物理拆分会产生大量碎文件，难以同步，且**破坏文档内部的交叉引用**
- 章节信息以数据形式集中在 `manifest.json` / `INDEX.md`，AI 可检索、可编程

---

## ⚠️ 三组易混淆文档（读错必返工）

本库有 3 组同名或高度重叠的文档，`CORE.md` 里为此专门设了铁律 3（先查路由再读）。GitHub 读者看不到 `SKILL.md`，所以直接列在这里：

| 陷阱 | 怎么分辨 |
|---|---|
| `聊天页面实现.md` 有**两份** | 网页版在 `开发：网页前后端/`，游戏版（内嵌聊天框）在 `编程：游戏制作/` |
| `联机实现.md` vs `联机实现2.md` | 前者用现成平台（Nakama/Steam 等），后者从零手写。**两者的原文原则几乎完全相反**，先确认约束是"用平台"还是"自建" |
| `安全与协作基础规范.md` vs `安全与协作基础实现规范.md` | 后者是完整版，优先读后者 |

还有一处文件名陷阱：`PPT  DOCX  表格 文件生成规范.md` **文件名含双空格**，脚本引用时不能改写成单空格。

---

## 设计上的几个取舍

**为什么不生成一份"超大 SKILL.md"**
因为它每次都会被完整载入。哪怕只用到 5%，也要为 100% 付费，且挤占上下文导致真正重要的信息被淹没。

**为什么不放 `references/` 让 AI 自由检索**
自由检索意味着 AI 要读多个文件才能判断相关性。本库用**人工编写的路由表**把选择成本降为 O(1)：
看 `SKILL.md` 的表 → 读一个 `routes/X.md` → 读一个章节。

**为什么路由文件要手写而不脚本生成**
脚本只能按标题切分，但"什么时候该读这一段"需要判断。`tools/*.py` 只负责**重建行号锚点**
（源文档改动后行号会漂移，需要重跑），路由内容由人维护。

---

## 维护

源文档修改后，行号会漂移，需要重建索引：

```bash
python tools/rebuild_manifest.py    # 重建 manifest.json 行号锚点
python tools/gen_index.py           # 重新生成 INDEX.md
```

> `routes/*.md` 是手工编写的高价值路由，脚本**不会**覆盖它，需要人工同步。

### 新增文档的注意事项

每章**至少写一个 `N.N` 小节标记**，否则索引会把它吞进上一段。
（这不是脚本的 bug，是 Markdown 标题层级本身的信息缺失。）

---

## 一些已知的坑

这些都是实际踩过并修好的，记录下来省得后来人重蹈：

<details>
<summary><b>各工具路径差异</b></summary>

- **Windsurf 的全局 skills 是 `~/.codeium/windsurf/skills/`**，不是 `~/.windsurf/skills/`。装错目录的后果是"文件在磁盘上，但永远不被读取"。
- **Trae 没有 SKILL.md 机制**，只有规则文件：全局 `~/.trae/user_rules/`、项目 `.trae/rules/*.md`。
- **Cursor 的 `.mdc` 要求 YAML frontmatter 在文件第一行**，前面连 HTML 注释都不能有。
- `.cursorrules` 是 legacy 格式，新版应写 `.cursor/rules/*.mdc`。

</details>

<details>
<summary><b>静默失败（最危险的一类）</b></summary>

- **Windsurf 全局规则限 6000 字符，项目规则限 12000 字符**，超出会被**静默截断**，规则尾部直接消失且**不报任何错**。
- **Codex 的技能清单有上下文预算**：最多占 2% 窗口（未知时按 8000 字符算），装太多技能时它会先缩短 `description`，甚至直接省略部分技能。
- **Cursor 单条规则建议 500 行内**。超长的 always-apply 规则会持续吃上下文，包括与它完全无关的对话。

</details>

<details>
<summary><b>打包成 exe 的坑</b></summary>

- **PyInstaller 的 `--windowed` 模式下 `sys.stdout` / `sys.stderr` 都是 `None`**。任何 `sys.stderr.write(...)` 都会抛
  `AttributeError: 'NoneType' object has no attribute 'write'`，
  且因为发生在模块导入期，界面来不及显示，只会弹一个 "Unhandled exception in script"。
  → 所有诊断输出必须走判空的安全 log 函数。
- **验证路径 ≠ 使用路径**：`--selftest` 从命令行跑、有控制台，永远 PASS；用户是双击、无控制台。
  打包产物必须在**真实使用方式**下再验一遍。

</details>

<details>
<summary><b>多副本共存</b></summary>

装到多个工具后，每个副本里的绝对路径可能指向不同位置，其中一份失效时**你不会收到任何报错**。
所以 `CORE.md` 里写明了降级顺序：
`绝对路径 → 本副本的 corpus/ → 按文件名全局搜索`（39 个文件名全库唯一，一定搜得到）。

</details>

---

## 许可

MIT。文档内容为工程规范知识，可自由修改、翻译、二次分发。

> **安全提示**：本项目是**纯知识库**（Markdown + JSON），不执行任何脚本、不联网、不修改你的项目代码。
> 但请注意 —— **技能本身就是高权限指令**，AI 会照着它执行。
> 若你从第三方来源安装别人的 skill，等同于在授予它执行权限，请像 review 依赖一样 review 它。
