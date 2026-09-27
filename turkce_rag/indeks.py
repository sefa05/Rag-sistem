"""Belgeleri okuyup parçalayan ve BM25, anlamsal ya da karma yöntemle arayan indeks."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from .metin import jetonla, parcala

DESTEKLENEN_UZANTILAR = {".md", ".txt", ".pdf"}
YONTEMLER = ("bm25", "anlamsal", "karma")

# Reciprocal rank fusion sabiti. 60, yöntemi öneren çalışmadaki (Cormack vd., 2009) değerdir; ayarlanmadı.
RRF_K = 60


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


def _vektor_yolu(indeks_yolu: Path) -> Path:
    return indeks_yolu.with_suffix(".vektorler.npy")


class Indeks:
    """Okapi BM25 (k1 ve b literatürdeki yaygın varsayılanlar) ve isteğe bağlı gömme vektörleri."""

    def __init__(self, parcalar: list[Parca], k1: float = 1.5, b: float = 0.75):
        self.parcalar = parcalar
        self.k1 = k1
        self.b = b
        self.vektorler = None  # numpy matrisi; anlamsal_hazirla() ya da yukle() doldurur
        self._gomucu = None
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

    @property
    def anlamsal_var(self) -> bool:
        return self.vektorler is not None

    def _parca_metinleri(self) -> list[str]:
        from .anlamsal import parca_metni

        return [parca_metni(p.baslik, p.metin) for p in self.parcalar]

    def anlamsal_hazirla(self, gomucu) -> None:
        self._gomucu = gomucu
        self.vektorler = gomucu.gom(self._parca_metinleri(), "passage")

    def _bm25(self, sorgu: str) -> list[Sonuc]:
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
        return sonuclar

    def _anlamsal(self, sorgu: str) -> list[Sonuc]:
        if not self.anlamsal_var:
            raise SystemExit("Bu indekste anlamsal vektör yok. `rag indeksle <klasör> --anlamsal` ile yeniden oluşturun.")
        if self._gomucu is None:
            from .anlamsal import Gomucu

            self._gomucu = Gomucu()
        benzerlik = self.vektorler @ self._gomucu.gom([sorgu], "query")[0]
        sira = benzerlik.argsort()[::-1]
        return [Sonuc(self.parcalar[i], float(benzerlik[i])) for i in sira]

    def _karma(self, sorgu: str) -> list[Sonuc]:
        """İki sıralamayı puanlarına değil sıralarına göre birleştirir; BM25 ve kosinüs ölçekleri farklı olduğu için."""
        puanlar: Counter[int] = Counter()
        for liste in (self._bm25(sorgu), self._anlamsal(sorgu)):
            for sira, s in enumerate(liste, 1):
                puanlar[s.parca.kimlik] += 1 / (RRF_K + sira)
        return [Sonuc(self.parcalar[i], p) for i, p in puanlar.most_common()]

    def ara(self, sorgu: str, k: int = 5, yontem: str = "bm25") -> list[Sonuc]:
        if yontem not in YONTEMLER:
            raise ValueError(f"Bilinmeyen yöntem: {yontem}")
        return getattr(self, f"_{yontem}")(sorgu)[:k]

    def varsayilan_yontem(self) -> str:
        # Örnek soru setinde anlamsal arama BM25'ten anlamlı ölçüde iyi, karmadan ise farksız çıktı (README > Ölçüm).
        return "anlamsal" if self.anlamsal_var else "bm25"

    def kaydet(self, yol: Path) -> None:
        yol.parent.mkdir(parents=True, exist_ok=True)
        veri = {"k1": self.k1, "b": self.b, "parcalar": [asdict(p) for p in self.parcalar]}
        vektor_yolu = _vektor_yolu(yol)
        if self.anlamsal_var:
            import numpy as np
            from .anlamsal import parca_ozeti

            np.save(vektor_yolu, self.vektorler)
            veri["vektor_ozeti"] = parca_ozeti(self._parca_metinleri())
        elif vektor_yolu.exists():
            vektor_yolu.unlink()  # eski indeksten kalan vektörler yeni parçalara ait değil
        yol.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def yukle(cls, yol: Path) -> Indeks:
        if not yol.exists():
            raise SystemExit(f"İndeks bulunamadı: {yol}. Önce `rag indeksle <klasör>` çalıştırın.")
        veri = json.loads(yol.read_text(encoding="utf-8"))
        indeks = cls([Parca(**p) for p in veri["parcalar"]], veri["k1"], veri["b"])
        if "vektor_ozeti" in veri:
            from .anlamsal import bagimliliklar, parca_ozeti

            np = bagimliliklar()[0]
            if parca_ozeti(indeks._parca_metinleri()) != veri["vektor_ozeti"]:
                raise SystemExit(f"{_vektor_yolu(yol)} bu indeksin parçalarına ait değil; indeksi yeniden oluşturun.")
            indeks.vektorler = np.load(_vektor_yolu(yol))
        return indeks
