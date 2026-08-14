# Dükkan Takip Programı

Stok, maliyet ve kâr takibi. Dondurmacı, pastane, fırın, restoran — hangisi olduğunu
sen söylersin, program hiçbir ürünü baştan bilmez.

## Nasıl açılır

`baslat.bat` dosyasına çift tıkla. Siyah bir pencere açılır ve tarayıcı kendiliğinden gelir.

- **Bu bilgisayardan:** http://localhost:8000
- **Telefondan:** Siyah pencerede yazan `http://192.168...:8000` adresini telefonun
  tarayıcısına yaz. Telefon ve bilgisayar aynı wifi'da olmalı, bilgisayar da açık olmalı.
- Windows ilk açılışta "güvenlik duvarı izni" sorabilir — **İzin ver** de, yoksa telefondan
  bağlanamazsın.
- Kapatmak için siyah pencerede `Ctrl + C` yap ya da pencereyi kapat.

İlk açılışta program bir **dükkan şablonu** seçmeni ister: Dondurmacı, Pastane, Fırın,
Restoran ya da Boş. Şablon sana hazır bir malzeme–ürün–reçete listesi verir; hepsi
örnektir, sonradan değiştirirsin.

## Programın tek kuralı: her şey bir "kalem"

Dükkanda adı, birimi ve stoğu olan her şey bir **kalem**. Un bir kalem, hamur bir kalem,
ekmek bir kalem. Bir kalemin ne olduğunu, **Ürün & Malzeme** sayfasında işaretlediğin
üç kutucuk belirler:

| Kutucuk | Ne olur |
|---|---|
| **Satın alınır** | Alım ekranında çıkar, alış fiyatı ve tedarikçisi olur |
| **Üretilir** | Reçetesi olur, Üretim ekranında çıkar |
| **Satılır** | Satış fiyatı olur, Satış ekranında çıkar |

Bir kalem birkaçını birden taşıyabilir. Külah hem alınır hem satılır. Pandispanya hem
üretilir hem başka bir reçetede malzeme olur.

### Tür — sadece düzen için

Her kaleme bir **tür** başlığı yazabilirsin: Hammadde, Ambalaj, Sarf, Ürün, Ara ürün…
Listeler bu başlıklara göre gruplanır, Stok sayfasında her tür için ara toplam çıkar,
uzun açılır listeler bölümlere ayrılır.

Tür serbest metindir — kendi başlığını yazarsın. Restoranda "Et", "Sebze", "Kuru gıda",
"İçecek" daha işe yarar; hazır restoran şablonu da öyle geliyor. Kutuya yazmaya
başladığında daha önce kullandığın başlıklar öneri olarak çıkar.

> **Tür hiçbir hesaba girmez.** Maliyeti, stok düşümünü ve sayım davranışını yukarıdaki
> kutucuklar ile "gün sonu sayımı" ayarı belirler. Türü boş bırakabilirsin, o zaman
> kalem "Türü yazılmamış" başlığı altında toplanır.

### Reçete ne zaman düşer

Bu tek soruyu doğru cevaplarsan gerisi kendiliğinden yürür:

- Kalem **"üretilir" işaretliyse** reçetesi **üretim girdiğinde** düşer.
  *Fırın: 50 kg un + maya → 120 ekmek. Unu tekneyi yoğururken düşersin.*
- Kalem **üretilmiyorsa** reçetesi **her satışta** düşer.
  *Dondurmacı: külahı satarken içine 60 gram dondurma gider.*

Reçeteler zincirlenir: `dilim pasta ← yaş pasta ← pandispanya ← un`. Bir ürünün birden
fazla reçetesi de olabilir — Sade, Çikolata ve Çilek hepsi aynı "Dondurma" stoğuna akar.

## Günlük kullanım

1. **Alım / Gider** — Malzeme aldığında gir. Koli/çuval ile aldıysan "kaç koli" kutusuna
   yaz, program birime çevirir. Kira, elektrik ve tedarikçiye ödeme de burada.
2. **Üretim** — Kaç parti yaptığını gir. Reçetedeki malzemeler stoktan düşer, çıkan
   ürün stoğa girer.
3. **Satış** — İki yol var, Ayarlar'dan seçersin:
   - **Gün sonu sayımı** — Rafta ne kaldığını sayarsın, program farkı satış kabul eder.
   - **Doğrudan satış girişi** — Kaç sattığını sen yazarsın.
4. **Bugün** sayfası kasanı, borcunu, kârını ve "şu malzemeden şu kadar al" önerilerini
   gösterir.

> **Sıra önemli:** O gün malzeme aldıysan **önce alımı gir, sonra sayımı yap.**
> Tersini yaparsan program aldığın malı satılmış sanır.

Yanlış giriş yaptıysan ilgili sayfadaki **sil** düğmesine bas — stok ve kasa geri alınır.

## Gün sonu sayımı nasıl çalışıyor

Akşam kaç tane sattığını saymana gerek yok. Rafta kaç *kaldığını* sayıyorsun, program
aradaki farkı satış kabul ediyor. 3.000 külahtan 2.962 kaldıysa 38 külah satılmış
demektir; ciro ve kâr oradan çıkıyor.

Her kalem için sayımın nasıl olacağını **Ürün & Malzeme** sayfasından seçersin:

| Ayar | Ne zaman kullanılır |
|---|---|
| Sorulmasın | Rafta durmayan hammaddeler (un, süt) |
| Rafta kalanı sayarım | Külah, ekmek, pet su, dolaptaki dondurma |
| Tek tek saymam, "bir kolisi bitti" derim | Kaşık, peçete, mendil |
| Sattığım miktarı elle yazarım | Kilo ile satış, porsiyon |

- **Toplu kap ile sayabilirsin:** "5 koli + 462 adet" yazarsın, program toplar. Kabın
  adını sen koyarsın: koli, çuval, kutu, viyol, tepsi.
- **Satılmayan ama harcanan** malzemeleri (kaşık, peçete) işaretlersen o günkü tutarları
  günün satışlarına paylaştırılır — böylece bir külahın gerçek maliyeti çıkar.
- **Sayılan ama satılmayan** kalemlerde (dolaptaki dondurma) fark fire yazılır.
  Fark büyükse program uyarır: erime, ikram ya da kaplara fazla konulmuş olabilir.
- Aynı güne ikinci kez sayım girersen program öncekini silip baştan hesaplar,
  kayıtlar ikiye katlanmaz.

## Hava durumu ve satış tahmini

**Tahmin** sayfası önümüzdeki günlerin havasını ve o günlerde ne kadar satış
bekleneceğini gösterir. Hava verisi **resmi MGM servisinden** gelir (Ayarlar →
Hava ve tahmin bölümünden ilini seçmen yeterli).

Tahmin şöyle öğrenir: her günün havasını kaydeder, sen gün sonu satışını girince
o günün cirosuyla eşleştirir. Yeterince gün birikince "sıcaklık 1 derece artınca
ciro şu kadar artıyor", "yağmurlu günlerde şu kadar düşüyor", "cumartesi normalin
şu katı" ilişkilerini kendisi çıkarır.

| Ne zaman ne olur | |
|---|---|
| İlk 10 gün | Tahmin yok. Program "kaç gün daha lazım" der. Hava yine de kaydedilir. |
| 10 gün sonra | Ciro tahmini başlar, aralık geniştir |
| 14 gün sonra | Sıcaklık etkisi devreye girer (havalar birbirinden yeterince farklıysa) |
| 28 gün sonra | Haftanın günü etkisi devreye girer |

> **Program uydurmaz.** Elinde yeterli veri yoksa tahmin vermeyi reddeder ve
> neyin eksik olduğunu söyler. Verdiği tahminin yanında hep bir aralık vardır;
> bu aralık geçmişte ne kadar yanıldığından hesaplanır ve veri arttıkça daralır.

Tahmin sayfası ayrıca **"önümüzdeki 7 gün için ne üretmeli"** der: beklenen
satışları reçetelerden geçirip kaç kazan/tepsi/tekne gerektiğini hesaplar.

**İnternet gerekmiyor.** Bağlantı yoksa program hiçbir şey söylemeden normal
çalışmaya devam eder, sadece tahmin susar. İl seçilene kadar program hiçbir
şekilde internete çıkmaz. Ekranlar hiçbir zaman ağ beklemez — hava arka planda,
üç saatte bir tazelenir.

## Maliyet nasıl hesaplanıyor

- **Satın alınan** kalemin maliyeti son alış fiyatıdır; alım girdikçe kendiliğinden
  güncellenir.
- **Üretilen** kalemin maliyeti gerçek üretim kayıtlarının ortalamasıdır. Hiç üretim
  yoksa reçeteden tahmin edilir, böylece ilk günlerde de kâr sıfır çıkmaz.
- **Bir satışın maliyeti** = kalemin kendi maliyeti + (üretilmiyorsa) reçetesi.
  Üretilen bir kalemde reçete ikinci kez eklenmez; o maliyet zaten üretimde işlendi.

Verim reçeteden hesaplanmaz, sen yazarsın: 4,5 kg girip 7,5 kg çıkabilir (çırpmada hava
girer), 50 kg un 120 ekmek olur. Program toplamdan hesaplasaydı maliyeti yanlış bulurdu.

## Dosyalar

| Dosya | Ne işe yarar |
|---|---|
| `HATIRLATMALAR.md` | Yapılacaklar listesi — sırada ne var |
| `baslat.bat` | Programı açar |
| `uygulama.py` | Ekranlar ve web sunucusu |
| `hesap.py` | Stok, maliyet, kâr hesapları |
| `hava.py` | MGM ve Open-Meteo'dan hava verisi — programın internete çıkan tek yeri |
| `tahmin.py` | Havaya ve haftanın gününe göre satış tahmini |
| `veritabani.py` | Veritabanı düzeni, göç ve dükkan şablonları |
| `veri.db` | **Bütün kayıtların burada.** Yedeklemek istersen bu dosyayı kopyala |
| `yedek-*.db` | Sürüm yükseltmelerinde otomatik alınan yedekler |
| `1-malzemeler.csv` ve diğerleri | **Artık kullanılmıyor.** Eski sürümün başlangıç dosyalarıydı; düzenlemek hiçbir şeyi değiştirmez, silebilirsin |

Veriler bilgisayarında duruyor, hiçbir yere gönderilmiyor. Program internetsiz çalışır.

## Sık sorulanlar

**Yeni bir ürün nasıl eklerim?**
Ürün & Malzeme → adını, birimini ve türünü yaz, "satılır" işaretle → ekle. Sonra açılan
sayfada fiyatını ve varsa reçetesini gir.

**Türleri nasıl değiştiririm?**
Ayrı bir tür listesi yok. Bir kalemin türünü değiştirdiğinde başlık kendiliğinden
oluşur; o başlıkta kalem kalmayınca da kendiliğinden kaybolur.

**Bir ürünün içindekileri nasıl değiştiririm?**
Ürün & Malzeme → ürüne tıkla → Reçete bölümünden miktarı düzelt ya da yeni malzeme ekle.

**Bir kalemi sildiğimde geçmişim gider mi?**
Hayır. Geçmiş kaydı olan bir kalem silinmez, "kullanım dışı" yapılır: listelerden kalkar
ama eski raporlar bozulmaz.

**Fiyatları toplu güncelleyebilir miyim?**
Ayarlar → Fiyatlar tablosundan hepsini tek ekranda.

**Program bir hata verdi, verilerim gitti mi?**
Hayır. Hata sayfası çıksa bile kayıtlar olduğu gibi durur; her işlem ya tamamen yazılır
ya hiç yazılmaz.
