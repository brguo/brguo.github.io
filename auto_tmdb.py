#!/usr/bin/env python3

# -*- coding: utf-8 -*-

import os

import re

import sys

import json

import time

import argparse

import requests

from pathlib import Path

API = "https://api.themoviedb.org/3"

IMAGE_API = "https://image.tmdb.org/t/p"

# ============================================================

# TMDB Token

#

# 推荐：

# export TMDB_TOKEN="你的 TMDB API Read Access Token"

#

# 或者直接写在这里：

# TMDB_TOKEN = "xxxxxxxx"

# ============================================================

TMDB_TOKEN = os.environ.get("TMDB_TOKEN", "")

# TMDB 查询语言

LANGUAGE = "zh-CN"

# 图片下载重试次数

IMAGE_RETRY = 3

# 图片尺寸

POSTER_SIZE = "w500"

BACKDROP_SIZE = "w1280"

STILL_SIZE = "w780"

# ============================================================

# TMDB API

# ============================================================

def api_get(url, params=None):

    headers = {

        "Authorization": f"Bearer {TMDB_TOKEN}",

        "accept": "application/json"

    }

    try:

        r = requests.get(

            url,

            headers=headers,

            params=params,

            timeout=30

        )

    except requests.RequestException as e:

        print(f"TMDB 网络错误: {e}")

        sys.exit(1)

    if r.status_code != 200:

        print("\nTMDB API 错误:")

        print("HTTP:", r.status_code)

        print(r.text[:1000])

        sys.exit(1)

    return r.json()

# ============================================================

# 文件名清理

# ============================================================

def clean_name(name):

    if not name:

        return "Unknown"

    name = str(name)

    # Linux / Windows 通用清理

    name = re.sub(

        r'[\/\\:*?"<>|]',

        "_",

        name

    )

    name = name.strip()

    name = name.rstrip(". ")

    return name

# ============================================================

# XML 转义

# ============================================================

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

# ============================================================

# 创建文本文件

# ============================================================

def create_file(path, content=""):

    if path.exists():

        return False

    path.write_text(

        content,

        encoding="utf-8"

    )

    return True

# ============================================================

# 下载图片

# ============================================================

def download_image(

    image_path,

    output_path,

    description=""

):

    if not image_path:

        print(

            f"    [没有图片] {description}"

        )

        return False

    if output_path.exists():

        print(

            f"    [已存在] {output_path.name}"

        )

        return True

    url = (

        f"{IMAGE_API}/"

        f"{description and ''}"

    )

    # description 参数不参与 URL

    # image_path 本身已经是 /xxxx.jpg

    url = (

        f"{IMAGE_API}/"

        f"{POSTER_SIZE if description == 'poster' else BACKDROP_SIZE if description == 'backdrop' else STILL_SIZE}"

        f"{image_path}"

    )

    print(

        f"    [下载] {description}: "

        f"{output_path.name}"

    )

    for retry in range(1, IMAGE_RETRY + 1):

        try:

            r = requests.get(

                url,

                timeout=60

            )

            if r.status_code == 200:

                # 简单检查是不是图片

                if len(r.content) < 100:

                    print(

                        f"    [失败] 图片文件太小"

                    )

                else:

                    output_path.write_bytes(

                        r.content

                    )

                    print(

                        f"    [完成] "

                        f"{len(r.content) / 1024:.1f} KB"

                    )

                    return True

            else:

                print(

                    f"    [失败] HTTP {r.status_code}"

                )

        except requests.RequestException as e:

            print(

                f"    [失败] {e}"

            )

        if retry < IMAGE_RETRY:

            print(

                f"    重试 {retry + 1}/{IMAGE_RETRY}..."

            )

            time.sleep(2)

    return False

# ============================================================

# 下载剧集图片

# ============================================================

def download_tv_images(tv, root):

    print()

    print("下载电视剧图片")

    print("-" * 70)

    # poster

    poster = tv.get("poster_path")

    download_image(

        poster,

        root / "poster.jpg",

        "poster"

    )

    # backdrop

    backdrop = tv.get("backdrop_path")

    download_image(

        backdrop,

        root / "backdrop.jpg",

        "backdrop"

    )

# ============================================================

# 获取 TV ID

# ============================================================

def get_tv_id(value):

    value = value.strip()

    # TMDB ID

    if value.isdigit():

        return int(value)

    # TMDB URL

    m = re.search(

        r'/tv/(\d+)',

        value

    )

    if m:

        return int(m.group(1))

    # 剧名搜索

    print()

    print(

        f"正在 TMDB 搜索：{value}"

    )

    data = api_get(

        f"{API}/search/tv",

        {

            "query": value,

            "language": LANGUAGE,

            "include_adult": "false"

        }

    )

    results = data.get(

        "results",

        []

    )

    if not results:

        print(

            "没有找到电视剧。"

        )

        sys.exit(1)

    print()

    print("找到以下结果：")

    print()

    for i, x in enumerate(

        results[:10],

        1

    ):

        print(

            f"{i}. "

            f"{x.get('name')} "

            f"({x.get('first_air_date', '')}) "

            f"[TMDB {x.get('id')}]"

        )

    if len(results) == 1:

        return results[0]["id"]

    while True:

        try:

            n = int(

                input("\n请选择编号：")

            )

            if 1 <= n <= min(

                10,

                len(results)

            ):

                return results[

                    n - 1

                ]["id"]

        except ValueError:

            pass

        print(

            "输入错误，请重新输入。"

        )

# ============================================================

# MP4 占位文件

# ============================================================

def make_fake_mp4(path):

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

    with open(

        path,

        "wb"

    ) as f:

        f.write(data)

    return True

# ============================================================

# TV NFO

# ============================================================

def create_tvshow_nfo(

    tv,

    root

):

    name = tv.get(

        "name",

        ""

    )

    original_name = tv.get(

        "original_name",

        ""

    )

    overview = tv.get(

        "overview",

        ""

    )

    first_air = tv.get(

        "first_air_date",

        ""

    )

    tmdb_id = tv.get(

        "id",

        ""

    )

    status = tv.get(

        "status",

        ""

    )

    genres = tv.get(

        "genres",

        []

    )

    genre_text = ", ".join(

        x.get("name", "")

        for x in genres

    )

    nfo = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>

<tvshow>

    <title>{xml_escape(name)}</title>

    <originaltitle>{xml_escape(original_name)}</originaltitle>

    <plot>{xml_escape(overview)}</plot>

    <premiered>{xml_escape(first_air)}</premiered>

    <status>{xml_escape(status)}</status>

    <genre>{xml_escape(genre_text)}</genre>

    <uniqueid type="tmdb" default="true">{tmdb_id}</uniqueid>

    <id>{tmdb_id}</id>

</tvshow>

"""

    create_file(

        root / "tvshow.nfo",

        nfo

    )

# ============================================================

# Season NFO

# ============================================================

def create_season_nfo(

    season,

    season_dir,

    tv_id

):

    season_number = season.get(

        "season_number",

        0

    )

    name = season.get(

        "name",

        ""

    )

    overview = season.get(

        "overview",

        ""

    )

    air_date = season.get(

        "air_date",

        ""

    )

    season_id = season.get(

        "id",

        ""

    )

    nfo = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>

<season>

    <title>{xml_escape(name)}</title>

    <seasonnumber>{season_number}</seasonnumber>

    <plot>{xml_escape(overview)}</plot>

    <aired>{xml_escape(air_date)}</aired>

    <uniqueid type="tmdb" default="true">{season_id}</uniqueid>

    <tvshowid>{tv_id}</tvshowid>

</season>

"""

    create_file(

        season_dir / "season.nfo",

        nfo

    )

# ============================================================

# Episode NFO

# ============================================================

def create_episode_nfo(

    tv_id,

    season_number,

    episode

):

    episode_number = episode.get(

        "episode_number",

        0

    )

    title = episode.get(

        "name",

        ""

    )

    overview = episode.get(

        "overview",

        ""

    )

    air_date = episode.get(

        "air_date",

        ""

    )

    episode_id = episode.get(

        "id",

        ""

    )

    runtime = episode.get(

        "runtime",

        ""

    )

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

    <runtime>{xml_escape(runtime)}</runtime>

    <uniqueid type="tmdb" default="true">{episode_id}</uniqueid>

    <showid>{tv_id}</showid>

</episodedetails>

"""

    return filename, nfo

# ============================================================

# 主程序

# ============================================================

def main():

    parser = argparse.ArgumentParser(

        description="TMDB -> Emby TV directory generator"

    )

    parser.add_argument(

        "tv",

        nargs="?",

        help="TMDB ID / URL / TV name"

    )

    parser.add_argument(

        "output",

        nargs="?",

        help="Output directory"

    )

    parser.add_argument(

        "--no-image",

        action="store_true",

        help="Do not download images"

    )

    args = parser.parse_args()

    print("=" * 70)

    print(

        " TMDB -> Emby 电视剧目录生成器"

    )

    print("=" * 70)

    # --------------------------------------------------------

    # Token

    # --------------------------------------------------------

    if not TMDB_TOKEN:

        print()

        print(

            "没有设置 TMDB_TOKEN。"

        )

        print()

        print(

            "执行："

        )

        print()

        print(

            'export TMDB_TOKEN="你的TMDB Read Access Token"'

        )

        print()

        sys.exit(1)

    # --------------------------------------------------------

    # 输入

    # --------------------------------------------------------

    if args.tv:

        tv_input = args.tv

    else:

        tv_input = input(

            "\n输入 TMDB 剧名 / TMDB ID / TMDB URL："

        ).strip()

    if args.output:

        output_dir = args.output

    else:

        output_dir = input(

            "输入保存目录，例如 /media/tv："

        ).strip()

    if not output_dir:

        print(

            "没有指定保存目录。"

        )

        sys.exit(1)

    # --------------------------------------------------------

    # 获取 TV ID

    # --------------------------------------------------------

    tv_id = get_tv_id(

        tv_input

    )

    print()

    print(

        f"TMDB ID: {tv_id}"

    )

    print(

        "正在获取电视剧信息..."

    )

    tv = api_get(

        f"{API}/tv/{tv_id}",

        {

            "language": LANGUAGE

        }

    )

    title = tv.get(

        "name",

        f"TV_{tv_id}"

    )

    safe_title = clean_name(

        title

    )

    print()

    print(

        "电视剧：",

        title

    )

    print(

        "原名：",

        tv.get("original_name")

    )

    print(

        "首播：",

        tv.get("first_air_date")

    )

    print(

        "状态：",

        tv.get("status")

    )

    print(

        "季数：",

        tv.get("number_of_seasons")

    )

    print(

        "集数：",

        tv.get("number_of_episodes")

    )

    print()

    # --------------------------------------------------------

    # 根目录

    # --------------------------------------------------------

    root = (

        Path(output_dir)

        / safe_title

    )

    root.mkdir(

        parents=True,

        exist_ok=True

    )

    print(

        "目录：",

        root

    )

    # --------------------------------------------------------

    # 保存 TMDB JSON

    # --------------------------------------------------------

    create_file(

        root / "tmdb.json",

        json.dumps(

            tv,

            ensure_ascii=False,

            indent=2

        )

    )

    # --------------------------------------------------------

    # TV NFO

    # --------------------------------------------------------

    create_tvshow_nfo(

        tv,

        root

    )

    # --------------------------------------------------------

    # TV 图片

    # --------------------------------------------------------

    if not args.no_image:

        download_tv_images(

            tv,

            root

        )

    # --------------------------------------------------------

    # Seasons

    # --------------------------------------------------------

    seasons = tv.get(

        "seasons",

        []

    )

    total_created = 0

    total_images = 0

    for season_info in seasons:

        season_number = season_info.get(

            "season_number",

            0

        )

        # 跳过 Special

        if season_number == 0:

            print(

                "\n跳过 Special / Season 00"

            )

            continue

        season_name = season_info.get(

            "name",

            f"Season {season_number:02d}"

        )

        season_dir = (

            root

            / f"Season {season_number:02d}"

        )

        season_dir.mkdir(

            parents=True,

            exist_ok=True

        )

        print()

        print("=" * 70)

        print(

            f"Season {season_number:02d} "

            f"{season_name}"

        )

        print("=" * 70)

        # ----------------------------------------------------

        # 获取季详细信息

        # ----------------------------------------------------

        season = api_get(

            f"{API}/tv/{tv_id}/season/{season_number}",

            {

                "language": LANGUAGE

            }

        )

        # ----------------------------------------------------

        # Season NFO

        # ----------------------------------------------------

        create_season_nfo(

            season,

            season_dir,

            tv_id

        )

        # ----------------------------------------------------

        # Season Poster

        # ----------------------------------------------------

        if not args.no_image:

            season_poster = season.get(

                "poster_path"

            )

            if download_image(

                season_poster,

                season_dir / "poster.jpg",

                "poster"

            ):

                total_images += 1

        # ----------------------------------------------------

        # Episodes

        # ----------------------------------------------------

        episodes = season.get(

            "episodes",

            []

        )

        print(

            f"发现 {len(episodes)} 集"

        )

        for ep in episodes:

            ep_num = ep.get(

                "episode_number",

                0

            )

            ep_title = ep.get(

                "name",

                f"Episode {ep_num}"

            )

            ep_title_clean = clean_name(

                ep_title

            )

            filename = (

                f"{safe_title} "

                f"S{season_number:02d}"

                f"E{ep_num:02d} "

                f"- {ep_title_clean}.mp4"

            )

            mp4 = (

                season_dir

                / filename

            )

            # ------------------------------------------------

            # MP4

            # ------------------------------------------------

            new_mp4 = make_fake_mp4(

                mp4

            )

            if new_mp4:

                total_created += 1

            # ------------------------------------------------

            # Episode NFO

            # ------------------------------------------------

            _, nfo_content = create_episode_nfo(

                tv_id,

                season_number,

                ep

            )

            nfo_path = (

                season_dir

                / (

                    Path(filename).stem

                    + ".nfo"

                )

            )

            create_file(

                nfo_path,

                nfo_content

            )

            # ------------------------------------------------

            # Episode still / thumb

            # ------------------------------------------------

            if not args.no_image:

                still = ep.get(

                    "still_path"

                )

                thumb_path = (

                    season_dir

                    / (

                        Path(filename).stem

                        + "-thumb.jpg"

                    )

                )

                if download_image(

                    still,

                    thumb_path,

                    "still"

                ):

                    total_images += 1

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

    print(

        "电视剧目录："

    )

    print(

        root

    )

    print()

    print(

        "新建 MP4：",

        total_created

    )

    if not args.no_image:

        print(

            "下载图片：",

            total_images

        )

    else:

        print(

            "图片下载：已关闭"

        )

    print()

    print(

        "Emby 可以扫描："

    )

    print(

        root

    )

    print()

if __name__ == "__main__":

    main()
