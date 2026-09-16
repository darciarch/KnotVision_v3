# img2texcelle – Kullanım Kılavuzu

Bu belge, projeyi hiç bilmeyen birinin aracı kurup kullanabilmesi ve arka planda
ne yapıldığını anlayabilmesi için yazıldı. Önce kavramlar, sonra kurulum ve
komutlar, sonra her adımın ayrıntısı, en sonda da sık karşılaşılan sorunlar
anlatılıyor.

---

## 1. Bu araç ne yapar?

`img2texcelle`, bitmiş bir **halı deseni görüntüsünü** (jpg/png) alır ve onu
Texcelle programının okuyabildiği **indeksli (paletli) TIFF veya BMP** dosyasına
çevirir.

Texcelle, halı/dokuma tezgâhları için kullanılan bir CAD programıdır. Texcelle
dosyasında:

- **Her palet girişi bir ipliktir.** Dosyada 5 renk varsa halıda 5 iplik
  kullanılır. Ara renk, gölge, geçiş yoktur.
- **Her piksel bir düğümdür (nokta/ilmek).** Görüntüdeki 1 piksel, halıdaki 1
  düğüme karşılık gelir.

Bu yüzden çıktı dosyası sadece palet renklerinden oluşmalı; içinde tek
piksellik gürültü, benek veya kenarlarda "iki rengin arası" karışım renkleri
bulunmamalıdır. Sonuçlar çıktıya yakınlaştırılarak (zoom) gözle kontrol edilir.

Kısaca: **Gemini gibi bir araçla üretilmiş düz renkli halı deseni → dokunabilir
Texcelle dosyası.**

---

## 2. Temel kavramlar

| Kavram | Anlamı |
|---|---|
| **Düğüm (knot / point)** | Halıdaki en küçük birim. Çıktıda 1 piksel = 1 düğüm. |
| **Reed (tarak)** | Yatayda metre başına düğüm sayısı. Örnek: 397 → 1 metrede 397 düğüm. |
| **Density (sıklık)** | Dikeyde metre başına sıra sayısı. Örnek: 500 → 1 metrede 500 sıra (10 cm'de 50 sıra). |
| **Düğüm ızgarası (grid)** | Çıktının piksel boyutu. 200×300 cm halı, 397×500 kalitede ≈ 794×1500 düğüm olur. |
| **Palet** | Kullanılacak iplik renklerinin listesi. Çıktıda indeks 0 siyah ve boştur; iplikler 1'den başlar. |
| **Kaynak görüntü** | Dönüştürülecek desen resmi (jpg/png). Düz renkli ve halının en/boy oranında olmalı. |
| **Kaynak ölçeği (scale)** | Her düğüme kaç kaynak pikseli düştüğü. İdeal değer 2 (yani 1 düğüm = 2×2 kaynak pikseli). |
| **Round trip (gidiş-dönüş testi)** | Gerçek bir Texcelle dosyasını resme çevirip aracı bu resimle çalıştırmak ve kaç düğümün doğru çıktığını saymak. |

### Gerçek tezgâh referansı

`data/real_design/003_200X300_397X50_X.bmp` dosyası, gerçekten dokunmaya hazır
bir 200×300 cm Texcelle tasarımıdır. Aracın ürettiği her şey bu dosyaya
benzemelidir:

- Izgara: **793×1501** düğüm (tarak 397, sıklık 500). Bir düğüm 2,52×2,00 mm,
  yani **kare değildir**.
- Başlık: Texcelle, dosyanın çözünürlük alanlarına tarak/sıklık değerlerini
  sanki dpi gibi yazar (397×500). Araç da aynısını yapar.
- Palet: indeks 0 siyah ve kullanılmaz, iplikler 1..15 arasındadır.
- Stil: düz, sembolik renkler; gölge yok. Tüm düğümlerin %21'i 1 düğüm
  kalınlığında çizgilerdedir. Yani "3 düğümden ince olan şey gürültüdür" gibi bir
  kural gerçek tasarımı yok eder. Bu yüzden araç ince çizgilere dokunmaz.

---

## 3. Kurulum

Gereksinimler: Python 3.10 veya üstü.

```bash
cd /path/to/ammk
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
```

Bu komut `pillow`, `numpy`, `scipy` ve test için `pytest` kurar. Arch Linux'ta
sistem `pip` engelli olduğu için mutlaka sanal ortam (`.venv`) kullanın.

Kurulumu doğrulamak için:

```bash
.venv/bin/python -m pytest
```

Tüm testler geçmeli.

---

## 4. Dosya ve klasör düzeni (data klasörü)

Her çalıştırma `data/<isim>/` klasöründe yaşar. `<isim>`, kaynak dosyanın
uzantısız adıdır.

Örnek: `desen.jpg` dosyasını dönüştürdüğünüzde:

```
data/
  desen/
    desen.jpg            <- kaynak resim buraya TAŞINIR (kopyalanmaz)
    desen.tiff           <- Texcelle çıktısı
    desen_palette.txt    <- palet listesi
```

Kurallar:

1. **Kaynak resim taşınır.** Dönüştürme başarılı olduktan sonra resim
   `data/<isim>/` içine taşınır. Dönüştürme başarısız olursa resim yerinde kalır
   ve boş klasör silinir.
2. **Hiçbir şey üzerine yazılmaz.** Aynı resmi ikinci kez çalıştırırsanız
   `desen_2.tiff` ve `desen_2_palette.txt` oluşur; üçüncüde `_3`, vb.
3. Resim zaten `data/<isim>/` içindeyse yerinde bırakılır. Bu sayede aynı
   resmi farklı ayarlarla tekrar tekrar çalıştırabilirsiniz:
   `python -m img2texcelle data/desen/desen.jpg ...`
4. Farklı bir klasörde aynı isimli başka bir dosya varsa ve
   `data/<isim>/<isim>.jpg` zaten mevcutsa araç hata verir; dosyayı yeniden
   adlandırın.
5. `data/` klasörü git'e girmez (`.gitignore` içinde).

Bölme aracının (`img2texcelle.split`, bkz. bölüm 6) çıktıları ise ayrı bir
yerde durur: `data/cropped_images/<isim>/`. Kaynak resim orada **taşınmaz**,
yerinde kalır:

```
data/
  cropped_images/
    desen/
      desen_tl.png       <- sol üst çeyrek
      desen_tr.png       <- sağ üst çeyrek
      desen_tl_2.png     <- aynı resim ikinci kez bölünürse
```

---

## 5. Hızlı başlangıç

### En sık kullanılan komut (tezgâh kalitesi, bilinen iplik renkleri)

```bash
.venv/bin/python -m img2texcelle desen.jpg \
  --width 200 --height 300 \
  --reed 397 --density 500 \
  --palette "#510A15,#FEF7D4,#D5A556,#774133"
```

Anlamı:
- `desen.jpg` → kaynak resim
- `--width 200 --height 300` → halı 200 cm en, 300 cm boy
- `--reed 397 --density 500` → tezgâh kalitesi (yatay 397, dikey 500 düğüm/m)
- `--palette "..."` → kullanılacak iplik renkleri (hex). Tezgâhın iplikleri
  bilindiği için **her zaman verilmesi önerilir.**

Çıktı: `data/desen/desen.tiff` ve `data/desen/desen_palette.txt`.

### Gölgeli Gemini render'ı, BMP çıktısı

```bash
.venv/bin/python -m img2texcelle render.jpg \
  --width 200 --height 300 --reed 397 --density 500 \
  --palette "#530C17,#FDECC7,#C49B66,#341D0E,#614027" \
  --specks 12 --format bmp
```

`--specks 12`, gölge ve parlaklık artıklarını (aynı renk tonunun küçük
kırıntılarını) siler. Varsayılan olarak kapalıdır, çünkü gerçek tasarımdaki
küçük detayların yaklaşık %1'ini de siler.

### Mevcut bir Texcelle dosyasının birebir ızgarası

```bash
.venv/bin/python -m img2texcelle desen.jpg \
  --width 200 --height 300 --grid 793x1501 --reed 397 --density 500 \
  --palette "..."
```

`--grid` verildiğinde çıktı tam olarak 793×1501 piksel olur; `--reed` ve
`--density` sadece dosya başlığına yazılır.

### Otomatik palet (iplik renkleri bilinmiyorsa)

```bash
.venv/bin/python -m img2texcelle desen.jpg \
  --width 200 --height 300 --reed 397 --density 500 --colors 8
```

Araç en fazla 8 renk seçer. Uyarı: tezgâh kalitesinde otomatik palet, sadece
1 düğümlük çizgilerde kullanılan iplikleri kaçırır. Gerçek tasarımda
`--colors 15` ile sadece %71 doğruluk alınır; sabit palet ile %98,7.

Bir çalıştırma, 1696×2528 boyutundaki bir render için yaklaşık **60 saniye**
sürer.

---

## 6. Deseni eş parçalara bölme (`img2texcelle.split`)

Ayna simetrik bir desende yalnızca bir yarı ya da bir çeyrek üzerinde çalışmak
yeter. `img2texcelle.split`, bir resmi **birebir eş** 2 veya 4 parçaya böler ve
parçaları kayıpsız PNG olarak kaydeder. Dönüştürme yapmaz; sadece keser.

```bash
# sol / sağ yarılar (dikey kesik)
.venv/bin/python -m img2texcelle.split desen.jpg --parts 2 --axis lr

# üst / alt yarılar (yatay kesik)
.venv/bin/python -m img2texcelle.split desen.jpg --parts 2 --axis tb

# dört çeyrek
.venv/bin/python -m img2texcelle.split desen.jpg --parts 4

# yalnızca sol üst çeyreği kaydet
.venv/bin/python -m img2texcelle.split desen.jpg --parts 4 --keep tl

# yalnızca sol yarıyı kaydet
.venv/bin/python -m img2texcelle.split desen.jpg --parts 2 --axis lr --keep left

# ayna ekseni tam ortada olmayan bir desen: gerçek ekseni bul, ona göre böl
.venv/bin/python -m img2texcelle.split desen.jpg --parts 2 --axis lr --symmetric

# ekseni elle ver: eksen merkezin 3 px sağında (DX = 2 x 3 = 6), dikeyde ortada
.venv/bin/python -m img2texcelle.split desen.jpg --parts 4 --shift 6,0
```

| Seçenek | Açıklama |
|---|---|
| `src` | Bölünecek resim (jpg/png). Yerinde kalır, taşınmaz. |
| `--parts 2` / `--parts 4` | İki yarı ya da dört çeyrek. Zorunlu. |
| `--axis lr` / `--axis tb` | Yalnızca `--parts 2` için zorunlu: `lr` = sol/sağ, `tb` = üst/alt. `--parts 4` ile verilmez. |
| `--keep a,b` | Kaydedilecek parçalar, virgülle. Verilmezse hepsi. |
| `--symmetric` | Kesilecek eksen(ler)de desenin **gerçek ayna eksenini** bulur ve resmi, eksen tam ortaya gelecek şekilde bir kenardan kırpar; sonra böler. Parçalar böylece birbirinin birebir aynası olur. Verilmezse resim geometrik ortadan kesilir (eski davranış). |
| `--shift DX,DY` | Ekseni elle verir (`--symmetric` gerekmez): eksen merkezin DX/2 px sağında ve DY/2 px altındadır; eksi değer sol/üst. Örn. eksen 3 px solda ise `--shift -6,0`. Kesilmeyen eksenin değeri yok sayılır. |

Parça adları:

- 2 parça, `--axis lr`: `left`, `right`
- 2 parça, `--axis tb`: `top`, `bottom`
- 4 parça: `tl` (sol üst), `tr` (sağ üst), `bl` (sol alt), `br` (sağ alt)

Kurallar:

1. Çıktılar `data/cropped_images/<isim>/<isim>_<parça>.png` yoluna yazılır;
   her resmin kendi klasörü vardır. Klasör zaten varsa yeni dosyalar oraya
   eklenir.
2. **Hiçbir şey üzerine yazılmaz.** Aynı parça ikinci kez üretilirse
   `<isim>_<parça>_2.png`, üçüncüde `_3`, vb.
3. Resmin eni ya da boyu **tek sayı** ise tam yarı yoktur; ortadaki piksel
   sütunu/satırı **iki parçaya da** girer, böylece parçalar hep aynı boyutta
   olur. Bu durumda ekrana bir uyarı yazılır. Örnek: 1697 px genişlik → iki
   yarı da 849 px.
4. Çıkan parça, ana araca kaynak olarak verilebilir. 1696×2528'lik bir
   render'ın çeyreği 848×1264'tür ve 2:3 oranını korur; örneğin
   `--width 100 --height 150 --reed 397 --density 500` ile dönüştürülebilir.
   Ana araç bu parçayı her zamanki gibi `data/<parça adı>/` içine taşır.
4. `--symmetric` ile eksen ortada değilse bir kenardan birkaç px atılır;
   kayma ve kırpılmış boyut ekrana yazılır (`symmetry: left/right axis off
   centre by 2.5 px`, `image cropped to 1787x2390 ...`). Eksen simetrik
   görünmüyorsa (ör. yalnızca sol/sağ simetrik bir desende `--parts 4`) o
   eksen için uyarı verilir ve ortadan kesilir, kırpma yapılmaz. Kırpma en/boy
   oranını %2'den fazla değiştirirse dönüştürmede `--fit crop` gerekebilir.
   Not: `--symmetric` yalnızca **eksenin yerini** düzeltir; Gemini iki yarıyı
   biraz farklı çizdiyse (motifler birebir aynı değilse) parçalar yine farklı
   olur. Bunu dönüştürme aşaması çözer (`--symmetry`, bkz. bölüm 8).

---

## 7. Kaynak görüntü kuralları

Araç yalnızca şu şartları sağlayan görüntülerle doğru çalışır:

1. **Düz renkli olmalı.** Gölge, gradyan, kabartma (bevel), doku olmamalı.
   Gölgeli bir render, kenarlarda aynı renk tonunun ince şeritlerini üretir.
   `--specks 12` bunun için bir çare, ama asıl çözüm düz bir kaynaktır.
2. **Halının en/boy oranında olmalı.** 200×300 cm için 2:3. Alternatif olarak
   düğüm oranında (793:1501) da olabilir. %2 tolerans vardır. Oran tutmuyorsa
   araç hata verir; `--fit crop` (ortadan kes) veya `--fit stretch` (esnet)
   ile geçilebilir.
3. **Düğüm ızgarasından daha ince olmalı.** Her düğüme 1'den fazla kaynak
   pikseli düşmeli. En iyisi düğüm başına 2 piksel: 397×500 kalitede 200×300 cm
   için **1586×3002** piksel. Kaynak daha kabaysa (örneğin 600×900) araç hata
   verir; deseni daha büyük render edin.
4. Mevcut Gemini render'ları (1696×2528, 2:3) yaklaşık 2,1 piksel/düğüm verir
   ve uygundur.

---

## 8. Tüm komut satırı seçenekleri

### Zorunlu

| Seçenek | Açıklama |
|---|---|
| `src` | Kaynak görüntü dosyası (jpg/png). |
| `--width` | Halı eni, cm. |
| `--height` | Halı boyu, cm. |
| Izgara için biri: `--reed` + `--density`, `--points` veya `--grid` | Düğüm ızgarasını belirler (aşağıda). |

### Izgara / kalite

| Seçenek | Açıklama |
|---|---|
| `--reed N` | Yatayda metre başına düğüm (ör. 397). `--density` ile birlikte kullanılır. (TARAK SAYISI) |
| `--density N` | Dikeyde metre başına sıra (ör. 500 = 10 cm'de 50 sıra). (ATKI SAYISI) |
| `--points N` | Metrekare başına düğüm, kare düğüm varsayımıyla (ör. 1000000 → 1000×1000/m). |
| `--grid WxH` | Tam ızgara boyutu (ör. `793x1501`). Mevcut bir Texcelle dosyasıyla aynı boyutu zorlamak için. Bu durumda `--reed/--density` sadece başlığa yazılır. |
| `--fit crop` / `--fit stretch` | Görüntü oranı halıyla tutmuyorsa: ortadan kes ya da esnet. Verilmezse hata. |
| `--no-rotate` | Görüntü ile halı yönü farklıysa (biri yatay biri dikey) araç görüntüyü 90° döndürür. Bu seçenek döndürmeyi kapatır. |

### Renk / palet

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--palette "#RRGGBB,#RRGGBB,..."` | yok | Sabit iplik renkleri. Verildiğinde `--colors` yok sayılır. **Önerilen.** |
| `--colors N` | 8 | Otomatik palette en fazla kaç iplik seçileceği. |
| `--merge D` | 12 | Otomatik palette bu delta E'den yakın renkler tek renge birleştirilir. |
--merge 12 ne yapıyor ? Aralarındaki delta E 12'den küçük olan renkleri tek renge birleştirir. 12 yüksek bir eşik — belirgin farklı sayılabilecek renkleri bile birleştiriyor. Yani agresif.

### Temizlik

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--min-area N` | 20 mm²'lik düğüm sayısı (397×500'de 4) | Bu kadar düğümden küçük adacıklar çevresindeki baskın rengi alır. 0 = kapalı. |
| `--specks N` | 0 (kapalı) | Gölgeli render'lar için: tek bir rengin çevrelediği ve o renkle aynı tona sahip, N düğümden küçük adacıkları o renge boyar. 397×500'de 12 iyi değerdir. Gerçek detayların ~%1'ini de siler, o yüzden kapalı. |
| `--denoise N` | 0 (kapalı) | Kaynak görüntüye N boyutunda medyan filtresi. 1 piksellik çizgileri bozar; kullanmayın. |

### Simetri

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--symmetry auto` | auto | Görüntüden ayna simetrisi tespit edilir. |
| `--symmetry none` | | Simetri işlemleri kapalı. |
| `--symmetry lr` | | Sol/sağ simetri zorlanır. |
| `--symmetry tb` | | Üst/alt simetri zorlanır. |
| `--symmetry both` | | Her iki eksen zorlanır. |

Simetrik eksende iki yarı birlikte karar verilir ve sol/üst yarı sağ/alt
yarıya kopyalanır; karşılıklı motifler birebir aynı olur.

### Çıktı

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--format tiff` / `--format bmp` | tiff | Çıktı biçimi. İkisi de 8 bit indeksli, sıkıştırmasız. |
| `--debug-dir KLASÖR` | yok | Temizlik öncesi etiket haritasını `regions.png` olarak buraya yazar. |

---

## 9. Çıktı dosyaları

### `<isim>.tiff` veya `<isim>.bmp`

- 8 bit, paletli ("P" modu), sıkıştırmasız.
- **İndeks 0 siyah ve boş** (Texcelle'in kendi dosyaları gibi). İplikler indeks
  1'den başlar.
- Çözünürlük alanlarına tarak ve sıklık yazılır (ör. 397×500). Texcelle bunu
  kalite bilgisi olarak okur.
- Boyut = düğüm ızgarası (ör. 794×1500 veya `--grid` ile 793×1501).

### `<isim>_palette.txt`

Her satır bir iplik, sekme ile ayrılmış:

```
1	81	10	21	#510A15
2	254	247	212	#FEF7D4
3	213	165	86	#D5A556
4	119	65	51	#774133
```

Sütunlar: `indeks  R  G  B  #RRGGBB`. İndeks 0 listelenmez.

### Ekran çıktısı

Çalıştırma sırasında araç şunları yazar:

- Düğüm ızgarası, düğüm boyutu (mm), düğüm başına kaynak pikseli, `min area`
- Döndürme / kesme / simetri tespiti bilgileri
- Kaç kenar karışım pikselinin ayrıştırıldığı
- Kaç düğümün adacık temizliğinde yeniden boyandığı
- Her ipliğin çıktıdaki yüzdesi
- Kaynağın taşındığı yer ve çalıştırma klasörü

---

## 10. Arka planda ne yapılıyor? (Boru hattı adım adım)

Ana fikir: kaynak görüntü düğüm ızgarasından daha ince olduğu için **her düğüm,
alanının çoğunu kaplayan ipliği alır.** Bu basit fikri doğru uygulamak için
yedi adım gerekir. Sıra önemlidir.

### Adım 1 – Yön, simetri, en/boy oranı (`grid.py`, `symmetry.py`)

1. **Döndürme:** Görüntü yatay, halı dikeyse (veya tersi) görüntü 90°
   döndürülür. `--no-rotate` ile kapatılır.
2. **Simetri tespiti:** Görüntü gri tona çevrilip 1/4 boyuta küçültülür ve
   aynadaki görüntüsüyle karşılaştırılır (boyutun ±%2'si içinde en iyi kayma
   aranır). Fark, görüntünün 8 piksel kaydırılmış haliyle olan farkın
   0,35 katından küçükse o eksen simetrik sayılır. Ölçülen değerler: Gemini
   render'larında sol/sağ 0,07–0,27 (simetrik), üst/alt 0,76–0,94 (değil);
   gerçek tasarımda her iki yönde 0,00–0,02.
3. **Ekseni ortalama:** Simetri ekseni tam ortada değilse tam çözünürlükte
   incelenir ve görüntü, eksen düğüm ızgarasının tam ortasına gelecek şekilde
   kesilir.
4. **Oran kontrolü:** Görüntü oranı, halının cm oranıyla veya düğüm ızgarası
   oranıyla %2 içinde uyuşmalı. Uyuşmazsa `--fit` gerekir, yoksa hata.
5. **Ölçek kontrolü:** `scale = sqrt(sx*sy)` (düğüm başına kaynak pikseli)
   1'den büyük olmalı, yoksa hata.

**Dikkat:** Neredeyse simetrik bir desende de eksen tespit edilir ve sadece bir
tarafta olan bir motif ortalanarak kaybolur. Böyle bir durumda `--symmetry lr`
veya `--symmetry none` ile elle belirleyin.

### Adım 2 – İsteğe bağlı medyan gürültü giderme

`--denoise` verildiğinde kaynak görüntüye medyan filtresi uygulanır.
Varsayılan kapalı, çünkü 1 piksellik çizgileri kırar.

### Adım 3 – Palet (`color.py`)

`--palette` verildiyse doğrudan kullanılır.

Verilmediyse **otomatik palet**: Görüntü Lab renk uzayına çevrilir. Yalnızca
"düz" pikseller (3×3 komşuluğunda düşük kontrast olan, yani kenarda olmayan
pikseller) üzerinde k-means kümeleme yapılır. Böylece kenarlardaki karışım
renkleri palete girmez. `--merge` değerinden yakın kümeler birleştirilir,
çok küçük kümeler atılır.

Tezgâh kalitesinde otomatik palet yetersizdir: sadece 1 düğümlük çizgilerde
kullanılan iplikler düz piksel örneğine hiç girmez.

### Adım 4 – Kaplama ayrıştırma (unmixing) (`color.smooth_chroma`, `unmix.py`)

Bu adım, aracın kalbidir.

1. **Renk yumuşatma:** JPEG, rengi (a/b kanalları) yarı çözünürlükte saklar.
   Bu yüzden tek pikseller kırmızımsı/yeşilimsi lekeler alır. Parlaklık (L)
   güvenilirdir, bu yüzden a/b kanalları yalnızca benzer parlaklıktaki
   komşular üzerinden ortalanır (joint bilateral filtre). Lekeler kaybolur,
   ince çizgiler kendi rengini korur.

2. **Ayrıştırma:** Her piksel ya **tek bir saf iplik rengi** ya da **iki
   ipliğin karışımı** olarak açıklanır. Bulanık bir kahverengi/krem kenarı
   "yanlış bir ara renk" değil, "%60 kahverengi + %40 krem" olur. Her renk için
   piksel başına bir **kaplama oranı (alpha)** çıkar. Saf renk, karışımdan
   3 delta E daha kötü olmadıkça kazanır (böylece geniş bir ara renk alanı
   kendi rengi olarak kalır).

   Kısıt: bir çift, sadece iki renk de `reach` piksel (= ölçeğin yukarı
   yuvarlaması) içinde en yakın saf renk olarak görünüyorsa izinlidir. Aksi
   halde 15 iplikle hemen her renk, ilgisiz iki rengin arasındaki bir doğru
   üzerine düşer (hafif soluk bir magenta çizgi "%30 mor + %70 turuncu" olarak
   açıklanmıştı ve doğruluk %98'den %94'e düşmüştü).

3. **İnce karışım şeritleri:** Mavi ile krem arasında gri varsa, bulanık bir
   mavi/krem kenarı da bulanık bir 1 piksellik mavi çizgi de gri görünür.
   Geniş bir gri alana bağlı olmayan ince gri şeritler, karıştırdığı iki renge
   ayrıştırılır. Bu adım atlandığında tam sayı olmayan ölçekli bir render'da
   çizgi hataları %19'dan %34'e çıkmıştı.

### Adım 5 – Kaplama oyu (`vote.py`)

1. **Alan ortalaması:** Kaplama oranları BOX yöntemiyle düğüm ızgarasına
   küçültülür. BOX, tam alan ortalamasıdır: her düğüm, alanının her iplik
   tarafından ne kadarının kaplandığını tutar ("yumuşak" kaplama). Bilinear
   yöntem 2 piksellik çizgileri aralıklarına bulaştırıyordu.
2. **Ayna ortalaması:** Simetrik eksenlerde kaplama haritası aynadaki haliyle
   ortalanır; iki yarı aynı kanıttan karar verilir.
3. **Argmax:** Her düğüm en çok kaplayan ipliği alır. Bu yumuşak kaplama,
   piksel etiketlerinin çoğunluğundan ("sert") daha iyidir: gidiş-dönüşte
   %98,8'e karşı %98,2 (2 px/düğüm), %99,3'e karşı %97,8 (tam sayı olmayan
   ölçek).
4. **Düz çizgileri düzeltme (`straighten_runs`):** Bir bant kenarı veya ince
   çizgi bir düğüm sırasının tam ortasından geçiyorsa, o sıradaki her düğüm
   iki renkle yaklaşık yarı yarıya kaplanır. Tek tek karar JPEG gürültüsüyle
   rastgele döner ve dümdüz bir kenar tırtıklı çıkar (bir Gemini render'ında
   üst bordür 440 sütunda 1. sırada, 254 sütunda 2. sırada başlıyordu).
   Çözüm: kararsız düğümler (en az değişen yöndeki ortalama kaplama 0,6'nın
   altında ve kendi kaplaması 0,85'in altında, böylece temiz noktalar ve
   çizgiler hiç dokunulmaz) o yön boyunca gruplanır ve 15 düğüm ve üzeri her
   grup, grubun tamamındaki sert piksel etiketlerinin çoğunluğunu alır. Kısa
   gruplar (kavisli kenarlar, küçük şekiller) kendi kararını korur.

### Adım 6 – Temizlik (`cleanup.py`, `symmetry.mirror_copy`)

1. **Adacık temizliği (`remove_islands`):** `--min-area`'dan küçük bağlı
   parçalar, 1 düğümlük çevresindeki en yaygın rengi alır. Değişiklik
   kalmayana kadar tekrarlanır. Gerçek tasarımda `min area 4` ile 1,19 milyon
   düğümden yalnızca 494'üne dokunulur.
2. **Gölge kırıntıları (`remove_shading_specks`, yalnızca `--specks`):** Tek bir
   rengin en az %80 çevrelediği, o renkle aynı Lab tonuna sahip (25° içinde ya
   da biri nötr) ve `--specks` değerinden küçük parçalar çevreleyen rengi alır.
   Koyu kırmızı üzerindeki krem bir nokta (farklı ton) korunur.
3. **Ayna kopyası (`mirror_copy`):** Simetrik eksenlerde sol/üst yarı sağ/alt
   yarıya birebir kopyalanır. Bu olmadan bir Gemini çıktısı kendi aynasıyla
   yalnızca %93,8 eşleşiyordu; dokumacının ilk fark edeceği şey simetri
   bozukluğudur.

**Burada yapılmayanlar:** Mod filtresi veya köşe yumuşatma eklenmez. Gerçek
tezgâh ızgarasında her 1 düğümlük çapraz merdivenin köşe düğümünün 3 yabancı
komşusu vardır; yumuşatma gerçek tasarımın %3'ünü silmişti.

### Adım 7 – Dosyaları yazma (`output.py`)

8 bit paletli TIFF veya BMP, sıkıştırmasız, indeks 0 ayrılmış, çözünürlük
alanlarında tarak/sıklık; yanına `<isim>_palette.txt`. İki biçim de Texcelle
tarafından tüketildiği için değiştirilmez.

---

## 11. Sonucu nasıl kontrol edersiniz?

Testler geçse bile asıl hatalar görsel ve sayısaldır.

### Gözle kontrol

1. Kaynak görüntüyü BOX ile düğüm ızgarasına küçültün, çıktıyla aynı bölgeyi
   kesin, ikisini NEAREST ile büyütün ve yan yana bakın.
2. Gemini render'ında şunlara bakın: bir köşe, göbek (medalyon), üst bordür
   bandı (düz mü?), sol ve sağ yarı aynı mı?
3. Çıktıda `--min-area`'dan küçük bağlı parça kalmamış olmalı (8 komşuluk,
   `scipy.ndimage.label`).

### Gidiş-dönüş testi (gerçek tasarım)

Her değişiklikte tek bir sayı:

1. `data/real_design/003_200X300_397X50_X.bmp` dosyasını düz RGB olarak
   düğüm başına 2 piksel boyutunda render edin (`1586×3002`, NEAREST,
   Gaussian bulanıklık 0,7, JPEG q90) ve tam sayı olmayan bir ölçekte
   (`1792×2688`, LANCZOS, JPEG q92).
2. İkisini de `--grid 793x1501 --reed 397 --density 500 --palette <gerçek
   BMP'nin 15 rengi>` ile dönüştürün.
3. Çıktı indekslerini en yakın RGB ile gerçek palete eşleyin ve eşleşen
   düğümleri sayın; 1 düğümlük çizgilerdeki düğümleri ayrı sayın.

2026-09-16 tarihli seviyeler:

| Ölçek | Toplam doğruluk | Çizgi hatası | Diğer hata |
|---|---|---|---|
| 2 px/düğüm | %98,71 | %5,8 | ≤ %0,1 |
| Tam sayı olmayan | %99,29 | %2,9 | ≤ %0,1 |

`--symmetry none` yalnızca oy adımını ölçer (98,6 / 99,3).

### Gemini regresyonu

`data/sonGemini_Generated_Image_t4zyvst4zyvst4zy.jpeg` dosyası
`--reed 397 --density 500 --palette "#510A15,#FEF7D4,#D5A556,#774133" --specks 12`
ile (ve bir kez `--colors 8` ile) önceki çıktıyla piksel piksel aynı kalmalıdır.
Oy veya temizlik adımına dokunmadan önce eski çıktının bir kopyasını saklayın.

---

## 12. Sık karşılaşılan hatalar ve çözümleri

| Hata mesajı / durum | Sebep | Çözüm |
|---|---|---|
| `give --reed and --density, --points, or --grid` | Izgara belirtilmedi. | `--reed 397 --density 500` ekleyin. |
| `source image not found` | Dosya yolu yanlış. | Yolu kontrol edin. |
| `... already exists; remove it or rename the source` | `data/<isim>/` içinde aynı adlı kaynak zaten var. | Dosyayı yeniden adlandırın veya `data/<isim>/` içindeki dosyayı doğrudan kaynak olarak verin. |
| `image ratio ... matches neither the carpet ratio ... nor the knot grid ratio` | Görüntü oranı halıyla uyuşmuyor. | `--fit crop` (önerilen) veya `--fit stretch`, ya da kaynağı doğru oranda üretin (1586×3002). |
| `source is coarser than the knot grid` | Görüntü çok küçük, düğüm başına 1 pikselden az. | Deseni daha büyük render edin (2 px/düğüm). |
| `bad palette color` | Palet hex değeri hatalı. | `#RRGGBB` biçimini kullanın, virgülle ayırın. |
| `2 parts need --axis lr ... or tb` (split) | `--parts 2` verildi ama eksen yok. | `--axis lr` ya da `--axis tb` ekleyin. |
| `unknown part(s) ...; valid: ...` (split) | `--keep` içinde o modda olmayan bir parça adı var. | 2 parçada `left,right` / `top,bottom`, 4 parçada `tl,tr,bl,br` kullanın. |
| `warning: odd width ...` (split) | Resmin eni/boyu tek sayı. | Hata değil: orta piksel iki parçaya da girer. Tam yarı isteniyorsa resmi çift boyuta getirin. |
| Üst bordür tırtıklı | Kenar bir düğüm sırasının ortasından geçiyor. | Normalde `straighten_runs` çözer; tekrar oluşursa kaynağın 2 px/düğüm olduğundan emin olun. |
| Karşılıklı motifler farklı | Simetri tespit edilmedi. | `--symmetry lr` / `tb` / `both` ile zorlayın. |
| Bir tarafta olan motif kayboldu | Neredeyse simetrik desen, eksen tespit edildi ve ortalandı. | `--symmetry none` ya da yalnızca doğru ekseni zorlayın. |
| Kenarlarda aynı rengin ince kırıntıları | Gölgeli/kabartmalı render. | `--specks 12`; asıl çözüm düz renkli kaynak. |
| İnce çizgiler kayıp | Otomatik palet o ipliği seçmedi. | `--palette` ile iplik renklerini elle verin. |

---

## 13. Denenip vazgeçilenler (tekrar denemeyin)

- **Büyütme sonrası keskinleştirme (unsharp mask):** kenarlarda sahte
  konturlar üretir.
- **RGB küçültme + sonra renk indirgeme:** iki iplik arasında üçüncü bir
  renkten saçak pikseller oluşur.
- **Piksel başına en yakın renk + adacık silme:** ince çizgiler tespih gibi
  parçalanır.
- **Çizgi/iskelet tespiti (eski kaba kaynak yolu):** gidiş-dönüş %78'e karşı
  %98; ince çizgileri kalınlaştırır. 2026-09-16'da kaldırıldı.
- **Düğüm başına "tutarlı oy" (belirsiz düğümü 9 düğümlük yön ortalamasıyla
  değiştirmek):** −%1,5, çünkü iki sıraya yayılan 1 düğümlük çizgiler iki
  sırada da berabere kalır.
- **Kaynak kaplamasına Gaussian yumuşatma:** 2 piksellik çizgileri aralıklarına
  bulaştırır.
- **Düğüm ızgarasında köşe yumuşatma / mod filtresi:** 1 düğümlük çapraz
  merdivenlerin köşelerini siler (gerçek tasarımın %3'ü).
- **Dört çeyreği ortalamak:** her zaman en iyisini seçmez; dokumacı önce tam
  simetriyi fark eder.

---

## 14. Kod düzeni (geliştirici için kısa harita)

```
img2texcelle/
  __main__.py   python -m img2texcelle girişi
  cli.py        argparse -> Options, data/<isim>/ klasörü, convert()
  options.py    Options veri sınıfı (tüm ayarlar)
  workspace.py  data/<isim>/: kaynağı taşı, <isim>[_N].tiff/bmp + _palette.txt seç
  pipeline.py   convert(src, dst, opts): yukarıdaki 7 adım, ~100 satır
  grid.py       düğüm ızgarası + başlık ppm, düğüm boyutu, döndürme/oran, ölçek kontrolü
  symmetry.py   simetri tespiti, eksen ortalama, ayna ortalaması ve kopyası
  color.py      rgb_to_lab, parse_palette, flat_mask, auto_palette (k-means), smooth_chroma
  unmix.py      unmix (iki renk kaplama oranları), blend_pairs, unmix_thin_blends
  vote.py       resize_alpha (BOX), directional_mean, straighten_runs, vote_knots
  cleanup.py    remove_islands, remove_shading_specks
  output.py     save_indexed (TIFF/BMP, indeks 0 ayrılmış, dpi = ppm), write_palette_txt
  split.py      python -m img2texcelle.split: 2/4 eş parça -> data/cropped_images/<isim>/
tests/
  test_smoke.py      sentetik 2:3 desen uçtan uca; kaba kaynak ve oran hatası testleri
  test_workspace.py  data/<isim>/ klasör kuralları (taşıma, _2/_3 adlandırma, çakışma)
  test_split.py      bölme: eş kutular, tek boyutta orta piksel, ayna eşitliği, --keep, klasör kuralı
```

Testleri çalıştırmak için:

```bash
.venv/bin/python -m pytest
```




Gelistiricinin Kendi Notlari :
-> Split tam calismiyor.
-> finer details icin baska bir cözüm yolu gerekli 