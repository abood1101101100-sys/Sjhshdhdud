# 🚀 دليل نشر البوت على Railway

## المتطلبات قبل البدء
- حساب على [railway.app](https://railway.app)
- حساب GitHub (لرفع الكود)
- المتغيرات الضرورية (API_ID, BOT_TOKEN, إلخ)

---

## الخطوة 1 — رفع الكود على GitHub

1. افتح [github.com/new](https://github.com/new)
2. أنشئ repository جديد (مثلاً `yukki-music-bot`) — اجعله **Private**
3. ارفع ملفات البوت:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/USERNAME/REPO_NAME.git
git push -u origin main
```

---

## الخطوة 2 — إنشاء مشروع على Railway

1. اذهب إلى [railway.app](https://railway.app) وسجّل دخول
2. اضغط **New Project**
3. اختر **Deploy from GitHub repo**
4. اربط حساب GitHub وانتقِ الـ repository

---

## الخطوة 3 — إضافة المتغيرات (Variables)

اضغط على المشروع ← **Variables** ← **Add Variable** وأضف:

| المتغير | القيمة | من أين تحصل عليه |
|---------|--------|-----------------|
| `API_ID` | رقم | [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | نص | [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | نص | [@BotFather](https://t.me/BotFather) |
| `MONGO_DB_URI` | رابط MongoDB | [mongodb.com](https://mongodb.com) |
| `LOG_GROUP_ID` | رقم المجموعة (سالب) | ID مجموعة السجلات |
| `OWNER_ID` | رقم حسابك | [@userinfobot](https://t.me/userinfobot) |
| `MUSIC_BOT_NAME` | اسم البوت | اختر أي اسم |
| `STRING_SESSION` | الـ session | [@YukkiStringBot](https://t.me/YukkiStringBot) |
| `API_URL` | رابط ArtistBots | من ArtistBots |
| `VIDEO_API_URL` | نفس API_URL | من ArtistBots |
| `API_KEYS` | مفاتيح مفصولة بفاصلة | من ArtistBots |

---

## الخطوة 4 — تشغيل البوت

1. بعد إضافة المتغيرات، اضغط **Deploy**
2. راقب الـ **Logs** للتأكد من عدم وجود أخطاء
3. يجب أن تظهر رسالة `MusicBot Started as ...` في السجلات

---

## ⚠️ ملاحظات مهمة

- **Railway Free Plan**: يعطيك 500 ساعة شهرياً (يكفي لبوت واحد)
- **المجموعة LOG_GROUP_ID**: يجب أن تضيف البوت كمشرف فيها أولاً
- **STRING_SESSION**: مطلوب لحساب مساعد يدخل المكالمات الصوتية
- إذا ظهر خطأ `ffmpeg not found` → الـ Dockerfile سيحله تلقائياً

---

## استكشاف الأخطاء

| الخطأ | الحل |
|-------|------|
| `API_ID must be integer` | تأكد أن API_ID أرقام فقط |
| `MongoDB connection failed` | تحقق من MONGO_DB_URI |
| `Bot failed to access log group` | أضف البوت مشرفاً في LOG group |
| `Invalid bot token` | تأكد من BOT_TOKEN من @BotFather |
