#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技能库安装器（通用版，适用于任意 AI 平台）

用法:
  python install.py list [--install-dir DIR] [--check-updates]
  python install.py info <技能名称> [--install-dir DIR]
  python install.py install <技能名称> [--install-dir DIR] [--force]
  python install.py install-category <一级分类> [--install-dir DIR] [--force]
  python install.py install-subcategory <一级分类> <二级分类> [--install-dir DIR] [--force]
  python install.py sync-catalog
  python install.py version

安装目录优先级: --install-dir 参数 > 环境变量 SKILL_INSTALL_DIR > 自动探测 .user_skills/skills 目录 > 当前目录下 skills 文件夹
"""

import json
import os
import re
import sys
import io
import shutil
import tempfile
import argparse
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

# 强制 UTF-8 输出
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
CATALOG_PATH = SCRIPT_DIR.parent / "references" / "catalog.json"
SKILL_MD_PATH = SCRIPT_DIR.parent / "SKILL.md"
VERSION_FILENAME = ".skill_version"


# ---------- 基础工具 ----------

def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_install_dir(cli_dir=None):
    """探测技能安装目录，优先级: CLI参数 > 环境变量 > 自动探测 .user_skills/skills 目录 > 当前目录/skills"""
    # 1. CLI 参数
    if cli_dir:
        p = Path(cli_dir).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 2. 环境变量
    env_dir = os.environ.get("SKILL_INSTALL_DIR", "").strip()
    if env_dir:
        p = Path(env_dir).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 3. 自动探测：从本技能位置向上找 .user_skills / skills 目录
    candidate = SCRIPT_DIR.parent.parent
    if candidate.name in (".user_skills", "skills"):
        return candidate

    # 4. 当前目录下的 skills 文件夹
    p = Path.cwd() / "skills"
    p.mkdir(parents=True, exist_ok=True)
    return p


def find_skill(catalog, name):
    """按名称查找技能，返回 (一级分类, 二级分类, 技能信息)"""
    for cat1, subcats in catalog["categories"].items():
        for cat2, skills in subcats.items():
            for skill in skills:
                if skill["name"] == name:
                    return cat1, cat2, skill
    return None, None, None


def read_frontmatter_version(file_path):
    """从 Markdown 文件的 YAML frontmatter 中读取 version 字段。"""
    p = Path(file_path)
    if not p.exists():
        return None
    try:
        content = p.read_text(encoding="utf-8").lstrip("\ufeff\r\n\t ")
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                for line in content[3:end].splitlines():
                    line = line.strip()
                    if line.lower().startswith("version:"):
                        v = line.split(":", 1)[1].strip().strip('"').strip("'")
                        if v:
                            return v
    except Exception:
        pass
    return None


# ---------- 版本管理 ----------

def parse_version(v):
    """解析版本号，支持 v 前缀和带后缀的版本（如 1.0.0-beta、v2.1.0）。"""
    try:
        s = str(v).strip().lstrip("vV")
        m = re.match(r"^(\d+(?:\.\d+)*)", s)
        if m:
            return tuple(int(x) for x in m.group(1).split("."))
        return (0,)
    except (ValueError, AttributeError):
        return (0,)


def version_compare(v1, v2):
    p1, p2 = parse_version(v1), parse_version(v2)
    maxlen = max(len(p1), len(p2))
    p1 += (0,) * (maxlen - len(p1))
    p2 += (0,) * (maxlen - len(p2))
    if p1 < p2:
        return -1
    if p1 > p2:
        return 1
    return 0


def get_installed_version(skill_dir):
    vfile = Path(skill_dir) / VERSION_FILENAME
    if vfile.exists():
        try:
            return vfile.read_text(encoding="utf-8").strip()
        except Exception:
            return None
    return None


def write_version_file(skill_dir, version):
    vfile = Path(skill_dir) / VERSION_FILENAME
    try:
        vfile.write_text(str(version), encoding="utf-8")
    except Exception:
        pass


_remote_version_cache = {}


def fetch_remote_version(repo, branch="main"):
    """从 GitHub 仓库 SKILL.md frontmatter 实时读取最新版本号。
    依次尝试配置分支 → main → master，任一成功即返回；全部失败才返回 None。
    """
    repo_fail_key = f"{repo}__fail"
    if repo_fail_key in _remote_version_cache:
        return None

    branches = []
    for b in [branch, "main", "master"]:
        if b and b not in branches:
            branches.append(b)

    for br in branches:
        cache_key = f"{repo}@{br}"
        if cache_key in _remote_version_cache:
            cached = _remote_version_cache[cache_key]
            if cached is not None:
                return cached
            continue  # 该分支缓存为 None，尝试下一个分支

        url = f"https://raw.githubusercontent.com/{repo}/{br}/SKILL.md"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                content = resp.read().decode("utf-8", errors="ignore").lstrip("\ufeff\r\n\t ")
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    for line in content[3:end].splitlines():
                        line = line.strip()
                        if line.lower().startswith("version:"):
                            v = line.split(":", 1)[1].strip().strip('"').strip("'")
                            if v:
                                _remote_version_cache[cache_key] = v
                                return v
            # 页面可达但无 version 字段，缓存 None 并继续下一个分支
            _remote_version_cache[cache_key] = None
        except urllib.error.HTTPError:
            # 404/403/500 等均视为该分支不可用，继续尝试下一个分支
            _remote_version_cache[cache_key] = None
            continue
        except Exception:
            _remote_version_cache[cache_key] = None
            continue

    # 所有分支均失败，标记仓库级失败
    _remote_version_cache[repo_fail_key] = True
    return None


def get_latest_version(skill):
    remote = fetch_remote_version(skill["repo"], skill.get("branch", "main"))
    if remote:
        return remote
    return skill.get("version", "1.0.0")


def get_skill_status(skill, install_dir, use_remote=False):
    target = install_dir / skill["name"]
    latest = get_latest_version(skill) if use_remote else skill.get("version", "1.0.0")
    if not target.exists():
        return "未安装", "-", latest
    installed = get_installed_version(target)
    if installed is None:
        return "已安装", latest, latest
    if version_compare(installed, latest) < 0:
        return "可更新", installed, latest
    return "已安装", installed, latest


# ---------- 终端表格辅助 ----------

def display_width(s):
    w = 0
    for ch in str(s):
        w += 2 if ord(ch) > 127 else 1
    return w


def pad_to(s, width):
    s = str(s)
    return s + " " * max(0, width - display_width(s))


def print_skill_table(rows, title=None, subtitle=None, group_by_category=False):
    """统一表格输出：技能名称、分类、本地版本、最新版本、状态
    rows: list of dict with keys: name, category, local, latest, status
    group_by_category: 按分类分组输出标题行
    """
    if not rows:
        return
    col_name = max(16, max(display_width(r["name"]) for r in rows) + 2)
    col_cat = max(16, max(display_width(r["category"]) for r in rows) + 2)
    col_local = max(10, max(display_width(str(r["local"])) for r in rows) + 2)
    col_latest = max(10, max(display_width(str(r["latest"])) for r in rows) + 2)
    col_status = max(8, max(display_width(r["status"]) for r in rows) + 2)
    total_width = col_name + col_cat + col_local + col_latest + col_status + 3 * 5 + 1
    group_content_width = total_width - 4

    if title or subtitle:
        print("=" * total_width)
        if title:
            print(title)
        if subtitle:
            print(subtitle)
        print("=" * total_width)

    header = (
        f"| {pad_to('技能名称', col_name)} "
        f"| {pad_to('分类', col_cat)} "
        f"| {pad_to('本地版本', col_local)} "
        f"| {pad_to('最新版本', col_latest)} "
        f"| {pad_to('状态', col_status)} |"
    )
    print(header)
    print("-" * total_width)

    current_cat = None
    for r in rows:
        if group_by_category and r["category"] != current_cat:
            current_cat = r["category"]
            print(f"| {pad_to('【' + current_cat + '】', group_content_width)} |")
        line = (
            f"| {pad_to(r['name'], col_name)} "
            f"| {pad_to(r['category'], col_cat)} "
            f"| {pad_to(str(r['local']), col_local)} "
            f"| {pad_to(str(r['latest']), col_latest)} "
            f"| {pad_to(r['status'], col_status)} |"
        )
        print(line)
    print("=" * total_width)


def make_row(cat1, cat2, name, local_v, latest_v, status):
    """构造表格行字典"""
    return {
        "name": name,
        "category": f"{cat1}/{cat2}",
        "local": local_v,
        "latest": latest_v,
        "status": status,
    }


# ---------- 下载安装 ----------

def download_zip(repo, branch, dest_path):
    """下载 GitHub 仓库 ZIP 压缩包。任何异常均返回 False，由上层决定是否回退分支。"""
    zip_url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
    try:
        req = urllib.request.Request(zip_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        return True
    except Exception:
        return False


def safe_extract_zip(zip_path, dest_dir):
    """安全解压 ZIP，防止 Zip Slip 路径遍历攻击。"""
    dest_resolved = Path(dest_dir).resolve()
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            member_path = (dest_resolved / member).resolve()
            if not str(member_path).startswith(str(dest_resolved) + os.sep) and member_path != dest_resolved:
                raise RuntimeError(f"检测到不安全的压缩包路径（Zip Slip）: {member}")
        zf.extractall(dest_dir)


def download_and_install(skill, install_dir, force=False):
    name = skill["name"]
    repo = skill["repo"]
    configured_branch = skill.get("branch", "main")
    display_version = get_latest_version(skill)
    target_dir = install_dir / name

    tmpdir = tempfile.mkdtemp(prefix="skill_install_")
    try:
        zip_path = Path(tmpdir) / "skill.zip"
        branches_to_try = []
        for b in [configured_branch, "main", "master"]:
            if b and b not in branches_to_try:
                branches_to_try.append(b)

        branch_used = None
        for branch in branches_to_try:
            print(f"  尝试分支 [{branch}]: https://github.com/{repo}")
            if download_zip(repo, branch, zip_path):
                branch_used = branch
                break

        if not branch_used:
            print(f"  [失败] 无法下载仓库 https://github.com/{repo}")
            print(f"         可能原因: 仓库不存在、为私有仓库、网络不可达、或分支名不是 main/master")
            return False

        print(f"  下载成功（分支: {branch_used}），解压中...")
        safe_extract_zip(zip_path, tmpdir)

        repo_name = repo.split("/")[-1]
        extracted_dir = Path(tmpdir) / f"{repo_name}-{branch_used}"
        if not extracted_dir.exists():
            subdirs = [d for d in Path(tmpdir).iterdir() if d.is_dir() and d.name != "skill.zip"]
            if len(subdirs) == 1:
                extracted_dir = subdirs[0]
            else:
                raise RuntimeError(f"无法确定解压目录，内容: {list(Path(tmpdir).iterdir())}")

        # 从解压后的 SKILL.md 读取实际版本号（以 GitHub 实际内容为准）
        actual_version = read_frontmatter_version(extracted_dir / "SKILL.md")

        # 版本保护：GitHub 仓库版本没更新，本地版本不得更新
        current_installed = get_installed_version(target_dir) if target_dir.exists() else None
        version_unchanged = False
        if actual_version:
            if current_installed and version_compare(actual_version, current_installed) <= 0:
                version = current_installed
                version_unchanged = True
            else:
                version = actual_version
        else:
            # 无法读取下载包版本时，保持本地已有版本；全新安装才用 catalog 基线
            version = current_installed if current_installed else display_version

        # 下载解压均成功后，再替换旧目录（避免下载失败导致旧技能被删）
        if target_dir.exists():
            if not force and not version_unchanged:
                print(f"  [提示] 技能「{name}」已存在，将覆盖安装为 v{version}...")
            shutil.rmtree(target_dir)

        shutil.move(str(extracted_dir), str(target_dir))
        write_version_file(target_dir, version)
        if version_unchanged:
            print(f"  [提示] GitHub 版本 v{actual_version} 未高于本地 v{current_installed}，本地版本保持不变")
        print(f"  [成功] 已安装 v{version} 到: {target_dir}")
        return True

    except Exception as e:
        print(f"  [失败] {e}")
        return False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------- 命令实现 ----------

def cmd_list(catalog, install_dir, check_updates=False):
    rows = []
    for cat1, subcats in catalog["categories"].items():
        for cat2, skills in subcats.items():
            for skill in skills:
                status, local_v, latest_v = get_skill_status(skill, install_dir, use_remote=check_updates)
                rows.append(make_row(cat1, cat2, skill["name"], local_v, latest_v, status))

    print_skill_table(rows, title="可用技能库", subtitle=f"安装目录: {install_dir}", group_by_category=True)

    total = len(rows)
    installed = sum(1 for r in rows if r["status"] in ("已安装", "可更新"))
    updatable = sum(1 for r in rows if r["status"] == "可更新")
    not_installed = sum(1 for r in rows if r["status"] == "未安装")
    print(f"共 {total} 个技能 | 已安装 {installed} 个 | 可更新 {updatable} 个 | 未安装 {not_installed} 个")
    print("=" * 60)

    if updatable > 0:
        names = "、".join(r["name"] for r in rows if r["status"] == "可更新")
        print(f"提示: 有 {updatable} 个技能可更新: {names}")
    if not_installed > 0:
        names = "、".join(r["name"] for r in rows if r["status"] == "未安装")
        print(f"提示: 有 {not_installed} 个技能未安装: {names}")
    if updatable == 0 and not_installed == 0:
        print("提示: 所有技能均为最新版本，无需操作")
    print("=" * 60)


def cmd_install(catalog, name, install_dir, force=False):
    cat1, cat2, skill = find_skill(catalog, name)
    if not skill:
        print(f"[错误] 未找到技能「{name}」，请用 list 查看可用技能")
        return False
    status, local_v, remote_v = get_skill_status(skill, install_dir, use_remote=True)
    row = make_row(cat1, cat2, skill["name"], local_v, remote_v, status)
    print_skill_table([row], title="安装技能")
    print(f"仓库: https://github.com/{skill['repo']}")
    print(f"安装目录: {install_dir}")
    print()
    ok = download_and_install(skill, install_dir, force=force)
    print()
    if ok:
        new_status, new_local, new_remote = get_skill_status(skill, install_dir, use_remote=False)
        result_row = make_row(cat1, cat2, skill["name"], new_local, new_remote, new_status)
        print_skill_table([result_row], title="安装结果")
    else:
        fail_row = make_row(cat1, cat2, skill["name"], local_v, remote_v, "安装失败")
        print_skill_table([fail_row], title="安装失败")
    return ok


def _batch_install(skills_with_cat, install_dir, force=False, label=""):
    """批量安装公共逻辑。skills_with_cat: list of (cat1, cat2, skill)"""
    total = len(skills_with_cat)
    if label:
        print(f"将安装「{label}」下共 {total} 个技能到 {install_dir}")
        print()
    success = 0
    results = []
    for idx, (cat1, cat2, skill) in enumerate(skills_with_cat, 1):
        status, local_v, remote_v = get_skill_status(skill, install_dir, use_remote=True)
        row = make_row(cat1, cat2, skill["name"], local_v, remote_v, status)
        print_skill_table([row], title=f"[{idx}/{total}] 安装技能")
        ok = download_and_install(skill, install_dir, force=force)
        if ok:
            success += 1
            new_status, new_local, new_remote = get_skill_status(skill, install_dir, use_remote=False)
            results.append(make_row(cat1, cat2, skill["name"], new_local, new_remote, new_status))
        else:
            results.append(make_row(cat1, cat2, skill["name"], local_v, remote_v, "安装失败"))
    print()
    print_skill_table(results, title=f"批量安装结果: {success}/{total} 个成功")
    return success == total


def cmd_install_category(catalog, cat1_name, install_dir, force=False):
    if cat1_name not in catalog["categories"]:
        print(f"[错误] 未找到分类「{cat1_name}」，可用分类: {list(catalog['categories'].keys())}")
        return False
    skills = []
    for cat2, slist in catalog["categories"][cat1_name].items():
        for skill in slist:
            skills.append((cat1_name, cat2, skill))
    return _batch_install(skills, install_dir, force=force, label=cat1_name)


def cmd_install_subcategory(catalog, cat1_name, cat2_name, install_dir, force=False):
    if cat1_name not in catalog["categories"]:
        print(f"[错误] 未找到分类「{cat1_name}」")
        return False
    if cat2_name not in catalog["categories"][cat1_name]:
        print(f"[错误] 「{cat1_name}」下未找到子分类「{cat2_name}」")
        print(f"  可用子分类: {list(catalog['categories'][cat1_name].keys())}")
        return False
    skills = [(cat1_name, cat2_name, skill) for skill in catalog["categories"][cat1_name][cat2_name]]
    return _batch_install(skills, install_dir, force=force, label=f"{cat1_name}/{cat2_name}")


def cmd_info(catalog, name, install_dir):
    cat1, cat2, skill = find_skill(catalog, name)
    if not skill:
        print(f"[错误] 未找到技能「{name}」")
        return False
    status, local_v, remote_v = get_skill_status(skill, install_dir, use_remote=True)
    row = make_row(cat1, cat2, skill["name"], local_v, remote_v, status)
    print_skill_table([row], title="技能详情")
    print(f"仓库: https://github.com/{skill['repo']}")
    print(f"分支: {skill.get('branch', 'main')}")
    print(f"安装目录: {install_dir / skill['name']}")
    print(f"描述: {skill['description']}")
    return True


def cmd_sync_catalog(catalog):
    """遍历所有技能，从远程读取最新版本，更新 catalog.json 中的 version 字段。"""
    updated = []
    failed = []
    skipped = []

    for cat1, subcats in catalog["categories"].items():
        for cat2, skills in subcats.items():
            for skill in skills:
                name = skill["name"]
                current_version = skill.get("version", "1.0.0")
                remote_version = fetch_remote_version(skill["repo"], skill.get("branch", "main"))
                if remote_version is None:
                    failed.append((cat1, cat2, name, current_version))
                    continue
                if version_compare(remote_version, current_version) > 0:
                    skill["version"] = remote_version
                    updated.append((cat1, cat2, name, current_version, remote_version))
                else:
                    skipped.append((cat1, cat2, name, current_version, remote_version))

    if updated:
        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)

    updated_rows = [make_row(c1, c2, n, old, new, "已更新") for c1, c2, n, old, new in updated]
    skipped_rows = [make_row(c1, c2, n, local_v, remote_v, "已是最新") for c1, c2, n, local_v, remote_v in skipped]
    failed_rows = [make_row(c1, c2, n, local_v, "-", "检测失败") for c1, c2, n, local_v in failed]

    print()
    if updated_rows:
        print_skill_table(updated_rows, title=f"已更新 {len(updated_rows)} 个技能")
    if skipped_rows:
        print_skill_table(skipped_rows, title=f"已是最新 {len(skipped_rows)} 个技能")
    if failed_rows:
        print_skill_table(failed_rows, title=f"检测失败 {len(failed_rows)} 个技能（保持原版本）")
    print("=" * 60)
    print(f"统计: 更新 {len(updated)} | 已是最新 {len(skipped)} | 检测失败 {len(failed)}")
    print("=" * 60)
    return len(failed) == 0


def cmd_version():
    """显示技能库自身版本号（读取 SKILL.md frontmatter）。"""
    v = read_frontmatter_version(SKILL_MD_PATH)
    if v:
        print(f"技能库版本: v{v}")
    else:
        try:
            catalog = load_catalog()
            v = catalog.get("version", "未知")
            print(f"技能库版本: v{v}（数据版本）")
        except Exception:
            print("技能库版本: 未知")
    return True


# ---------- 入口 ----------

def main():
    parser = argparse.ArgumentParser(description="技能库安装器", add_help=True)
    sub = parser.add_subparsers(dest="command")

    # 仅含 --install-dir 的公共参数（list / info 使用）
    with_dir = argparse.ArgumentParser(add_help=False)
    with_dir.add_argument("--install-dir", default=None, help="技能安装目录（默认自动探测）")

    # 安装类命令的公共参数（含 --install-dir + --force）
    install_opts = argparse.ArgumentParser(add_help=False, parents=[with_dir])
    install_opts.add_argument("--force", action="store_true", help="覆盖已存在技能时不输出提示信息")

    p_list = sub.add_parser("list", parents=[with_dir], help="列出全部技能及状态")
    p_list.add_argument("--check-updates", action="store_true", help="实时检测远程版本（较慢，默认关闭）")

    p_info = sub.add_parser("info", parents=[with_dir], help="查看技能详情")
    p_info.add_argument("name", help="技能名称")

    p_install = sub.add_parser("install", parents=[install_opts], help="安装/更新单个技能")
    p_install.add_argument("name", help="技能名称")

    p_cat = sub.add_parser("install-category", parents=[install_opts], help="安装一级分类下全部技能")
    p_cat.add_argument("category", help="一级分类名称")

    p_sub = sub.add_parser("install-subcategory", parents=[install_opts], help="安装二级分类下全部技能")
    p_sub.add_argument("category", help="一级分类名称")
    p_sub.add_argument("subcategory", help="二级分类名称")

    p_sync = sub.add_parser("sync-catalog", help="同步 catalog.json 中所有技能的版本到最新")

    p_version = sub.add_parser("version", help="显示技能库自身版本")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "version":
        cmd_version()
        sys.exit(0)

    catalog = load_catalog()
    install_dir = detect_install_dir(getattr(args, "install_dir", None))
    force = getattr(args, "force", False)

    if args.command == "list":
        cmd_list(catalog, install_dir, check_updates=getattr(args, "check_updates", False))
    elif args.command == "info":
        cmd_info(catalog, args.name, install_dir)
    elif args.command == "install":
        ok = cmd_install(catalog, args.name, install_dir, force=force)
        sys.exit(0 if ok else 1)
    elif args.command == "install-category":
        ok = cmd_install_category(catalog, args.category, install_dir, force=force)
        sys.exit(0 if ok else 1)
    elif args.command == "install-subcategory":
        ok = cmd_install_subcategory(catalog, args.category, args.subcategory, install_dir, force=force)
        sys.exit(0 if ok else 1)
    elif args.command == "sync-catalog":
        ok = cmd_sync_catalog(catalog)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
