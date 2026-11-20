# Zukko — O‘zbekcha AI repetitor

Telegram boti matn yoki ovozdagi savolni sinf, fan va mavzuga ajratadi; qisqa Feynman uslubidagi dars, O‘zbekcha mini-podkast va xato tushunchani aniqlovchi uch savolli test beradi. O‘nta mavzu ilova ichida tayyor bo‘lib, Gemini javob bermaganda ham ishlaydi.

## Ishga tushirish

Python 3.11+ o‘rnating. Ishchi papkada:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

Tayyor `.env` fayliga BotFather bergan `BOT_TOKEN` va Google AI Studio bergan `GEMINI_API_KEY` ni kiriting. Kalitlarni repozitoriyga joylamang. So‘ng:

```powershell
.venv\Scripts\python -m zukko
```

## Web ilova

Web ilova Telegram tokenisiz ham mahalliy ishlaydi:

```powershell
.venv\Scripts\python -m zukko.web
```

Brauzerda `http://127.0.0.1:8000` ni oching. Tayyor 10 mavzu, matnli savol, audio dars va uch bosqichli diagnostik test ishlaydi. Mikrofonli savol va tayyor mavzulardan tashqari AI dars uchun `.env` dagi `GEMINI_API_KEY` zarur. Mikrofon brauzer ruxsatini talab qiladi; localhost brauzerlarda xavfsiz kontekst hisoblanadi.

### Asosiy imkoniyatlar:
- **O‘quv monitoringi va statistika (`/api/analytics`):** Jami yechilgan testlar, aniqlik foizi va mavzular bo‘yicha o‘zlashtirish tahlili.
- **Fanlar bo‘yicha filtr va tezkor qidiruv:** Matematika, Fizika, Kimyo, Biologiya va Ona tili mavzularini alohida saralash.
- **Konspekt yuklab olish (`/api/summary/{id}`):** Har bir darsning Feynman strukturasidagi konspektini Markdown fayl sifatida saqlash.
- **Audio boshqaruvi:** 1.0x, 1.25x va 1.5x ijro tezliklari.
- **Interaktiv audio & vizual rag‘bat:** Web Audio API chimes va 3/3 natijada konfetti effekti.

Web ilova rasmlari, ikonlari va shriftlari lokal saqlanadi. Generatsiya promptlari va font litsenziyalari [ASSETS.md](ASSETS.md) da.

10 ta tayyor mavzuning audiosi loyiha ichida birga keladi. Matn yoki ovoz o‘zgartirilsa, internet bor paytda yangi audio keshini yaratish mumkin:

```powershell
.venv\Scripts\python scripts/prewarm_audio.py
```

`GEMINI_API_KEY` bo‘lmasa, 10 ta offline mavzu bo‘yicha matnli dars va test ishlaydi. Ovozli xabarni matnga aylantirish va boshqa mavzularga javob berish Gemini ulanishini talab qiladi. `edge-tts` tarmoq xizmatiga ulanadi; audio chiqmasa matn va test davom etadi. Telegram boti ham Telegram tarmog‘isiz xabar qabul qila olmaydi. Offline fallback deganda Gemini API uzilganda ilova ichidagi darsni ishlatish nazarda tutiladi.

Maqsad hujjatida `gemini-1.5-flash` ko‘rsatilgan. U xizmatdan olingani uchun standart `gemini-3.8-flash`; kerak bo‘lsa `.env` dagi `GEMINI_MODEL` bilan o‘zgartiring.

Botga `/start` yozing, so‘ng `8-sinfman, kvadrat ildizni tushunmayapman` yoki ovozli xabar yuboring. `/topics` tayyor mavzularni ko‘rsatadi. Uch savolga inline tugmalar orqali javob beriladi.

## Tekshiruv

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m ruff check .
```

`data/zukko.db` da test javoblari saqlanadi. `data/audio_cache` da bir marta yaratilgan audio qayta ishlatiladi. Ilova bitta jarayonga mo‘ljallangan; test holati xotirada saqlanadi va restartdan keyin yangi dars boshlash kerak.
Uch savol oxirida to‘g‘ri javoblar soni va qayta ko‘riladigan birinchi xato tushuncha ko‘rsatiladi. Web dars sessiyasi bir soatdan keyin tugaydi; tugallanmagan sessiyalar soni cheklangan.

## Muhim cheklovlar

35 son va 0.8 soniya qiymatlari kafolatlanmaydi: nutq uzunligi, tarmoq va Edge TTS javobiga bog‘liq. Oldindan yaratilgan audio qayta yuborilganda tezroq bo‘ladi. Ovozli xabarni tanish uchun Gemini API ishlaydi; faqat lokal offline bazaning o‘zi ovozni tanimaydi.
