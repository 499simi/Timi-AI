# Timi AI (Fase 1 + 2 + 3 + 4)

Satu entry point: **`Timi Py.py`** — chat Gemini, screenshot+OCR, aksi Windows aman, MBTI dinamis, sprite berjalan, plus voice/scheduler/scan.

## Quick start

1) Install dependency:

```bash
pip install -r requirements.txt
```

2) Install Tesseract OCR (Windows): [UB Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) — default `C:\Program Files\Tesseract-OCR`

3) Set API key Gemini:

```powershell
$env:GEMINI_API_KEY="API_KEY_KAMU"
```

4) (Opsional) Telegram — environment variable:

```powershell
$env:TELEGRAM_TOKEN="bot_token_dari_botfather"
$env:TELEGRAM_CHAT_ID="id_chat_kamu"
```

5) Cek API:

```bash
python "Timi Py.py" --check-api
```

6) Self-test:

```bash
python "Timi Py.py" --self-test
```

7) Jalankan aplikasi:

```bash
python "Timi Py.py"
```

## Fitur ringkas

| Fase | Isi |
|------|-----|
| **1** | Widget always-on-top, draggable, chat, screenshot + OCR |
| **2** | `TIMI_ACTION:` buka folder/app, `JALANKAN_CMD` (konfirmasi UI), `TELEGRAM`, blacklist perintah berbahaya |
| **3** | MBTI (ENTP, ENFJ, ISTP, INFP, ENTJ): bar mode + ganti manual, analisis otomatis tiap **8 pesan** chat, `TIMI_ACTION:GANTI_MBTI:XXXX` (tanpa konfirmasi), sprite Shimeji + tombol **🐾 / 💤** |
| **4** | Voice input (`🎙️`), TTS output, action jadwal `TIMI_ACTION:JADWAL:HH:MM:pesan:Y/N`, action `TOGGLE_TTS`, tombol scan `🛡️` (startup/temp suspicious scan) |

Model: `gemini-2.5-flash` via `google-genai`.

## Troubleshooting

| Masalah | Tindakan |
|---------|----------|
| `GEMINI_API_KEY belum di-set` | Set `$env:GEMINI_API_KEY` lalu jalankan ulang |
| `429` / quota | Cek kuota & billing di Google AI Studio |
| `503` / high demand | Coba lagi setelah beberapa menit |
| Voice tidak aktif | Pastikan mic aktif & `SpeechRecognition` terinstall |
| TTS tidak bersuara | Cek `pyttsx3` (offline) atau `gTTS+playsound` (online) |
| Scheduler tidak jalan | Pastikan package `schedule` terinstall |
| Scan antivirus tidak jalan | Fitur registry butuh Windows (`winreg`) |
| Sprite tidak transparan | Windows + tema tertentu bisa mempengaruhi `-transparentcolor` |
| `TesseractNotFoundError` | Sesuaikan `pytesseract.pytesseract.tesseract_cmd` di `Timi Py.py` |
| `ModuleNotFoundError` | `pip install -r requirements.txt` |

## Catatan

- Jangan commit API key ke repo; pakai environment variable.
- File eksperimen fase lama sudah digabung ke `Timi Py.py` agar tidak duplikat.

## Dependencies

Lihat `requirements.txt` (stdlib `json` / `random` tidak perlu di-install).
