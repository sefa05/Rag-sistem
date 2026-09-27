# Türkçe RAG

Türkçe belgeler üzerinde soru-cevap yapan küçük bir RAG (retrieval-augmented generation) sistemi. Soru önce
belgelerde aranır, bulunan parçalar **Claude**'a verilir ve Claude cevabı yalnızca bu parçalara dayanarak, kaynak
numarası göstererek yazar.

Üç arama yöntemi var, hepsi yerelde çalışır; aramada dış servise veri gitmez:

| Yöntem | Nasıl | Gerekenler |
|---|---|---|
| `bm25` | Kelime eşleşmesi (Okapi BM25), Türkçeye özgü normalleştirme ve kök bulma | Yalnızca Python |
| `anlamsal` | `multilingual-e5-large` gömme vektörleri, kosinüs benzerliği | `.[anlamsal]` paketleri + model (~2,2 GB) |
| `karma` | İki sıralamanın reciprocal rank fusion ile birleşimi | `anlamsal` ile aynı |

- Türkçe normalleştirme: `I/İ` dönüşümü, Türkçe karakterli ve karaktersiz yazımın eşleşmesi
  (`çalışan` = `calisan`), eklerin 5 harflik kökle atılması (`izinlerini` → `izinl`).
- Komut satırı ve yerel web arayüzü (karanlık mod ve mobil uyumlu).
- Modeli çağırmadan retrieval isabetini ölçen, yöntemleri karşılaştıran bir değerlendirme seti.

`derlem/` klasöründeki örnek belgeler **kurmaca** bir şirketin ("Fener Yazılım") çalışan el kitabıdır. Sistemi
denemek için yazıldı; kendi belgelerinizi başka bir klasöre koyup indeksleyebilirsiniz.

## Kurulum

```bash
pip install -e .                    # yalnızca BM25
pip install -e ".[anlamsal]"        # anlamsal ve karma arama için (numpy, onnxruntime, tokenizers)
rag model-indir                     # multilingual-e5-large, ~1,3 GB indirme → ~/.cache/turkce-rag/e5
export ANTHROPIC_API_KEY=...        # yalnızca `sor` ve arayüzdeki "Sor" için gerekli
```

PDF okumak için `pip install -e ".[pdf]"`. Modeli başka bir klasörde tutmak için `RAG_MODEL_KLASORU` ortam
değişkenini ayarlayın.

## Kullanım

```bash
rag indeksle derlem --anlamsal      # parçalar + BM25 + gömme vektörleri → .rag/ (--anlamsal olmadan yalnızca BM25)
rag ara "laptop bozuldu"            # yalnızca retrieval: en ilgili 5 parça (API gerekmez)
rag sor "Yıllık izin kaç gün?"      # parçaları bulur, Claude'dan kaynaklı cevap alır
rag degerlendir                     # yöntemleri soru setinde karşılaştırır (API gerekmez)
rag web                             # http://127.0.0.1:8000 adresinde arayüz
```

`ara`, `sor`, `degerlendir` ve `web` komutları `--yontem bm25|anlamsal|karma` alır. Verilmezse indekste vektör
varsa `anlamsal`, yoksa `bm25` kullanılır.

`rag sor` çıktısının biçimi aşağıdaki gibidir. Kaynak listesi gerçek retrieval çıktısıdır; cevap satırı biçimi
göstermek için elle yazılmış bir örnektir, modelin gerçek cevabı değildir:

```
Yıllık izin hakkı 20 iş günüdür; 5 yılını dolduranlar için 24, 10 yılını dolduranlar için 28 iş günüdür [1].

Kaynaklar:
[1] 01_izin_politikasi.md — İzin Politikası > Yıllık izin  (puan 0.904)
[2] 01_izin_politikasi.md — İzin Politikası > Hastalık izni  (puan 0.859)
[3] 01_izin_politikasi.md — İzin Politikası > Mazeret izinleri  (puan 0.844)
...
```

Model varsayılan olarak `claude-opus-5`'tir; `RAG_MODEL` ortam değişkeniyle değiştirilebilir. İstekte sunucu
tarafı yedek model (`fallbacks: "default"`) açıktır: güvenlik sınıflandırıcısı isteği reddederse API aynı isteği
uygun bir modelle tekrar dener.

## Nasıl çalışır

```
belgeler ──► parçala ──┬─► jetonla ──► BM25 indeksi ──────────┐
                       └─► e5 "passage:" ──► vektörler (.npy) ─┤  .rag/
                                                               │
soru ──► BM25 / e5 "query:" / ikisi (RRF) ──► ilk k parça ─────┴──► numaralı kaynaklar + soru ──► Claude ──► [n] atıflı cevap
```

| Dosya | Görev |
|---|---|
| `turkce_rag/metin.py` | Normalleştirme, durak kelimeler, kök bulma, Markdown'ı başlık bilgisiyle parçalama |
| `turkce_rag/indeks.py` | Belge okuma, BM25 (k1=1,5, b=0,75), anlamsal ve karma arama, kaydetme ve yükleme |
| `turkce_rag/anlamsal.py` | e5 modelini ONNX Runtime ile çalıştırma, model indirme |
| `turkce_rag/cevap.py` | Sistem istemi, kaynak biçimi, Claude'a akışlı istek |
| `turkce_rag/degerlendir.py` | Belge ve bölüm düzeyinde isabet@k ve MRR |
| `turkce_rag/web.py`, `arayuz.html` | Standart kütüphaneyle yazılmış sunucu, NDJSON akışı, tek dosyalık arayüz |

**Parçalama.** Markdown başlıkları parça sınırıdır; bir bölüm 900 karakteri aşarsa paragraf sınırından bölünür.
Her parça başlık yolunu taşır (`İzin Politikası > Yıllık izin`). Başlık hem aramaya hem vektöre girer, modele de
gösterilir.

**Anlamsal arama.** e5'in resmi kullanımı uygulanır: sorgulara `query: `, parçalara `passage: ` öneki, dikkat
maskesine göre ortalama havuzlama ve L2 normalizasyonu. Model, Qdrant'ın fastembed için yayımladığı ONNX
dönüşümüdür. Vektörler indeksin yanına `.npy` olarak kaydedilir; parça metinlerinin özeti de saklanır, vektörler
başka bir indekse aitse yükleme reddedilir. Bu makinede (4 çekirdekli CPU) model 6 saniyede yüklenir, 41 parça
yaklaşık 10 saniyede vektörleşir, bir sorgu ~50 ms sürer (BM25: ~0,04 ms).

**Karma arama.** BM25 puanı ile kosinüs benzerliği farklı ölçeklerde olduğu için puanlar değil sıralar
birleştirilir: her listedeki sırası `r` olan parça `1 / (60 + r)` puan alır. 60, yöntemi öneren çalışmadaki
değerdir, ayarlanmadı.

**Cevap.** Model, kaynaklarda olmayan bilgiyi eklememesi, eksik bilgiyi açıkça söylemesi ve her bilginin
sonunda kaynak numarası vermesi için yönlendirilir. BM25'te hiçbir parça eşleşmezse model hiç çağrılmaz.

## Ölçüm

`degerlendirme/sorular.jsonl` dosyasında 30 soru var. Sorular belgelerdeki ifadeleri tekrarlamaz, günlük dille
yazılmıştır (`"Zam ne zaman yapılıyor?"`, `"Laptopum bozulursa ne olur?"`); bazıları Türkçe karakter kullanmaz.
Her soru için doğru belge ve doğru bölüm işaretlidir. Soru seti anlamsal arama eklenmeden önce yazıldı ve
sonradan değiştirilmedi.

| Düzey | Yöntem | isabet@1 | isabet@3 | isabet@5 | MRR |
|---|---|---|---|---|---|
| Belge | bm25 | %80,0 | %83,3 | %90,0 | 0,833 |
| Belge | anlamsal | **%96,7** | %100 | %100 | **0,983** |
| Belge | karma | %93,3 | %100 | %100 | 0,956 |
| Bölüm | bm25 | %70,0 | %80,0 | %86,7 | 0,761 |
| Bölüm | anlamsal | **%96,7** | %100 | %100 | **0,983** |
| Bölüm | karma | %90,0 | %100 | %100 | 0,939 |

**Farklar anlamlı mı?** 30 soru az, bu yüzden isabet@1 için eşleştirilmiş işaret testi yapıldı (yalnızca bir
yöntemin doğru bulduğu sorular sayılır):

| Karşılaştırma (bölüm düzeyi) | Yalnız ilki doğru | Yalnız ikincisi doğru | p |
|---|---|---|---|
| bm25 – anlamsal | 1 | 9 | 0,021 |
| bm25 – karma | 0 | 6 | 0,031 |
| karma – anlamsal | 1 | 3 | 0,625 |

Anlamsal ve karma arama BM25'ten anlamlı ölçüde iyi. Anlamsal ile karma arasındaki fark ise gürültü düzeyinde;
varsayılan yöntem, ölçülen en iyi sonuç olan `anlamsal` seçildi.

**Anlamsal arama neyi düzeltti?** BM25'in hiç bulamadığı üç soru kelime uyuşmazlığından kaynaklanıyordu:
`"laptop"` ile `"dizüstü bilgisayar"`, `"zam"` ile `"maaş artışı"`, `"ofise gitmek"` ile `"ofiste bir araya
gelir"`. Anlamsal arama üçünde de doğru bölümü ilk sıraya koydu. BM25'te `"Yıllık izin kaç gün?"` sorusunda
ilk sıraya "Mazeret izinleri" geliyordu (kısa parçada "yıllık izinden" ve "gün" geçtiği için); anlamsal aramada
"Yıllık izin" ilk sırada.

**Bölüm düzeyi neden ayrı ölçülüyor?** Belge düzeyi tek başına yanıltıcı: doğru dosya ilk sırada gelse bile gelen
parça dosyanın başka bir bölümü olabilir. Yukarıdaki "Yıllık izin" örneği belge düzeyinde isabet sayılır.

**Karmanın ölçülmeyen avantajı.** Bu soru setinde kod, ürün adı, belge numarası gibi birebir eşleşmesi gereken
terimler yok. Böyle sorgularda kelime araması genelde anlamsal aramadan iyidir ve karma yöntem daha güvenli
olabilir. Derleminiz böyleyse `--yontem karma` ile kendi sorularınızda karşılaştırın.

**Bilinen sınır: "cevap yok" durumu.** BM25 hiçbir kelime eşleşmezse boş döner, model çağrılmaz. Anlamsal arama
her zaman en yakın k parçayı döner ve puanlar dar bir aralıkta toplanır (bu derlemde ~0,77–0,90). Örneğin
belgelerde olmayan `"Kafeteryada vegan yemek var mı?"` sorusu da 0,78 puanla kaynak getirir. Bu yüzden "cevap
yok" kararı eşikle verilmiyor; modelin "kaynaklarda yoksa söyle" talimatına kalıyor.

**BM25'te denenip eklenmeyenler.** Aynı soru setiyle iki ayar denendi, ikisi de gürültü düzeyinde kaldı:

| Deneme | Sonuç |
|---|---|
| Kök uzunluğu 3 / 4 / 5 / 6 / 7 / kök yok | Belge isabet@1: %76,7 / %83,3 / %80,0 / %83,3 / %80,0 / %76,7 |
| Bölüm başlığına ek ağırlık (1–4 kat) | Bölüm isabet@1 %70,0 → %73,3, belge isabet@1 %80,0 → %76,7 |

Farklar 30 soruda 1-2 soru kadar; bu setten ayar seçmek soru setine aşırı uyum olurdu.

Bu ölçüm yalnızca retrieval'ı kapsar. Cevap kalitesi (atıfların doğruluğu, uydurma olup olmadığı) ayrıca
ölçülmedi.

## Testler

```bash
pip install -e ".[test,anlamsal]" && pytest
```

Testler API çağırmaz. Anlamsal arama testlerinin çoğu gerçek model yerine küçük, belirlenimci bir sahte gömücü
kullanır. Gerçek modelle ölçüm yapan test, model indirilmemişse atlanır. İki test değerlendirme setini çalıştırır
ve isabet eşiğin altına düşerse başarısız olur.

## Sonraki adımlar

- Cevap düzeyinde değerlendirme: beklenen cevapla karşılaştırma ve atıfların gerçekten o bilgiyi içerip içermediği.
- Cevabı belgelerde olmayan sorular ekleyip modelin "bilgi yok" deme oranını ölçmek.
- Daha büyük ve gerçek bir derlemle soru setini genişletmek; kod ve özel ad içeren sorularla karma aramayı sınamak.
