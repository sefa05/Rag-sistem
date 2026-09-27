"""Belgeleri okuyup parçalayan ve BM25 ile arayan indeks."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from .metin import jetonla, parcala

DESTEKLENEN_UZANTILAR = {".md", ".txt", ".pdf"}


@dataclass
class Parca:
    kimlik: int
    kaynak: str  # derlem klasörüne göre dosya yolu
    baslik: str
    metin: str


@dataclass
class Sonuc:
    parca: Parca
    puan: float


def _dosya_oku(yol: Path) -> str:
    if yol.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as hata:
            raise SystemExit(f"{yol} bir PDF; okumak için `pip install pypdf` gerekli.") from hata
        return "\n\n".join(sayfa.extract_text() or "" for sayfa in PdfReader(yol).pages)
    return yol.read_text(encoding="utf-8")


class Indeks:
    """Okapi BM25. k1 ve b literatürdeki yaygın varsayılanlardır."""

    def __init__(self, parcalar: list[Parca], k1: float = 1.5, b: float = 0.75):
        self.parcalar = parcalar
        self.k1 = k1
        self.b = b
        # Başlık da jetonlara girer: "Uzaktan Çalışma" başlıklı parça, metinde bu kelimeler geçmese de bulunur.
        self._jetonlar = [Counter(jetonla(f"{p.baslik}\n{p.metin}")) for p in parcalar]
        self._uzunluk = [sum(j.values()) for j in self._jetonlar]
        self._ort_uzunluk = sum(self._uzunluk) / len(parcalar) if parcalar else 0.0
        belge_frekansi: Counter[str] = Counter()
        for jetonlar in self._jetonlar:
            belge_frekansi.update(jetonlar.keys())
        n = len(parcalar)
        self._idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in belge_frekansi.items()}

    @classmethod
    def klasorden(cls, klasor: Path, azami_karakter: int = 900) -> Indeks:
        parcalar: list[Parca] = []
        for yol in sorted(klasor.rglob("*")):
            if yol.suffix.lower() not in DESTEKLENEN_UZANTILAR or not yol.is_file():
                continue
            for baslik, metin in parcala(_dosya_oku(yol), azami_karakter):
                parcalar.append(Parca(len(parcalar), yol.relative_to(klasor).as_posix(), baslik, metin))
        if not parcalar:
            raise SystemExit(f"{klasor} içinde okunacak belge yok ({', '.join(sorted(DESTEKLENEN_UZANTILAR))}).")
        return cls(parcalar)

    def ara(self, sorgu: str, k: int = 5) -> list[Sonuc]:
        sorgu_jetonlari = set(jetonla(sorgu))
        sonuclar = []
        for parca, jetonlar, uzunluk in zip(self.parcalar, self._jetonlar, self._uzunluk):
            puan = 0.0
            for t in sorgu_jetonlari:
                f = jetonlar.get(t)
                if f:
                    norm = self.k1 * (1 - self.b + self.b * uzunluk / self._ort_uzunluk)
                    puan += self._idf[t] * f * (self.k1 + 1) / (f + norm)
            if puan > 0:
                sonuclar.append(Sonuc(parca, puan))
        sonuclar.sort(key=lambda s: s.puan, reverse=True)
        return sonuclar[:k]

    def kaydet(self, yol: Path) -> None:
        yol.parent.mkdir(parents=True, exist_ok=True)
        veri = {"k1": self.k1, "b": self.b, "parcalar": [asdict(p) for p in self.parcalar]}
        yol.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def yukle(cls, yol: Path) -> Indeks:
        if not yol.exists():
            raise SystemExit(f"İndeks bulunamadı: {yol}. Önce `rag indeksle <klasör>` çalıştırın.")
        veri = json.loads(yol.read_text(encoding="utf-8"))
        return cls([Parca(**p) for p in veri["parcalar"]], veri["k1"], veri["b"])
