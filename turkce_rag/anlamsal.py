"""Anlamsal arama: multilingual-e5 ile gömme vektörleri (embedding) ve kosinüs benzerliği.

BM25 yalnızca ortak kelimeleri görür; "laptop" ile "dizüstü bilgisayar" eşleşmez. Gömme modeli metnin anlamını
vektöre çevirir, anlamca yakın metinler kelime paylaşmasa da yakın düşer.

Model yerelde ONNX Runtime ile çalışır, dış servise veri gitmez. e5'in resmi kullanımı uygulanır: sorgulara
"query: ", belgelere "passage: " öneki, dikkat maskesine göre ortalama havuzlama (mean pooling), L2 normalizasyonu.
"""

from __future__ import annotations

import hashlib
import os
import tarfile
import urllib.request
from pathlib import Path

VARSAYILAN_MODEL_KLASORU = Path(os.environ.get("RAG_MODEL_KLASORU", Path.home() / ".cache" / "turkce-rag" / "e5"))

# Qdrant'ın fastembed projesi için yayımladığı ONNX dönüşümü (~1,3 GB indirme, açılınca ~2,2 GB).
MODEL_ADRESI = "https://storage.googleapis.com/qdrant-fastembed/fast-multilingual-e5-large.tar.gz"


def bagimliliklar():
    try:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
    except ImportError as hata:
        raise SystemExit('Anlamsal arama için ek paketler gerekli: pip install -e ".[anlamsal]"') from hata
    return np, ort, Tokenizer


def model_indir(hedef: Path = VARSAYILAN_MODEL_KLASORU) -> Path:
    if (hedef / "model.onnx").exists():
        print(f"Model zaten var: {hedef}")
        return hedef
    hedef.mkdir(parents=True, exist_ok=True)
    arsiv = hedef / "model.tar.gz"
    print(f"İndiriliyor: {MODEL_ADRESI}")

    def ilerleme(blok: int, boyut: int, toplam: int) -> None:
        print(f"\r  {blok * boyut / 1e6:,.0f} / {toplam / 1e6:,.0f} MB", end="", flush=True)

    urllib.request.urlretrieve(MODEL_ADRESI, arsiv, ilerleme)
    print("\nAçılıyor…")
    with tarfile.open(arsiv) as tar:
        for uye in tar.getmembers():
            ad = Path(uye.name).name
            # Arşivde macOS'un "._" meta dosyaları da var; yalnızca model dosyaları alınır.
            if uye.isfile() and not ad.startswith("._"):
                uye.name = ad
                tar.extract(uye, hedef)
    arsiv.unlink()
    print(f"Model hazır: {hedef}")
    return hedef


class Gomucu:
    def __init__(self, klasor: Path = VARSAYILAN_MODEL_KLASORU, azami_jeton: int = 512):
        np, ort, Tokenizer = bagimliliklar()
        if not (klasor / "model.onnx").exists():
            raise SystemExit(f"Gömme modeli bulunamadı: {klasor}. Önce `rag model-indir` çalıştırın.")
        self._np = np
        self._oturum = ort.InferenceSession(str(klasor / "model.onnx"), providers=["CPUExecutionProvider"])
        self._jetonlayici = Tokenizer.from_file(str(klasor / "tokenizer.json"))
        self._jetonlayici.enable_truncation(azami_jeton)
        self._jetonlayici.enable_padding()

    def gom(self, metinler: list[str], tur: str, grup: int = 8):
        """tur: sorgu için "query", belge parçası için "passage". Satırları birim uzunlukta bir matris döner."""
        np = self._np
        parcalar = []
        for i in range(0, len(metinler), grup):
            kodlar = self._jetonlayici.encode_batch([f"{tur}: {m}" for m in metinler[i : i + grup]])
            kimlikler = np.array([k.ids for k in kodlar], dtype=np.int64)
            maske = np.array([k.attention_mask for k in kodlar], dtype=np.int64)
            gizli = self._oturum.run(None, {"input_ids": kimlikler, "attention_mask": maske})[0]
            m = maske[..., None].astype(gizli.dtype)
            ortalama = (gizli * m).sum(axis=1) / m.sum(axis=1)
            parcalar.append(ortalama / np.linalg.norm(ortalama, axis=1, keepdims=True))
        return np.concatenate(parcalar).astype(np.float32)


def parca_ozeti(metinler: list[str]) -> str:
    """Vektörlerin hangi parçalara ait olduğunu doğrulamak için parça metinlerinin özeti."""
    return hashlib.sha256("\x00".join(metinler).encode()).hexdigest()[:16]


def parca_metni(baslik: str, metin: str) -> str:
    return f"{baslik}\n{metin}" if baslik else metin
