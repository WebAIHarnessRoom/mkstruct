# 开发指南

本文档面向需要修改、扩展或重新打包 mkstruct 的开发者。最终用户请看 [`README.md`](README.md)。

---

## 项目结构

```
mkstruct/
├── core.py            # 核心逻辑，无 I/O 打印
├── mkstruct.py        # CLI 入口
├── gui.py             # GUI 入口（Tkinter）
├── resource/
│   └── app.ico        # 应用图标
├── README.md
├── DEVELOPMENT.md
├── CHANGELOG.md
└── LICENSE
```

---

## 架构分层

```
┌─────────────────────────────────────────────┐
│  mkstruct.py (CLI)      gui.py (GUI)        │  ← 表现层
├─────────────────────────────────────────────┤
│              core.py                        │  ← 逻辑层
│  parse_structure / build_forest / finalize  │
│  prepare / create_all / count_stats         │
└─────────────────────────────────────────────┘
```

**核心约束：`core.py` 不做任何 I/O 打印、不读 `sys.stdin`、不写 `sys.stdout`。**

所有输出通过返回值（`Prepared`、`ParseResult`）或回调（`on_event(Event)`）交给上层渲染。这样 CLI 和 GUI 对同一份输入必然得到相同结果，不会出现行为漂移。

### 数据流

```
文本输入
   │
   ▼
parse_structure(text) ──► ParseResult(entries, issues)
   │
   ▼
build_forest(entries) ──► 森林（嵌套 dict）
   │
   ▼
finalize(forest)      ──► 就地判定 is_dir 并去掉尾部斜杠
   │
   ▼
create_all(forest, dest, dry_run, on_event) ──► stats
                                              │
                              ┌───────────────┴───────────────┐
                              ▼                               ▼
                         CLI: print(...)              GUI: queue.Queue
                                                        → 主线程渲染日志
```

---

## 核心 API

### `prepare(text: str) -> Prepared`

一步完成解析、组装、判定，返回可直接渲染/创建的结果。

```python
@dataclass
class Prepared:
    forest: list      # 森林根节点列表
    entries: list     # [(depth, name), ...]
    issues: list      # ParseIssue 列表（无法解析的行）
```

`entries` 为空表示没有任何有效结构行，调用方应据此禁用执行。

### `ParseIssue`

```python
@dataclass
class ParseIssue:
    line_no: int      # 1-based 行号
    text: str         # 原始行内容
    reason: str       # 无法解析的原因
```

GUI 用它来高亮问题行、状态栏跳转定位。

### `create_all(forest, base, *, dry_run=False, on_event=None, stats=None) -> dict`

递归创建。事件通过 `on_event(Event)` 回调，不直接打印。

```python
@dataclass
class Event:
    type: str         # "dir" | "file" | "skip"
    path: Path
    created: bool     # 是否本次实际新建（dir 已存在时为 False）
```

`stats` 返回 `{"dirs": int, "files": int, "skipped": int}`。

`dry_run=True` 时不写磁盘，但仍检查文件是否存在，因此预览中也能看到 `skip` 标记。

### `count_stats(forest) -> (dirs, files)`

遍历森林统计目录/文件数量（含子节点），用于 GUI 状态栏与确认对话框。

### 节点结构

森林中每个节点是 dict：

```python
{
    "name": str,          # 节点名（目录已去掉尾部斜杠）
    "children": list,     # 子节点列表
    "is_dir": bool|None,  # finalize 后一定为 bool
}
```

用 dict 而非 class 是为了让 `--show` 的打印和 JSON 序列化简单直接。

---

## 环境搭建

```bash
# 推荐 Python 3.8+
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 开发阶段无需第三方依赖
# 打包阶段需要 PyInstaller
pip install pyinstaller
```

GUI 依赖 Tkinter。Windows 官方 Python 与 conda 环境默认自带；Linux 需要 `sudo apt install python3-tk`。

---

## 运行与调试

```bash
# CLI
python mkstruct.py tree.txt -d ./out --show --dry-run

# GUI
python gui.py
```

### GUI 调试技巧

- 想看被吞掉的异常？把 `gui.py` 的 `main()` 里 `--windowed` 相关逻辑临时换成直接运行，异常会打印到终端。
- `sys.excepthook` 已安装，未捕获异常会写入 `~/mkstruct-gui-error.log` 并弹窗。
- 解析逻辑有问题时，先单独跑 `python -c "from core import prepare; print(prepare(open('tree.txt').read()))"`，排除 UI 干扰。

---

## 打包

打包必须使用**绝对路径**指定 `--icon` 和 `--add-data` 的源文件。原因见下方“常见打包问题”。

### CLI

```powershell
pyinstaller --onefile --console --clean --name mkstruct `
  --icon "$PWD\resource\app.ico" `
  --distpath dist/mkstruct --workpath build --specpath build `
  mkstruct.py
```

产物：`dist/mkstruct/mkstruct.exe`

### GUI

```powershell
pyinstaller --onefile --windowed --clean --name mkstruct-gui `
  --icon "$PWD\resource\app.ico" `
  --add-data "$PWD\resource\app.ico;resource" `
  --distpath dist/mkstruct-gui --workpath build --specpath build `
  gui.py
```

产物：`dist/mkstruct-gui/mkstruct-gui.exe`

**关键参数：**

| 参数 | 说明 |
| --- | --- |
| `--onefile` | 单文件分发 |
| `--console` / `--windowed` | CLI 保留控制台；GUI 不弹黑框 |
| `--icon` | exe 文件图标（同时写入 PE 资源） |
| `--add-data "src;dest"` | GUI 运行时通过 `_MEIPASS` 读取图标；Windows 用分号 |
| `--distpath` | 产物输出目录 |
| `--workpath` / `--specpath` | 中间产物与 spec 收拢到 `build/`，保持源码目录干净 |

### 推荐：固化打包脚本

每次手敲长命令容易忘，项目根建议保留两个 PowerShell 脚本：

**`build_cli.ps1`**

```powershell
$root = $PSScriptRoot
pyinstaller --onefile --console --clean --name mkstruct `
  --icon "$root\resource\app.ico" `
  --distpath "$root\dist\mkstruct" --workpath "$root\build" --specpath "$root\build" `
  "$root\mkstruct.py"
```

**`build_gui.ps1`**

```powershell
$root = $PSScriptRoot
pyinstaller --onefile --windowed --clean --name mkstruct-gui `
  --icon "$root\resource\app.ico" `
  --add-data "$root\resource\app.ico;resource" `
  --distpath "$root\dist\mkstruct-gui" --workpath "$root\build" --specpath "$root\build" `
  "$root\gui.py"
```

`$PSScriptRoot` 始终是脚本所在目录，从任何工作目录调用都不会出错。

---

## 常见打包问题

### 1. `FileNotFoundError: Icon input file .../build/resource/app.ico not found`

**现象**：日志前面一切正常，最后 `Copying icon to EXE` 阶段崩溃。

**原因**：使用了 `--specpath build`，但 `--icon` 给的是相对路径 `resource\app.ico`。PyInstaller 执行 spec 时以 spec 所在目录（`build/`）为基准解析相对路径，于是去找 `build/resource/app.ico`。

**解决**：把 `--icon` 和 `--add-data` 的**源路径**改成绝对路径（见上方脚本）。`--distpath` / `--workpath` / `--specpath` 保持相对路径没问题。

### 2. exe 文件图标显示为旧图标

**原因**：Windows 图标缓存。

**解决**：把 exe 改名、复制到新目录，或运行 `ie4uinit.exe -ClearIconCache` 后重启资源管理器。多尺寸 ICO（至少含 16/32/48/256）显示更稳定。

### 3. GUI 运行时找不到 `resource/app.ico`

**原因**：忘记 `--add-data`，或分隔符写成了冒号（macOS/Linux 语法）。

**解决**：Windows 用分号 `;`，路径写成 `"$PWD\resource\app.ico;resource"`。代码侧通过 `_resource_path()` 读取 `_MEIPASS/resource/app.ico`。

### 4. GUI 启动后秒退、无任何提示

**原因**：`--windowed` 隐藏了 stderr，异常被吞。

**解决**：临时改用 `--console` 重新打包，在终端里看完整堆栈；或检查 `~/mkstruct-gui-error.log`。

---

## 代码规范

- **`core.py` 禁止 I/O**：不加 `print`、不读写 `sys.stdin/stdout`、不弹窗。
- **类型注解**：所有公开函数加类型注解（Python 3.8 兼容语法，`from __future__ import annotations`）。
- **不引入第三方依赖**：GUI 保持纯 Tkinter，CLI 保持纯标准库。需要拖拽等能力时再评估是否引入，并做好降级。
- **新增命令行参数**：先在 `mkstruct.py` 的 `build_parser()` 添加，再按需在 `core.py` 增加对应参数，最后同步 GUI。
- **新增解析规则**：只改 `core.py`，CLI 与 GUI 自动生效。改完务必补测试样例（见下）。

### 手工回归测试清单

修改 `core.py` 后，至少验证以下用例：

```
# 1. 基础树形
src/
├── main.py
└── utils/
    └── helper.py

# 2. 行内注释
src/                     # 源码目录
├── main.py              # 入口

# 3. 简写展开
RtmpDataSource.h/.cpp

# 4. 无扩展名文件
Makefile
LICENSE

# 5. 混合缩进 / tree 输出
|-- a/
|   `-- b.txt
`-- c.md

# 6. 已有文件 skip
（先创建 out/a.txt，再跑一次）

# 7. 无法解析的行
（故意写一行乱码，确认 issues 有值、GUI 状态栏变红）
```

---

## 发布流程

发布包含两部分：**打 tag 并推送**、**在 GitHub 创建 Release 并上传 exe**。

### 1. 准备

1. 更新 `core.py` 的 `__version__`（如 `1.4.0`）。
2. 在 `CHANGELOG.md` 顶部新增该版本条目，并把文末的版本链接指向真实 tag。
3. 运行回归清单（见“代码规范”一节）。

### 2. 本地打包

```powershell
.\build_cli.ps1
.\build_gui.ps1
```

产物：

```
dist\mkstruct\mkstruct.exe
dist\mkstruct-gui\mkstruct-gui.exe
```

### 3. 本地验证

```powershell
# CLI
dist\mkstruct\mkstruct.exe -V
dist\mkstruct\mkstruct.exe --help
dist\mkstruct\mkstruct.exe tree.txt -d .\tmp-out --dry-run

# GUI
dist\mkstruct-gui\mkstruct-gui.exe
```

GUI 至少走一遍：打开文件 → 解析 → 预览 → 创建 → 深色模式切换。
确认 **exe 文件图标、窗口标题栏图标、任务栏图标** 都正确显示（图标缓存问题见“常见打包问题”第 2 条）。

### 4. 提交并打 tag

```powershell
git add .
git commit -m "release: v1.4.0"
git tag v1.4.0
git push origin main
git push origin v1.4.0
```

`dist/`、`build/`、`*.spec` 已被 `.gitignore` 忽略，不会误提交。

### 5. 创建 GitHub Release

1. 打开仓库 → **Releases** → **Draft a new release**。
2. **Choose a tag**：选刚推送的 `v1.4.0`。
3. **Release title**：`v1.4.0`。
4. **Describe this release**：从 `CHANGELOG.md` 对应条目复制。
5. **Attach binaries**：把下面两个文件拖入上传区
   - `dist\mkstruct\mkstruct.exe`
   - `dist\mkstruct-gui\mkstruct-gui.exe`
6. 点击 **Publish release**。

发布后 `README.md` 的「方式一」链接即可正常下载。

### 6. 若已配置 GitHub Actions（可选）

若仓库包含 `.github/workflows/release.yml`，推送 tag 后 CI 会自动构建两个 exe 并附加到对应 Release，可省去手动上传。工作流文件内容见下一节。

---

## 可选：GitHub Actions 自动打包

在 `.github/workflows/release.yml` 放置以下内容，推送 `v*` 标签时自动在 Windows runner 上构建并上传到 Release：

```yaml
name: Build and Release

on:
  push:
    tags: ["v*"]

permissions:
  contents: write

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install PyInstaller
        run: pip install pyinstaller

      - name: Build CLI
        run: |
          pyinstaller --onefile --console --clean --name mkstruct `
            --icon "$PWD\resource\app.ico" `
            --distpath dist/mkstruct --workpath build --specpath build `
            mkstruct.py

      - name: Build GUI
        run: |
          pyinstaller --onefile --windowed --clean --name mkstruct-gui `
            --icon "$PWD\resource\app.ico" `
            --add-data "$PWD\resource\app.ico;resource" `
            --distpath dist/mkstruct-gui --workpath build --specpath build `
            gui.py

      - name: Create Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            dist/mkstruct/mkstruct.exe
            dist/mkstruct-gui/mkstruct-gui.exe
          generate_release_notes: true
```

启用后，「发布流程」第 5 步可跳过，只需 push tag。