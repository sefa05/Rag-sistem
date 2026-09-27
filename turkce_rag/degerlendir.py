"""Retrieval ölçümü: her soru için doğru belgenin ve doğru bölümün kaçıncı sırada geldiği.

Bu ölçüm modeli çağırmaz, API anahtarı gerektirmez ve her çalıştırmada aynı sonucu verir. RAG'de cevap kalitesinin
tavanı retrieval'dır: doğru parça bağlama girmezse model de doğru cevabı veremez.

Belge düzeyi tek başına yanıltıcıdır: doğru dosya ilk sıradaysa ama gelen parça dosyanın başka bir bölümüyse,
belge düzeyinde isabet sayılır, oysa modele giden en iyi parça yanlış bölümdür. Bu yüzden soru setinde bölüm
de ("bolum": parçanın en alt başlığı) varsa ayrıca ölçülür.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .indeks import Indeks


@dataclass
class SoruSonucu:
    soru: str
    belge_sirasi: int | None  # doğru belgenin ilk göründüğü sıra (1'den başlar); ilk k içinde yoksa None
    bolum_sirasi: int | None  # doğru bölümün sırası; soru bölüm belirtmiyorsa ya da ilk k içinde yoksa None


@dataclass
class Ozet:
    sonuclar: list[SoruSonucu]
    k: int
    bolumlu: bool  # tüm sorularda beklenen bölüm var mı

    @staticmethod
    def _isabet(siralar: list[int | None], n: int) -> float:
        return sum(1 for s in siralar if s is not None and s <= n) / len(siralar)

    @staticmethod
    def _mrr(siralar: list[int | None]) -> float:
        return sum(1 / s for s in siralar if s) / len(siralar)

    def isabet(self, n: int, duzey: str = "belge") -> float:
        return self._isabet(self._siralar(duzey), n)

    def mrr(self, duzey: str = "belge") -> float:
        return self._mrr(self._siralar(duzey))

    def _siralar(self, duzey: str) -> list[int | None]:
        return [s.belge_sirasi if duzey == "belge" else s.bolum_sirasi for s in self.sonuclar]


def sorulari_oku(yol: Path) -> list[dict]:
    return [json.loads(satir) for satir in yol.read_text(encoding="utf-8").splitlines() if satir.strip()]


def _ilk_sira(kosullar: list[bool]) -> int | None:
    return kosullar.index(True) + 1 if True in kosullar else None


def degerlendir(indeks: Indeks, sorular: list[dict], k: int = 5) -> Ozet:
    sonuclar = []
    for s in sorular:
        parcalar = [r.parca for r in indeks.ara(s["soru"], k)]
        belge = _ilk_sira([p.kaynak == s["belge"] for p in parcalar])
        bolum = None
        if s.get("bolum"):
            bolum = _ilk_sira([p.kaynak == s["belge"] and p.baslik.split(" > ")[-1] == s["bolum"] for p in parcalar])
        sonuclar.append(SoruSonucu(s["soru"], belge, bolum))
    return Ozet(sonuclar, k, all(s.get("bolum") for s in sorular))
