"""Bulunan parçalarla Claude'dan kaynak gösteren bir cevap üretir."""

from __future__ import annotations

import os
from collections.abc import Iterator

from .indeks import Sonuc

MODEL = os.environ.get("RAG_MODEL", "claude-opus-5")

SISTEM = """Sen bir belge asistanısın. Soruları yalnızca kullanıcının verdiği numaralı kaynaklara dayanarak, \
Türkçe cevaplarsın.

- Her bilginin sonunda dayandığın kaynağı köşeli parantezle göster: [1], [2][3] gibi.
- Kaynaklarda olmayan bir bilgiyi ekleme, tahmin yürütme. Cevap kaynaklarda yoksa ya da yalnızca kısmen varsa \
bunu açıkça söyle ve eksik kalan kısmı belirt.
- Kaynaklar birbiriyle çelişiyorsa ikisini de kaynağıyla birlikte aktar.
- Kısa ve doğrudan cevap ver; soru bir liste gerektiriyorsa madde kullan."""


def kaynaklari_bicimle(sonuclar: list[Sonuc]) -> str:
    bloklar = []
    for i, s in enumerate(sonuclar, 1):
        baslik = f" — {s.parca.baslik}" if s.parca.baslik else ""
        bloklar.append(f'<kaynak no="{i}" dosya="{s.parca.kaynak}{baslik}">\n{s.parca.metin}\n</kaynak>')
    return "\n\n".join(bloklar)


class KimlikHatasi(RuntimeError):
    pass


KIMLIK_MESAJI = (
    "Claude API kimlik bilgisi bulunamadı. ANTHROPIC_API_KEY ortam değişkenini ayarlayın ya da `ant auth login` "
    "ile giriş yapın. Anahtar olmadan da `rag ara` / arayüzdeki \"Yalnızca ara\" çalışır."
)


def _istek(soru: str, sonuclar: list[Sonuc]) -> dict:
    icerik = f"{kaynaklari_bicimle(sonuclar)}\n\nSoru: {soru}"
    return {
        "model": MODEL,
        "max_tokens": 16000,
        "system": SISTEM,
        "messages": [{"role": "user", "content": icerik}],
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "medium"},
        # Güvenlik sınıflandırıcısı isteği reddederse API, uygun bir modelle aynı isteği sunucu tarafında tekrar dener.
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
    }


def cevapla_akis(soru: str, sonuclar: list[Sonuc]) -> Iterator[str]:
    """Cevabı parça parça üretir. Kaynak bulunmadıysa modeli hiç çağırmaz."""
    if not sonuclar:
        yield "Belgelerde bu soruyla ilgili bir bölüm bulunamadı."
        return

    import anthropic

    client = anthropic.Anthropic()
    try:
        with client.beta.messages.stream(**_istek(soru, sonuclar)) as akis:
            yield from akis.text_stream
            mesaj = akis.get_final_message()
    except anthropic.AuthenticationError as hata:
        raise KimlikHatasi(f"API anahtarı geçersiz: {hata.message}") from hata
    except TypeError as hata:
        # SDK, hiçbir kimlik kaynağı bulamadığında istek anında TypeError verir.
        if "authentication" not in str(hata):
            raise
        raise KimlikHatasi(KIMLIK_MESAJI) from hata
    if mesaj.stop_reason == "refusal":
        yield "\n\n(Model bu soruyu cevaplamayı reddetti.)"
    elif mesaj.stop_reason == "max_tokens":
        yield "\n\n(Cevap uzunluk sınırında kesildi.)"


def cevapla(soru: str, sonuclar: list[Sonuc]) -> str:
    return "".join(cevapla_akis(soru, sonuclar))
