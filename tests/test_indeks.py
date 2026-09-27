from pathlib import Path

import pytest

from turkce_rag.degerlendir import degerlendir, sorulari_oku
from turkce_rag.indeks import Indeks

KOK = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def indeks():
    return Indeks.klasorden(KOK / "derlem")


def test_ilgili_belge_ilk_sirada(indeks):
    assert indeks.ara("taksi masrafı geri ödeme")[0].parca.kaynak == "03_masraf_yonetimi.md"


def test_eslesme_yoksa_bos_doner(indeks):
    assert indeks.ara("zzzz qqqq") == []


def test_kaydet_yukle_ayni_sonucu_verir(indeks, tmp_path):
    yol = tmp_path / "indeks.json"
    indeks.kaydet(yol)
    once = [(s.parca.kimlik, round(s.puan, 6)) for s in indeks.ara("yıllık izin devri")]
    sonra = [(s.parca.kimlik, round(s.puan, 6)) for s in Indeks.yukle(yol).ara("yıllık izin devri")]
    assert once == sonra


def test_retrieval_isabeti_gerilemedi(indeks):
    # Eşikler ölçülen değerlerin (isabet@5: belge %90, bölüm %86,7) biraz altında: kök bulma ya da parçalama
    # değişip isabeti düşürürse bu test uyarır.
    ozet = degerlendir(indeks, sorulari_oku(KOK / "degerlendirme" / "sorular.jsonl"))
    assert ozet.bolumlu
    assert ozet.isabet(5) >= 0.85
    assert ozet.isabet(5, "bolum") >= 0.8
