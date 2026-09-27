# Türkçe RAG

Türkçe belgeler üzerinde soru-cevap yapan küçük ve bağımlılığı az bir RAG (retrieval-augmented generation) sistemi.
Soru önce belgelerde **BM25** ile aranır, bulunan parçalar **Claude**'a verilir ve Claude cevabı yalnızca bu
parçalara dayanarak, kaynak numarası göstererek yazar.

- Retrieval tamamen yereldir: embedding servisi ya da vektör veritabanı yok, sonuçlar her çalıştırmada aynıdır.
- Türkçeye özgü normalleştirme: `I/İ` dönüşümü, Türkçe karakterli ve karaktersiz yazımın eşleşmesi
  (`çalışan` = `calisan`), eklerin 5 harflik kökle atılması (`izinlerini` → `izinl`).
- Komut satırı ve yerel web arayüzü (karanlık mod ve mobil uyumlu).
- Modeli çağırmadan retrieval isabetini ölçen bir değerlendirme seti.

`derlem/` klasöründeki örnek belgeler **kurmaca** bir şirketin ("Fener Yazılım") çalışan el kitabıdır. Sistemi
denemek için yazıldı; kendi belgelerinizi başka bir klasöre koyup indeksleyebilirsiniz.

## Kurulum

```bash
pip install -e .          # PDF okumak için: pip install -e ".[pdf]"
export ANTHROPIC_API_KEY=...   # yalnızca `sor` ve arayüzdeki "Sor" için gerekli
```

## Kullanım

```bash
rag indeksle derlem                 # .md / .txt / .pdf belgeleri parçalara ayırıp .rag/indeks.json'a yazar
rag ara "taksi masrafı"             # yalnızca retrieval: en ilgili 5 parça (API gerekmez)
rag sor "Yıllık izin kaç gün?"      # parçaları bulur, Claude'dan kaynaklı cevap alır
rag degerlendir                     # retrieval isabetini ölçer (API gerekmez)
rag web                             # http://127.0.0.1:8000 adresinde arayüz
```

`rag sor` çıktısının biçimi aşağıdaki gibidir. Kaynak listesi gerçek retrieval çıktısıdır; cevap satırı biçimi
göstermek için elle yazılmış bir örnektir, modelin gerçek cevabı değildir:

```
Yıllık izin hakkı 20 iş günüdür; 5 yılını dolduranlar için 24, 10 yılını dolduranlar için 28 iş günüdür [3].

Kaynaklar:
[1] 01_izin_politikasi.md — İzin Politikası > Mazeret izinleri  (puan 7.28)
[2] 01_izin_politikasi.md — İzin Politikası > Hastalık izni  (puan 6.11)
[3] 01_izin_politikasi.md — İzin Politikası > Yıllık izin  (puan 5.43)
...
```

Model varsayılan olarak `claude-opus-5`'tir; `RAG_MODEL` ortam değişkeniyle değiştirilebilir. İstekte sunucu
tarafı yedek model (`fallbacks: "default"`) açıktır: güvenlik sınıflandırıcısı isteği reddederse API aynı isteği
uygun bir modelle tekrar dener.

## Nasıl çalışır

```
belgeler ──► parçala ──► jetonla ──► BM25 indeksi (.rag/indeks.json)
                                          │
soru ──► jetonla ──► BM25 ile ilk k parça ┴──► numaralı kaynaklar + soru ──► Claude ──► [n] atıflı cevap
```

| Dosya | Görev |
|---|---|
| `turkce_rag/metin.py` | Normalleştirme, durak kelimeler, kök bulma, Markdown'ı başlık bilgisiyle parçalama |
| `turkce_rag/indeks.py` | Belge okuma, Okapi BM25 (k1=1,5, b=0,75), indeksi kaydetme ve yükleme |
| `turkce_rag/cevap.py` | Sistem istemi, kaynak biçimi, Claude'a akışlı istek |
| `turkce_rag/degerlendir.py` | Belge ve bölüm düzeyinde isabet@k ve MRR |
| `turkce_rag/web.py`, `arayuz.html` | Standart kütüphaneyle yazılmış sunucu, NDJSON akışı, tek dosyalık arayüz |

**Parçalama.** Markdown başlıkları parça sınırıdır; bir bölüm 900 karakteri aşarsa paragraf sınırından bölünür.
Her parça başlık yolunu taşır (`İzin Politikası > Yıllık izin`). Başlık hem aramaya girer hem modele gösterilir.

**Cevap.** Model, kaynaklarda olmayan bilgiyi eklememesi, eksik bilgiyi açıkça söylemesi ve her bilginin
sonunda kaynak numarası vermesi için yönlendirilir. Hiçbir parça eşleşmezse model hiç çağrılmaz.

## Ölçüm

`degerlendirme/sorular.jsonl` dosyasında 30 soru var. Sorular belgelerdeki ifadeleri tekrarlamaz, günlük dille
yazılmıştır (`"Zam ne zaman yapılıyor?"`, `"Laptopum bozulursa ne olur?"`); bazıları Türkçe karakter kullanmaz.
Her soru için doğru belge ve doğru bölüm işaretlidir.

| Düzey | isabet@1 | isabet@3 | isabet@5 | MRR |
|---|---|---|---|---|
| Belge | %80,0 | %83,3 | %90,0 | 0,833 |
| Bölüm | %70,0 | %80,0 | %86,7 | 0,761 |

**Bölüm düzeyi neden ayrı ölçülüyor?** Belge düzeyi tek başına yanıltıcı. Doğru dosya ilk sırada gelse bile gelen
parça dosyanın başka bir bölümü olabilir. Örneğin `"Yıllık izin kaç gün?"` sorusunda ilk sırada "Mazeret
izinleri" gelir, çünkü o kısa parçada "yıllık izinden" ve "gün" geçer. Asıl cevap 3. sıradadır. Belge düzeyinde
bu durum isabet sayılır.

**Kaçırılan sorular kelime uyuşmazlığından.** BM25 yalnızca ortak kelimeleri görür. `"laptop"` ile
`"dizüstü bilgisayar"`, `"zam"` ile `"maaş artışı"`, `"ofise gitmek"` ile `"ofiste bir araya gelir"` eşleşmez.
Bu, kelime tabanlı aramanın bilinen sınırı; embedding tabanlı arama tam olarak bu sorunu çözer.

**Denenip eklenmeyenler.** Aynı soru setiyle iki ayar denendi, ikisi de gürültü düzeyinde kaldı:

| Deneme | Sonuç |
|---|---|
| Kök uzunluğu 3 / 4 / 5 / 6 / 7 / kök yok | Belge isabet@1: %76,7 / %83,3 / %80,0 / %83,3 / %80,0 / %76,7 |
| Bölüm başlığına ek ağırlık (1–4 kat) | Bölüm isabet@1 %70,0 → %73,3, belge isabet@1 %80,0 → %76,7 |

Farklar 30 soruda 1-2 soru kadar. Bu setten ayar seçmek soru setine aşırı uyum olurdu. Kök uzunluğu
literatürdeki yaygın değer olan 5'te bırakıldı, başlık ağırlığı eklenmedi.

Bu ölçüm yalnızca retrieval'ı kapsar. Cevap kalitesi (atıfların doğruluğu, uydurma olup olmadığı) ayrıca
ölçülmedi.

## Testler

```bash
pip install -e ".[test]" && pytest
```

Testler API çağırmaz. İçlerinden biri değerlendirme setini çalıştırır ve isabet eşiğin altına düşerse başarısız
olur; kök bulma ya da parçalamadaki bir değişikliğin retrieval'ı bozduğu böylece fark edilir.

## Sonraki adımlar

- Embedding tabanlı arama ekleyip BM25 ile aynı soru setinde karşılaştırmak; ikisini birleştiren karma arama
  (ör. reciprocal rank fusion).
- Cevap düzeyinde değerlendirme: beklenen cevapla karşılaştırma ve atıfların gerçekten o bilgiyi içerip içermediği.
- Daha büyük ve gerçek bir derlemle soru setini genişletmek.
