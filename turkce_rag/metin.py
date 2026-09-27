"""Türkçe metni arama için normalleştirme ve parçalama."""

from __future__ import annotations

import re

# Türkçe büyük/küçük harf dönüşümü: Python'un lower() fonksiyonu "I" harfini "i" yapar, "İ" harfini "i̇" yapar.
_KUCUK = str.maketrans({"I": "ı", "İ": "i"})

# Aramada Türkçe karakterli ve karaktersiz yazımlar eşleşsin diye ASCII'ye katlanır ("şirket" = "sirket").
_ASCII = str.maketrans("çğıöşüâîû", "cgiosuaiu")

_KELIME = re.compile(r"[a-z0-9]+")

# Çok sık geçen, anlam taşımayan kelimeler (ASCII'ye katlanmış halleriyle).
DURAK_KELIMELER = frozenset(
    """
    acaba ama ancak artik aslinda az bana bazi belki ben beni benim beri bile bir biri birkac birsey biz bize
    bizi bizim bu buna bunda bundan bunu bunun burada cok cunku da daha dahi de defa diye en gibi hem hep hepsi
    her hic icin ile ise kadar ki kim kime kimi mi mu ne neden nerde nerede nereye nasil niye o olan olarak
    oldu olur ona ondan onlar onlari onlarin onu onun orada oyle sanki sen senin siz sizi sizin sey seyler su
    suna sunu tum ve veya ya yani yine zaten var yok midir mudur nedir nelerdir hangi hangisi kac
    """.split()
)

# Türkçe eklemeli bir dil: "izinler", "iznimi", "izinlerini" aynı köke gider. Kelimeyi ilk 5 harfle sınırlamak
# (F5 kök bulma) Türkçe bilgi erişiminde ağır bir kök bulucuya yakın sonuç veren, bilinen basit bir yöntemdir.
KOK_UZUNLUGU = 5


def normallestir(metin: str) -> str:
    return metin.translate(_KUCUK).lower().translate(_ASCII)


def kok(kelime: str) -> str:
    return kelime[:KOK_UZUNLUGU]


def jetonla(metin: str) -> list[str]:
    """Metni arama jetonlarına ayırır: normalleştir, kelimelere böl, durak kelimeleri at, köke indir."""
    return [kok(k) for k in _KELIME.findall(normallestir(metin)) if k not in DURAK_KELIMELER and len(k) > 1]


def parcala(metin: str, azami_karakter: int = 900) -> list[tuple[str, str]]:
    """Markdown metni (başlık, parça metni) çiftlerine böler.

    Paragraflar sırayla birleştirilir, parça azami uzunluğu aşınca yeni parça başlar. Her parça en yakın
    başlığı taşır; böylece "İzin Politikası > Yıllık izin" gibi bağlam aramaya ve cevaba girer.
    """
    parcalar: list[tuple[str, str]] = []
    basliklar: dict[int, str] = {}
    tampon: list[str] = []

    def bosalt() -> None:
        if tampon:
            baslik = " > ".join(basliklar[d] for d in sorted(basliklar))
            parcalar.append((baslik, "\n\n".join(tampon)))
            tampon.clear()

    for paragraf in re.split(r"\n\s*\n", metin):
        paragraf = paragraf.strip()
        if not paragraf:
            continue
        baslik = re.match(r"^(#{1,6})\s+(.*)", paragraf)
        if baslik and "\n" not in paragraf:
            bosalt()
            derinlik = len(baslik.group(1))
            basliklar = {d: b for d, b in basliklar.items() if d < derinlik}
            basliklar[derinlik] = baslik.group(2).strip()
            continue
        if tampon and sum(len(p) for p in tampon) + len(paragraf) > azami_karakter:
            bosalt()
        tampon.append(paragraf)
    bosalt()
    return parcalar
