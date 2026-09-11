---
name: 技能库
version: 1.0.0
description: "通用技能包管理器，维护两级分类的可安装技能清单并从 GitHub 执行安装与版本检测。适用于任意 AI 平台。当用户说「安装XX技能」「安装建筑工程/创意设计分类下的技能」「安装所有XX类技能」「列出可用技能」「技能库」「有哪些技能可以装」「更新技能」「技能库版本」时使用。支持按技能名称精确安装、按一级/二级分类批量安装、实时版本对比与更新提示、--force 静默覆盖、version 版本查询、Zip Slip 安全解压。数据源为 references/catalog.json，安装器为 scripts/install.py。"
---

> 通用技能包管理器 ｜ 适用于任意 AI 平台

# 技能库

维护一份两级分类的可安装技能清单，从 GitHub 下载安装对应技能，并实时检测版本更新。本技能不绑定任何特定 AI 平台，安装目录可通过参数、环境变量或配置文件指定。

## 分类体系

技能按一级分类 → 二级分类组织，完整分类体系与技能清单见 `references/catalog.json`。

执行安装、查询等操作前，先读取该文件获取最新的分类与技能名称，不依赖本文件中的硬编码列表。新增分类或技能时无需修改本文件。

## 安装目录

安装目标目录按以下优先级确定（高优先级覆盖低优先级）：

1. 命令行参数 `--install-dir <路径>`
2. 环境变量 `SKILL_INSTALL_DIR`
3. 自动探测：从本技能所在位置向上查找 `.user_skills` 或 `skills` 目录
4. 默认：当前工作目录下的 `skills/` 文件夹（不存在则自动创建）

执行安装类命令时，脚本会输出实际使用的安装目录，便于确认。

## 跨平台适配

本技能不绑定任何特定 AI 平台，在豆包、千问、灵犀等支持脚本执行的 AI 环境中均可使用。不同平台的适配要点如下：

### 安装目录配置

- **豆包（办公/工作模式）**：自动探测 `.user_skills` 或 `skills` 目录，无需额外配置，安装的技能与本技能平级放置。
- **其他 AI 平台（千问、灵犀等）**：自动探测可能不生效，需通过以下任一方式显式指定安装目录：
  - 每次执行命令时加 `--install-dir <平台技能目录路径>` 参数；
  - 设置环境变量 `SKILL_INSTALL_DIR=<平台技能目录路径>`，后续所有命令自动生效。
- 若均未指定，默认安装到当前工作目录下的 `skills/` 文件夹。

### 版本自检行为

- **支持网页访问 + 文件修改的平台**（如豆包办公模式）：完整执行末尾「版本更新检查」段落，自动检测远程版本并提示更新，用户确认后可自动完成文件替换。
- **仅支持脚本执行、不支持网页访问的平台**：跳过「版本更新检查」段落中的远程版本对比；可定期手动执行 `python scripts/install.py sync-catalog` 将 catalog 中各技能的版本基线同步到最新。技能库本身的更新需手动从 GitHub 下载最新版覆盖。
- **不支持脚本执行的平台**：本技能的安装器功能不可用；可仅参考本文件中的分类体系和 `references/catalog.json` 中的技能清单，手动从对应 GitHub 仓库下载 ZIP 并解压到平台技能目录。

### 通用约束

- 所有命令均依赖 Python 3.8+ 环境，且仅使用标准库，无需安装额外依赖。
- 输出统一为 UTF-8，在 Windows 平台已处理控制台中文乱码问题。
- 安装的技能目录名为 catalog 中的 `name` 字段（中文名），各平台均按此名称识别。
- 本技能的 `SKILL.md`、`README.md`、`references/`、`scripts/` 四个组成部分在所有平台均一致，无平台特定文件。

## 触发与执行

### 安装单个技能

按名称安装单个技能。先在 catalog 中匹配名称，匹配到后执行安装。

```bash
python scripts/install.py install "监理日志"
```

若需指定安装目录：

```bash
python scripts/install.py install "监理日志" --install-dir "/path/to/skills"
```

匹配规则：与 catalog 中 `name` 字段完全一致。若用户说法与正式名称有出入（如简称、别名），先在 catalog 中定位到最接近的正式名称，告知用户实际安装的技能名并确认后再执行。

### 按分类安装

按分类批量安装，分两种粒度：

**一级分类全装**（如「安装建筑工程类技能」「把创意设计的都装上」）：

```bash
python scripts/install.py install-category "建筑工程"
```

**二级分类全装**（如「安装监理类技能」「装一下规范类的」）：

```bash
python scripts/install.py install-subcategory "建筑工程" "监理"
```

用户只说二级分类名（如「安装监理技能」）时，先在 catalog 中定位该二级分类所属的一级分类，再执行 `install-subcategory`；若同名二级分类存在于多个一级分类下，向用户确认范围。

### 列出技能

```bash
python scripts/install.py list
```

以表格形式输出所有技能，包含：技能名称、分类、已安装版本、最新版本、状态（未安装/已安装/可更新），末尾附统计与安装引导提示。默认使用 catalog 中的版本号，响应快；如需实时检测 GitHub 最新版本，加 `--check-updates` 参数（较慢）。

### 查看技能详情

```bash
python scripts/install.py info "建筑施工手册"
```

输出技能名称、分类、仓库、分支、最新版本、已安装版本、状态、安装目录、描述。

### 更新技能

安装命令本身即为覆盖安装，直接执行 `install <技能名>` 即可更新到最新版本。若 `list` 显示状态为「可更新」，回复技能名称即可触发更新。

## 版本检测

- 每个技能在 catalog 中配置 `version` 字段作为基线版本。
- `list` 和 `info` 命令实时从对应 GitHub 仓库的 `SKILL.md` frontmatter 中读取 `version` 字段作为最新版本（自动尝试配置分支 → main → master），获取失败时回退到 catalog 中的版本。
- 安装成功后自动在技能库下写入 `.skill_version` 文件记录当前版本。
- 已安装但无 `.skill_version` 文件的技能（旧版安装），已安装版本直接显示为最新版本，状态为「已安装」。
- 已安装版本低于最新版本时，状态显示为「可更新」。

## 安装行为说明

- 若目标技能已存在，覆盖安装前会输出提示信息（通知式，非交互式确认），随后直接覆盖；加 `--force` 参数可静默覆盖不输出提示。
- 下载源为 GitHub ZIP（`https://github.com/{repo}/archive/refs/heads/{branch}.zip`），分支按 catalog 中配置的 `branch` 尝试，失败自动回退 `main` → `master`；任何 HTTP 错误（404/403/500 等）均触发分支回退，而非直接终止。
- 若仓库 404（不存在或私有），脚本会明确报错并提示可能原因，不要静默失败或编造安装成功。
- 解压时进行 Zip Slip 路径校验，防止恶意压缩包写入安装目录之外。
- 安装版本号优先从解压后技能自身的 `SKILL.md` frontmatter 读取，确保与实际安装内容一致；读取失败时回退到远程探测或 catalog 基线版本。
- 安装完成后自动列出全部技能状态（无需再手动执行 `list`）。

## 脚本命令参考

```
python scripts/install.py list [--install-dir DIR] [--check-updates]    列出全部技能及状态（--check-updates 实时检测远程版本）
python scripts/install.py info <技能名> [--install-dir DIR]                  查看技能详情（实时检测远程版本）
python scripts/install.py install <技能名> [--install-dir DIR] [--force]     安装/更新单个技能（--force 静默覆盖）
python scripts/install.py install-category <一级分类> [--install-dir DIR] [--force]    安装一级分类下全部技能
python scripts/install.py install-subcategory <一级分类> <二级分类> [--install-dir DIR] [--force]  安装二级分类下全部技能
python scripts/install.py sync-catalog                            同步 catalog.json 中所有技能的版本到最新
python scripts/install.py version                                   显示技能库自身版本号
```

所有命令均为 UTF-8 输出。脚本路径为 `scripts/install.py`（相对于本技能根目录）。

## 维护目录

新增或修改技能时，编辑 `references/catalog.json`：

- `categories.<一级分类>.<二级分类>` 下追加对象，字段：
  - `name`：技能中文名，即安装后的目录名
  - `repo`：GitHub 仓库 `owner/repo`
  - `branch`：可选，默认 main
  - `version`：技能版本号（如 `1.0.0`），升级时递增此值
  - `description`：一句话说明

### 版本号更新规则

技能库有两个独立版本号，分别维护，不需保持一致：

| 版本文件 | 字段 | 何时更新 |
|---------|------|---------|
| `SKILL.md` | frontmatter 的 `version` | 修改 `SKILL.md`、`scripts/install.py`、`README.md` 时 |
| `references/catalog.json` | 顶层的 `version` | 新增/修改/删除技能、调整分类时 |

版本检测会同时检查这两个版本号，任一有更新即提示用户升级。版本号遵循语义化版本（主版本.次版本.修订号）：新增功能升次版本，bug 修复或小改动升修订号，不兼容变更升主版本。

---

## 版本更新检查（每次调用本技能时必须执行）

1. **对比版本号**：分别检测两个版本文件，任一有更新即视为技能库有新版本：
   - **程序/文档版本**：读取本地 `SKILL.md` frontmatter 的 `version` 字段；用网页访问能力打开 `https://raw.githubusercontent.com/881000/skills/main/SKILL.md`，读取远程 `version`。
   - **数据版本**：读取本地 `references/catalog.json` 顶层的 `version` 字段；用网页访问能力打开 `https://raw.githubusercontent.com/881000/skills/main/references/catalog.json`，读取远程顶层 `version`。
2. **网络失败降级**：若上述任一网络请求失败（超时、不可达、解析错误等），静默跳过版本检测，不影响本技能正常功能；可在回答末尾轻量提示「版本检测暂不可用」，但不得因检测失败而中断或拒绝正常操作。
3. **判断**：若任一文件的远程版本高于本地版本，在本技能回答的末尾追加提示，提示语根据更新来源动态选择：
   - 仅 catalog.json 有更新（新增/调整技能）：「检测到技能库有新技能可用，是否立即更新？」
   - 仅 SKILL.md 有更新（程序/文档更新）：「检测到技能库有新版本，是否立即更新？」
   - 两者都有更新：「检测到技能库有更新（含新技能），是否立即更新？」
   若用户同意，继续执行第 4 步。
4. **执行更新**（仅当用户明确同意时）：从 `https://codeload.github.com/881000/skills/zip/refs/heads/main` 下载最新仓库压缩包并解压，**仅提取**仓库根目录下的技能库文件（`SKILL.md`、`README.md`、`references/`、`scripts/`），用它们替换**本技能当前安装所在目录**的对应内容，仓库中的其他技能库一律不触碰；全部文件一律以仓库为准整体替换，不做任何本地保留；替换完成后，**必须重新注入本「版本更新检查」段落**，使下次更新检查继续生效；最后执行 `python scripts/install.py sync-catalog`，自动将 catalog.json 中各技能的版本基线同步到对应仓库的最新版本。
5. **无更新**：两个文件的远程版本均与本地一致时，不提示，直接正常回答。
