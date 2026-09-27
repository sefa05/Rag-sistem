import json
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from turkce_rag.anlamsal import VARSAYILAN_MODEL_KLASORU  # noqa: E402
from turkce_rag.degerlendir import degerlendir, sorulari_oku  # noqa: E402
from turkce_rag.indeks import RRF_K, Indeks, Parca  # noqa: E402
from turkce_rag.metin import jetonla  # noqa: E402

KOK = Path(__file__).parent.parent


class SahteGomucu:
    """Modelsiz testler için: jetonları sabit boyutlu vektöre katlayan, belirlenimci bir gömücü."""

    def gom(self, metinler, tur):
        vektorler = np.zeros((len(metinler), 64), dtype=np.float32)
        for i, metin in enumerate(metinler):
            for jeton in jetonla(metin):
                vektorler[i, sum(map(ord, jeton)) % 64] += 1
        return vektorler / np.maximum(np.linalg.norm(vektorler, axis=1, keepdims=True), 1e-9)


@pytest.fixture
def indeks():
    parcalar = [
        Parca(0, "a.md", "Kedi", "Kediler süt içer ve uyur."),
        Parca(1, "b.md", "Köpek", "Köpekler kemik sever, parkta koşar."),
        Parca(2, "c.md", "Kuş", "Kuşlar uçar, yuva yapar."),
    ]
    ix = Indeks(parcalar)
    ix.anlamsal_hazirla(SahteGomucu())
    return ix


def test_vektorler_birim_uzunlukta_ve_parca_sayisinca(indeks):
    assert indeks.vektorler.shape == (3, 64)
    assert np.allclose(np.linalg.norm(indeks.vektorler, axis=1), 1)


def test_anlamsal_tum_parcalari_benzerlige_gore_siralar(indeks):
    sonuclar = indeks.ara("köpekler parkta", 3, "anlamsal")
    assert sonuclar[0].parca.kaynak == "b.md"
    assert [s.puan for s in sonuclar] == sorted((s.puan for s in sonuclar), reverse=True)


def test_karma_iki_listede_de_ilk_olana_rrf_puanini_verir(indeks):
    ilk = indeks.ara("köpekler parkta", 1, "karma")[0]
    assert ilk.parca.kaynak == "b.md"
    assert ilk.puan == pytest.approx(2 / (RRF_K + 1))


def test_varsayilan_yontem_vektor_varsa_anlamsal(indeks):
    assert indeks.varsayilan_yontem() == "anlamsal"
    assert Indeks(indeks.parcalar).varsayilan_yontem() == "bm25"


def test_vektorler_kaydedilip_yuklenir(indeks, tmp_path):
    yol = tmp_path / "indeks.json"
    indeks.kaydet(yol)
    yuklenen = Indeks.yukle(yol)
    assert np.array_equal(yuklenen.vektorler, indeks.vektorler)


def test_baska_parcalara_ait_vektorler_reddedilir(indeks, tmp_path):
    yol = tmp_path / "indeks.json"
    indeks.kaydet(yol)
    veri = json.loads(yol.read_text(encoding="utf-8"))
    veri["parcalar"][0]["metin"] = "değişti"
    yol.write_text(json.dumps(veri), encoding="utf-8")
    with pytest.raises(SystemExit, match="ait değil"):
        Indeks.yukle(yol)


def test_vektorsuz_yeniden_indeksleme_eski_vektorleri_siler(indeks, tmp_path):
    yol = tmp_path / "indeks.json"
    indeks.kaydet(yol)
    Indeks(indeks.parcalar).kaydet(yol)
    assert not yol.with_suffix(".vektorler.npy").exists()
    assert not Indeks.yukle(yol).anlamsal_var


def test_vektorsuz_indekste_anlamsal_arama_aciklayici_hata_verir():
    with pytest.raises(SystemExit, match="--anlamsal"):
        Indeks([Parca(0, "a.md", "", "metin")]).ara("metin", 1, "anlamsal")


@pytest.mark.skipif(not (VARSAYILAN_MODEL_KLASORU / "model.onnx").exists(), reason="gömme modeli indirilmemiş")
def test_gercek_model_ile_isabet_gerilemedi():
    pytest.importorskip("onnxruntime")
    from turkce_rag.anlamsal import Gomucu

    ix = Indeks.klasorden(KOK / "derlem")
    ix.anlamsal_hazirla(Gomucu())
    # Eşik, ölçülen değerin (bölüm isabet@1 %96,7) biraz altında.
    ozet = degerlendir(ix, sorulari_oku(KOK / "degerlendirme" / "sorular.jsonl"), yontem="anlamsal")
    assert ozet.isabet(1, "bolum") >= 0.9
    # BM25'in kelime uyuşmazlığı yüzünden hiç bulamadığı soru.
    assert ix.ara("Laptopum bozulursa ne olur?", 1, "anlamsal")[0].parca.baslik.endswith("Dizüstü bilgisayar")
