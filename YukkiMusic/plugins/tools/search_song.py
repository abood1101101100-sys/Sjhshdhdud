#
# بحث / mp3 — يبحث في يوتيوب ويرسل النتيجة كملف MP3 مباشرة في المحادثة.
# مستقل تماماً عن نظام تشغيل المكالمات الصوتية (/تشغيل) — لا يدخل المكالمة،
# فقط يبحث، يحمّل، ويرفع الملف كصوت.
#
# الاستخدام:
#   بحث <اسم الأغنية>      → بحث نصي، يأخذ أول نتيجة
#   بحث <رابط يوتيوب>      → تحميل مباشر من الرابط
#   رد على رسالة فيها رابط + بحث  → تحميل الرابط المردود عليه
#

import asyncio
import os

import aiohttp
from PIL import Image
from pyrogram import filters
from pyrogram.types import Message

from config import BANNED_USERS, SONG_DOWNLOAD_DURATION, SONG_DOWNLOAD_DURATION_LIMIT
from strings import get_command
from YukkiMusic import YouTube, app
from YukkiMusic.utils.decorators import language
from YukkiMusic.utils.database import is_commanddelete_on
from YukkiMusic.utils.formatters import time_to_seconds

SEARCH_COMMAND = get_command("SEARCH_COMMAND")


async def _ensure_mp3(src_path: str, video_id: str) -> str:
    """
    يضمن أن الملف المُرسل MP3 حقيقي دائماً.
    تحميل ArtistBots API يرجع .mp3 بالفعل، لكن احتياط yt-dlp قد يرجع
    .m4a/.webm/.opus حسب الصيغة المتاحة — هذا يحوّله عبر ffmpeg ليظهر
    كملف صوتي صحيح في تيليجرام (بدل ملف عام/فيديو).
    """
    if src_path.lower().endswith(".mp3"):
        return src_path

    mp3_path = f"downloads/{video_id}.mp3"
    if os.path.isfile(mp3_path):
        return mp3_path

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", src_path,
        "-vn", "-acodec", "libmp3lame", "-b:a", "192k",
        mp3_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    if proc.returncode == 0 and os.path.isfile(mp3_path):
        return mp3_path
    return src_path  # فشل التحويل: أرسل الملف الأصلي كما هو كحل أخير


async def _download_thumb(url: str, video_id: str) -> str | None:
    """تحميل الصورة المصغرة وتصغيرها لتناسب حدود تيليجرام (320x320 وأقل من 200kb)."""
    if not url:
        return None
    raw_path = f"downloads/thumb_{video_id}_raw.jpg"
    out_path = f"downloads/thumb_{video_id}.jpg"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                with open(raw_path, "wb") as f:
                    f.write(await resp.read())
        with Image.open(raw_path) as img:
            img = img.convert("RGB")
            img.thumbnail((320, 320))
            img.save(out_path, "JPEG", quality=85, optimize=True)
        return out_path
    except Exception:
        return None
    finally:
        if os.path.isfile(raw_path):
            try:
                os.remove(raw_path)
            except OSError:
                pass


@app.on_message(
    filters.command(SEARCH_COMMAND)
    & filters.group
    & ~BANNED_USERS
)
@language
async def search_and_send_mp3(client, message: Message, _):
    if await is_commanddelete_on(message.chat.id):
        try:
            await message.delete()
        except Exception:
            pass

    url = await YouTube.url(message)
    if url:
        if not await YouTube.exists(url):
            return await message.reply_text(_["song_5"])
        query = url
    elif len(message.command) > 1:
        query = message.text.split(None, 1)[1]
    else:
        return await message.reply_text(
            "**مثال:**\n\n`بحث اسم الأغنية`\nأو رد على رابط يوتيوب وأرسل `بحث`"
        )

    status = await message.reply_text(_["play_1"])

    try:
        details, vidid = await YouTube.track(query)
    except Exception:
        return await status.edit_text(_["song_7"])

    duration_min = details.get("duration_min")
    if str(duration_min) == "None":
        return await status.edit_text(_["song_3"])

    duration_sec = int(time_to_seconds(duration_min))
    if duration_sec > SONG_DOWNLOAD_DURATION_LIMIT:
        return await status.edit_text(
            _["play_6"].format(SONG_DOWNLOAD_DURATION, duration_min)
        )

    await status.edit_text(_["song_8"])
    try:
        file_path, _ok = await YouTube.download(vidid, status, videoid=True)
    except Exception as e:
        return await status.edit_text(_["song_9"].format(e))

    if not file_path or not os.path.isfile(file_path):
        return await status.edit_text(_["song_9"].format("empty result"))

    file_path = await _ensure_mp3(file_path, vidid)
    thumb_path = await _download_thumb(details.get("thumb"), vidid)

    await status.edit_text(_["song_11"])
    try:
        await app.send_chat_action(message.chat.id, "upload_audio")
        await message.reply_audio(
            file_path,
            title=details["title"],
            performer="YouTube",
            duration=duration_sec,
            thumb=thumb_path,
            caption=f"🎵 {details['title']}",
        )
    except Exception as e:
        if thumb_path:
            try:
                await message.reply_audio(
                    file_path,
                    title=details["title"],
                    performer="YouTube",
                    duration=duration_sec,
                    caption=f"🎵 {details['title']}",
                )
            except Exception:
                return await status.edit_text(_["song_10"])
        else:
            print(f"[SearchMp3] ❌ فشل رفع الملف لـ {vidid}: {e}")
            return await status.edit_text(_["song_10"])
    finally:
        if thumb_path and os.path.isfile(thumb_path):
            try:
                os.remove(thumb_path)
            except OSError:
                pass

    try:
        await status.delete()
    except Exception:
        pass
