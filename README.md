# 🚀 Telegram Dev Bridge & AI Coding Agent

Kompyuteringiz yonida bo'lmaganingizda ham smartfoningizdagi Telegram orqali kompyuteringiz va loyihalaringizni masofadan to'liq boshqarish, fayllarni tahrirlash, terminal buyruqlarini bajarish, skrinshot olish va sun'iy intellekt (AI Agent) orqali kodlarni tekshirish va tuzatish tizimi.

---

## 🌟 Asosiy Imkoniyatlar

- 📁 **Fayllar Menejeri va Muharrir:**
  - Papkalar bo'ylab interaktiv inline tugmalar orqali kezish (`/ls`, `/files`, `/cd`);
  - Fayllarni syntax highlight bilan o'qish (`/view <fayl>`);
  - Fayllarni to'g'ridan-to'g'ri Telegramdan tahrirlash yoki yangi kod yozish (`/edit <fayl>`);
  - Yangi fayl va papkalar yaratish (`/create`, `/mkdir`), xavfsiz o'chirish (`/rm`);
  - Fayl almashinuvi: kompyuterdan telefonga yuklab olish (`/download <fayl>`) va telefondan Telegramga fayl tashlasangiz kompyuterga avtomatik saqlash;
  - Loyiha ichidan matn va kod qidirish (`/search <kod>`).

- 💻 **Masofaviy Terminal (PowerShell / CMD):**
  - Istalgan buyruqni asinxron bajarish (`/sh <buyruq>`, masalan: `/sh git status`, `/sh pytest`, `/sh npm test`);
  - Natijani chiroyli monospace blokda chiqarish (uzun natijalar `.txt` fayl qilib yuboriladi);
  - Tezkor tugmalar: `[Git Status]`, `[Git Pull]`, `[Git Diff]`, `[Pip List]`, `[Papka daraxti]`.

- 🤖 **Avtonom AI Coding Agent (Google Gemini):**
  - `/agent <vazifa>`: AI mustaqil ravishda fayllarni o'qiydi, xatolarni qidiradi, o'zgartirishlar kiritadi va terminalda tekshiradi (Tool Calling);
  - `/fix <fayl> [muammo]`: Fayldagi xatolikni aniqlab, uni avtomatik tuzatadi va saqlaydi;
  - `/explain <fayl>`: Kodning qanday ishlashini o'zbek tilida tushuntiradi;
  - `/review <fayl>`: Kodni xavfsizlik va tozalik (Clean Code) bo'yicha ko'rib chiqadi;
  - `/ai <savol>`: Dasturlash bo'yicha sun'iy intellekt bilan to'g'ridan-to'g'ri maslahat.

- 📊 **Kompyuter Monitoringi va Boshqaruv:**
  - `/status`: CPU %, RAM %, Disklardagi bo'sh joy, Uptime va Batareya holati;
  - `/screenshot`: Kompyuter monitorining ayni damdagi skrinshotini olib rasm ko'rinishida yuborish;
  - `/processes`: Eng ko'p resurs yeyotgan jarayonlar (Top RAM/CPU) va `/kill <pid>`;
  - `/lock`: Kompyuter ekranini masofadan bloklash (Windows Lock);
  - `/notify <matn>`: Kompyuter monitorida Windows bildirishnomasi (Toast) chiqarish.

- 🧹 **Telegram Hisobni Tozalash (Account Cleaner):**
  - **O'chib ketgan hisoblar:** "Deleted Account" bo'lib qolgan chatlarni aniqlab, bir bosishda tozalash (`/clean_deleted`);
  - **Faol bo'lmagan kanallar:** 60 kundan ortiq kirmagan yoki nofaol kanallar va guruhlardan avtomatik chiqish (`/clean_channels`);
  - **Eski dialoglar:** 90 kundan eski yozishmalarni aniqlash va o'chirish (`/clean_old`).


- 🛡️ **Yuqori Xavfsizlik (Whitelist Security):**
  - Faqatgina `.env` faylida ko'rsatilgan sizning Telegram User ID laringizga (`ADMIN_IDS`) ruxsat beriladi. Begona shaxslar botdan foydalana olmaydi.

---

## 🛠️ O'rnatish va Sozlash (Step-by-Step)

### 1-Qadam: Telegram Bot yaratish
1. Telegramda [@BotFather](https://t.me/BotFather) botini oching.
2. `/newbot` buyrug'ini yuboring.
3. Botingizga nom va username bering (masalan: `MyDevBridgeBot`).
4. BotFather sizga bergan **HTTP API Token**ni nusxalab oling.

### 2-Qadam: O'zingizning Telegram ID raqamingizni aniqlash
1. Telegramda [@userinfobot](https://t.me/userinfobot) yoki [@myidbot](https://t.me/myidbot) ga kiring va `/start` bosing.
2. Bot sizga ko'rsatgan **ID** raqamingizni nusxalab oling (masalan: `123456789`).

### 3-Qadam: (Ixtiyoriy) Bepul Gemini API Kalit olish
1. [Google AI Studio](https://aistudio.google.com/app/apikey) saytiga kiring.
2. **Create API key** tugmasini bosing va kalitni nusxalab oling.

### 4-Qadam: Konfiguratsiya (.env)
Loyihadagi `.env.example` faylidan nusxa olib `.env` faylini yarating yoki `setup.bat` ni ishga tushiring:

```env
# Telegram Bot Token
BOT_TOKEN=7123456789:AAFxExampleTokenStringHere

# Sizning Telegram User ID raqamingiz (agar bir nechta bo'lsa vergul bilan)
ADMIN_IDS=123456789

# AI API Kalit (Bepul Google Gemini)
GEMINI_API_KEY=AIzaSyExampleGeminiKeyHere

# Boshlang'ich ishchi katalog (bo'sh qoldirilsa joriy papka olinadi)
DEFAULT_WORKING_DIR=
```

---

## ⚡ Botni Ishga Tushirish

### Usul 1: Bitta bosishda (Windows)
Fayllar ichidagi `run.bat` faylini sichqoncha bilan ikki marta bosing.

### Usul 2: Terminal orqali
```bash
# 1. Kutubxonalarni o'rnatish
pip install -r requirements.txt

# 2. Botni ishga tushirish
python bot.py
```

Bot ishga tushganda Telegramingizga avtomatik ravishda bildirishnoma keladi:
`🟢 Telegram Dev Bridge ishga tushdi!`

---

## 📱 Telegramdan Foydalanish Qo'llanmasi

| Buyruq | Vazifasi |
|---|---|
| `/start` | Asosiy boshqaruv menyusini ochish |
| `/files` yoki `/ls` | Interaktiv fayl va papkalar brauzerini ko'rsatish |
| `/cd <papka>` | Boshqa papkaga o'tish (masalan: `/cd ..` yoki `/cd src`) |
| `/view <fayl>` | Fayl kodini syntax highlight bilan ko'rish |
| `/edit <fayl>` | Faylga yangi kod yozish |
| `/create <fayl>` | Yangi fayl yaratish |
| `/mkdir <papka>` | Yangi papka ochish |
| `/rm <yo'l>` | Fayl yoki papkani o'chirish (tasdiqlash bilan) |
| `/download <fayl>` | Faylni kompyuterdan telefonga yuklab olish |
| `/search <kod>` | Loyiha bo'ylab matn/kod qidirish |
| `/sh <buyruq>` | Terminal buyrug'ini bajarish (masalan: `/sh git status`) |
| `/agent <vazifa>` | Avtonom AI dasturchiga vazifa berish |
| `/fix <fayl>` | Koddagi xatolikni AI orqali avtomatik tuzatish |
| `/explain <fayl>` | Kod qanday ishlashini AI orqali tushuntirish |
| `/review <fayl>` | Code Review va tozalik tahlili |
| `/ai <savol>` | AI bilan to'g'ridan-to'g'ri suhbatlashish |
| `/status` | CPU, RAM, Disk, Batareya va Uptime ko'rsatkichlari |
| `/screenshot` | Kompyuter monitorining skrinshotini olish |
| `/processes` | Eng ko'p resurs olayotgan jarayonlar |
| `/kill <pid>` | Jarayonni to'xtatish |
| `/lock` | Kompyuter ekranini masofadan bloklash |
| `/notify <matn>` | Kompyuter monitorida bildirishnoma chiqarish |

---

## 🔒 Xavfsizlik bo'yicha maslahatlar
1. `.env` faylini hech qachon GitHub yoki ochiq internetga yuklamang (`.gitignore` ga kiritilgan).
2. `ADMIN_IDS` ga faqat o'zingiz ishonadigan Telegram hisobingiz ID sini kiriting.
3. Bot faqat shaxsiy serveringiz yoki ishchi kompyuteringizda fon rejimida ishlab turadi.
