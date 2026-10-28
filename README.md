# mkstruct

根据树形结构文本，一键创建目录与空文件的项目骨架生成器。

把 `tree` 命令风格的目录树（或设计文档里常见的树形结构）直接粘贴给它，就能在指定位置批量创建出完整的目录和文件结构，省去手工 `mkdir` / `touch` 的重复劳动。

---

## 特性

- **三种输入方式**：结构文本文件、命令行字符串、标准输入 / 管道 / 剪贴板。
- **自动识别层级**：支持 `├──`、`└──`、`│`、`--`、空格缩进等多种树形画法，缩进宽度自动推断。
- **目录以 `/` 结尾**：约定简单明确——带 `/` 结尾或有子节点的节点视为目录，其余视为文件。
- **忽略行内注释**：`空格 + #` 之后的内容会被剥离，方便直接复用带说明文字的结构文本。
- **简写自动展开**：`RtmpDataSource.h/.cpp` 这类写法会自动创建 `RtmpDataSource.h` 和 `RtmpDataSource.cpp` 两个文件。
- **预览模式**：`--dry-run` 只显示将要创建的内容，不写磁盘。
- **幂等安全**：已存在的文件不会被覆盖，只会标记为 `skip`。
- **零依赖**：仅使用 Python 标准库，单文件即可运行。

---

## 环境要求

- Python 3.7 或更高版本（推荐 3.8+）
- 无第三方依赖

---

## 获取脚本

将 `mkstruct.py` 保存到任意目录即可。如果想在任意位置直接调用，可以给它加上可执行权限并放入 `PATH`：

```bash
chmod +x mkstruct.py
mv mkstruct.py /usr/local/bin/mkstruct
```

之后就可以直接用 `mkstruct` 代替 `python mkstruct.py`。

---

## 快速开始

假设当前目录下有一个 `tree.txt`，内容为：

```
VideoPlayer/
├── CMakeLists.txt                  # 顶层CMake
├── cmake/
│   ├── FindFFmpeg.cmake            # FFmpeg查找模块
│   └── vcpkg.cmake                 # vcpkg工具链配置
├── third_party/
│   └── vcpkg/                      # vcpkg子模块（可选）
├── src/
│   ├── main.cpp                    # 阶段一：控制台测试入口
│   ├── common/
│   │   ├── Logger.h                # 日志接口
│   │   ├── Logger.cpp
│   │   ├── ThreadSafeQueue.h       # 线程安全队列模板
│   │   └── Types.h                 # 通用类型/枚举定义
│   ├── datasource/
│   │   ├── IDataSource.h           # 数据源抽象接口
│   │   ├── StreamConfig.h          # 流配置结构
│   │   └── RtmpDataSource.h/.cpp   # RTMP数据源实现
│   ├── decoder/
│   │   ├── VideoDecoder.h          # 解码器封装
│   │   └── VideoDecoder.cpp
│   └── session/
│       └── DecodeSession.h/.cpp    # 阶段一简化版会话（仅接入+解码）
├── tests/
│   ├── test_thread_safe_queue.cpp  # 单元测试
│   └── test_rtmp_decode.cpp        # 集成测试
└── docs/
    ├── design_stage1.md
    ├── todo_stage1.md
    └── test_stage1.md
```

先预览，再创建：

```bash
# 预览要创建的内容（不写磁盘）
python mkstruct.py .\example\tree.txt -d .\example --dry-run

# 正式创建到当前目录
python mkstruct.py .\example\tree.txt -d .\example
```

执行完成后，当前目录下会多出完整的 `VideoPlayer/` 项目骨架。

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

展开规则：`/` 前面部分含 `.`，`/` 后面像纯扩展名（字母数字下划线）时才展开，避免误伤 `dir/.gitignore` 这类写法。

---

## 命令行参数

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

优先级：`-s` > 位置参数 `structure` > 标准输入。

---

## 使用示例

### 从文件创建

```bash
python mkstruct.py tree.txt -d ./out
```

### 直接传入字符串

```bash
python mkstruct.py -s "src/
├── main.py
└── utils/
    └── helper.py" -d ./out
```

### 从标准输入 / 管道

```bash
# 手动粘贴后按 Ctrl-D（macOS/Linux）或 Ctrl-Z 回车（Windows）
python mkstruct.py -d ./out

# 从管道读取
cat tree.txt | python mkstruct.py -d ./out

# macOS：直接从剪贴板创建
pbpaste | python mkstruct.py -d ./out

# Windows PowerShell：从剪贴板创建
Get-Clipboard | python mkstruct.py -d ./out
```

### 先预览再执行

```bash
python mkstruct.py tree.txt -d ./out --dry-run
```

### 排查解析问题

```bash
# 打印脚本眼中的目录树，确认层级和文件/目录判定是否符合预期
python mkstruct.py tree.txt -d ./out --show --dry-run
```

### 静默执行（适合脚本调用）

```bash
python mkstruct.py tree.txt -d ./out -q
```

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

脚本已经尝试将标准输出重新配置为 UTF-8。如果仍然乱码，可以在运行前执行：

```powershell
chcp 65001
```

### Q：支持 `tree` 命令直接输出的格式吗？

支持。Linux/macOS 的 `tree` 以及 Windows 的 `tree /F` 输出（去掉开头的统计行）都能被解析，只要目录带有可识别的树形连接符或缩进。

### Q：如何把结构文本从 Markdown 代码块里直接喂给它？

````bash
# 从 Markdown 文件中提取第一个代码块并创建
awk '/^```/{f=!f;next} f' design.md | python mkstruct.py -d ./out