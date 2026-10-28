# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.3.0] - 2026-10-28

### 新增

- 图形界面 `gui.py`：实时解析预览树、预览/创建分离、创建确认对话框、
  错误行高亮、日志着色、生成 CLI 命令、深色模式、快捷键。
- GUI 配置文件 `~/.mkstruct_gui.json`，记忆目标目录、复选框状态、窗口大小与主题。
- GUI 未捕获异常写入 `~/mkstruct-gui-error.log`。
- 应用图标 `resource/app.ico`，同时应用于 exe 文件、窗口标题栏、任务栏与工具栏。

### 变更

- **架构拆分**：原单文件 `mkstruct.py` 拆为 `core.py`（逻辑）+ `mkstruct.py`（CLI）+ `gui.py`（GUI）。
  - `core.py` 不再直接打印，改用 `Event` 回调与 `Prepared` 返回值。
  - `mkstruct.py` 命令用法保持不变。
  - **破坏性变更**：`mkstruct.py` 依赖同目录 `core.py`，不能再单独拷走单文件运行。
- CLI `--dry-run` 现在也会检查文件是否存在，预览中标出 `skip` 并计入 `skipped` 统计。

### 修复

- 预览模式下已存在文件的统计与正式创建不一致。

## [1.2.0] - 2026-10-27

### 新增

- `--show` 参数：打印解析出的树，便于校对层级与目录/文件判定。
- `--dry-run` 参数：只显示将创建的内容，不写磁盘。
- `-q, --quiet` 参数：静默模式，仅输出最终统计。
- 行内注释剥离：`空白 + #` 之后内容被忽略。

### 改进

- 缩进宽度自动推断失败时回退为 4，并支持 `tree` 命令输出格式。

## [1.1.0] - 2026-10-26

### 新增

- 简写展开：`Foo.h/.cpp` 自动展开为 `Foo.h` 与 `Foo.cpp`。
- 支持从标准输入 / 管道读取结构文本。

### 修复

- `dir/.gitignore` 这类写法被误判为简写。

## [1.0.0] - 2026-10-25

### 新增

- 初版：解析树形结构文本，批量创建目录与空文件。
- 目录名以 `/` 结尾、有子节点即为目录的判定规则。
- 幂等创建：已存在文件跳过不覆盖。

[1.3.0]: https://example.com/compare/v1.2.0...v1.3.0
[1.2.0]: https://example.com/compare/v1.1.0...v1.2.0
[1.1.0]: https://example.com/compare/v1.0.0...v1.1.0
[1.0.0]: https://example.com/releases/tag/v1.0.0