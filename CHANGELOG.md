# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-10-28

首个公开版本。提供命令行（CLI）与图形界面（GUI）两种形态，二者共享同一套解析与创建逻辑。

### 新增

**核心功能**
- 解析 `tree` 命令风格的树形结构文本，支持 `├──`、`└──`、`│`、`|--`、`` `-- ``、空格缩进等多种画法，缩进宽度自动推断。
- 目录/文件判定规则：名字以 `/` 或 `\` 结尾、或有子节点即为目录，其余为文件；`Makefile`、`LICENSE` 等无扩展名文件可正确识别。
- 行内注释剥离：`空白 + #` 之后的内容被忽略，`C#.md` 这类文件名不受影响。
- 简写展开：`Foo.h/.cpp` 自动展开为 `Foo.h` 与 `Foo.cpp`，并避免误伤 `dir/.gitignore`。
- 幂等创建：已存在的文件跳过不覆盖，重复执行安全。

**命令行（CLI）**
- 三种输入方式：结构文本文件、`-s` 字符串、标准输入 / 管道。
- 参数：`-d/--dest`、`-n/--dry-run`、`-q/--quiet`、`--show`、`-V/--version`。
- `--dry-run` 预览时也会检查文件是否存在，已存在文件标为 `skip` 并计入统计。

**图形界面（GUI）**
- 输入即解析（300ms 防抖），右侧树视图实时呈现目录/文件判定与层级。
- 预览与创建分离；创建前弹出确认对话框，必须勾选「我已预览并确认写入」才能提交。
- 无法解析的行在文本区高亮，状态栏提示行号，点击可跳转定位。
- 执行日志按 `dir` / `file` / `skip` / `error` 着色，带类型前缀符号。
- 「生成 CLI 命令」：把当前配置拼成命令并复制到剪贴板。
- 深色模式、快捷键（`Ctrl+O` / `Ctrl+Enter` / `Ctrl+Shift+Enter` / `Ctrl+L` / `F1`）。
- 配置持久化到 `~/.mkstruct_gui.json`（目标目录、复选框状态、窗口大小、主题）。
- 未捕获异常写入 `~/mkstruct-gui-error.log` 并弹窗提示。

**项目**
- 架构分为 `core.py`（纯逻辑，无 I/O 打印）、`mkstruct.py`（CLI）、`gui.py`（GUI）。
- 应用图标 `resource/app.ico`，应用于 exe 文件、窗口标题栏、任务栏与工具栏。
- 提供 PyInstaller 打包脚本与 GitHub Release 发布流程。

[0.1.0]: https://github.com/<你的用户名>/mkstruct/releases/tag/v0.1.0