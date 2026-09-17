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
| **Kaynak görüntü** | Dönüştürülecek desen resmi (jpg/png): kare pikselli, düz renkli, en/boy oranı halınınkine yakın (bkz. `--stretch`), her iki yönde düğümden çok pikselli. |
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
   uyuşmayabilir; varsayılan olarak boy resimden hesaplanır (bkz. bölüm 7),
   `--stretch` ile %10'a kadar fark esnetilerek geçilir, üstü hatadır.
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
3. **En/boy oranı halının cm oranına yakın olmalı.** 200×300 cm için 2:3.
   Varsayılan olarak hiçbir şey esnetilmez: `--width` sabittir, boy resmin
   oranından hesaplanır ve düğüm ızgarası buna göre büyür/küçülür; yeni ölçü
   ve düğüm sayısı ekrana belirgin yazılır. Boy `--height`'tan %10'dan fazla
   sapıyorsa hata verilir ve `--stretch` önerilir. `--stretch` verilirse
   resim verilen cm ölçüsüne esnetilerek sığdırılır ve bozulma yüzde olarak
   yazılır; %10'un üstü hatadır.
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

### Ölçü

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--stretch` | kapalı | Verilen cm ölçüsüne sığdırır, deseni esnetir (en çok %10; üstü hata). Verilmezse hiçbir şey esnetilmez: `--width` sabit kalır, boy resmin oranından hesaplanır, düğüm ızgarası buna göre büyür; yeni ölçü ve düğüm sayısı ekrana belirgin yazılır (fom: `*** CARPET 200 x 313.2 cm, KNOT GRID 794 x 1566 ***`). Boy `--height`'tan %10'dan fazla sapıyorsa hata verilir ve `--stretch` önerilir. |

Görüntü ile halı yönü farklıysa (biri yatay biri dikey) araç görüntüyü 90°
döndürür. Oran kuralları için bkz. bölüm 7.

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

Geçerli değerler yalnızca `auto`, `none`, `lr`, `tb`, `both`'tur (`tl` gibi bir
mod yoktur).

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--symmetry auto` | auto | İki ekseni de (sol/sağ ve üst/alt) resimden ölçer, her birine ayrı karar verir: kontrastı **0,4'ün altında** olan eksen alınır. 0,4–0,7 arası "belirsiz" sayılır: alınmaz, ama uyarı en iyi adayı, kontrastı ve zorlamak için gereken `--symmetry` bayrağını yazar (fom'un üst/alt ekseni 0,57 böyledir). 0,7 ve üstü simetrik değildir. Ortada olmayan eksen de bulunur. |
| `--symmetry none` | | Simetri işlemi yok, ölçüm de yok. Tüm ızgara dönüştürülür. |
| `--symmetry lr` | | Sol/sağ eksenini **mutlaka** alır: kontrast 0,9'un altındaysa ölçülen yerinde, üstündeyse ortada (uyarı basılır). Üst/alt eksenine hiç bakmaz. |
| `--symmetry tb` | | Üst/alt eksenini mutlaka alır (aynı 0,9 sınırı). Sol/sağ eksenine hiç bakmaz. |
| `--symmetry both` | | İki ekseni de mutlaka alır, her biri ölçülen yerinde (0,9 sınırı). fom bununla çalıştırılır. |
| `--no-average` | kapalı | Hiçbir eksende iki yarı birlikte oylanmaz; her eksen yalnız tutulan yarıdan karar verilir. Daha hızlı (fom'da ızgaranın %27'si dönüştürülür, %51 yerine) ama çıktı değişir (fom'da düğümlerin %6,4'ü, gerçek tasarımda %0,5'i). |

Bir eksen alındığında **yalnız tutulan parça** dönüştürülür: kopyalanan
eksende tutulan yarı artı eksenin ötesinde 20 düğümlük bir pay (payın
pikselleri tutulan yarının yansımasıdır, atılan yarının gerçek pikselleri
değil); iki yarısı birlikte oylanan ("average + copy") eksende ise o yönün
tamamı. Pay, düz kenar kararı (`straighten_runs`), yön ortalaması ve ada
temizliğinin erişimini karşılar; sonunda atılır ve parça aynalanır. Tek
sayılı bir ızgarada (79 düğüm) eksen üzerindeki orta düğüm parçaya aittir
(79 → 40 düğümlük parça); ızgara asla yuvarlanmaz, tezgâhın nokta sayısı
değişmez. 2026-09-17'de ölçüldü: fom ve gerçek tasarımda parça + pay ile
üretilen çıktı, tüm resmin dönüştürülmesiyle **düğüm düğüm aynıdır** (0
fark).

#### Bir eksen alındığında ne olur (her modda aynı)

1. **Ölçüm** (`symmetry.measure_axis`, ayrıntı bölüm 10 adım 1): eksenin
   yeri ve iki sayı bulunur. **Kontrast** (0 = kusursuz ayna, 1 = eksen yok)
   eksenin var olup olmadığını, **eşleşme** iki yarının bütün resimde mi
   yoksa yalnız eksen yakınında mı aynı olduğunu söyler.
2. **Eksen ortada değilse yarı seçimi ve aynalama:** iki yarının boyu
   farklıdır (fom: üstte 2400, altta 2656 satır). Biri seçilir ve aynası
   öteki yarının yerine konur; eksen resmin ortasına gelir, hiçbir şey
   kırpılmaz. `--stretch` verilmemişse büyük yarı seçilir (fom: alt yarı,
   resim 3392×5312 olur, halı 200×313,2 cm); `--stretch` verilmişse
   aynalanmış resmi halı oranına en yakın getiren yarı seçilir (fom: yine
   alt yarı, %4,4 bozulma; üst yarı %6,0 verirdi, ekrana yazılır). Ortadaki
   eksende resme dokunulmaz, iki yarının kanıtı korunur.
3. **Oy adımında:** eşleşme 0,35'in altındaysa iki yarı her yerde aynıdır
   (gerçek tasarım, fom sol/sağ 0,14); kaplama haritaları aynasıyla
   ortalanır, iki yarı birlikte karar verilir (ekranda `average + copy`).
   Üstündeyse yarılar yalnız eksen yakınında aynıdır (fom üst/alt 1,12:
   madalyon aynı, taçlar farklı); ortalama yapılmaz, yoksa farklı çizilmiş
   iki taç birbirine karışıp hayalet motif olur (ekranda `copy only`).
4. **Temizlikten sonra:** seçilen yarı öteki yarıya düğüm düğüm kopyalanır
   (`mirror_copy`). Karşılıklı motifler birebir aynı olur; kopyasız bir
   çıktı kendi aynasıyla düğümlerin yalnız %93,8'inde tutuyordu.

Ekran satırları tam bunu söyler (fom, `auto`):

```
symmetry: left/right axis at column 1695.5 (at the centre), contrast 0.12, halves match 0.14 -> average + copy
symmetry: top/bottom axis at row 2399.5 (128 px above the centre), contrast 0.57, halves match 1.12 -> copy only
symmetry: bottom half (2656 rows) kept and mirrored onto the top (2400 rows): image 3392x5312 (the larger half)
```

#### `auto` nasıl karar verir

İki eksen ayrı ayrı ölçülür. Kontrast 0,7'nin altındaysa eksen alınır ve
yukarıdaki adımlar işler; üstündeyse `symmetry: ... not symmetric (best axis
..., contrast 0.8x > 0.7)` yazılır ve o eksen için **hiçbir şey yapılmaz**.
Ölçülen değerler (2026-09-17): gerçek tasarım 0,00; WhatsApp taraması 0,16;
fom sol/sağ 0,12 ve üst/alt 0,57 (ikisi de alınır); simetrisiz fom çeyrek
görüntüleri 0,79–0,99 (ikisi de reddedilir). Yani fom'da `auto`, `both` gibi
davranır; fark, buna resmin karar vermesidir.


#
Program her yön için ayrı ayrı şunu yapıyor:

Resmi bir çizgiden ikiye katlıyor ve iki tarafın ne kadar farklı olduğuna bakıyor. Bu farka hata deniyor.
Bunu birçok farklı çizgi için tekrar ediyor.
En iyi çizgiyi (hatası en düşük olanı) buluyor.
Bu çizginin hatasını, ondan uzaktaki çizgilerin en iyisinin hatasıyla karşılaştırıyor.
Örnek

Çizgi	Hata
satır 2400 (en iyi)	10
uzaktaki en iyi	100
Kontrast = 10 / 100 = 0,1 → en iyi çizgi diğerlerinden çok daha iyi. Gerçek eksen var.

Çizgi	Hata
satır 2400 (en iyi)	90
uzaktaki en iyi	100
Kontrast = 90 / 100 = 0,9 → en iyi çizgi diğerlerinden pek farklı değil. Eksen yok.

Özet

Sol/sağ için dikey çizgiler denenir, üst/alt için yatay çizgiler. İki hesap birbirinden bağımsız.
Kontrast küçükse simetri var, büyükse yok. Sınır 0,7.
#

#### Zorlama modları (`lr`, `tb`, `both`) `auto`'dan nasıl ayrılır

- Eksen **reddedilmez**. Kontrast 0,7'nin altındaysa ölçülen yerinde
  kullanılır, tıpkı `auto` gibi.
- Kontrast 0,7'nin üstündeyse `warning: no clear left/right mirror axis
  (contrast 0.8x > 0.7; best candidate ...); forced, using the centre`
  uyarısı verilir ve eksen **ortada varsayılır** (rastgele bir yerden
  aynalamak yerine). Bu durumda ortalama yapılmaz, yalnız kopyalanır.
- Bakılmayan eksene hiç dokunulmaz: `lr` üst/alt eksenini, `tb` sol/sağ
  eksenini ölçmez bile.

#### fom'da modlar

| Mod | Alınan eksen | Sonuç |
|---|---|---|
| `auto` | yalnız sol/sağ (ortada); üst/alt (0,57) "belirsiz" uyarısıyla atlanır | yalnız sol/sağ simetrik |
| `both` | sol/sağ (ortada) + üst/alt (2399,5. satır) | iki yönde simetrik; `_10.bmp` (varsayılan), `_11.bmp` (`--stretch`), `_14.bmp` (`--no-average`), `_15_part.png` → `assemble` → `_16.bmp` = `_10.bmp` (`--part`) |
| `lr` | yalnız sol/sağ | üst/alt'a dokunulmaz; `_12.bmp` = `_6.bmp` (`--stretch` ile) |
| `tb` | yalnız üst/alt | sol ve sağ yarı birebir aynı olmaz |
| `none` | yok | iki yarı ayrı oylanır, karşılıklı motifler düğüm düğüm farklı olabilir |

#### Hangi durumda hangisi

- Desenin **bir tarafında tek başına** bir motif varsa `none` ya da yalnız
  doğru eksen (`lr` veya `tb`): kopyada o motif silinir.
- `auto` "belirsiz" uyarısı veriyorsa (kontrast 0,4–0,7; fom'un üst/alt
  ekseni) ve desen gerçekten simetrikse uyarıdaki bayrakla (`--symmetry tb`
  ya da `both`) zorlayın; ölçülen eksen kullanılır.
- Desen simetrik ama kontrast 0,9'un da üstündeyse (çok gürültülü bir
  tarama) zorlanan mod ekseni ortadan varsayar ve uyarı basar; resmin
  gerçekten ortadan simetrik olduğundan emin olun.
- Bunların dışında `auto` yeterlidir.

### Çıktı

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--format tiff` / `--format bmp` | tiff | Çıktı biçimi. İkisi de 8 bit indeksli, sıkıştırmasız. |
| `--part` | kapalı | Aynalama ve TIFF/BMP yazma atlanır; yalnız tutulan parça `<isim>_part.png` (8 bit paletli, indeks 0 rezerve) + `<isim>_part.json` + `<isim>_palette.txt` olarak yazılır. Parçayı bir resim editöründe düzeltip `python -m img2texcelle.assemble data/<isim>/<isim>_part.png [--format bmp]` ile bitirin: JSON'daki eksenlere göre aynalar, `<isim>[_N].tiff/bmp` + palet yazar (üzerine yazmaz), kaynak resim gerekmez. Pikseller indekse değil **RGB'ye göre** eşlenir (editör RGB kaydedebilir, palet sırasını bozabilir); palette olmayan bir renk (indeks 0'ın siyahı dahil) ya da JSON'dakinden farklı boyut hatadır ve konumları listelenir. `--symmetry none --part` tüm ızgarayı yazar, JSON'da eksen yoktur. |
| `--debug-dir KLASÖR` | yok | Temizlik öncesi parçanın etiket haritasını `regions.png` olarak buraya yazar. |

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
- Döndürme / simetri tespiti / seçilen ve aynalanan yarı / halı ölçüsü ve oran bozulması bilgileri
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
3. **Yarı seçimi ve aynalama** (`symmetry.mirror_halves`): Eksen ortada
   değilse iki yarının boyu farklıdır (`half_sizes`; fom: üstte 2400, altta
   2656 satır). Biri seçilir, aynası öteki yarının yerine konur
   (`mirror_half`): eksen resmin ortasına gelir, hiçbir şey kırpılmaz ve bu
   adımda esnetilmez. `--stretch` yoksa büyük yarı seçilir (fom: alt yarı,
   3392×5312); `--stretch` varsa aynalanmış resmi halı oranına en yakın
   getiren yarı (fom: yine alt yarı, %4,4; üst yarı %6,0 verirdi). Ortadaki
   eksende resme dokunulmaz, iki yarının kanıtı korunur. Temizlikten sonra
   `mirror_copy` seçilen yarıyı öteki yarıya kopyalar. Zorlanan bir eksen
   (`--symmetry lr/tb/both`) de ölçülen yerinde kullanılır; net değilse
   uyarıyla ortada kalır.
4. **Halı ölçüsü** (`grid.fit_carpet`): `--stretch` yoksa hiçbir şey
   esnetilmez: `--width` sabit, boy resmin oranından hesaplanır, düğüm
   ızgarası buna göre büyür ve ekrana belirgin bir başlıkla yazılır (fom:
   `*** CARPET 200 x 313.2 cm, KNOT GRID 794 x 1566 ***`, bozulma %0). Boy
   `--height`'tan %10'dan fazla sapıyorsa hata verilir ve `--stretch`
   önerilir. `--stretch` varsa verilen ölçü kullanılır, görüntü adım 4'te
   düğüm ızgarasına esnetilir ve bozulma (`grid.distortion`: büyük ölçek
   çarpanı / küçük − 1) yazılır; %10'un üstü hatadır (fom %4,4,
   `--symmetry lr --stretch` %0,6).
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
<_6_palette.txt'deki renkler> --format bmp --symmetry both` ile
çalıştırıldığında sol/sağ ekseni ortada, üst/alt ekseni 2399,5. satırda
bulmalı, `bottom half (2656 rows) kept and mirrored onto the top (2400
rows): image 3392x5312`, `*** CARPET 200 x 313.2 cm, KNOT GRID 794 x 1566
***` ve `part: knots [0, 397) x [783, 1566) of 794 x 1566 (397 x 783);
converting 794 x 803 knots = 51% of the grid` yazmalı ve
`fomggggggbro_10.bmp` (794×1566) ile piksel piksel aynı, iki yönde de
simetrik, taçlarda hayalet motifsiz bir çıktı vermelidir (`--symmetry
both` olmadan üst/alt ekseni yalnız uyarıda adlandırılır, çıktı yalnız
sol/sağ simetrik olur). `--symmetry both --no-average` ile `converting 417
x 803 knots = 27% of the grid` yazmalı ve `fomggggggbro_14.bmp` ile aynı
olmalıdır (`_10`'dan düğümlerin %6,4'ünde farklıdır: her düğüm yalnız
sol/alt çeyrekten karar verilir). Aynı komut
`--stretch` ile yine alt yarıyı seçmeli (`4.4% distortion against 6.0% with
the top half`), `4.4% distortion (--stretch)` yazmalı ve `fomggggggbro_11.bmp`
(794×1500) ile aynı olmalıdır. `--symmetry lr --stretch` ile `0.6% distortion`
yazmalı ve `fomggggggbro_6.bmp` = `fomggggggbro_12.bmp` ile piksel piksel
aynı olmalıdır (yalnız sol/sağ simetrik; eksen ortada olduğu için resme
dokunulmaz). Eski `fomggggggbro_3.bmp` kaldırılan kırpma mantığının
(üst yarı, 3392×4800, %6,0) çıktısıdır, artık üretilmez (2026-09-17
referansları).

### Gerçek tasarımda regresyon

`data/roundtrip/003_200X300_397X50_X_sample/003_200X300_397X50_X_render.jpg`
(3388×5082, gerçek tasarımın render'ı) `--width 200 --height 300 --reed 397
--density 500` ve gerçek tasarımın 15 ipliği `--palette` olarak (yanındaki
`003_200X300_397X50_X_render_ref_palette.txt`) verildiğinde iki ekseni de
ortada bulmalı (kontrast 0,00, average + copy, %100 dönüştürülür) ve
`003_200X300_397X50_X_render_ref.bmp` (794×1500) ile piksel piksel aynı
kalmalıdır; `--no-average` ile (%27) `..._ref_noavg.bmp` ile. Oy veya
temizlik adımına dokunmadan önce eski çıktının bir kopyasını saklayın.

---

## 12. Sık karşılaşılan hatalar ve çözümleri

| Hata mesajı / durum | Sebep | Çözüm |
|---|---|---|
| `the following arguments are required: --reed, --density` | Izgara belirtilmedi. | `--reed 397 --density 500` ekleyin. |
| `source image not found` | Dosya yolu yanlış. | Yolu kontrol edin. |
| `... already exists; remove it or rename the source` | `data/<isim>/` içinde aynı adlı kaynak zaten var. | Dosyayı yeniden adlandırın veya `data/<isim>/` içindeki dosyayı doğrudan kaynak olarak verin. |
| `... gives a W x H cm carpet, N% off the requested ... height ...; use --stretch ...` | `--stretch` yok; resmin oranından çıkan boy `--height`'tan %10'dan fazla farklı. | Deseni esnetmek için `--stretch` ekleyin ya da resmin boyunu verin (mesajdaki `--height`). |
| `fitting the image ... would distort it by N%, more than 10%` | `--stretch` verildi ama resim halı oranından %10'dan fazla uzak. | Halının gerçek ölçüsünü verin ya da kaynağı halının oranında üretin (200×300 cm için 2:3). |
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
- **Ortada olmayan ekseni kırparak ortalamak** (`crop_to_axis`): büyük
  yarının bir kısmını atıyor ve oranı bozuyordu (fom 3392×4800, %6,0
  esnetme). 2026-09-17'de yerini bir yarıyı seçip aynalamak
  (`mirror_halves`) ve `--stretch` aldı.

---

## 14. Kod düzeni (geliştirici için kısa harita)

```
img2texcelle/
  __main__.py   python -m img2texcelle girişi
  cli.py        argparse -> Options, data/<isim>/ klasörü, convert()
  options.py    Options veri sınıfı (tüm ayarlar)
  workspace.py  data/<isim>/: kaynağı taşı, <isim>[_N].tiff/bmp + _palette.txt seç
  pipeline.py   convert(src, dst, opts): yukarıdaki 6 adım, ~100 satır
  grid.py       düğüm ızgarası + başlık ppm, düğüm boyutu, döndürme, bozulma, halı ölçüsü (fit_carpet: --stretch / boy resimden, %10), ölçek kontrolü
  symmetry.py   eksen ölçümü (measure_axis, find_axes), yarı seçimi ve aynalama (half_sizes, mirror_half, mirror_halves), ayna ortalaması ve kopyası
  color.py      rgb_to_lab, parse_palette, flat_mask, auto_palette (k-means), smooth_chroma
  unmix.py      unmix (iki renk kaplama oranları), blend_pairs, unmix_thin_blends
  vote.py       resize_alpha (BOX), directional_mean, straighten_runs, vote_knots
  cleanup.py    remove_islands
  output.py     save_indexed (TIFF/BMP, indeks 0 ayrılmış, dpi = ppm), write_palette_txt
  split.py      python -m img2texcelle.split: ayna ekseninden 2/4 parça -> data/cropped_images/<isim>/
tests/
  test_smoke.py      sentetik 2:3 desen uçtan uca; kaba kaynak, --stretch / boy resimden, ortada olmayan eksen testleri
  test_workspace.py  data/<isim>/ klasör kuralları (taşıma, _2/_3 adlandırma, çakışma)
  test_split.py      bölme: kutular, eksendeki piksel, ortada olmayan eksen, --symmetric/--shift, --keep, klasör kuralı
  test_symmetry.py   measure_axis: ortada / %20 kaymış / yalnızca eksen yakınında simetrik / simetrisiz; find_axes modları, yarı seçimi ve aynalama, mirror_copy yönleri
```

Testleri çalıştırmak için:

```bash
.venv/bin/python -m pytest
```




Gelistiricinin Kendi Notlari :
-> Split tam calismiyor.
-> finer details icin baska bir cözüm yolu gerekli 