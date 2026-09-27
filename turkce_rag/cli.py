"""Komut satırı: rag indeksle | ara | sor | degerlendir | web | model-indir"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .indeks import YONTEMLER, Indeks

VARSAYILAN_INDEKS = Path(".rag/indeks.json")


def _indeksle(args: argparse.Namespace) -> None:
    indeks = Indeks.klasorden(Path(args.klasor), args.parca_boyu)
    if args.anlamsal:
        from .anlamsal import Gomucu

        print(f"{len(indeks.parcalar)} parça için gömme vektörleri hesaplanıyor…")
        indeks.anlamsal_hazirla(Gomucu(Path(args.model_klasoru)))
    indeks.kaydet(Path(args.indeks))
    belgeler = {p.kaynak for p in indeks.parcalar}
    ek = " (BM25 + anlamsal)" if indeks.anlamsal_var else " (yalnızca BM25)"
    print(f"{len(belgeler)} belge, {len(indeks.parcalar)} parça indekslendi{ek} → {args.indeks}")


def _yontem(indeks: Indeks, args: argparse.Namespace) -> str:
    return args.yontem or indeks.varsayilan_yontem()


def _kaynaklari_yaz(sonuclar) -> None:
    for i, s in enumerate(sonuclar, 1):
        baslik = f" — {s.parca.baslik}" if s.parca.baslik else ""
        print(f"[{i}] {s.parca.kaynak}{baslik}  (puan {s.puan:.3g})")


def _ara(args: argparse.Namespace) -> None:
    indeks = Indeks.yukle(Path(args.indeks))
    sonuclar = indeks.ara(args.sorgu, args.k, _yontem(indeks, args))
    if not sonuclar:
        print("Eşleşen parça yok.")
    for i, s in enumerate(sonuclar, 1):
        baslik = f" — {s.parca.baslik}" if s.parca.baslik else ""
        print(f"\n[{i}] {s.parca.kaynak}{baslik}  (puan {s.puan:.3g})\n{s.parca.metin}")


def _sor(args: argparse.Namespace) -> None:
    from .cevap import KimlikHatasi, cevapla_akis

    indeks = Indeks.yukle(Path(args.indeks))
    sonuclar = indeks.ara(args.soru, args.k, _yontem(indeks, args))
    try:
        for parca in cevapla_akis(args.soru, sonuclar):
            print(parca, end="", flush=True)
    except KimlikHatasi as hata:
        raise SystemExit(str(hata)) from None
    print("\n\nKaynaklar:")
    _kaynaklari_yaz(sonuclar)


def _degerlendir(args: argparse.Namespace) -> None:
    from .degerlendir import degerlendir, sorulari_oku

    indeks = Indeks.yukle(Path(args.indeks))
    sorular = sorulari_oku(Path(args.sorular))
    # Yöntem verilmezse indeksin desteklediği tüm yöntemler aynı sorularla karşılaştırılır.
    yontemler = [args.yontem] if args.yontem else (list(YONTEMLER) if indeks.anlamsal_var else ["bm25"])
    ozetler = {y: degerlendir(indeks, sorular, args.k, y) for y in yontemler}

    ilk = next(iter(ozetler.values()))
    sira = lambda s: str(s) if s else "-"  # noqa: E731
    genislik = 5 * len(ozetler)
    print(f"{'belge sırası':^{genislik}}  {'bölüm sırası':^{genislik}}" if ilk.bolumlu else "belge sırası")
    print(" ".join(f"{y[:4]:>4}" for y in ozetler) + ("  " + " ".join(f"{y[:4]:>4}" for y in ozetler)) * ilk.bolumlu)
    for i, s in enumerate(ilk.sonuclar):
        belge = " ".join(f"{sira(o.sonuclar[i].belge_sirasi):>4}" for o in ozetler.values())
        bolum = " ".join(f"{sira(o.sonuclar[i].bolum_sirasi):>4}" for o in ozetler.values()) if ilk.bolumlu else ""
        print(f"{belge}  {bolum}  {s.soru}")

    print(f"\n{len(ilk.sonuclar)} soru, ilk {ilk.k} sonuç ('-': bulunamadı)\n")
    print(f"{'düzey':<6} {'yöntem':<9} {'isabet@1':>9} {'isabet@3':>9} {f'isabet@{ilk.k}':>9} {'MRR':>6}")
    for duzey in ("belge", "bolum") if ilk.bolumlu else ("belge",):
        for y, o in ozetler.items():
            print(f"{'bölüm' if duzey == 'bolum' else 'belge':<6} {y:<9} {o.isabet(1, duzey) * 100:>8.1f}% "
                  f"{o.isabet(3, duzey) * 100:>8.1f}% {o.isabet(o.k, duzey) * 100:>8.1f}% {o.mrr(duzey):>6.3f}")


def _web(args: argparse.Namespace) -> None:
    from .web import calistir

    indeks = Indeks.yukle(Path(args.indeks))
    calistir(indeks, args.adres, args.port, args.k, _yontem(indeks, args))


def _model_indir(args: argparse.Namespace) -> None:
    from .anlamsal import model_indir

    model_indir(Path(args.model_klasoru))


def main(argv: list[str] | None = None) -> None:
    from .anlamsal import VARSAYILAN_MODEL_KLASORU

    ana = argparse.ArgumentParser(prog="rag", description="Türkçe belgeler için BM25 / anlamsal arama + Claude RAG")
    ana.add_argument("--indeks", default=str(VARSAYILAN_INDEKS), help="indeks dosyası (varsayılan: %(default)s)")
    alt = ana.add_subparsers(dest="komut", required=True)

    def yontem_ekle(p: argparse.ArgumentParser) -> None:
        p.add_argument("--yontem", choices=YONTEMLER,
                       help="arama yöntemi (varsayılan: indekste vektör varsa anlamsal, yoksa bm25)")

    def model_klasoru_ekle(p: argparse.ArgumentParser) -> None:
        p.add_argument("--model-klasoru", default=str(VARSAYILAN_MODEL_KLASORU),
                       help="gömme modelinin klasörü (varsayılan: %(default)s, RAG_MODEL_KLASORU ile de verilebilir)")

    p = alt.add_parser("indeksle", help="bir klasördeki .md/.txt/.pdf belgeleri indeksle")
    p.add_argument("klasor")
    p.add_argument("--parca-boyu", type=int, default=900, help="parça başına azami karakter")
    p.add_argument("--anlamsal", action="store_true", help="anlamsal arama için gömme vektörlerini de hesapla")
    model_klasoru_ekle(p)
    p.set_defaults(islev=_indeksle)

    p = alt.add_parser("ara", help="yalnızca retrieval: en ilgili parçaları göster (API gerekmez)")
    p.add_argument("sorgu")
    p.add_argument("-k", type=int, default=5)
    yontem_ekle(p)
    p.set_defaults(islev=_ara)

    p = alt.add_parser("sor", help="soruyu bulunan parçalarla Claude'a cevaplat")
    p.add_argument("soru")
    p.add_argument("-k", type=int, default=5)
    yontem_ekle(p)
    p.set_defaults(islev=_sor)

    p = alt.add_parser("degerlendir", help="retrieval isabetini soru setiyle ölç (API gerekmez)")
    p.add_argument("sorular", nargs="?", default="degerlendirme/sorular.jsonl")
    p.add_argument("-k", type=int, default=5)
    yontem_ekle(p)
    p.set_defaults(islev=_degerlendir)

    p = alt.add_parser("web", help="yerel web arayüzünü başlat")
    p.add_argument("--adres", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("-k", type=int, default=5)
    yontem_ekle(p)
    p.set_defaults(islev=_web)

    p = alt.add_parser("model-indir", help="anlamsal arama için multilingual-e5-large modelini indir (~1,3 GB)")
    model_klasoru_ekle(p)
    p.set_defaults(islev=_model_indir)

    args = ana.parse_args(argv)
    try:
        args.islev(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
