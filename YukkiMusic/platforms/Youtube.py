#
# Copyright (C) 2021-2022 by TeamYukki@Github, < https://github.com/TeamYukki >.
# ArtistBots API integration added for faster downloads.
#
# All rights reserved.

import asyncio
import glob
import os
import re
from typing import Optional, Union

import aiohttp
import yt_dlp
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

import config
from YukkiMusic.utils.database import is_on_off
from YukkiMusic.utils.formatters import time_to_seconds

# ── regex to pull bare 11-char video ID from any YouTube URL ──────────────────
_YT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
# ── how many bytes to read per chunk when streaming the API response ──────────
_CHUNK = 128 * 1024


def _extract_video_id(link: str) -> str:
    """Return the bare 11-char YouTube video ID from a URL or bare ID."""
    s = (link or "").strip()
    if _YT_ID_RE.match(s):
        return s
    if "v=" in s:
        return s.split("v=")[-1].split("&")[0]
    last = s.split("/")[-1].split("?")[0]
    if _YT_ID_RE.match(last):
        return last
    return ""


async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

        # ── ArtistBots key rotation ───────────────────────────────────────────
        self._api_key_index = 0
        self._api_key_lock = asyncio.Lock()

        # ── shared aiohttp session ────────────────────────────────────────────
        self._api_session: Optional[aiohttp.ClientSession] = None
        self._api_session_lock = asyncio.Lock()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _use_audio_api(self) -> bool:
        return bool(getattr(config, "API_URL", "") and getattr(config, "API_KEYS", []))

    def _use_video_api(self) -> bool:
        return bool(getattr(config, "VIDEO_API_URL", "") and getattr(config, "API_KEYS", []))

    async def _next_api_key(self) -> Optional[str]:
        """Round-robin across config.API_KEYS so quota is spread evenly."""
        keys = getattr(config, "API_KEYS", [])
        if not keys:
            return None
        async with self._api_key_lock:
            key = keys[self._api_key_index % len(keys)]
            self._api_key_index = (self._api_key_index + 1) % len(keys)
            return key

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._api_session and not self._api_session.closed:
            return self._api_session
        async with self._api_session_lock:
            if self._api_session and not self._api_session.closed:
                return self._api_session
            timeout = aiohttp.ClientTimeout(total=600, sock_connect=20, sock_read=60)
            connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300, enable_cleanup_closed=True)
            self._api_session = aiohttp.ClientSession(timeout=timeout, connector=connector)
            return self._api_session

    async def _artistbots_download(self, video_id: str, base_url: str, video: bool) -> Optional[str]:
        """
        تحميل الصوت أو الفيديو عبر ArtistBots API.
        GET {base_url}/download?url={video_id}&type={audio|video}&api_key={key}
        يُشغّل key rotation تلقائياً بين كل المفاتيح في config.API_KEYS.
        """
        api_key = await self._next_api_key()
        if not api_key or not base_url:
            return None

        dl_type = "video" if video else "audio"
        ext = ".mp4" if video else ".mp3"
        out_path = f"downloads/{video_id}{ext}"

        os.makedirs("downloads", exist_ok=True)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path  # مخزّن مسبقاً

        params = {"url": video_id, "type": dl_type, "api_key": api_key}
        masked = api_key[:8] + "..." if len(api_key) > 8 else "***"

        try:
            session = await self._get_session()
            endpoint = f"{base_url.rstrip('/')}/download"
            async with session.get(
                endpoint,
                params=params,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status != 200:
                    print(f"[ArtistBots] ⚠️ HTTP {resp.status} لـ {video_id} (مفتاح {masked})")
                    return None
                with open(out_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(_CHUNK):
                        if chunk:
                            f.write(chunk)

            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                print(f"[ArtistBots] ✅ {dl_type} تم تحميله عبر API: {video_id}")
                return out_path

            if os.path.exists(out_path):
                os.remove(out_path)
            return None

        except asyncio.TimeoutError:
            print(f"[ArtistBots] ⏰ انتهى الوقت لـ {video_id}")
            return None
        except Exception as e:
            print(f"[ArtistBots] ❌ خطأ لـ {video_id}: {e}")
            return None

    # ── دوال الواجهة الأصلية ───────────────────────────────────────────────────

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == "url":
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == "text_link":
                        return entity.url
        if offset in (None,):
            return None
        return text[offset: offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "-g", "-f", "best[height<=?720][width<=?1280]", f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        # ── song_video / song_audio (تحميل صيغة محددة) — يبقى yt-dlp ─────────
        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            yt_dlp.YoutubeDL(ydl_optssx).download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            yt_dlp.YoutubeDL(ydl_optssx).download([link])

        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            return f"downloads/{title}.mp4"
        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            return f"downloads/{title}.mp3"

        # ── تشغيل فيديو في المكالمة ───────────────────────────────────────────
        elif video:
            if await is_on_off(config.YTDOWNLOADER):
                # 1️⃣ جرّب ArtistBots API أولاً
                vid_id = _extract_video_id(link)
                if vid_id and self._use_video_api():
                    api_result = await self._artistbots_download(
                        vid_id, config.VIDEO_API_URL, video=True
                    )
                    if api_result:
                        return api_result, True

                # 2️⃣ Fallback: yt-dlp
                def video_dl():
                    ydl_optssx = {
                        "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                        "outtmpl": "downloads/%(id)s.%(ext)s",
                        "geo_bypass": True,
                        "nocheckcertificate": True,
                        "quiet": True,
                        "no_warnings": True,
                    }
                    x = yt_dlp.YoutubeDL(ydl_optssx)
                    info = x.extract_info(link, False)
                    xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                    if os.path.exists(xyz):
                        return xyz
                    x.download([link])
                    return xyz

                downloaded_file = await loop.run_in_executor(None, video_dl)
                return downloaded_file, True
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp", "-g", "-f", "best[height<=?720][width<=?1280]", f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    return stdout.decode().split("\n")[0], None
                else:
                    return

        # ── تشغيل صوت في المكالمة ─────────────────────────────────────────────
        else:
            # 1️⃣ جرّب ArtistBots API أولاً
            vid_id = _extract_video_id(link)
            if vid_id and self._use_audio_api():
                api_result = await self._artistbots_download(
                    vid_id, config.API_URL, video=False
                )
                if api_result:
                    return api_result, True

            # 2️⃣ Fallback: yt-dlp
            def audio_dl():
                ydl_optssx = {
                    "format": "bestaudio/best",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "geo_bypass": True,
                    "nocheckcertificate": True,
                    "quiet": True,
                    "no_warnings": True,
                }
                x = yt_dlp.YoutubeDL(ydl_optssx)
                info = x.extract_info(link, False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz):
                    return xyz
                x.download([link])
                return xyz

            downloaded_file = await loop.run_in_executor(None, audio_dl)
            return downloaded_file, True
