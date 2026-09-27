import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from turkce_rag.indeks import Indeks
from turkce_rag.web import _isleyici


def test_yalnizca_ara_kaynaklari_akitir():
    indeks = Indeks.klasorden(Path(__file__).parent.parent / "derlem")
    sunucu = ThreadingHTTPServer(("127.0.0.1", 0), _isleyici(indeks, 3))
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    try:
        adres = f"http://127.0.0.1:{sunucu.server_port}"
        assert b"<title>" in urllib.request.urlopen(adres).read()
        istek = urllib.request.Request(
            f"{adres}/api/sor",
            data=json.dumps({"soru": "yıllık izin kaç gün", "yalnizca_ara": True}).encode(),
            headers={"Content-Type": "application/json"},
        )
        satirlar = urllib.request.urlopen(istek).read().decode().splitlines()
        olay = json.loads(satirlar[0])
        assert len(satirlar) == 1 and olay["tur"] == "kaynaklar"
        assert olay["kaynaklar"][0]["dosya"] == "01_izin_politikasi.md"
    finally:
        sunucu.shutdown()
