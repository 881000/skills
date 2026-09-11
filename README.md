# Agent技能｜可靠、可控、可复用的AI能力库

> 作者：hxw ｜ 工作室：https://18.cx

## 技能介绍

**技能库**是 [Agent-Skills](https://github.com/881000/skills) 通用技能包中的一员，是一个面向 AI Agent 设计的**轻量化、标准化、跨平台**的技能包管理器。它将零散的技能安装、版本检测、分类管理封装为标准化技能单元，解决 Agent 能力安装繁琐、版本不可控、跨平台复用成本高等问题。

本技能不绑定任何特定 AI 平台，安装目录支持 `--install-dir` 参数和 `SKILL_INSTALL_DIR` 环境变量两种方式指定，另支持自动探测与默认目录，可在任意支持脚本执行的 AI 环境中使用。

## 功能特性

- **两级分类管理**：按一级分类 → 二级分类组织技能，支持按分类批量安装。
- **按名称安装**：回复技能名称即可安装单个技能，已存在时输出提示后覆盖（可用 `--force` 静默覆盖）。
- **实时版本检测**：`list --check-updates` 和 `info` 命令从对应 GitHub 仓库的 SKILL.md 实时读取最新版本号，自动对比本地版本，提示更新；分支自动回退（配置分支 → main → master），任一 HTTP 错误均触发回退。
- **通用安装目录**：支持 `--install-dir` 参数、`SKILL_INSTALL_DIR` 环境变量指定安装目录，另支持自动探测与默认目录，不绑定平台路径。
- **表格化列表**：以对齐表格展示技能名称、分类、已安装版本、最新版本、状态；列宽动态计算，长名称不再撑破表格。
- **安全解压**：解压时进行 Zip Slip 路径校验，防止恶意压缩包写入安装目录之外。
- **版本号准确性**：安装后版本号优先从解压后技能自身的 SKILL.md 读取，确保与实际安装内容一致。
- **异常自动降级**：下载失败、解析错误自动捕获，返回规范错误信息；版本检测网络失败时静默降级，不影响正常功能。
- **参数强校验**：使用 argparse 校验命令与参数，拒绝无效调用。
- **零依赖**：仅依赖 Python 标准库，跨平台开箱即用。

## 快速开始

```bash
# 1. 列出所有可用技能及安装状态
python scripts/install.py list

# 2. 安装单个技能（已存在则覆盖更新）
python scripts/install.py install "<技能名>"

# 3. 查看技能详细信息
python scripts/install.py info "<技能名>"
```

## 安装与更新

### 环境要求

- Python 3.8+（本技能仅依赖 Python 标准库，开箱即用，无需安装额外依赖）

### 安装到 AI

> 本技能在仓库中的目录名为 `skill`，安装到 AI 后通常以中文名「技能库」作为目录名。两种名称指的是同一个技能。

技能支持本地直接使用，也可安装到支持技能 / Agent 能力的 AI 中，两种方式任选：

**方式一：提供仓库链接给 AI**

把仓库链接直接发给 AI，告知其安装本技能：

> 请从 https://github.com/881000/skills 仓库中安装本技能（仓库内 `skill/` 目录）

AI 会自动拉取仓库、读取 `skill/SKILL.md` 并挂载，之后直接描述需求即可调用。

**方式二：本地安装**

先将技能包下载到本地（`git clone` 本仓库，或下载仓库压缩包并解压），再按 AI 支持的方式安装：

- 把 `skill/` 文件夹直接拖给 AI，由 AI 自动安装；
- 或将 `skill/` 文件夹放入 AI 的技能库（如 `.skills`、`.user_skills`），AI 会自动识别挂载；
- 或在 AI 的「创建技能 / 上传技能」入口选择本地的 `SKILL.md` 文档上传。

> 提示：本技能需在支持执行脚本的环境中使用（如具备代码执行能力的智能体平台、本地命令行）。

### 更新

本技能的版本自检由 AI 在调用时按 `SKILL.md` 中的版本检查段落执行：AI 会对比远程仓库与本地的版本号，若有新版本会在回答末尾提示「检测到新版本，是否立即更新？」，回复确认即可自动更新。

也可手动重新执行安装步骤覆盖安装最新版。

## 跨平台适配

本技能不绑定任何特定 AI 平台，在豆包、千问、灵犀等支持脚本执行的 AI 环境中均可使用。

### 兼容平台

| 平台 | 脚本执行 | 版本自检 | 自动更新 | 说明 |
|------|---------|---------|---------|------|
| 豆包（办公/工作模式） | 支持 | 完整支持 | 支持 | 自动探测安装目录，开箱即用 |
| 千问 | 支持 | 需手动 sync-catalog | 手动更新 | 通过 `--install-dir` 或环境变量指定目录 |
| 灵犀 | 支持 | 需手动 sync-catalog | 手动更新 | 通过 `--install-dir` 或环境变量指定目录 |
| 其他支持 Python 的平台 | 支持 | 需手动 sync-catalog | 手动更新 | 通用适配 |
| 不支持脚本的平台 | 不支持 | 不支持 | 不支持 | 可手动下载技能 ZIP 解压使用 |

### 安装目录配置

不同平台的技能存放目录不同，按以下优先级配置（高优先级覆盖低优先级）：

1. **命令行参数**（最高优先级）：每次执行加 `--install-dir <路径>`
2. **环境变量**：设置 `SKILL_INSTALL_DIR=<路径>`，全局生效
3. **自动探测**：豆包平台自动识别 `.user_skills` / `skills` 目录
4. **默认目录**：当前工作目录下的 `skills/` 文件夹

示例：

```bash
# 千问平台指定安装目录
python scripts/install.py list --install-dir "/path/to/qwen/skills"

# 灵犀平台通过环境变量指定（Linux/macOS）
export SKILL_INSTALL_DIR="/path/to/lingxi/skills"
python scripts/install.py install "建筑施工手册"

# Windows PowerShell 环境变量
$env:SKILL_INSTALL_DIR="C:\path\to\skills"
python scripts/install.py list
```

### 版本更新

- **豆包平台**：每次调用时 AI 自动检测远程版本，有更新时提示确认，确认后自动完成更新。
- **其他平台**：定期手动执行以下命令同步各技能的版本基线到最新：
  ```bash
  python scripts/install.py sync-catalog
  ```
  需更新技能库本身（SKILL.md / 安装器脚本）时，重新从 GitHub 下载最新版覆盖安装即可。

### 不支持脚本执行的平台

若所用 AI 平台不支持执行 Python 脚本，可手动使用本技能库：

1. 打开 `references/catalog.json`，查看技能清单和对应 GitHub 仓库地址；
2. 手动访问目标技能的 GitHub 仓库，下载 ZIP 压缩包；
3. 解压到平台的技能目录，文件夹命名为技能中文名（与 catalog 中 `name` 字段一致）。

## 使用说明

### 命令一览

| 命令 | 说明 |
|------|------|
| `list [--check-updates]` | 列出全部技能及版本状态（表格形式；`--check-updates` 实时检测远程版本，较慢） |
| `info <技能名>` | 查看单个技能详情（实时检测远程版本） |
| `install <技能名> [--force]` | 安装或更新单个技能（`--force` 静默覆盖已存在的技能） |
| `install-category <一级分类> [--force]` | 安装一级分类下全部技能 |
| `install-subcategory <一级分类> <二级分类> [--force]` | 安装二级分类下全部技能 |
| `sync-catalog` | 同步 catalog.json 中所有技能的版本到最新 |
| `version` | 显示技能库自身版本号 |

安装类命令（install / install-category / install-subcategory）和 list / info 均支持 `--install-dir` 参数指定安装目录（需放在子命令之后），输出为 UTF-8。

### 列出可用技能

```bash
python scripts/install.py list
```

以表格形式输出所有技能，包含：技能名称、分类、已安装版本、最新版本、状态（未安装/已安装/可更新），末尾附统计与安装引导提示。默认使用 catalog 中的版本号，响应快；如需实时检测 GitHub 最新版本，加 `--check-updates` 参数（较慢）。

输出示例：

```
技能名称    分类              已安装版本  最新版本  状态
----------  ----------------  ----------  --------  ------
<技能名>    <一级分类>/<二级分类>  1.0.0       1.0.0     已安装
<技能名>    <一级分类>/<二级分类>  -           1.0.0     未安装
...
共 N 个技能，已安装 M 个，可更新 K 个。
```

### 安装单个技能

```bash
python scripts/install.py install "<技能名>"
```

若技能已存在，会输出提示信息后覆盖安装为最新版（通知式，非交互式确认）；加 `--force` 参数可静默覆盖不输出提示。安装完成后自动列出全部技能及状态，方便查看还需安装哪些技能。

### 按分类批量安装

```bash
# 安装一级分类下全部技能
python scripts/install.py install-category "<一级分类>"

# 安装二级分类下全部技能
python scripts/install.py install-subcategory "<一级分类>" "<二级分类>"
```

### 查看技能详情

```bash
python scripts/install.py info "<技能名>"
```

输出技能名称、分类、仓库、分支、最新版本、已安装版本、状态、安装目录、描述。

### 指定安装目录

安装目录按以下优先级确定（高优先级覆盖低优先级）：

1. 命令行参数 `--install-dir <路径>`
2. 环境变量 `SKILL_INSTALL_DIR`
3. 自动探测：从本技能所在位置向上查找 `.user_skills` 或 `skills` 目录
4. 默认：当前工作目录下的 `skills/` 文件夹（不存在则自动创建）

示例：

```bash
# 参数指定（Linux/macOS）
python scripts/install.py install "<技能名>" --install-dir "/path/to/skills"

# 参数指定（Windows）
python scripts/install.py install "<技能名>" --install-dir "C:\Users\name\skills"

# 环境变量指定（Linux/macOS）
export SKILL_INSTALL_DIR="/path/to/skills"
python scripts/install.py list

# 环境变量指定（Windows PowerShell）
$env:SKILL_INSTALL_DIR="C:\Users\name\skills"
python scripts/install.py list
```

执行安装类命令时，脚本会输出实际使用的安装目录，便于确认。

### 版本管理

- 每个技能在 `references/catalog.json` 中配置 `version` 字段作为基线。
- `list --check-updates` 和 `info` 实时从 GitHub 仓库 SKILL.md 的 frontmatter 读取最新版本（自动尝试配置分支 → main → master），失败回退到 catalog 中的版本。
- 安装成功后在技能库写入 `.skill_version` 文件记录版本。
- 已安装但无版本记录的技能，已安装版本直接显示为最新版本。
- 版本落后时状态显示「可更新」，重新执行 `install` 即可覆盖更新。

### 目录结构

```
技能库/
├── SKILL.md            # AI 操作指南（含 version frontmatter + 版本自检段落）
├── README.md           # 本文件，人类说明
├── references/
│   └── catalog.json    # 技能库数据
└── scripts/
    └── install.py      # 安装器脚本（仅依赖 Python 标准库）
```

### 维护技能库

新增或修改技能时，编辑 `references/catalog.json`，在对应分类下追加：

```json
{
  "name": "技能名称",
  "repo": "owner/repo",
  "branch": "main",
  "version": "1.0.0",
  "description": "一句话说明"
}
```

## 许可证

本项目采用 **MIT License** 开源协议，可自由使用、修改与分发。使用时请保留原作者信息。

## 联系方式

- 作者：hxw
- 工作室：[https://18.cx](https://18.cx)
- 项目地址：[https://github.com/881000/skills](https://github.com/881000/skills)
