#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import json
import requests
from pathlib import Path

API = "https://api.themoviedb.org/3"

# ============================================================
# 修改这里：填入你的 TMDB API Read Access Token
# 获取方式：TMDB -> Account Settings -> API
# ============================================================

TMDB_TOKEN = os.environ.get("TMDB_TOKEN", "")

# 默认语言
LANGUAGE = "zh-CN"


def api_get(url, params=None):
    headers = {
        "Authorization": f"Bearer {TMDB_TOKEN}",
        "accept": "application/json"
    }

    r = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30
    )

    if r.status_code != 200:
        print("TMDB API 错误:")
        print(r.status_code)
        print(r.text[:1000])
        sys.exit(1)

    return r.json()


def clean_name(name):
    """
    清理 Linux 文件名非法字符
    """
    if not name:
        return "Unknown"

    name = re.sub(r'[\/\\:*?"<>|]', '_', name)
    name = name.strip()

    # 避免 Linux 下奇怪的结尾
    name = name.rstrip(". ")

    return name


def get_tv_id(value):
    """
    支持：
    1399
    https://www.themoviedb.org/tv/1399-game-of-thrones
    https://www.themoviedb.org/tv/1399
    剧名
    """

    value = value.strip()

    # 直接输入数字 ID
    if value.isdigit():
        return int(value)

    # TMDB URL
    m = re.search(r'/tv/(\d+)', value)

    if m:
        return int(m.group(1))

    # 按剧名搜索
    print(f"正在 TMDB 搜索：{value}")

    data = api_get(
        f"{API}/search/tv",
        {
            "query": value,
            "language": LANGUAGE,
            "include_adult": "false"
        }
    )

    results = data.get("results", [])

    if not results:
        print("没有找到电视剧。")
        sys.exit(1)

    print("\n找到以下结果：\n")

    for i, x in enumerate(results[:10], 1):
        print(
            f"{i}. {x.get('name')} "
            f"({x.get('first_air_date', '')}) "
            f"[TMDB {x.get('id')}]"
        )

    if len(results) == 1:
        return results[0]["id"]

    while True:
        try:
            n = int(input("\n请选择编号："))
            if 1 <= n <= min(10, len(results)):
                return results[n - 1]["id"]
        except ValueError:
            pass

        print("输入错误，请重新输入。")


def create_file(path, content=""):
    """
    创建文件。
    如果文件已经存在，不覆盖。
    """

    if path.exists():
        return False

    path.write_text(content, encoding="utf-8")
    return True


def make_fake_mp4(path):
    """
    创建一个很小的 MP4 占位文件。

    注意：
    这是一个最小的 MP4 文件头占位，并不是实际视频。
    如果你的 Emby 不把它识别为媒体，可以改成真正的短 MP4。
    """

    if path.exists():
        return False

    # 最小 ftyp box
    data = (
        b'\x00\x00\x00\x18'
        b'ftyp'
        b'isom'
        b'\x00\x00\x02\x00'
        b'isom'
        b'iso2'
        b'mp41'
    )

    with open(path, "wb") as f:
        f.write(data)

    return True


def create_tvshow_nfo(tv, root):
    """
    创建 Emby / Kodi 通用 tvshow.nfo
    """

    name = tv.get("name", "")
    original_name = tv.get("original_name", "")
    overview = tv.get("overview", "")
    first_air = tv.get("first_air_date", "")
    tmdb_id = tv.get("id", "")

    nfo = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<tvshow>
    <title>{xml_escape(name)}</title>
    <originaltitle>{xml_escape(original_name)}</originaltitle>
    <plot>{xml_escape(overview)}</plot>
    <premiered>{xml_escape(first_air)}</premiered>
    <uniqueid type="tmdb" default="true">{tmdb_id}</uniqueid>
    <id>{tmdb_id}</id>
</tvshow>
"""

    create_file(root / "tvshow.nfo", nfo)


def create_season_nfo(season, season_dir, tv_id):
    season_number = season.get("season_number", 0)
    name = season.get("name", "")
    overview = season.get("overview", "")
    air_date = season.get("air_date", "")

    nfo = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<season>
    <title>{xml_escape(name)}</title>
    <seasonnumber>{season_number}</seasonnumber>
    <plot>{xml_escape(overview)}</plot>
    <aired>{xml_escape(air_date)}</aired>
    <uniqueid type="tmdb" default="true">{season.get('id', '')}</uniqueid>
</season>
"""

    create_file(season_dir / "season.nfo", nfo)


def create_episode_nfo(tv_id, season_number, episode):
    episode_number = episode.get("episode_number", 0)
    title = episode.get("name", "")
    overview = episode.get("overview", "")
    air_date = episode.get("air_date", "")
    episode_id = episode.get("id", "")

    filename = (
        f"S{season_number:02d}"
        f"E{episode_number:02d}"
        f".nfo"
    )

    nfo = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<episodedetails>
    <title>{xml_escape(title)}</title>
    <season>{season_number}</season>
    <episode>{episode_number}</episode>
    <plot>{xml_escape(overview)}</plot>
    <aired>{xml_escape(air_date)}</aired>
    <uniqueid type="tmdb" default="true">{episode_id}</uniqueid>
    <showid>{tv_id}</showid>
</episodedetails>
"""

    return filename, nfo


def xml_escape(s):
    if s is None:
        return ""

    s = str(s)

    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&apos;")
    )


def main():

    print("=" * 70)
    print(" TMDB -> Emby 电视剧目录生成器")
    print("=" * 70)

    if not TMDB_TOKEN:
        print("\n没有设置 TMDB_TOKEN。")
        print("\n方法一：")
        print("export TMDB_TOKEN='你的TMDB Read Access Token'")
        print("\n方法二：直接修改程序顶部的 TMDB_TOKEN")
        print()
        sys.exit(1)

    # --------------------------------------------------------
    # 获取输入
    # --------------------------------------------------------

    if len(sys.argv) >= 2:
        tv_input = sys.argv[1]
    else:
        tv_input = input("\n输入 TMDB 剧名 / TMDB ID / TMDB URL：").strip()

    if len(sys.argv) >= 3:
        output_dir = sys.argv[2]
    else:
        output_dir = input(
            "输入保存目录，例如 /media/tv ："
        ).strip()

    if not output_dir:
        print("没有指定保存目录。")
        sys.exit(1)

    # --------------------------------------------------------
    # 获取 TMDB ID
    # --------------------------------------------------------

    tv_id = get_tv_id(tv_input)

    print(f"\nTMDB ID: {tv_id}")
    print("正在获取电视剧信息...")

    tv = api_get(
        f"{API}/tv/{tv_id}",
        {
            "language": LANGUAGE
        }
    )

    title = tv.get("name", f"TV_{tv_id}")

    print()
    print("电视剧：", title)
    print("原名：", tv.get("original_name"))
    print("首播：", tv.get("first_air_date"))
    print("状态：", tv.get("status"))
    print("季数：", tv.get("number_of_seasons"))
    print("集数：", tv.get("number_of_episodes"))
    print()

    # --------------------------------------------------------
    # 创建电视剧目录
    # --------------------------------------------------------

    root = Path(output_dir) / clean_name(title)

    root.mkdir(
        parents=True,
        exist_ok=True
    )

    print("目录：", root)

    # 保存完整 TMDB 数据
    create_file(
        root / "tmdb.json",
        json.dumps(
            tv,
            ensure_ascii=False,
            indent=2
        )
    )

    # tvshow.nfo
    create_tvshow_nfo(tv, root)

    seasons = tv.get("seasons", [])

    total_created = 0

    # --------------------------------------------------------
    # 遍历所有季
    # --------------------------------------------------------

    for season_info in seasons:

        season_number = season_info.get(
            "season_number",
            0
        )

        # 跳过 Special
        if season_number == 0:
            print("\n跳过 Special (Season 00)")
            continue

        season_name = season_info.get(
            "name",
            f"Season {season_number:02d}"
        )

        season_dir = root / f"Season {season_number:02d}"

        season_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        print()
        print("-" * 70)
        print(
            f"Season {season_number:02d} "
            f"{season_name}"
        )
        print("-" * 70)

        # ----------------------------------------------------
        # 获取这一季详细信息
        # ----------------------------------------------------

        season = api_get(
            f"{API}/tv/{tv_id}/season/{season_number}",
            {
                "language": LANGUAGE
            }
        )

        # season.nfo
        create_season_nfo(
            season,
            season_dir,
            tv_id
        )

        episodes = season.get(
            "episodes",
            []
        )

        print(
            f"发现 {len(episodes)} 集"
        )

        # ----------------------------------------------------
        # 创建每一集
        # ----------------------------------------------------

        for ep in episodes:

            ep_num = ep.get(
                "episode_number",
                0
            )

            ep_title = ep.get(
                "name",
                f"Episode {ep_num}"
            )

            ep_title_clean = clean_name(ep_title)

            filename = (
                f"{title} "
                f"S{season_number:02d}"
                f"E{ep_num:02d} "
                f"- {ep_title_clean}.mp4"
            )

            mp4 = season_dir / filename

            nfo_name, nfo_content = create_episode_nfo(
                tv_id,
                season_number,
                ep
            )

            nfo_path = season_dir / (
                Path(filename).stem + ".nfo"
            )

            new_mp4 = make_fake_mp4(mp4)

            create_file(
                nfo_path,
                nfo_content
            )

            if new_mp4:
                total_created += 1

            print(
                f"  S{season_number:02d}"
                f"E{ep_num:02d} "
                f"{ep_title}"
            )

    # --------------------------------------------------------
    # 完成
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("完成")
    print("=" * 70)
    print()
    print("电视剧目录：")
    print(root)
    print()
    print("新建 MP4：", total_created)
    print()
    print("可以把下面这个目录加入 Emby：")
    print(root)
    print()


if __name__ == "__main__":
    main()
