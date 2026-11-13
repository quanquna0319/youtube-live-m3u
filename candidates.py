# -*- coding: utf-8 -*-
"""候选频道池：名称 | 分类 | 直播地址

用 @handle 形式而非手写 channel id，避免 ID 写错导致 404。
真实存活情况由 build.py 实测决定，不在线的自动剔除。

注意：YouTube 直播是"事件型"的，任何频道都可能临时下播。
想长期稳定，请用 run_daemon.py 定时刷新；想加自己的频道，直接往这里加一行。
"""

CANDIDATES = [
    # ---------- 新闻 ----------
    ("NBC News NOW", "新闻", "https://www.youtube.com/@NBCNews/live"),
    ("ABC News Live", "新闻", "https://www.youtube.com/@ABCNews/live"),
    ("CBS News 24/7", "新闻", "https://www.youtube.com/@cbsnews/live"),
    ("Al Jazeera English", "新闻", "https://www.youtube.com/@aljazeeraenglish/live"),
    ("DW News", "新闻", "https://www.youtube.com/@dwnews/live"),
    ("Sky News", "新闻", "https://www.youtube.com/@SkyNews/live"),
    ("Euronews", "新闻", "https://www.youtube.com/@euronews/live"),
    ("TRT World", "新闻", "https://www.youtube.com/@trtworld/live"),
    ("CNA", "新闻", "https://www.youtube.com/@channelnewsasia/live"),
    ("Reuters", "新闻", "https://www.youtube.com/@Reuters/live"),
    ("India Today", "新闻", "https://www.youtube.com/@IndiaToday/live"),
    ("WION", "新闻", "https://www.youtube.com/@WION/live"),
    ("Times of India", "新闻", "https://www.youtube.com/@TimesofIndia/live"),
    ("Republic World", "新闻", "https://www.youtube.com/@RepublicWorld/live"),
    ("Firstpost", "新闻", "https://www.youtube.com/@Firstpost/live"),
    ("Al Arabiya", "新闻", "https://www.youtube.com/@AlArabiya/live"),
    ("Sky News Arabia", "新闻", "https://www.youtube.com/@SkyNewsArabia/live"),

    # ---------- 财经 ----------
    ("CNBC Television", "财经", "https://www.youtube.com/@cnbc/live"),
    ("Yahoo Finance", "财经", "https://www.youtube.com/@YahooFinance/live"),
    ("The Economic Times", "财经", "https://www.youtube.com/@TheEconomicTimes/live"),
    ("NDTV Profit", "财经", "https://www.youtube.com/@NDTVProfit/live"),

    # ---------- 科技 ----------
    ("NASA Live", "科技", "https://www.youtube.com/@NASA/live"),
    ("SpaceX", "科技", "https://www.youtube.com/@SpaceX/live"),

    # ---------- 体育 ----------
    ("UFC", "体育", "https://www.youtube.com/@UFC/live"),
    ("WWE", "体育", "https://www.youtube.com/@WWE/live"),
    ("talkSPORT", "体育", "https://www.youtube.com/@talkSPORT/live"),
    ("NBA", "体育", "https://www.youtube.com/@NBA/live"),
    ("NFL", "体育", "https://www.youtube.com/@NFL/live"),
    ("FIFA", "体育", "https://www.youtube.com/@FIFA/live"),
    ("Red Bull", "体育", "https://www.youtube.com/@redbull/live"),
    ("Formula 1", "体育", "https://www.youtube.com/@Formula1/live"),
    ("ESL", "体育", "https://www.youtube.com/@ESL/live"),

    # ---------- 音乐 ----------
    ("Lofi Girl", "音乐", "https://www.youtube.com/@LofiGirl/live"),
    ("Chillhop Music", "音乐", "https://www.youtube.com/@ChillhopMusic/live"),
    ("Trap Nation", "音乐", "https://www.youtube.com/@TrapNation/live"),
    ("Monstercat", "音乐", "https://www.youtube.com/@Monstercat/live"),
    ("MrSuicideSheep", "音乐", "https://www.youtube.com/@MrSuicideSheep/live"),

    # ---------- 纪录 ----------
    ("Discovery", "纪录", "https://www.youtube.com/@discovery/live"),
    ("Science Channel", "纪录", "https://www.youtube.com/@ScienceChannel/live"),
    ("National Geographic", "纪录", "https://www.youtube.com/@NatGeo/live"),
    ("DW Documentary", "纪录", "https://www.youtube.com/@DWDocumentary/live"),

    # ---------- 少儿 ----------
    ("Booba", "少儿", "https://www.youtube.com/@Booba/live"),
    ("Cocomelon", "少儿", "https://www.youtube.com/@CoComelon/live"),
    ("Baby Shark", "少儿", "https://www.youtube.com/@BabyShark/live"),
    ("Kids Diana Show", "少儿", "https://www.youtube.com/@KidsDianaShow/live"),
    ("Like Nastya", "少儿", "https://www.youtube.com/@LikeNastyaofficial/live"),

    # ---------- 生活 ----------
    ("EarthCam", "生活", "https://www.youtube.com/@EarthCam/live"),
    ("Skyline Webcams", "生活", "https://www.youtube.com/@SkylineWebcams/live"),
    ("FOX Weather", "生活", "https://www.youtube.com/@FoxWeather/live"),
]
