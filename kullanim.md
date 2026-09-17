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

Kısaca: **düz renkli halı deseni görüntüsü → dokunabilir Texcelle dosyası.**

---

## 2. Temel kavramlar

| Kavram | Anlamı |
|---|---|
| **Düğüm (knot / point)** | Halıdaki en küçük birim. Çıktıda 1 piksel = 1 düğüm. |
| **Reed (tarak)** | Yatayda metre başına düğüm sayısı. Örnek: 397 → 1 metrede 397 düğüm. |
| **Density (sıklık)** | Dikeyde metre başına sıra sayısı. Örnek: 500 → 1 metrede 500 sıra (10 cm'de 50 sıra). |
| **Düğüm ızgarası (grid)** | Çıktının piksel boyutu. 200×300 cm halı, 397×500 kalitede ≈ 794×1500 düğüm olur. |
| **Palet** | Kullanılacak iplik renklerinin listesi. Çıktıda indeks 0 siyah ve boştur; iplikler 1'den başlar. |
| **Kaynak görüntü** | Dönüştürülecek desen resmi (jpg/png): kare pikselli, düz renkli, en/boy oranı halınınkinden en çok %10 farklı, her iki yönde düğümden çok pikselli. |
| **Kaynak ölçeği (scale)** | Her düğüme kaç kaynak pikseli düştüğü. Her iki yönde 1'den büyük olmalı. |

### Gerçek tezgâh referansı

`data/real_designs/003_200X300_397X50_X/003_200X300_397X50_X.bmp` dosyası,
gerçekten dokunmaya hazır
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

### BMP çıktısı

```bash
.venv/bin/python -m img2texcelle desen.jpg \
  --width 200 --height 300 --reed 397 --density 500 \
  --palette "#530C17,#FDECC7,#C49B66,#341D0E,#614027" \
  --format bmp
```

### Otomatik palet (iplik renkleri bilinmiyorsa)

```bash
.venv/bin/python -m img2texcelle desen.jpg \
  --width 200 --height 300 --reed 397 --density 500 --colors 8
```

Araç en fazla 8 renk seçer. Uyarı: tezgâh kalitesinde otomatik palet, sadece
1 düğümlük çizgilerde kullanılan iplikleri kaçırır; gerçek tasarımda `--colors 15`
ile düğümlerin dörtte birinden fazlası yanlış ipliğe gider.

Bir çalıştırma 3392×5056'lık bir kaynak için yaklaşık **4 dakika**, 1700×2500'lük
bir kaynak için yaklaşık **60 saniye** sürer.

---

## 6. Deseni eş parçalara bölme (`img2texcelle.split`)

Ayna simetrik bir desende yalnızca bir yarı ya da bir çeyrek üzerinde çalışmak
yeter. `img2texcelle.split`, bir resmi ortadan ya da (`--symmetric` ile) gerçek
ayna ekseninden 2 veya 4 parçaya böler ve parçaları kayıpsız PNG olarak
kaydeder. Dönüştürme yapmaz; sadece keser.

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

# ayna ekseni ortada olmayan bir desen (madalyon yukarıda): gerçek ekseni bul, oradan kes
.venv/bin/python -m img2texcelle.split desen.jpg --parts 2 --axis tb --symmetric

# ekseni elle ver: eksen merkezin 128 px üstünde (DY = -2 x 128 = -256), yatayda ortada
.venv/bin/python -m img2texcelle.split desen.jpg --parts 4 --shift 0,-256
```

| Seçenek | Açıklama |
|---|---|
| `src` | Bölünecek resim (jpg/png). Yerinde kalır, taşınmaz. |
| `--parts 2` / `--parts 4` | İki yarı ya da dört çeyrek. Zorunlu. |
| `--axis lr` / `--axis tb` | Yalnızca `--parts 2` için zorunlu: `lr` = sol/sağ, `tb` = üst/alt. `--parts 4` ile verilmez. |
| `--keep a,b` | Kaydedilecek parçalar, virgülle. Verilmezse hepsi. |
| `--symmetric` | Kesilecek eksen(ler)de desenin **gerçek ayna eksenini** ölçer (ana araçla aynı ölçüm, bkz. bölüm 10 adım 1; merkezden ±%25 uzağa kadar arar) ve resmi oradan keser. Her parça eksenden kendi kenarına kadar uzanır: hiçbir şey kırpılmaz, ama eksen ortada değilse parçaların boyu farklı olur (fom: üst 3392×2400, alt 3392×2656). Eksen bir pikselin üstüne denk gelirse o satır/sütun iki parçaya da girer. Eksen net değilse (kontrast > 0,7) uyarı verilir, en iyi aday ve onu zorlayan `--shift` değeri yazılır, kesik ortada kalır. Verilmezse resim geometrik ortadan kesilir. |
| `--shift DX,DY` | Ekseni elle verir (`--symmetric` gerekmez): eksen merkezin DX/2 px sağında ve DY/2 px altındadır; eksi değer sol/üst. Örn. eksen 128 px yukarıdaysa `--shift 0,-256`. Kesilmeyen eksenin değeri yok sayılır. |

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
5. `--symmetric` ile eksenin yeri ekrana yazılır (`symmetry: top/bottom axis
   at row 2399.5 (128 px above the centre), contrast 0.57`). Eksen ortada
   değilse parçalar farklı boyda çıkar; her parça eksiksizdir ve tek başına
   aynalanınca tam halıyı verir. Eksen net değilse (ör. yalnızca sol/sağ
   simetrik bir desende `--parts 4`) o eksen için uyarı verilir ve ortadan
   kesilir. Farklı boydaki parça ana araca verilirken en/boy oranı halıyla
   uyuşmayabilir; %10'a kadar fark esnetilerek geçilir, üstü hatadır.
   Not: `--symmetric` yalnızca **eksenin yerini** bulur; iki yarı biraz
   farklı çizildiyse (motifler birebir aynı değilse) parçalar yine farklı
   olur. Bunu dönüştürme aşaması çözer (`--symmetry`, bkz. bölüm 8).

---

## 7. Kaynak görüntü kuralları

Aracın tek girdisi düz bir görüntü dosyasıdır (pratikte .jpg). Başka bir girdi
yoktur: Texcelle dosyası ya da düğüm ölçeğinde resim verilmez. Görüntü şu
şartları sağlamalıdır:

1. **Kare pikselli olmalı.**
2. **Düz renkli olmalı.** Gölge, gradyan, kabartma (bevel), doku olmamalı.
   Gölgeli bir kaynak, kenarlarda aynı renk tonunun ince şeritlerini üretir;
   tek çözüm düz bir kaynaktır.
3. **En/boy oranı halının cm oranına yakın olmalı.** 200×300 cm için 2:3. %10'a
   kadar fark kabul edilir: görüntü düğüm ızgarasına esnetilir ve bozulma
   yüzde olarak ekrana yazılır. %10'un üstü hatadır.
4. **Her iki yönde düğümden çok pikseli olmalı.** Her düğüme 1'den fazla
   kaynak pikseli düşmeli. Kaynak daha kabaysa (örneğin 600×900) araç hata
   verir; deseni daha büyük üretin.

---

## 8. Tüm komut satırı seçenekleri

### Zorunlu

| Seçenek | Açıklama |
|---|---|
| `src` | Kaynak görüntü dosyası (jpg/png). |
| `--width` | Halı eni, cm. |
| `--height` | Halı boyu, cm. |
| `--reed` + `--density` | Düğüm ızgarasını belirler (aşağıda). |

### Izgara / kalite

| Seçenek | Açıklama |
|---|---|
| `--reed N` | Yatayda metre başına düğüm (ör. 397). `--density` ile birlikte kullanılır. (TARAK SAYISI) |
| `--density N` | Dikeyde metre başına sıra (ör. 500 = 10 cm'de 50 sıra). (ATKI SAYISI) |

Görüntü ile halı yönü farklıysa (biri yatay biri dikey) araç görüntüyü 90°
döndürür. Görüntü oranı halının cm oranından en çok %10 farklı olabilir;
fark esnetilerek geçilir ve ekrana yazılır (bkz. bölüm 7).

### Renk / palet

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--palette "#RRGGBB,#RRGGBB,..."` | yok | Sabit iplik renkleri. Verildiğinde `--colors` yok sayılır. **Önerilen.** |
| `--colors N` | 8 | Otomatik palette en fazla kaç iplik seçileceği. |
| `--merge D` | 6 | Otomatik palette bu delta E'den yakın renkler tek renge birleştirilir. |

### Temizlik

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--min-area N` | 20 mm²'lik düğüm sayısı (397×500'de 4) | Bu kadar düğümden küçük adacıklar çevresindeki baskın rengi alır. 0 = kapalı. |

### Simetri

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--symmetry auto` | auto | Görüntüden ayna eksenleri ölçülür (ortada olmayan eksen de bulunur). |
| `--symmetry none` | | Simetri işlemleri kapalı. |
| `--symmetry lr` | | Sol/sağ simetri zorlanır (ölçülen eksen yerinde). |
| `--symmetry tb` | | Üst/alt simetri zorlanır. |
| `--symmetry both` | | Her iki eksen zorlanır. |

Simetrik eksende sol/üst yarı sağ/alt yarıya kopyalanır; karşılıklı motifler
birebir aynı olur. İki yarı her yerde eşleşiyorsa (gerçek tasarım, fom
sol/sağ) oy adımında iki yarı birlikte karar verilir; yalnızca eksen yakınında
eşleşiyorsa (fom üst/alt: madalyon aynı, taçlar farklı) yalnızca kopyalanır.
Eksen ortada değilse resim eksen ortaya gelecek şekilde kırpılır; bu en/boy
oranını değiştirir ve fark %10'un altında kaldığı sürece esnetilerek geçilir
(fom: 3392×4800 olur, %6,0 bozulma).

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
- Boyut = düğüm ızgarası (ör. 794×1500).

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
- Döndürme / kesme / simetri tespiti / oran bozulması bilgileri
- Kaç kenar karışım pikselinin ayrıştırıldığı
- Kaç düğümün adacık temizliğinde yeniden boyandığı
- Her ipliğin çıktıdaki yüzdesi
- Kaynağın taşındığı yer ve çalıştırma klasörü

---

## 10. Arka planda ne yapılıyor? (Boru hattı adım adım)

Ana fikir: kaynak görüntü düğüm ızgarasından daha ince olduğu için **her düğüm,
alanının çoğunu kaplayan ipliği alır.** Bu basit fikri doğru uygulamak için
altı adım gerekir. Sıra önemlidir.

### Adım 1 – Yön, simetri, en/boy oranı (`grid.py`, `symmetry.py`)

1. **Döndürme:** Görüntü yatay, halı dikeyse (veya tersi) görüntü 90°
   döndürülür.
2. **Eksen ölçümü** (`symmetry.measure_axis`, `img2texcelle.split --symmetric`
   ile ortak): Görüntü gri tona çevrilip en çok 8 kat küçültülür ve merkezden
   ±%25 uzağa kadar her eksen adayı denenir. Karşılaştırma yalnızca adayın
   ±%15 (boyutun) çevresindeki satırlarla yapılır: kesikte buluşan satırlar.
   Bordür ve uzak motifler sayılmaz; fom'da taçlar ayna konumlarından 100+ px
   uzağa çizilmiştir, bütün görüntüyle karşılaştıran eski ölçüm bu yüzden
   ekseni hiç bulamıyordu. En iyi aday tam çözünürlükte inceltilir. İki sayı
   çıkar: **kontrast** = en iyi eksendeki hata / 32 px'den uzaktaki en iyi
   hata (0 = kusursuz ayna, 1 = eksen yok). 0,7'nin altındaysa eksen kabul
   edilir. Ölçülen (2026-09-17): gerçek tasarım 0,00; WhatsApp taraması 0,16;
   fom sol/sağ 0,12, üst/alt **0,57** (madalyon merkezden 128 px yukarıda);
   simetrisiz fom çeyrek görüntüleri 0,79–0,99. **eşleşme** = o eksende
   bütün görüntünün hatası / 32 px kaydırma hatası (eski ölçüt): 0,35'in
   altındaysa iki yarı her yerde eşleşir (gerçek tasarım 0,00–0,02, fom
   sol/sağ 0,14), değilse yalnızca eksen yakınında (fom üst/alt 1,12).
3. **Ekseni ortalama:** Eksen ortada değilse görüntü, eksen düğüm ızgarasının
   tam ortasına gelecek şekilde kırpılır (fom: 3392×4800). Zorlanan bir eksen (`--symmetry lr/tb/both`) de ölçülen
   yerinde kullanılır; net değilse uyarıyla ortada kalır.
4. **Oran kontrolü:** Görüntü oranı halının cm oranından en çok %10 farklı
   olabilir; üstü hatadır. Altında görüntü adım 4'te düğüm ızgarasına
   esnetilir ve bozulma yüzde olarak yazılır (fom kırpmadan sonra %6,0,
   kırpmasız %0,6).
5. **Ölçek kontrolü:** Her iki yönde düğüm başına 1'den fazla kaynak pikseli
   düşmeli, yoksa hata.

**Dikkat:** Eksen bulunan bir desende sadece bir tarafta olan motif kopyada
kaybolur. Böyle bir durumda `--symmetry none` ya da yalnızca doğru ekseni
(`--symmetry lr` / `tb`) verin.

### Adım 2 – Palet (`color.py`)

`--palette` verildiyse doğrudan kullanılır.

Verilmediyse **otomatik palet**: Görüntü Lab renk uzayına çevrilir. Yalnızca
"düz" pikseller (3×3 komşuluğunda düşük kontrast olan, yani kenarda olmayan
pikseller) üzerinde k-means kümeleme yapılır. Böylece kenarlardaki karışım
renkleri palete girmez. `--merge` değerinden yakın kümeler birleştirilir,
çok küçük kümeler atılır.

Tezgâh kalitesinde otomatik palet yetersizdir: sadece 1 düğümlük çizgilerde
kullanılan iplikler düz piksel örneğine hiç girmez.

### Adım 3 – Kaplama ayrıştırma (unmixing) (`color.smooth_chroma`, `unmix.py`)

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
   açıklanmış, bütün çizgiler iplik değiştirmişti).

3. **İnce karışım şeritleri:** Mavi ile krem arasında gri varsa, bulanık bir
   mavi/krem kenarı da bulanık bir 1 piksellik mavi çizgi de gri görünür.
   Geniş bir gri alana bağlı olmayan ince gri şeritler, karıştırdığı iki renge
   ayrıştırılır. Bu adım atlanınca bulanık 1 piksellik çizgiler ara renk gibi
   görünür ve çizgi hataları neredeyse iki katına çıkar.

### Adım 4 – Kaplama oyu (`vote.py`)

1. **Alan ortalaması:** Kaplama oranları BOX yöntemiyle düğüm ızgarasına
   küçültülür. BOX, tam alan ortalamasıdır: her düğüm, alanının her iplik
   tarafından ne kadarının kaplandığını tutar ("yumuşak" kaplama). Bilinear
   yöntem 2 piksellik çizgileri aralıklarına bulaştırıyordu.
2. **Ayna ortalaması:** İki yarısı her yerde eşleşen eksenlerde (eşleşme <
   0,35) kaplama haritası aynadaki haliyle ortalanır; iki yarı aynı kanıttan
   karar verilir. Yalnızca eksen yakınında eşleşen bir eksende (fom üst/alt)
   ortalama yapılmaz: farklı çizilmiş iki taç üst üste binerdi.
3. **Argmax:** Her düğüm en çok kaplayan ipliği alır. Bu yumuşak kaplama,
   piksel etiketlerinin çoğunluğundan ("sert") daha iyidir, özellikle tam
   sayı olmayan ölçekte.
4. **Düz çizgileri düzeltme (`straighten_runs`):** Bir bant kenarı veya ince
   çizgi bir düğüm sırasının tam ortasından geçiyorsa, o sıradaki her düğüm
   iki renkle yaklaşık yarı yarıya kaplanır. Tek tek karar JPEG gürültüsüyle
   rastgele döner ve dümdüz bir kenar tırtıklı çıkar (bir kaynakta
   üst bordür 440 sütunda 1. sırada, 254 sütunda 2. sırada başlıyordu).
   Çözüm: kararsız düğümler (en az değişen yöndeki ortalama kaplama 0,6'nın
   altında ve kendi kaplaması 0,85'in altında, böylece temiz noktalar ve
   çizgiler hiç dokunulmaz) o yön boyunca gruplanır ve 15 düğüm ve üzeri her
   grup, grubun tamamındaki sert piksel etiketlerinin çoğunluğunu alır. Kısa
   gruplar (kavisli kenarlar, küçük şekiller) kendi kararını korur.

### Adım 5 – Temizlik (`cleanup.py`, `symmetry.mirror_copy`)

1. **Adacık temizliği (`remove_islands`):** `--min-area`'dan küçük bağlı
   parçalar, 1 düğümlük çevresindeki en yaygın rengi alır. Değişiklik
   kalmayana kadar tekrarlanır. Gerçek tasarımda `min area 4` ile 1,19 milyon
   düğümden yalnızca 494'üne dokunulur.
2. **Ayna kopyası (`mirror_copy`):** Simetrik eksenlerde sol/üst yarı sağ/alt
   yarıya birebir kopyalanır. Bu olmadan bir çıktı kendi aynasıyla
   yalnızca %93,8 eşleşiyordu; dokumacının ilk fark edeceği şey simetri
   bozukluğudur.

**Burada yapılmayanlar:** Mod filtresi veya köşe yumuşatma eklenmez. Gerçek
tezgâh ızgarasında her 1 düğümlük çapraz merdivenin köşe düğümünün 3 yabancı
komşusu vardır; yumuşatma gerçek tasarımın %3'ünü silmişti.

### Adım 6 – Dosyaları yazma (`output.py`)

8 bit paletli TIFF veya BMP, sıkıştırmasız, indeks 0 ayrılmış, çözünürlük
alanlarında tarak/sıklık; yanına `<isim>_palette.txt`. İki biçim de Texcelle
tarafından tüketildiği için değiştirilmez.

---

## 11. Sonucu nasıl kontrol edersiniz?

Testler geçse bile asıl hatalar görsel ve sayısaldır.

### Gözle kontrol

1. Kaynak görüntüyü BOX ile düğüm ızgarasına küçültün, çıktıyla aynı bölgeyi
   kesin, ikisini NEAREST ile büyütün ve yan yana bakın.
2. Şunlara bakın: bir köşe, göbek (medalyon), üst bordür
   bandı (düz mü?), sol ve sağ yarı aynı mı?
3. Çıktıda `--min-area`'dan küçük bağlı parça kalmamış olmalı (8 komşuluk,
   `scipy.ndimage.label`).

### Ortada olmayan eksen (fom)

`data/fomggggggbro/fomggggggbro.jpg` (3392×5056, madalyon merkezden 128 px
yukarıda) `--width 200 --height 300 --reed 397 --density 500 --palette
<_6_palette.txt'deki renkler> --format bmp` ile çalıştırıldığında sol/sağ
ekseni ortada, üst/alt ekseni 2399,5. satırda bulmalı, resmi 3392×4800'e
kırpmalı, `6.0% distortion` yazmalı ve `fomggggggbro_3.bmp` ile piksel piksel
aynı, iki yönde de simetrik bir çıktı vermelidir. Aynı komut `--symmetry lr`
ile `0.6% distortion` yazmalı ve `fomggggggbro_6.bmp` ile piksel piksel aynı
olmalıdır (2026-09-17 referansları).

### Başka bir kaynakta regresyon

`data/sonGemini_Generated_Image_t4zyvst4zyvst4zy.jpeg` dosyası
`--reed 397 --density 500 --palette "#510A15,#FEF7D4,#D5A556,#774133"`
ile (ve bir kez `--colors 8` ile) önceki çıktıyla piksel piksel aynı kalmalıdır.
Oy veya temizlik adımına dokunmadan önce eski çıktının bir kopyasını saklayın.

---

## 12. Sık karşılaşılan hatalar ve çözümleri

| Hata mesajı / durum | Sebep | Çözüm |
|---|---|---|
| `the following arguments are required: --reed, --density` | Izgara belirtilmedi. | `--reed 397 --density 500` ekleyin. |
| `source image not found` | Dosya yolu yanlış. | Yolu kontrol edin. |
| `... already exists; remove it or rename the source` | `data/<isim>/` içinde aynı adlı kaynak zaten var. | Dosyayı yeniden adlandırın veya `data/<isim>/` içindeki dosyayı doğrudan kaynak olarak verin. |
| `image ratio ... is N% off the carpet ratio ...` | Görüntü oranı halının cm oranından %10'dan fazla farklı. | Kaynağı halının oranında üretin (200×300 cm için 2:3). |
| `source ... is coarser than the knot grid` | Görüntü çok küçük: en az bir yönde düğüm başına 1 pikselden az. | Deseni daha büyük üretin. |
| `bad palette color` | Palet hex değeri hatalı. | `#RRGGBB` biçimini kullanın, virgülle ayırın. |
| `2 parts need --axis lr ... or tb` (split) | `--parts 2` verildi ama eksen yok. | `--axis lr` ya da `--axis tb` ekleyin. |
| `unknown part(s) ...; valid: ...` (split) | `--keep` içinde o modda olmayan bir parça adı var. | 2 parçada `left,right` / `top,bottom`, 4 parçada `tl,tr,bl,br` kullanın. |
| `warning: odd width ...` (split) | Resmin eni/boyu tek sayı. | Hata değil: orta piksel iki parçaya da girer. Tam yarı isteniyorsa resmi çift boyuta getirin. |
| Üst bordür tırtıklı | Kenar bir düğüm sırasının ortasından geçiyor. | Normalde `straighten_runs` çözer; tekrar oluşursa kaynağın düğüm ızgarasından yeterince ince olduğundan emin olun. |
| Karşılıklı motifler farklı | Simetri tespit edilmedi. | `--symmetry lr` / `tb` / `both` ile zorlayın. |
| Bir tarafta olan motif kayboldu | Neredeyse simetrik desen, eksen tespit edildi ve ortalandı. | `--symmetry none` ya da yalnızca doğru ekseni zorlayın. |
| Kenarlarda aynı rengin ince kırıntıları | Gölgeli/kabartmalı kaynak. | Düz renkli bir kaynak üretin. |
| İnce çizgiler kayıp | Otomatik palet o ipliği seçmedi. | `--palette` ile iplik renklerini elle verin. |

---

## 13. Denenip vazgeçilenler (tekrar denemeyin)

- **Büyütme sonrası keskinleştirme (unsharp mask):** kenarlarda sahte
  konturlar üretir.
- **RGB küçültme + sonra renk indirgeme:** iki iplik arasında üçüncü bir
  renkten saçak pikseller oluşur.
- **Piksel başına en yakın renk + adacık silme:** ince çizgiler tespih gibi
  parçalanır.
- **Çizgi/iskelet tespiti (eski kaba kaynak yolu):** gerçek tasarımda kaplama
  oyundan çok daha kötü; ince çizgileri kalınlaştırır. 2026-09-16'da kaldırıldı.
- **Düğüm başına "tutarlı oy" (belirsiz düğümü 9 düğümlük yön ortalamasıyla
  değiştirmek):** gerçek tasarımda düğüm kaybettirir, çünkü iki sıraya yayılan
  1 düğümlük çizgiler iki sırada da berabere kalır.
- **Kaynak kaplamasına Gaussian yumuşatma:** 2 piksellik çizgileri aralıklarına
  bulaştırır.
- **Düğüm ızgarasında köşe yumuşatma / mod filtresi:** 1 düğümlük çapraz
  merdivenlerin köşelerini siler (gerçek tasarımın %3'ü).
- **Dört çeyreği ortalamak:** her zaman en iyisini seçmez; dokumacı önce tam
  simetriyi fark eder.
- **Kaynağa özel düğmeler** `--specks` (gölgeli kaynakların aynı tondaki
  kırıntılarını boyamak; gerçek detayların ~%1'ini de siliyordu), `--denoise`
  (medyan filtre; 1 piksellik çizgileri kırar), `--fit crop` / `--fit stretch`,
  `--points`, `--no-rotate`, `--grid` ve oran kontrolündeki düğüm oranı
  kabulü: 2026-09-17'de kaldırıldı; yerini bölüm 7'deki kaynak kuralları aldı.

---

## 14. Kod düzeni (geliştirici için kısa harita)

```
img2texcelle/
  __main__.py   python -m img2texcelle girişi
  cli.py        argparse -> Options, data/<isim>/ klasörü, convert()
  options.py    Options veri sınıfı (tüm ayarlar)
  workspace.py  data/<isim>/: kaynağı taşı, <isim>[_N].tiff/bmp + _palette.txt seç
  pipeline.py   convert(src, dst, opts): yukarıdaki 6 adım, ~100 satır
  grid.py       düğüm ızgarası + başlık ppm, düğüm boyutu, döndürme, oran kontrolü (%10), ölçek kontrolü
  symmetry.py   eksen ölçümü (measure_axis), eksen ortalama, ayna ortalaması ve kopyası
  color.py      rgb_to_lab, parse_palette, flat_mask, auto_palette (k-means), smooth_chroma
  unmix.py      unmix (iki renk kaplama oranları), blend_pairs, unmix_thin_blends
  vote.py       resize_alpha (BOX), directional_mean, straighten_runs, vote_knots
  cleanup.py    remove_islands
  output.py     save_indexed (TIFF/BMP, indeks 0 ayrılmış, dpi = ppm), write_palette_txt
  split.py      python -m img2texcelle.split: ayna ekseninden 2/4 parça -> data/cropped_images/<isim>/
tests/
  test_smoke.py      sentetik 2:3 desen uçtan uca; kaba kaynak, oran hatası ve %10 altı oran farkı testleri
  test_workspace.py  data/<isim>/ klasör kuralları (taşıma, _2/_3 adlandırma, çakışma)
  test_split.py      bölme: kutular, eksendeki piksel, ortada olmayan eksen, --symmetric/--shift, --keep, klasör kuralı
  test_symmetry.py   measure_axis: ortada / %20 kaymış / yalnızca eksen yakınında simetrik / simetrisiz; find_and_centre modları
```

Testleri çalıştırmak için:

```bash
.venv/bin/python -m pytest
```




Gelistiricinin Kendi Notlari :
-> Split tam calismiyor.
-> finer details icin baska bir cözüm yolu gerekli 