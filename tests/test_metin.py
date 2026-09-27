from turkce_rag.metin import jetonla, normallestir, parcala


def test_turkce_buyuk_harfler_dogru_kuculur():
    assert normallestir("IŞIK İzmir") == "isik izmir"


def test_turkce_karaktersiz_yazim_eslesir():
    assert jetonla("çalışanlara ödeme") == jetonla("calisanlara odeme")


def test_ekler_ayni_koke_iner_ve_durak_kelimeler_atilir():
    assert jetonla("izinler") == jetonla("izinlerini") == ["izinl"]
    assert jetonla("bu ve ile için") == []


def test_parcalar_basligi_tasir_ve_boyu_asmaz():
    metin = "# Ana\n\nGiriş.\n\n## Alt\n\n" + "\n\n".join(["x" * 300] * 4)
    parcalar = parcala(metin, azami_karakter=700)
    assert parcalar[0] == ("Ana", "Giriş.")
    assert all(baslik == "Ana > Alt" for baslik, _ in parcalar[1:])
    assert all(len(m) <= 700 for _, m in parcalar[1:])
    assert sum(m.count("x" * 300) for _, m in parcalar) == 4
