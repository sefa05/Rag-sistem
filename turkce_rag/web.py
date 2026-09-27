"""Standart kütüphaneyle çalışan küçük yerel web arayüzü.

POST /api/sor gövdesi {"soru": "...", "yalnizca_ara": false} alır ve satır satır JSON (NDJSON) akıtır:
önce {"tur": "kaynaklar", ...}, sonra cevap geldikçe {"tur": "metin", ...}, sorun olursa {"tur": "hata", ...}.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

from .indeks import Indeks


def _isleyici(indeks: Indeks, k: int) -> type[BaseHTTPRequestHandler]:
    sayfa = files("turkce_rag").joinpath("arayuz.html").read_bytes()

    class Isleyici(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:  # istek günlüğünü sustur
            pass

        def do_GET(self) -> None:
            if self.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(sayfa)))
            self.end_headers()
            self.wfile.write(sayfa)

        def _satir(self, veri: dict) -> None:
            self.wfile.write(json.dumps(veri, ensure_ascii=False).encode() + b"\n")
            self.wfile.flush()

        def do_POST(self) -> None:
            if self.path != "/api/sor":
                self.send_error(404)
                return
            try:
                govde = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                soru = str(govde["soru"]).strip()
            except (ValueError, KeyError):
                self.send_error(400, "Gövde {\"soru\": \"...\"} biçiminde olmalı")
                return
            if not soru:
                self.send_error(400, "Soru boş")
                return

            sonuclar = indeks.ara(soru, k)
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self._satir({
                "tur": "kaynaklar",
                "kaynaklar": [
                    {"no": i, "dosya": s.parca.kaynak, "baslik": s.parca.baslik, "metin": s.parca.metin,
                     "puan": round(s.puan, 2)}
                    for i, s in enumerate(sonuclar, 1)
                ],
            })
            if govde.get("yalnizca_ara"):
                return

            from .cevap import KimlikHatasi, cevapla_akis

            try:
                for parca in cevapla_akis(soru, sonuclar):
                    self._satir({"tur": "metin", "metin": parca})
            except KimlikHatasi as hata:
                self._satir({"tur": "hata", "mesaj": str(hata)})
            except Exception as hata:  # anahtar yok, ağ hatası vb. kullanıcıya gösterilir
                self._satir({"tur": "hata", "mesaj": f"{type(hata).__name__}: {hata}"})

    return Isleyici


def calistir(indeks: Indeks, adres: str, port: int, k: int) -> None:
    sunucu = ThreadingHTTPServer((adres, port), _isleyici(indeks, k))
    print(f"Arayüz: http://{adres}:{port}  (durdurmak için Ctrl+C)")
    try:
        sunucu.serve_forever()
    finally:
        sunucu.server_close()
