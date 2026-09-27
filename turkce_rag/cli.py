"""Komut satırı: rag indeksle | ara | sor | degerlendir | web"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .indeks import Indeks

VARSAYILAN_INDEKS = Path(".rag/indeks.json")


def _indeksle(args: argparse.Namespace) -> None:
    indeks = Indeks.klasorden(Path(args.klasor), args.parca_boyu)
    indeks.kaydet(Path(args.indeks))
    belgeler = {p.kaynak for p in indeks.parcalar}
    print(f"{len(belgeler)} belge, {len(indeks.parcalar)} parça indekslendi → {args.indeks}")


def _kaynaklari_yaz(sonuclar) -> None:
    for i, s in enumerate(sonuclar, 1):
        baslik = f" — {s.parca.baslik}" if s.parca.baslik else ""
        print(f"[{i}] {s.parca.kaynak}{baslik}  (puan {s.puan:.2f})")


def _ara(args: argparse.Namespace) -> None:
    sonuclar = Indeks.yukle(Path(args.indeks)).ara(args.sorgu, args.k)
    if not sonuclar:
        print("Eşleşen parça yok.")
    for i, s in enumerate(sonuclar, 1):
        baslik = f" — {s.parca.baslik}" if s.parca.baslik else ""
        print(f"\n[{i}] {s.parca.kaynak}{baslik}  (puan {s.puan:.2f})\n{s.parca.metin}")


def _sor(args: argparse.Namespace) -> None:
    from .cevap import KimlikHatasi, cevapla_akis

    sonuclar = Indeks.yukle(Path(args.indeks)).ara(args.soru, args.k)
    try:
        for parca in cevapla_akis(args.soru, sonuclar):
            print(parca, end="", flush=True)
    except KimlikHatasi as hata:
        raise SystemExit(str(hata)) from None
    print("\n\nKaynaklar:")
    _kaynaklari_yaz(sonuclar)


def _degerlendir(args: argparse.Namespace) -> None:
    from .degerlendir import degerlendir, sorulari_oku

    ozet = degerlendir(Indeks.yukle(Path(args.indeks)), sorulari_oku(Path(args.sorular)), args.k)
    sira = lambda s: str(s) if s else "-"  # noqa: E731
    print(f"{'belge':>5} {'bölüm':>5}  soru")
    for s in ozet.sonuclar:
        print(f"{sira(s.belge_sirasi):>5} {sira(s.bolum_sirasi) if ozet.bolumlu else '':>5}  {s.soru}")
    print(f"\n{len(ozet.sonuclar)} soru, ilk {ozet.k} sonuç ('-': bulunamadı)")
    for duzey in ("belge", "bölüm") if ozet.bolumlu else ("belge",):
        d = "belge" if duzey == "belge" else "bolum"
        print(f"{duzey:>5}: isabet@1 %{ozet.isabet(1, d) * 100:.1f} | isabet@3 %{ozet.isabet(3, d) * 100:.1f} | "
              f"isabet@{ozet.k} %{ozet.isabet(ozet.k, d) * 100:.1f} | MRR {ozet.mrr(d):.3f}")


def _web(args: argparse.Namespace) -> None:
    from .web import calistir

    calistir(Indeks.yukle(Path(args.indeks)), args.adres, args.port, args.k)


def main(argv: list[str] | None = None) -> None:
    ana = argparse.ArgumentParser(prog="rag", description="Türkçe belgeler için BM25 + Claude RAG sistemi")
    ana.add_argument("--indeks", default=str(VARSAYILAN_INDEKS), help="indeks dosyası (varsayılan: %(default)s)")
    alt = ana.add_subparsers(dest="komut", required=True)

    p = alt.add_parser("indeksle", help="bir klasördeki .md/.txt/.pdf belgeleri indeksle")
    p.add_argument("klasor")
    p.add_argument("--parca-boyu", type=int, default=900, help="parça başına azami karakter")
    p.set_defaults(islev=_indeksle)

    p = alt.add_parser("ara", help="yalnızca retrieval: en ilgili parçaları göster (API gerekmez)")
    p.add_argument("sorgu")
    p.add_argument("-k", type=int, default=5)
    p.set_defaults(islev=_ara)

    p = alt.add_parser("sor", help="soruyu bulunan parçalarla Claude'a cevaplat")
    p.add_argument("soru")
    p.add_argument("-k", type=int, default=5)
    p.set_defaults(islev=_sor)

    p = alt.add_parser("degerlendir", help="retrieval isabetini soru setiyle ölç (API gerekmez)")
    p.add_argument("sorular", nargs="?", default="degerlendirme/sorular.jsonl")
    p.add_argument("-k", type=int, default=5)
    p.set_defaults(islev=_degerlendir)

    p = alt.add_parser("web", help="yerel web arayüzünü başlat")
    p.add_argument("--adres", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("-k", type=int, default=5)
    p.set_defaults(islev=_web)

    args = ana.parse_args(argv)
    try:
        args.islev(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
