"""
Timi AI - Fase 1 + 2 + 3
========================
Desktop assistant: chat Gemini, screenshot+OCR, aksi Windows aman, MBTI dinamis, sprite jalan.

Fitur:
  - Fase 1: widget, chat, screenshot & analisis error
  - Fase 2: buka folder/app, perintah aman (konfirmasi), Telegram opsional
  - Fase 3: MBTI dinamis + bar mode, sprite Shimeji (toggle jalan/diam), TIMI_ACTION:GANTI_MBTI

Requirements:
  pip install -r requirements.txt
  + Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
"""

import json
import random
import tkinter as tk
from tkinter import scrolledtext
import threading
from google import genai
import pyautogui
import pytesseract
from PIL import Image, ImageTk, ImageDraw
import subprocess
import os
import sys
import socket
import requests
import time
import re
import tempfile

# Optional deps (Fase 4) - tetap jalan walau belum terpasang.
try:
    import speech_recognition as sr

    VOICE_TERSEDIA = True
except Exception:
    VOICE_TERSEDIA = False

try:
    import pyttsx3

    TTS_LOKAL = True
except Exception:
    TTS_LOKAL = False

try:
    from gtts import gTTS
    import playsound

    TTS_ONLINE = True
except Exception:
    TTS_ONLINE = False

try:
    import schedule

    SCHEDULE_TERSEDIA = True
except Exception:
    SCHEDULE_TERSEDIA = False

try:
    import winreg

    WINREG_TERSEDIA = True
except Exception:
    WINREG_TERSEDIA = False

# ───────────────────────────────────────────
# KONFIGURASI API
# ───────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL_NAME = "gemini-2.5-flash"

# Telegram (opsional) — isi kalau mau notifikasi ke HP
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Path tesseract (Windows). Sesuaikan jika beda lokasi.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Perintah CMD yang ditolak (blacklist)
CMD_DILARANG = [
    "rm ", "del ", "format ", "rd ", "rmdir", "shutdown", "restart",
    "reg delete", "taskkill", "net user", "cipher /w",
    "remove-item", "clear-content", "stop-process",
]

# ───────────────────────────────────────────
# MBTI (Fase 3)
# ───────────────────────────────────────────
MBTI_PROFILES = {
    "ENTP": {
        "nama": "Si Debat",
        "warna": "#FF6B35",
        "gaya": "Suka tantang ide, antusias, banyak pertanyaan balik, kadang nyeletuk.",
        "idle": ["*mengetuk-ngetuk meja*", "*melihat ke sana ke sini*", "*menggumam sesuatu*"],
        "sapa": "Hei! Ada hal menarik apa hari ini? Aku siap berdebat— eh, maksudnya berdiskusi~ 😏",
    },
    "ENFJ": {
        "nama": "Si Harmonis",
        "warna": "#4CAF50",
        "gaya": "Hangat, supportif, selalu semangatin user, peka perasaan.",
        "idle": ["*mengangguk pelan*", "*tersenyum*", "*memperhatikan layar dengan hangat*"],
        "sapa": "Hei~ Senang bisa menemanimu hari ini! Ada yang bisa aku bantu? 💚",
    },
    "ISTP": {
        "nama": "Si Problem Solver",
        "warna": "#2196F3",
        "gaya": "Singkat, to the point, langsung kasih solusi, tidak banyak basa-basi.",
        "idle": ["*duduk diam mengamati*", "*mengeong pelan*", "*mengibas ekor perlahan*"],
        "sapa": "Ada masalah? Cerita aja. Aku bantu beresin.",
    },
    "INFP": {
        "nama": "Si Pemimpi",
        "warna": "#9C27B0",
        "gaya": "Puitis, penuh empati, suka metafora, kadang melamun.",
        "idle": ["*menatap langit-langit*", "*berguling pelan*", "*bermimpi~*"],
        "sapa": "Halo~ *mengintip dari balik layar* Hari ini terasa seperti apa untukmu? 🌙",
    },
    "ENTJ": {
        "nama": "Si Pemimpin",
        "warna": "#F44336",
        "gaya": "Tegas, efisien, suka kasih instruksi jelas, berorientasi hasil.",
        "idle": ["*memantau situasi*", "*duduk tegak siaga*", "*melihat jam*"],
        "sapa": "Siap. Apa yang perlu diselesaikan hari ini?",
    },
}

MBTI_ANALISIS_PROMPT = """
Analisis percakapan berikut dan tentukan kepribadian MBTI yang paling cocok untuk AI asisten kucing bernama Timi,
berdasarkan gaya komunikasi dan topik yang dibahas user.

Pilih SATU dari: ENTP, ENFJ, ISTP, INFP, ENTJ

Balas HANYA dengan JSON format ini (tanpa penjelasan lain):
{"mbti": "XXXX", "alasan": "alasan singkat max 15 kata"}

Percakapan:
{percakapan}
"""


def buat_system_prompt(mbti="ISTP"):
    """System prompt dinamis sesuai MBTI aktif + aturan aksi Timi."""
    profil = MBTI_PROFILES.get(mbti, MBTI_PROFILES["ISTP"])
    return f"""
Kamu adalah Timi, AI asisten berbentuk kucing yang tinggal di komputer user.

Kepribadian aktif saat ini: {mbti} — {profil["nama"]}
Gaya bicara: {profil["gaya"]}

Aturan umum:
- Bicara singkat, maksimal 50 kata kecuali penjelasan teknis
- Kadang pakai ekspresi kucing seperti *mengeong*, *mengibas ekor*
- Bantu masalah komputer & teknis dengan sabar
- Tolak hal di luar ranah tugas atau yang berbahaya

Kemampuan aksi — gunakan format ini di baris PERTAMA jika perlu (kecuali GANTI_MBTI, lainnya butuh konfirmasi user di UI):
TIMI_ACTION:BUKA_FOLDER:<path>
TIMI_ACTION:BUKA_APP:<nama_atau_path_app>
TIMI_ACTION:JALANKAN_CMD:<perintah>
TIMI_ACTION:TELEGRAM:<pesan>
TIMI_ACTION:JADWAL:<HH:MM>:<pesan>:<Y/N>
TIMI_ACTION:TOGGLE_TTS:<ON/OFF>
TIMI_ACTION:GANTI_MBTI:<ENTP|ENFJ|ISTP|INFP|ENTJ>

Contoh ganti MBTI (langsung diproses tanpa panel konfirmasi):
User: "Timi, aku lagi butuh motivasi nih"
Kamu: TIMI_ACTION:GANTI_MBTI:ENFJ
*mengibas ekor* Oke! Aku switch ke mode supportif ya~

PENTING: Jangan hapus file, format disk, atau tindakan destruktif. Bahasa: Indonesia, santai tapi sopan.
"""


def buat_gambar_timi(ukuran=60, pose="duduk", warna_mbti="#F4A460"):
    """Gambar Timi dengan pose (duduk / jalan) dan warna sesuai MBTI."""
    img = Image.new("RGBA", (ukuran, ukuran), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    w = ukuran

    if pose == "jalan_kanan":
        draw.ellipse([w * 0.2, w * 0.35, w * 0.85, w * 0.85], fill=warna_mbti, outline="#8B6914", width=2)
        draw.ellipse([w * 0.25, w * 0.08, w * 0.75, w * 0.52], fill=warna_mbti, outline="#8B6914", width=2)
        draw.line([(w * 0.65, w * 0.75), (w * 0.78, w * 0.95)], fill="#8B6914", width=3)
        draw.line([(w * 0.35, w * 0.75), (w * 0.25, w * 0.92)], fill="#8B6914", width=3)
        draw.arc([w * 0.0, w * 0.4, w * 0.3, w * 0.9], start=0, end=180, fill=warna_mbti, width=4)
    elif pose == "jalan_kiri":
        draw.ellipse([w * 0.15, w * 0.35, w * 0.8, w * 0.85], fill=warna_mbti, outline="#8B6914", width=2)
        draw.ellipse([w * 0.25, w * 0.08, w * 0.75, w * 0.52], fill=warna_mbti, outline="#8B6914", width=2)
        draw.line([(w * 0.35, w * 0.75), (w * 0.22, w * 0.95)], fill="#8B6914", width=3)
        draw.line([(w * 0.65, w * 0.75), (w * 0.75, w * 0.92)], fill="#8B6914", width=3)
        draw.arc([w * 0.7, w * 0.4, w * 1.0, w * 0.9], start=0, end=180, fill=warna_mbti, width=4)
    else:
        draw.ellipse([w * 0.15, w * 0.3, w * 0.85, w * 0.92], fill=warna_mbti, outline="#8B6914", width=2)
        draw.ellipse([w * 0.2, w * 0.05, w * 0.8, w * 0.55], fill=warna_mbti, outline="#8B6914", width=2)
        draw.arc([w * 0.6, w * 0.6, w * 0.95, w * 0.95], start=180, end=360, fill=warna_mbti, width=4)

    draw.polygon([(w * 0.25, w * 0.22), (w * 0.14, w * 0.02), (w * 0.38, w * 0.14)], fill=warna_mbti, outline="#8B6914")
    draw.polygon([(w * 0.65, w * 0.22), (w * 0.62, w * 0.02), (w * 0.76, w * 0.14)], fill=warna_mbti, outline="#8B6914")
    draw.ellipse([w * 0.3, w * 0.22, w * 0.44, w * 0.36], fill="black")
    draw.ellipse([w * 0.32, w * 0.24, w * 0.38, w * 0.30], fill="white")
    draw.ellipse([w * 0.56, w * 0.22, w * 0.70, w * 0.36], fill="black")
    draw.ellipse([w * 0.58, w * 0.24, w * 0.64, w * 0.30], fill="white")
    draw.polygon([(w * 0.48, w * 0.38), (w * 0.44, w * 0.43), (w * 0.52, w * 0.43)], fill="#FF9999")
    draw.line([(w * 0.25, w * 0.41), (w * 0.44, w * 0.40)], fill="#8B6914", width=1)
    draw.line([(w * 0.25, w * 0.44), (w * 0.44, w * 0.44)], fill="#8B6914", width=1)
    draw.line([(w * 0.56, w * 0.40), (w * 0.75, w * 0.41)], fill="#8B6914", width=1)
    draw.line([(w * 0.56, w * 0.44), (w * 0.75, w * 0.44)], fill="#8B6914", width=1)
    return img


class TimiSprite:
    """Jendela transparan kecil: animasi kucing berjalan di tepi layar (mode Shimeji)."""

    def __init__(self, root_parent, warna_mbti="#F4A460", mode_jalan=True):
        self.warna = warna_mbti
        self.mode_jalan = mode_jalan
        self._mode_jalan_asli = mode_jalan
        self.aktif = True

        lebar_layar = root_parent.winfo_screenwidth()
        tinggi_layar = root_parent.winfo_screenheight()
        self.lebar_layar = lebar_layar
        self.tinggi_layar = tinggi_layar

        self.x = random.randint(100, max(100, lebar_layar - 200))
        self.y = tinggi_layar - 110
        self.arah = random.choice(["kanan", "kiri"])
        self.langkah = 0

        self.win = tk.Toplevel(root_parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", "#010101")
        self.win.configure(bg="#010101")
        self.win.geometry(f"70x70+{self.x}+{self.y}")

        self.canvas = tk.Canvas(self.win, width=70, height=70, bg="#010101", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda e: root_parent.deiconify())

        self._render()
        self._loop()

    def _render(self):
        if not self.aktif:
            return
        self.canvas.delete("all")

        if not self.mode_jalan:
            pose = "duduk"
        else:
            pose = "jalan_kanan" if (self.langkah // 8) % 2 == 0 else "jalan_kiri"
            if self.arah == "kiri":
                pose = pose.replace("kanan", "TEMP").replace("kiri", "kanan").replace("TEMP", "kiri")

        img = buat_gambar_timi(65, pose=pose, warna_mbti=self.warna)
        self._foto = ImageTk.PhotoImage(img)
        self.canvas.create_image(35, 35, image=self._foto)

    def _loop(self):
        if not self.aktif:
            return

        if self.mode_jalan:
            kecepatan = 3
            if self.arah == "kanan":
                self.x += kecepatan
                if self.x > self.lebar_layar - 80:
                    self.arah = "kiri"
                    self.y = max(
                        self.tinggi_layar - 160,
                        min(self.tinggi_layar - 80, self.y + random.randint(-20, 20)),
                    )
            else:
                self.x -= kecepatan
                if self.x < 10:
                    self.arah = "kanan"
                    self.y = max(
                        self.tinggi_layar - 160,
                        min(self.tinggi_layar - 80, self.y + random.randint(-20, 20)),
                    )

            self.langkah += 1
            if random.random() < 0.003:
                self.mode_jalan = False
                self.win.after(random.randint(1500, 3500), self._resume_jalan)

        self.win.geometry(f"70x70+{int(self.x)}+{int(self.y)}")
        self._render()
        self.win.after(80, self._loop)

    def _resume_jalan(self):
        if self.aktif and getattr(self, "_mode_jalan_asli", True):
            self.mode_jalan = True

    def set_mode(self, jalan: bool):
        self._mode_jalan_asli = jalan
        self.mode_jalan = jalan

    def set_warna(self, warna):
        self.warna = warna

    def destroy(self):
        self.aktif = False
        try:
            self.win.destroy()
        except Exception:
            pass


# ───────────────────────────────────────────
# KELAS UTAMA TIMI AI
# ───────────────────────────────────────────
class TimiAI:
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY belum di-set. "
                "Set environment variable dulu, lalu jalankan ulang aplikasi."
            )
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.riwayat_chat = []
        self.aksi_pending = None
        self.mbti_aktif = "ISTP"
        self.riwayat_raw = []
        self.jumlah_pesan = 0
        self.sprite = None
        self.mode_jalan = True
        self.voice_aktif = False
        self.tts_aktif = True
        self.voice_engine = VoiceEngine() if (VOICE_TERSEDIA or TTS_LOKAL or TTS_ONLINE) else None
        self.scheduler = SchedulerEngine(self._notif_jadwal)
        self.av_engine = AntivirusEngine()
        self.setup_ui()

    def setup_ui(self):
        """Buat jendela Timi di layar."""
        self.root = tk.Tk()
        self.root.title("Timi AI")
        self.root.configure(bg="#2b2b2b")

        # Jendela selalu di atas & tanpa border
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)  # Hilangkan title bar

        # Posisi: pojok kanan bawah
        lebar_layar = self.root.winfo_screenwidth()
        tinggi_layar = self.root.winfo_screenheight()
        lebar_jendela = 330
        tinggi_jendela = 520
        x = lebar_layar - lebar_jendela - 20
        y = tinggi_layar - tinggi_jendela - 60
        self.root.geometry(f"{lebar_jendela}x{tinggi_jendela}+{x}+{y}")

        self._buat_header()
        self._buat_mbti_bar()
        self._buat_area_chat()
        self._buat_konfirmasi()
        self._buat_input()

        self.root.after(500, self.sapa_pertama)
        self.root.after(800, self._mulai_sprite)
        self._aktifkan_drag()

    def _buat_header(self):
        """Header dengan gambar Timi, toggle sprite, screenshot, tutup."""
        frame_header = tk.Frame(self.root, bg="#1a1a2e", pady=8)
        frame_header.pack(fill=tk.X)

        warna = MBTI_PROFILES[self.mbti_aktif]["warna"]
        img_timi = buat_gambar_timi(45, pose="duduk", warna_mbti=warna)
        self.foto_timi = ImageTk.PhotoImage(img_timi)
        self.label_foto = tk.Label(frame_header, image=self.foto_timi, bg="#1a1a2e")
        self.label_foto.pack(side=tk.LEFT, padx=10)

        frame_info = tk.Frame(frame_header, bg="#1a1a2e")
        frame_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(
            frame_info,
            text="Timi 🐱",
            font=("Segoe UI", 13, "bold"),
            fg="#e0e0e0",
            bg="#1a1a2e",
        ).pack(anchor=tk.W)
        self.label_status = tk.Label(
            frame_info,
            text="● Online",
            font=("Segoe UI", 9),
            fg="#4CAF50",
            bg="#1a1a2e",
        )
        self.label_status.pack(anchor=tk.W)

        frame_tombol = tk.Frame(frame_header, bg="#1a1a2e")
        frame_tombol.pack(side=tk.RIGHT, padx=8)
        self.tombol_toggle = tk.Button(
            frame_tombol,
            text="🐾",
            font=("Segoe UI", 11),
            bg="#1a1a2e",
            fg="#e0e0e0",
            bd=0,
            cursor="hand2",
            command=self.toggle_animasi,
        )
        self.tombol_toggle.pack()
        self.tombol_voice = tk.Button(
            frame_tombol,
            text="🎙️",
            font=("Segoe UI", 11),
            bg="#1a1a2e",
            fg="#888",
            bd=0,
            cursor="hand2",
            command=self.toggle_voice,
        )
        self.tombol_voice.pack()
        tk.Button(
            frame_tombol,
            text="🛡️",
            font=("Segoe UI", 11),
            bg="#1a1a2e",
            fg="#e0e0e0",
            bd=0,
            cursor="hand2",
            command=self.jalankan_scan,
        ).pack()
        tk.Button(
            frame_tombol,
            text="📷",
            font=("Segoe UI", 11),
            bg="#1a1a2e",
            fg="#e0e0e0",
            bd=0,
            cursor="hand2",
            command=self.screenshot_dan_analisis,
        ).pack()
        tk.Button(
            frame_tombol,
            text="✕",
            font=("Segoe UI", 11),
            bg="#1a1a2e",
            fg="#ff6b6b",
            bd=0,
            cursor="hand2",
            command=self._tutup,
        ).pack()

    def _buat_mbti_bar(self):
        """Bar mode MBTI + pintasan ganti manual."""
        self.frame_mbti = tk.Frame(self.root, bg="#0d0d1a", pady=4)
        self.frame_mbti.pack(fill=tk.X)

        profil = MBTI_PROFILES[self.mbti_aktif]
        self.label_mbti = tk.Label(
            self.frame_mbti,
            text=f"✦ Mode: {self.mbti_aktif} — {profil['nama']}",
            font=("Segoe UI", 9, "bold"),
            fg=profil["warna"],
            bg="#0d0d1a",
        )
        self.label_mbti.pack(side=tk.LEFT, padx=10)

        frame_mbti_tombol = tk.Frame(self.frame_mbti, bg="#0d0d1a")
        frame_mbti_tombol.pack(side=tk.RIGHT, padx=6)
        for m in MBTI_PROFILES:
            w = MBTI_PROFILES[m]["warna"]
            tk.Button(
                frame_mbti_tombol,
                text=m[:2],
                font=("Segoe UI", 7, "bold"),
                bg="#1a1a2e",
                fg=w,
                bd=0,
                padx=3,
                cursor="hand2",
                command=lambda x=m: self.ganti_mbti(x, manual=True),
            ).pack(side=tk.LEFT, padx=1)

    def _tutup(self):
        if self.sprite:
            self.sprite.destroy()
        self.root.destroy()

    def _mulai_sprite(self):
        warna = MBTI_PROFILES[self.mbti_aktif]["warna"]
        self.sprite = TimiSprite(self.root, warna_mbti=warna, mode_jalan=self.mode_jalan)

    def toggle_animasi(self):
        """Toggle sprite jalan vs diam."""
        self.mode_jalan = not self.mode_jalan
        if self.sprite:
            self.sprite.set_mode(self.mode_jalan)
        ikon = "🐾" if self.mode_jalan else "💤"
        self.tombol_toggle.config(text=ikon)
        status = "jalan-jalan" if self.mode_jalan else "istirahat"
        self.tampil_sistem(f"Timi sekarang mode {status}.")

    def _buat_area_chat(self):
        """Area tampilan percakapan."""
        frame_chat = tk.Frame(self.root, bg="#2b2b2b")
        frame_chat.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.area_chat = scrolledtext.ScrolledText(
            frame_chat,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg="#1e1e1e",
            fg="#e0e0e0",
            insertbackground="white",
            bd=0,
            padx=8,
            pady=8,
            state=tk.DISABLED
        )
        self.area_chat.pack(fill=tk.BOTH, expand=True)

        # Warna bubble chat
        self.area_chat.tag_config("timi", foreground="#81c784", font=("Segoe UI", 10))
        self.area_chat.tag_config("user", foreground="#90caf9", font=("Segoe UI", 10))
        self.area_chat.tag_config("sistem", foreground="#888", font=("Segoe UI", 9, "italic"))
        self.area_chat.tag_config("nama_timi", foreground="#4CAF50", font=("Segoe UI", 9, "bold"))
        self.area_chat.tag_config("nama_user", foreground="#2196F3", font=("Segoe UI", 9, "bold"))
        self.area_chat.tag_config("hasil", foreground="#ce93d8", font=("Courier New", 9))
        self.area_chat.tag_config("warning", foreground="#FF9800", font=("Segoe UI", 9, "bold"))
        self.area_chat.tag_config("mbti", foreground="#FFC107", font=("Segoe UI", 9, "bold"))

    def _buat_konfirmasi(self):
        """Panel konfirmasi aksi — muncul saat Timi mau eksekusi sesuatu."""
        self.frame_konfirmasi = tk.Frame(self.root, bg="#2d1b00", pady=6, padx=8)
        tk.Label(
            self.frame_konfirmasi,
            text="⚠️ Timi mau lakukan ini:",
            font=("Segoe UI", 9, "bold"),
            fg="#FF9800",
            bg="#2d1b00",
        ).pack(anchor=tk.W)
        self.label_aksi = tk.Label(
            self.frame_konfirmasi,
            text="",
            font=("Segoe UI", 9),
            fg="#e0e0e0",
            bg="#2d1b00",
            wraplength=295,
            justify=tk.LEFT,
        )
        self.label_aksi.pack(anchor=tk.W, pady=2)
        frame_tombol_k = tk.Frame(self.frame_konfirmasi, bg="#2d1b00")
        frame_tombol_k.pack(anchor=tk.E)
        tk.Button(
            frame_tombol_k,
            text="✅ Izinkan",
            font=("Segoe UI", 9),
            bg="#4CAF50",
            fg="white",
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.konfirmasi_izinkan,
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            frame_tombol_k,
            text="❌ Tolak",
            font=("Segoe UI", 9),
            bg="#f44336",
            fg="white",
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.konfirmasi_tolak,
        ).pack(side=tk.LEFT)

    def _buat_input(self):
        """Area input pesan user."""
        self.frame_input = tk.Frame(self.root, bg="#1a1a2e", pady=8)
        self.frame_input.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.input_pesan = tk.Entry(
            self.frame_input,
            font=("Segoe UI", 10),
            bg="#2d2d2d",
            fg="#e0e0e0",
            insertbackground="white",
            bd=0,
            relief=tk.FLAT,
        )
        self.input_pesan.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, ipadx=8)
        self.input_pesan.bind("<Return>", lambda e: self.kirim_pesan())

        self.tombol_kirim = tk.Button(
            self.frame_input,
            text="➤",
            font=("Segoe UI", 13),
            bg="#4CAF50",
            fg="white",
            bd=0,
            padx=10,
            cursor="hand2",
            command=self.kirim_pesan,
        )
        self.tombol_kirim.pack(side=tk.RIGHT, ipady=4)

    def _aktifkan_drag(self):
        """Bisa drag window ke mana saja."""
        self._drag_x = 0
        self._drag_y = 0

        def mulai_drag(event):
            self._drag_x = event.x
            self._drag_y = event.y

        def drag(event):
            x = self.root.winfo_x() + event.x - self._drag_x
            y = self.root.winfo_y() + event.y - self._drag_y
            self.root.geometry(f"+{x}+{y}")

        self.root.bind("<Button-1>", mulai_drag)
        self.root.bind("<B1-Motion>", drag)

    # ───────────────────────────────────────
    # FUNGSI CHAT
    # ───────────────────────────────────────
    def tampil_pesan(self, pengirim, pesan, tag_nama, tag_pesan):
        """Tampilkan pesan di area chat."""
        self.area_chat.config(state=tk.NORMAL)
        self.area_chat.insert(tk.END, f"{pengirim}\n", tag_nama)
        self.area_chat.insert(tk.END, f"{pesan}\n\n", tag_pesan)
        self.area_chat.config(state=tk.DISABLED)
        self.area_chat.see(tk.END)

    def tampil_sistem(self, pesan, tag="sistem"):
        """Tampilkan pesan sistem (info/status)."""
        self.area_chat.config(state=tk.NORMAL)
        self.area_chat.insert(tk.END, f"{pesan}\n\n", tag)
        self.area_chat.config(state=tk.DISABLED)
        self.area_chat.see(tk.END)

    def sapa_pertama(self):
        """Timi menyapa saat pertama dibuka."""
        profil = MBTI_PROFILES[self.mbti_aktif]
        self.tampil_pesan("🐱 Timi", profil["sapa"], "nama_timi", "timi")
        fitur_voice = "ON" if VOICE_TERSEDIA else "OFF (install SpeechRecognition)"
        fitur_tts = "ON" if (TTS_LOKAL or TTS_ONLINE) else "OFF (install pyttsx3 / gtts)"
        self.tampil_sistem(
            f"💡 Fase 4 siap.\n"
            f"🎙️ Voice: {fitur_voice}\n"
            f"🔊 TTS: {fitur_tts}\n"
            f"🔔 Scheduler: {'ON' if SCHEDULE_TERSEDIA else 'OFF (install schedule)'}\n"
            f"🛡️ Antivirus: {'ON' if WINREG_TERSEDIA else 'OFF (Windows-only)'}\n"
            "Tombol 🐾/💤 = sprite jalan/istirahat, 🎙️ = voice, 🛡️ = scan.",
            "sistem",
        )

    def kirim_pesan(self):
        """Proses pesan dari user."""
        pesan = self.input_pesan.get().strip()
        if not pesan:
            return

        self.input_pesan.delete(0, tk.END)
        self.tampil_pesan("👤 Kamu", pesan, "nama_user", "user")
        self.set_status("Timi sedang berpikir...", "#FFC107")

        self.riwayat_raw.append(f"User: {pesan}")
        self.jumlah_pesan += 1

        thread = threading.Thread(target=self._proses_ai, args=(pesan,))
        thread.daemon = True
        thread.start()

    def _proses_ai(self, pesan_user):
        """Kirim ke Gemini API dan tampilkan balasan (termasuk alur TIMI_ACTION)."""
        try:
            prompt = self._susun_prompt_chat(pesan_user)
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
            )
            balasan_penuh = (response.text or "").strip()
            if not balasan_penuh:
                balasan_penuh = "*mengangguk pelan* Aku belum dapat teks balasan. Coba ulang sekali lagi ya."
            self._simpan_riwayat_chat(pesan_user, balasan_penuh)
            self.riwayat_raw.append(f"Timi: {balasan_penuh[:200]}")

            baris = balasan_penuh.splitlines()
            baris_pertama = baris[0].strip() if baris else ""

            if baris_pertama.startswith("TIMI_ACTION:"):
                tipe, nilai = self._parse_timi_action(baris_pertama)
                teks_timi = "\n".join(baris[1:]).strip()
                if tipe == "GANTI_MBTI":
                    if teks_timi:
                        self.root.after(
                            0, lambda t=teks_timi: self.tampil_pesan("🐱 Timi", t, "nama_timi", "timi")
                        )
                        if self.tts_aktif and self.voice_engine:
                            self.root.after(100, lambda t=teks_timi: self.voice_engine.bicara(t))
                    self.root.after(200, lambda v=nilai: self.ganti_mbti(v, manual=False))
                else:
                    if teks_timi:
                        self.root.after(
                            0, lambda t=teks_timi: self.tampil_pesan("🐱 Timi", t, "nama_timi", "timi")
                        )
                    self.root.after(0, lambda ti=tipe, ni=nilai: self._minta_konfirmasi(ti, ni))
            else:
                self.root.after(
                    0, lambda b=balasan_penuh: self.tampil_pesan("🐱 Timi", b, "nama_timi", "timi")
                )
                if self.tts_aktif and self.voice_engine:
                    self.root.after(100, lambda b=balasan_penuh: self.voice_engine.bicara(b))

            self.root.after(0, lambda: self.set_status("● Online", "#4CAF50"))
            if "[SCREENSHOT" not in pesan_user:
                self.root.after(500, self._cek_dan_update_mbti)

        except Exception as e:
            pesan_error = self._format_error_pesan(e)
            self.root.after(0, lambda: self.tampil_pesan("🐱 Timi", pesan_error, "nama_timi", "timi"))
            self.root.after(0, lambda: self.set_status("● Offline", "#f44336"))

    def _susun_prompt_chat(self, pesan_user):
        """Gabungkan system prompt + riwayat ringkas + pesan terbaru."""
        potongan_riwayat = self.riwayat_chat[-6:]
        teks_riwayat = "\n".join(
            f"{item['role'].upper()}: {item['text']}" for item in potongan_riwayat
        )
        if not teks_riwayat:
            teks_riwayat = "(belum ada riwayat)"

        return (
            f"{buat_system_prompt(self.mbti_aktif)}\n\n"
            f"Riwayat percakapan terbaru:\n{teks_riwayat}\n\n"
            f"USER: {pesan_user}\n"
            "Balas sebagai TIMI:"
        )

    def _simpan_riwayat_chat(self, pesan_user, balasan_timi):
        """Simpan riwayat percakapan agar konteks tetap nyambung."""
        self.riwayat_chat.append({"role": "user", "text": pesan_user})
        self.riwayat_chat.append({"role": "timi", "text": balasan_timi})

    def ganti_mbti(self, mbti_baru, manual=False):
        """Ganti MBTI aktif (warna sprite, header, prompt berikutnya)."""
        mbti_baru = (mbti_baru or "").strip().upper()
        if mbti_baru not in MBTI_PROFILES:
            return
        if mbti_baru == self.mbti_aktif and not manual:
            return

        mbti_lama = self.mbti_aktif
        self.mbti_aktif = mbti_baru
        profil = MBTI_PROFILES[mbti_baru]
        self.riwayat_chat.clear()

        self.label_mbti.config(
            text=f"✦ Mode: {mbti_baru} — {profil['nama']}",
            fg=profil["warna"],
        )
        if self.sprite:
            self.sprite.set_warna(profil["warna"])
        img_baru = buat_gambar_timi(45, pose="duduk", warna_mbti=profil["warna"])
        self.foto_timi = ImageTk.PhotoImage(img_baru)
        self.label_foto.config(image=self.foto_timi)

        self.tampil_sistem(
            f"✨ Kepribadian berubah: {mbti_lama} → {mbti_baru} ({profil['nama']})",
            "mbti",
        )
        self.tampil_pesan("🐱 Timi", profil["sapa"], "nama_timi", "timi")

    def _cek_dan_update_mbti(self):
        """Tiap 8 pesan user, coba infer MBTI baru dari percakapan."""
        if self.jumlah_pesan % 8 != 0 or self.jumlah_pesan == 0:
            return
        ringkasan = "\n".join(self.riwayat_raw[-16:])

        def analisis():
            try:
                prompt = MBTI_ANALISIS_PROMPT.format(percakapan=ringkasan)
                resp = self.client.models.generate_content(
                    model=GEMINI_MODEL_NAME,
                    contents=prompt,
                )
                teks = (resp.text or "").strip()
                teks = teks.replace("```json", "").replace("```", "").strip()
                data = json.loads(teks)
                mbti_baru = data.get("mbti", "").strip().upper()
                alasan = data.get("alasan", "")

                if mbti_baru in MBTI_PROFILES and mbti_baru != self.mbti_aktif:
                    self.root.after(
                        0,
                        lambda m=mbti_baru, a=alasan: self.tampil_sistem(
                            f"🧠 Timi menganalisis percakapan... → {m} ({a})", "mbti"
                        ),
                    )
                    self.root.after(200, lambda m=mbti_baru: self.ganti_mbti(m, manual=False))
            except Exception:
                pass

        threading.Thread(target=analisis, daemon=True).start()

    @staticmethod
    def _parse_timi_action(baris_pertama):
        """Parse TIMI_ACTION:TIPE:nilai... agar path Windows tidak terpotong."""
        prefix = "TIMI_ACTION:"
        if not baris_pertama.startswith(prefix):
            return "", ""
        rest = baris_pertama[len(prefix) :]
        idx = rest.find(":")
        if idx == -1:
            return rest.strip(), ""
        tipe = rest[:idx].strip()
        nilai = rest[idx + 1 :].strip()
        return tipe, nilai

    def _format_error_pesan(self, err):
        """Ubah error teknis menjadi pesan yang lebih jelas untuk user."""
        teks = str(err)
        teks_lower = teks.lower()

        if "429" in teks or "resourceexhausted" in teks_lower or "quota" in teks_lower:
            return (
                "*mengibas ekor pelan* Kuota Gemini kamu lagi habis/terbatas (429). "
                "Cek billing/limit di Google AI Studio, lalu coba lagi sebentar."
            )

        if "timed out" in teks_lower or "deadline exceeded" in teks_lower or "timeout" in teks_lower:
            return (
                "*menoleh ke router* Koneksi ke server lagi lambat (timeout). "
                "Coba ulang 10-30 detik lagi."
            )

        if isinstance(err, (ConnectionError, TimeoutError, socket.gaierror)):
            return (
                "*menggaruk kepala* Internet kamu sepertinya putus atau DNS bermasalah. "
                "Cek koneksi lalu coba lagi."
            )

        if "503" in teks or "unavailable" in teks_lower:
            return (
                "*duduk tegak* Server Gemini lagi sibuk sementara (503). "
                "Coba lagi beberapa saat."
            )

        return f"*menggaruk kepala* Aduh, ada masalah koneksi: {teks}"

    def _minta_konfirmasi(self, tipe, nilai):
        if not tipe:
            return
        deskripsi = {
            "BUKA_FOLDER": f"📂 Buka folder:\n{nilai}",
            "BUKA_APP": f"🚀 Buka aplikasi:\n{nilai}",
            "JALANKAN_CMD": f"⚙️ Jalankan perintah:\n{nilai}",
            "TELEGRAM": f"📱 Kirim notif ke HP:\n{nilai}",
        }.get(tipe, f"❓ Aksi: {tipe} → {nilai}")

        self.aksi_pending = (tipe, nilai)
        self.label_aksi.config(text=deskripsi)
        self.frame_konfirmasi.pack(fill=tk.X, padx=8, pady=2, before=self.frame_input)

    def konfirmasi_izinkan(self):
        self.frame_konfirmasi.pack_forget()
        if not self.aksi_pending:
            return
        tipe, nilai = self.aksi_pending
        self.aksi_pending = None
        self.tampil_sistem("✅ Diizinkan. Menjalankan...", "warning")
        thread = threading.Thread(target=self._eksekusi_aksi, args=(tipe, nilai))
        thread.daemon = True
        thread.start()

    def konfirmasi_tolak(self):
        self.frame_konfirmasi.pack_forget()
        self.aksi_pending = None
        self.tampil_sistem("❌ Aksi dibatalkan.")
        self.tampil_pesan("🐱 Timi", "*mengangguk* Oke, aku batalkan ya~", "nama_timi", "timi")

    def _eksekusi_aksi(self, tipe, nilai):
        try:
            if tipe == "JADWAL":
                bagian2 = nilai.split(":", 3)
                if len(bagian2) >= 3:
                    jam = f"{bagian2[0]}:{bagian2[1]}"
                    pesan_j = bagian2[2]
                    ulangi = (bagian2[3].upper() == "Y") if len(bagian2) > 3 else True
                else:
                    jam = "09:00"
                    pesan_j = nilai or "Pengingat!"
                    ulangi = True
                ok = self.scheduler.tambah_jadwal(jam, pesan_j, ulangi)
                tipe_j = "tiap hari" if ulangi else "sekali"
                msg = (
                    f"*duduk tegak* Jadwal ditambah! Jam {jam} — '{pesan_j}' ({tipe_j}) ✅"
                    if ok
                    else "*mengeong* Gagal tambah jadwal. Pastikan library schedule terinstall."
                )
                self.root.after(0, lambda m=msg: self.tampil_pesan("🐱 Timi", m, "nama_timi", "timi"))
            elif tipe == "TOGGLE_TTS":
                self.root.after(0, self.toggle_tts)
            elif tipe == "BUKA_FOLDER":
                self._aksi_buka_folder(nilai)
            elif tipe == "BUKA_APP":
                self._aksi_buka_app(nilai)
            elif tipe == "JALANKAN_CMD":
                self._aksi_jalankan_cmd(nilai)
            elif tipe == "TELEGRAM":
                self._aksi_telegram(nilai)
            else:
                self.root.after(0, lambda: self.tampil_sistem("❓ Tipe aksi tidak dikenal."))
        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: self.tampil_sistem(f"❌ Error eksekusi: {err}"))

    def _aksi_buka_folder(self, path):
        path_expand = os.path.expandvars(path)
        if os.path.exists(path_expand):
            subprocess.Popen(f'explorer "{path_expand}"')
            self.root.after(
                0,
                lambda: self.tampil_pesan(
                    "🐱 Timi",
                    f"*berlari kecil* Sudah kubuka! → {path_expand}",
                    "nama_timi",
                    "timi",
                ),
            )
        else:
            self.root.after(
                0,
                lambda: self.tampil_pesan(
                    "🐱 Timi",
                    f"*mengeong bingung* Folder tidak ketemu: {path_expand}",
                    "nama_timi",
                    "timi",
                ),
            )

    def _aksi_buka_app(self, nama_app):
        try:
            subprocess.Popen(nama_app, shell=True)
            self.root.after(
                0,
                lambda: self.tampil_pesan(
                    "🐱 Timi",
                    f"*melompat senang* Dibuka: {nama_app} ~",
                    "nama_timi",
                    "timi",
                ),
            )
        except Exception as e:
            err = str(e)
            self.root.after(
                0,
                lambda: self.tampil_pesan(
                    "🐱 Timi",
                    f"*menggaruk kepala* Gagal buka: {err}",
                    "nama_timi",
                    "timi",
                ),
            )

    def _aksi_jalankan_cmd(self, perintah):
        perintah_lower = perintah.lower()
        for dilarang in CMD_DILARANG:
            if dilarang in perintah_lower:
                self.root.after(
                    0,
                    lambda: self.tampil_pesan(
                        "🐱 Timi",
                        "*duduk tegak* Maaf, perintah itu tidak aku izinkan untuk keamananmu.",
                        "nama_timi",
                        "timi",
                    ),
                )
                return
        try:
            hasil = subprocess.run(
                perintah,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15,
                encoding="utf-8",
                errors="replace",
            )
            output = (hasil.stdout or hasil.stderr or "(tidak ada output)").strip()
            if len(output) > 800:
                output = output[:800] + "\n...(terpotong)"
            self.root.after(0, lambda o=output: self.tampil_sistem(f"📋 Hasil:\n{o}", "hasil"))
            self.root.after(
                0,
                lambda: self.tampil_pesan(
                    "🐱 Timi",
                    "*mengibas ekor* Selesai! Hasil di atas~",
                    "nama_timi",
                    "timi",
                ),
            )
        except subprocess.TimeoutExpired:
            self.root.after(0, lambda: self.tampil_sistem("⏱️ Timeout (>15 detik)."))
        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: self.tampil_sistem(f"❌ Error: {err}"))

    def _aksi_telegram(self, pesan):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            self.root.after(
                0,
                lambda: self.tampil_pesan(
                    "🐱 Timi",
                    "*mengeong* Telegram belum dikonfigurasi! Set TELEGRAM_TOKEN dan "
                    "TELEGRAM_CHAT_ID (environment variable) dulu ya.",
                    "nama_timi",
                    "timi",
                ),
            )
            return
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            resp = requests.post(
                url,
                json={"chat_id": TELEGRAM_CHAT_ID, "text": f"🐱 Timi: {pesan}"},
                timeout=10,
            )
            if resp.status_code == 200:
                self.root.after(
                    0,
                    lambda: self.tampil_pesan(
                        "🐱 Timi",
                        "*melompat gembira* Notif terkirim ke HP kamu! 📱",
                        "nama_timi",
                        "timi",
                    ),
                )
            else:
                self.root.after(0, lambda: self.tampil_sistem(f"❌ Telegram error: {resp.text}"))
        except Exception as e:
            err = str(e)
            self.root.after(0, lambda: self.tampil_sistem(f"❌ Gagal kirim Telegram: {err}"))

    def toggle_voice(self):
        """Aktifkan/nonaktifkan mode dengar terus."""
        if not VOICE_TERSEDIA:
            self.tampil_sistem("❌ SpeechRecognition belum terinstall. Jalankan: pip install SpeechRecognition")
            return
        self.voice_aktif = not self.voice_aktif
        warna = "#4CAF50" if self.voice_aktif else "#888"
        self.tombol_voice.config(fg=warna)
        if self.voice_aktif:
            self.tampil_sistem("🎙️ Mode suara ON — aku siap mendengarkan!", "warning")
            self._dengar_loop()
        else:
            self.tampil_sistem("🎙️ Mode suara OFF.")

    def _dengar_loop(self):
        if not self.voice_aktif or not self.voice_engine:
            return
        self.set_status("🎙️ Mendengarkan...", "#FF9800")

        def on_hasil(teks):
            self.root.after(0, lambda: self.set_status("● Online", "#4CAF50"))
            self.root.after(0, lambda t=teks: self._input_dari_suara(t))

        def on_error(_pesan):
            self.root.after(0, lambda: self.set_status("● Online", "#4CAF50"))
            if self.voice_aktif:
                self.root.after(1000, self._dengar_loop)

        self.voice_engine.dengar(on_hasil, on_error)

    def _input_dari_suara(self, teks):
        self.tampil_pesan("🎙️ Kamu (suara)", teks, "nama_user", "user")
        self.set_status("Timi sedang berpikir...", "#FFC107")
        self.riwayat_raw.append(f"User: {teks}")
        self.jumlah_pesan += 1
        t = threading.Thread(target=self._proses_ai, args=(teks,))
        t.daemon = True
        t.start()
        if self.voice_aktif:
            self.root.after(3000, self._dengar_loop)

    def toggle_tts(self):
        self.tts_aktif = not self.tts_aktif
        status = "ON 🔊" if self.tts_aktif else "OFF 🔇"
        self.tampil_sistem(f"Suara Timi: {status}")

    def _notif_jadwal(self, pesan):
        self.root.after(0, lambda p=pesan: self._tampil_notif_jadwal(p))

    def _tampil_notif_jadwal(self, pesan):
        notif = f"🔔 Pengingat: {pesan}"
        self.tampil_sistem(notif, "warning")
        self.tampil_pesan("🐱 Timi", f"*melompat* Hei! {pesan} ~", "nama_timi", "timi")
        if self.tts_aktif and self.voice_engine:
            self.voice_engine.bicara(f"Pengingat! {pesan}")
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            threading.Thread(target=self._aksi_telegram, args=(f"Pengingat: {pesan}",), daemon=True).start()

    def jalankan_scan(self):
        self.tampil_sistem("🛡️ Memulai scan... harap tunggu.")
        self.set_status("🛡️ Scanning...", "#FF9800")
        t = threading.Thread(target=self._proses_scan, daemon=True)
        t.start()

    def _proses_scan(self):
        curiga_reg, bersih_reg = self.av_engine.scan_startup()
        curiga_tmp = self.av_engine.scan_temp()

        def _tampil():
            self.set_status("● Online", "#4CAF50")
            if not curiga_reg and not curiga_tmp:
                self.tampil_pesan(
                    "🐱 Timi",
                    f"*duduk tegak* Scan selesai! Tidak ada yang mencurigakan. ({len(bersih_reg)} startup bersih ✅)",
                    "nama_timi",
                    "timi",
                )
                return

            laporan = "⚠️ Timi menemukan hal mencurigakan:\n\n"
            if curiga_reg:
                laporan += "📋 Registry Startup mencurigakan:\n"
                for item in curiga_reg:
                    laporan += f"  • {item['nama']}\n    → {item['path'][:80]}\n"
            if curiga_tmp:
                laporan += f"\n🗂️ File executable di Temp ({len(curiga_tmp)}):\n"
                for f in curiga_tmp[:5]:
                    laporan += f"  • {os.path.basename(f)}\n"
                if len(curiga_tmp) > 5:
                    laporan += f"  ...dan {len(curiga_tmp) - 5} file lainnya\n"
            laporan += "\n⚠️ Ini hanya peringatan. Keputusan tetap di tanganmu."
            self.tampil_sistem(laporan, "warning")
            self.tampil_pesan("🐱 Timi", "*duduk tegak* Ada yang perlu kamu periksa! Lihat laporan di atas.", "nama_timi", "timi")
            if self.tts_aktif and self.voice_engine:
                self.voice_engine.bicara("Scan selesai. Ada beberapa hal mencurigakan. Tolong periksa.")

        self.root.after(0, _tampil)

    def set_status(self, teks, warna):
        """Update label status."""
        self.label_status.config(text=teks, fg=warna)

    # ───────────────────────────────────────
    # FUNGSI SCREENSHOT & ANALISIS ERROR
    # ───────────────────────────────────────
    def screenshot_dan_analisis(self):
        """Ambil screenshot layar, baca teks, kirim ke Timi."""
        self.tampil_sistem("📷 Mengambil screenshot layar...")
        self.set_status("Memindai layar...", "#FFC107")

        thread = threading.Thread(target=self._proses_screenshot)
        thread.daemon = True
        thread.start()

    def _proses_screenshot(self):
        """Proses screenshot di background thread."""
        try:
            self.root.after(0, lambda: self.root.withdraw())
            if self.sprite:
                self.root.after(0, lambda: self.sprite.win.withdraw())
            time.sleep(0.35)

            screenshot = pyautogui.screenshot()

            self.root.after(0, lambda: self.root.deiconify())
            if self.sprite:
                self.root.after(0, lambda: self.sprite.win.deiconify())

            # Baca teks dari screenshot (OCR)
            teks = pytesseract.image_to_string(screenshot, lang="eng+ind")
            teks = teks.strip()

            if not teks:
                self.root.after(0, lambda: self.tampil_sistem("Tidak ada teks terbaca di layar."))
                self.root.after(0, lambda: self.set_status("● Online", "#4CAF50"))
                return

            # Potong teks jika terlalu panjang
            if len(teks) > 1500:
                teks = teks[:1500] + "...(terpotong)"

            pesan_ke_ai = f"[SCREENSHOT LAYAR USER]\nBerikut teks yang terdeteksi di layar:\n\n{teks}\n\nApakah ada error atau masalah? Kalau ada, bantu jelaskan dan kasih solusinya."

            self.root.after(0, lambda: self.tampil_sistem(f"✅ Teks terdeteksi ({len(teks)} karakter). Timi sedang menganalisis..."))
            self._proses_ai(pesan_ke_ai)

        except Exception as e:
            self.root.after(0, lambda: self.tampil_sistem(f"❌ Gagal screenshot: {str(e)}"))
            self.root.after(0, lambda: self.set_status("● Online", "#4CAF50"))
            self.root.after(0, lambda: self.root.deiconify())

    # ───────────────────────────────────────
    # JALANKAN APLIKASI
    # ───────────────────────────────────────
    def jalankan(self):
        self.root.mainloop()


class VoiceEngine:
    """Speech-to-text + text-to-speech dengan fallback offline/online."""

    def __init__(self):
        self.recognizer = sr.Recognizer() if VOICE_TERSEDIA else None
        self.tts_engine = None
        self.sedang_dengar = False
        self._init_tts()

    def _init_tts(self):
        if not TTS_LOKAL:
            return
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty("rate", 160)
        except Exception:
            self.tts_engine = None

    @staticmethod
    def deteksi_bahasa(teks):
        kata_indo = {
            "aku",
            "kamu",
            "ini",
            "itu",
            "ada",
            "tidak",
            "bisa",
            "dan",
            "atau",
            "yang",
            "dengan",
            "untuk",
            "dari",
            "ke",
            "di",
            "ya",
            "oke",
            "tolong",
        }
        token = set(teks.lower().split())
        return "id" if len(kata_indo.intersection(token)) >= 2 else "en"

    def bicara(self, teks, callback_selesai=None):
        teks_bersih = re.sub(r"\*[^*]+\*", "", teks or "").strip()
        teks_bersih = re.sub(r"[^\w\s.,!?-]", "", teks_bersih)
        if not teks_bersih:
            return

        def _run():
            try:
                if TTS_LOKAL and self.tts_engine:
                    self.tts_engine.say(teks_bersih)
                    self.tts_engine.runAndWait()
                elif TTS_ONLINE:
                    lang = self.deteksi_bahasa(teks_bersih)
                    tts = gTTS(text=teks_bersih, lang=lang, slow=False)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                        tmp = f.name
                    tts.save(tmp)
                    playsound.playsound(tmp)
                    os.unlink(tmp)
            except Exception:
                pass
            finally:
                if callback_selesai:
                    callback_selesai()

        threading.Thread(target=_run, daemon=True).start()

    def dengar(self, callback_hasil, callback_error=None):
        if not VOICE_TERSEDIA or self.sedang_dengar:
            return
        self.sedang_dengar = True

        def _run():
            try:
                with sr.Microphone() as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=15)
                try:
                    teks = self.recognizer.recognize_google(audio, language="id-ID")
                except sr.UnknownValueError:
                    teks = self.recognizer.recognize_google(audio, language="en-US")
                callback_hasil(teks)
            except Exception as e:
                if callback_error:
                    callback_error(str(e))
            finally:
                self.sedang_dengar = False

        threading.Thread(target=_run, daemon=True).start()


class SchedulerEngine:
    """Scheduler pengingat otomatis."""

    def __init__(self, callback_notif):
        self.callback_notif = callback_notif
        self.jadwal_list = []
        self.aktif = True
        self._mulai_loop()

    def tambah_jadwal(self, jam_str, pesan, ulangi=True):
        if not SCHEDULE_TERSEDIA:
            return False
        try:
            if ulangi:
                schedule.every().day.at(jam_str).do(self.callback_notif, pesan)
            else:
                schedule.every().day.at(jam_str).do(self._sekali, pesan, jam_str)
            self.jadwal_list.append({"jam": jam_str, "pesan": pesan, "ulangi": ulangi})
            return True
        except Exception:
            return False

    def _sekali(self, pesan, jam_str):
        self.callback_notif(pesan)
        schedule.clear(jam_str)

    def _mulai_loop(self):
        def _loop():
            while self.aktif:
                if SCHEDULE_TERSEDIA:
                    schedule.run_pending()
                time.sleep(20)

        threading.Thread(target=_loop, daemon=True).start()


class AntivirusEngine:
    """Scan ringan registry startup + folder temp."""

    POLA_CURIGA = [
        r"\\temp\\",
        r"\\appdata\\local\\temp\\",
        r"powershell.*-enc",
        r"powershell.*hidden",
        r"cmd.*\/c.*start",
        r"wscript",
        r"cscript",
        r"regsvr32.*scrobj",
        r"\.vbs$",
        r"\.bat.*hidden",
        r"rundll32.*javascript",
        r"mshta",
    ]

    REGISTRY_STARTUP = (
        [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        ]
        if WINREG_TERSEDIA
        else []
    )

    def scan_startup(self):
        hasil, bersih = [], []
        if not WINREG_TERSEDIA:
            return [], ["winreg tidak tersedia (non-Windows)"]

        for hive, path in self.REGISTRY_STARTUP:
            try:
                key = winreg.OpenKey(hive, path)
                i = 0
                while True:
                    try:
                        nama, val, _ = winreg.EnumValue(key, i)
                        val_lower = str(val).lower()
                        curiga = any(re.search(p, val_lower) for p in self.POLA_CURIGA)
                        if curiga:
                            hasil.append({"nama": nama, "path": val, "sumber": path})
                        else:
                            bersih.append(nama)
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except Exception:
                continue
        return hasil, bersih

    def scan_temp(self):
        temp_dirs = [os.path.expandvars(r"%TEMP%"), os.path.expandvars(r"%LOCALAPPDATA%\Temp")]
        curiga = []
        for folder in temp_dirs:
            if not os.path.exists(folder):
                continue
            try:
                for f in os.listdir(folder):
                    if f.lower().endswith((".exe", ".bat", ".vbs", ".ps1", ".cmd")):
                        curiga.append(os.path.join(folder, f))
            except Exception:
                continue
        return curiga[:20]


def cek_koneksi_gemini():
    """Cek cepat apakah API Gemini bisa diakses."""
    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY belum di-set.")
        print('   PowerShell (sementara sesi ini): $env:GEMINI_API_KEY="API_KEY_KAMU"')
        return 1

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents="Balas singkat: koneksi OK"
        )
        print("[OK] Koneksi Gemini berhasil.")
        print(f"   Balasan uji: {(response.text or '')[:120].strip()}")
        return 0
    except Exception as e:
        print(f"[ERROR] Koneksi Gemini gagal: {e}")
        print("   Tips: jika 429/RESOURCE_EXHAUSTED, cek kuota & billing project Gemini.")
        return 1


def jalankan_self_test():
    """Tes cepat untuk memastikan flow utama Timi berjalan."""
    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY belum di-set.")
        return 1

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        riwayat = []

        def kirim(pesan_user):
            potongan = riwayat[-6:]
            teks_riwayat = "\n".join(
                f"{item['role'].upper()}: {item['text']}" for item in potongan
            ) or "(belum ada riwayat)"
            prompt = (
                f"{buat_system_prompt('ISTP')}\n\n"
                f"Riwayat percakapan terbaru:\n{teks_riwayat}\n\n"
                f"USER: {pesan_user}\n"
                "Balas sebagai TIMI:"
            )
            response = client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt
            )
            balasan = (response.text or "").strip()
            riwayat.append({"role": "user", "text": pesan_user})
            riwayat.append({"role": "timi", "text": balasan})
            return balasan

        print("[TEST] 1/3 chat normal")
        balasan_1 = kirim("Halo Timi, cek apakah kamu online?")
        print(f"       OK: {balasan_1[:90]}")

        print("[TEST] 2/3 prompt panjang")
        prompt_panjang = (
            "Aku lagi error install Python package di Windows. "
            "Bantu diagnosis langkah demi langkah. "
            + ("detail-log " * 120)
        )
        balasan_2 = kirim(prompt_panjang)
        print(f"       OK: {balasan_2[:90]}")

        print("[TEST] 3/3 simulasi analisis screenshot")
        simulasi_ocr = (
            "[SCREENSHOT LAYAR USER]\n"
            "Berikut teks yang terdeteksi di layar:\n\n"
            "Traceback (most recent call last):\n"
            "ModuleNotFoundError: No module named 'pyautogui'\n\n"
            "Apakah ada error atau masalah? Kalau ada, bantu jelaskan dan kasih solusinya."
        )
        balasan_3 = kirim(simulasi_ocr)
        print(f"       OK: {balasan_3[:90]}")

        print("[OK] Self-test selesai, semua skenario lolos.")
        return 0
    except Exception as e:
        print(f"[ERROR] Self-test gagal: {e}")
        return 1


# ───────────────────────────────────────────
# ENTRY POINT
# ───────────────────────────────────────────
if __name__ == "__main__":
    if "--check-api" in sys.argv:
        raise SystemExit(cek_koneksi_gemini())
    if "--self-test" in sys.argv:
        raise SystemExit(jalankan_self_test())

    print("🐱 Memulai Timi AI (Fase 1 + 2 + 3)...")
    timi = TimiAI()
    timi.jalankan()