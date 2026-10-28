# mkstruct

[![Latest Release](https://img.shields.io/github/v/release/WebAIHarnessRoom/mkstruct?label=release)](https://github.com/WebAIHarnessRoom/mkstruct/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

根据树形结构文本，一键创建目录与空文件的项目骨架生成器。

把 `tree` 命令风格的目录树（或设计文档里常见的树形结构）直接粘贴给它，就能在指定位置批量创建出完整的目录和文件结构，省去手工 `mkdir` / `touch` 的重复劳动。

提供 **命令行（CLI）** 与 **图形界面（GUI）** 两种形态，二者共享同一套解析与创建逻辑，行为完全一致。

> （此处放一张 GUI 截图，建议尺寸 1200×720，展示左侧结构文本、右侧解析树、底部日志）

---

## 特性

- **两种形态**：CLI 适合脚本与管道，GUI 适合可视化校对与交互确认。
- **三种输入方式**：结构文本文件、命令行字符串、标准输入 / 管道 / 剪贴板。
- **自动识别层级**：支持 `├──`、`└──`、`│`、`--`、空格缩进等多种树形画法，缩进宽度自动推断。
- **目录以 `/` 结尾**：带 `/` 结尾或有子节点的节点视为目录，其余视为文件，`Makefile`、`LICENSE` 这类无扩展名文件也能被正确识别。
- **忽略行内注释**：`空格 + #` 之后的内容会被剥离，方便直接复用带说明文字的结构文本。
- **简写自动展开**：`RtmpDataSource.h/.cpp` 会自动创建 `RtmpDataSource.h` 和 `RtmpDataSource.cpp` 两个文件。
- **实时预览**：GUI 输入即解析，右侧树视图实时呈现目录/文件判定结果。
- **预览与写入分离**：`--dry-run` / GUI「预览」不写磁盘；正式写入前必须确认。
- **幂等安全**：已存在的文件不会被覆盖，只会标记为 `skip`。
- **零第三方依赖**：仅使用 Python 标准库。

---

## 安装

### 方式一：下载发布版可执行文件（推荐，最终用户）

前往本项目的 **Releases** 页面下载最新版本：

- `mkstruct.exe` —— 命令行版本
- `mkstruct-gui.exe` —— 图形界面版本

两个文件均为独立单文件 exe，无需安装 Python 或任何依赖，下载后即可使用。

**让 CLI 可以在任意位置调用**：把 `mkstruct.exe` 放到一个已在 `PATH` 中的目录（如 `C:\Tools\`），或把其所在目录加入系统环境变量 `PATH`，之后即可：

```powershell
mkstruct tree.txt -d .\out
```

**GUI 直接双击** `mkstruct-gui.exe` 启动。

> 首次运行若被 Windows SmartScreen 或杀毒软件拦截，是因为单文件 exe 未做代码签名，属已知误报，可选择"仍要运行"或在杀软中添加信任。

### 方式二：从源码运行（开发者）

需要 Python 3.8 或更高版本，无第三方依赖。

```bash
git clone https://github.com/WebAIHarnessRoom/mkstruct.git
cd mkstruct
python mkstruct.py --help        # CLI
python gui.py                     # GUI
```

> ⚠️ `mkstruct.py` 依赖同目录的 `core.py`，**不能单独拷走单个文件**。源码分发请整目录 clone。

### 方式三：自行打包 exe

参见 [`DEVELOPMENT.md`](DEVELOPMENT.md) 的「打包」一节。

---

## 快速开始

假设有一个 `tree.txt`，内容为：

```
VideoPlayer/
├── CMakeLists.txt                  # 顶层CMake
├── cmake/
│   ├── FindFFmpeg.cmake
│   └── vcpkg.cmake
├── src/
│   ├── main.cpp
│   └── common/
│       ├── Logger.h
│       ├── Logger.cpp
│       └── Types.h
└── docs/
    ├── design_stage1.md
    └── todo_stage1.md
```

### CLI

```bash
# 先预览（不写磁盘）
mkstruct tree.txt -d ./out --dry-run

# 确认后正式创建
mkstruct tree.txt -d ./out
```

执行完成后，`./out/VideoPlayer/` 下会生成完整骨架。

### GUI

1. 双击 `mkstruct-gui.exe`（或 `python gui.py`）。
2. 点击「打开文件」选择 `tree.txt`，或直接粘贴到左侧文本框。
3. 右侧立即显示解析结果，核对目录/文件判定是否正确。
4. 在工具栏填写「目标目录」（可用「浏览…」选择）。
5. 点击「预览」在下方日志查看将创建的内容。
6. 确认无误后点击「创建」，勾选「我已预览并确认写入」，提交。

---

## 结构文本约定

为了让解析结果可预期，请遵循下面三条约定。

### 1. 目录名以 `/` 结尾

```
src/           ← 目录
main.cpp       ← 文件
common/        ← 目录
Logger.h       ← 文件
```

只要目录带 `/`，脚本就不需要靠“有没有扩展名”去猜，`Makefile`、`LICENSE` 这类无扩展名文件也能被正确识别为文件。

### 2. 行内注释用 `空格 + #`

```
├── Logger.h                # 日志接口
├── RtmpDataSource.h/.cpp   # RTMP数据源实现
```

`#` 之前必须有空白字符。如果 `#` 出现在文件名内部（比如 `C#.md`），不会被当成注释。

### 3. 简写 `Foo.h/.cpp` 会自动展开

```
RtmpDataSource.h/.cpp
```

等价于：

```
RtmpDataSource.h
RtmpDataSource.cpp
```

展开规则：`/` 前面部分含 `.`、`/` 后面像纯扩展名（字母数字下划线）时才展开，避免误伤 `dir/.gitignore` 这类写法。

---

## 命令行参考

```
usage: mkstruct [-h] [-s STRING] [-d DEST] [-n] [-q] [--show] [-V] [structure]
```

| 参数 | 说明 |
| --- | --- |
| `structure` | 位置参数。结构文本文件路径；传 `-` 表示从标准输入读取。 |
| `-s, --string` | 直接把结构文本作为字符串传入。 |
| `-d, --dest` | 创建位置，默认为当前目录 `.`。 |
| `-n, --dry-run` | 只显示将要创建的内容，不实际写入。 |
| `-q, --quiet` | 静默模式，只输出最终统计。 |
| `--show` | 打印解析出的树，用于校对解析结果。 |
| `-V, --version` | 显示版本号并退出。 |
| `-h, --help` | 显示帮助信息。 |

**输入优先级**：`-s` > 位置参数 `structure` > 标准输入。

**常用示例：**

```bash
# 从文件创建
mkstruct tree.txt -d ./out

# 直接传入字符串
mkstruct -s "src/
├── main.py
└── utils/
    └── helper.py" -d ./out

# 从标准输入 / 管道
cat tree.txt | mkstruct -d ./out

# macOS：直接从剪贴板创建
pbpaste | mkstruct -d ./out

# Windows PowerShell：从剪贴板创建
Get-Clipboard | mkstruct -d ./out

# 先预览再执行
mkstruct tree.txt -d ./out --dry-run

# 排查解析问题
mkstruct tree.txt -d ./out --show --dry-run

# 静默执行（适合脚本调用）
mkstruct tree.txt -d ./out -q
```

---

## GUI 使用说明

### 界面布局

```
┌────────────────────────────────────────────────────────────────────┐
│ [logo] mkstruct │ 打开文件 粘贴 清空 │ 目标目录 [________] [浏览…]  │
├────────────────────────────────────────────────────────────────────┤
│ ☑ 预览模式  ☑ 显示解析树  ☐ 深色模式  [生成 CLI 命令] [预览] [创建]│
├──────────────────────────────┬─────────────────────────────────────┤
│ 结构文本                      │ 解析预览                            │
│ ┌──────────────────────────┐ │ ┌─────────────────────────────────┐ │
│ │ VideoPlayer/             │ │ │ ▼ VideoPlayer/          [目录]  │ │
│ │ ├── CMakeLists.txt       │ │ │   ├─ CMakeLists.txt     [文件]  │ │
│ │ └── src/                 │ │ │   └─ src/               [目录]  │ │
│ └──────────────────────────┘ │ └─────────────────────────────────┘ │
│                              │ 执行日志                            │
│                              │ ┌─────────────────────────────────┐ │
│                              │ │ 目标位置：D:\out  [预览模式]    │ │
│                              │ │   ▸ [dir ] D:\out\VideoPlayer   │ │
│                              │ │   • [file] D:\out\...\main.cpp  │ │
│                              │ │ 完成：2 个目录，2 个文件        │ │
│                              │ └─────────────────────────────────┘ │
├──────────────────────────────┴─────────────────────────────────────┤
│ 已解析 2 个目录 / 2 个文件 · 目标: D:\out          预览模式         │
└────────────────────────────────────────────────────────────────────┘
```

### 关键行为

- **实时解析**：输入后 300ms 自动解析，无需手动触发。解析不出有效行时状态栏变红，「预览」「创建」按钮禁用。
- **错误行高亮**：无法解析的行在文本区背景标红，状态栏提示「第 N 行无法解析」，**点击状态栏可跳转到该行**。
- **预览 vs 创建**：「预览」只列日志不写盘；「创建」会弹出确认对话框，**必须勾选「我已预览并确认写入」**才能提交，防止误点。
- **已存在文件**：无论预览还是创建，已存在的文件都标为 `[skip]`，内容不会被覆盖。
- **生成 CLI 命令**：把当前配置（输入来源、目标目录、预览模式）拼成一条命令并复制到剪贴板，方便脚本化或记入文档。
- **深色模式**：勾选后立即切换，选择会持久化。

### 快捷键

| 快捷键 | 动作 |
| --- | --- |
| `Ctrl+O` | 打开结构文本文件 |
| `Ctrl+Enter` | 预览 |
| `Ctrl+Shift+Enter` | 创建 |
| `Ctrl+L` | 清空日志 |
| `F1` | 显示帮助 |

### 配置文件与日志

| 文件 | 位置 | 作用 |
| --- | --- | --- |
| 配置 | `~/.mkstruct_gui.json` | 记住上次的目标目录、复选框状态、窗口大小、深色模式 |
| 错误日志 | `~/mkstruct-gui-error.log` | GUI 未捕获异常的完整堆栈（正常使用时不会生成） |

删除配置文件即可恢复默认状态。

---

## 解析规则细节

1. **剥离行内注释**：遇到 `空白 + #` 就截断该行。
2. **跳过空行**：空行和纯装饰行会被忽略。
3. **去除树形前缀**：逐字符剥离 `空格`、`│`、`|`、`├`、`└`、`┌`、`─`、`-`、`+`、`` ` `` 等装饰字符，剩下的就是节点名。
4. **推断缩进宽度**：统计所有行中第一个连接符的出现位置，取其最大公约数作为每级宽度（常见为 4）。推断失败时回退为 4。
5. **计算层级深度**：根据连接符位置除以宽度得到 `depth`。
6. **组装树**：用栈按 `depth` 组装成树（森林）。
7. **判定目录/文件**：
   - 名字以 `/` 或 `\` 结尾 → 目录（去掉结尾的斜杠）
   - 有子节点 → 目录
   - 其余 → 文件
8. **创建**：
   - 目录用 `mkdir(parents=True, exist_ok=True)`
   - 文件用 `touch()`；如果已存在则跳过并计入 `skipped`

---

## 常见问题

### Q：顶层写了一个 `ProjectName/`，结果多套了一层目录？

因为第一行的 `ProjectName/` 会被当作一个子目录创建在 `-d` 指定的位置下。如果希望直接在当前位置展开所有内容，删掉第一行，并把所有行的缩进减一级即可。

### Q：无扩展名的文件（Makefile、LICENSE）被当成目录了吗？

不会。判定规则只看是否以 `/` 结尾或有子节点，与扩展名无关。只要结构文本里给文件不加 `/` 结尾，它就会被创建为文件。

### Q：已存在的文件会被覆盖吗？

不会。脚本只会 `touch()` 不存在的文件，已存在的会打印 `skip` 并计入统计，内容不受影响，重复执行是安全的。

### Q：Windows 下中文注释乱码？

CLI 已经尝试将标准输出重新配置为 UTF-8。如果仍然乱码，可以在运行前执行：

```powershell
chcp 65001
```

### Q：支持 `tree` 命令直接输出的格式吗？

支持。Linux/macOS 的 `tree` 以及 Windows 的 `tree /F` 输出（去掉开头的统计行）都能被解析，只要目录带有可识别的树形连接符或缩进。

### Q：如何把结构文本从 Markdown 代码块里直接喂给它？

```bash
# 从 Markdown 文件中提取第一个代码块并创建
awk '/^```/{f=!f;next} f' design.md | mkstruct -d ./out
```

### Q：GUI 里能看到图标，但 exe 在资源管理器里还是旧图标？

Windows 图标缓存问题。把 exe 改名或复制到新目录即可强制刷新，或运行 `ie4uinit.exe -ClearIconCache` 后重启资源管理器。

### Q：单文件 exe 启动比较慢？

`--onefile` 模式首次运行需要把 Python 运行时释放到临时目录，通常有 0.5–2 秒延迟，属正常现象。对启动速度敏感可改用 `--onedir` 模式（`dist/mkstruct/` 目录整体分发）。

---

## 项目结构

```
mkstruct/
├── core.py            # 核心逻辑：解析、组装、创建（无 I/O 打印）
├── mkstruct.py        # CLI 入口
├── gui.py             # GUI 入口（Tkinter）
├── resource/
│   └── app.ico        # 应用图标（CLI + GUI 共用）
├── README.md          # 本文档
├── DEVELOPMENT.md     # 开发与打包指南
├── CHANGELOG.md       # 版本历史
└── LICENSE            # MIT
```

---

## 许可证

[MIT](LICENSE)

---

## 致谢

灵感来自反复手敲 `mkdir -p` 和 `touch` 的痛苦。