# Hatırlatmalar

Yapılacaklar burada duruyor. Biten maddenin başındaki `[ ]` işaretini `[x]` yap
ya da sil.

---

## 1. Tüm hammaddelerin birim fiyatlarını gireceğiz

Şu an programdaki fiyatların çoğu tahmin. Fiyatlar kâr hesabının temeli: yanlışsa
"hangi ürün ne kadar kazandırıyor" sorusunun cevabı da yanlış çıkar.

**Nereden girilir:** Ayarlar → Fiyatlar (hepsi tek ekranda), ya da
Ürün & Malzeme → kaleme tıkla → Alış fiyatı.

**Not:** Alım girdiğinde program alış fiyatını kendiliğinden günceller. Yani bir
kere gerçek bir alım girersen o kalemin fiyatı zaten doğrulanmış olur; elle
girmek sadece ilk kurulum ve hiç almadığın kalemler için gerekli.

### Hammadde

- [ ] **Süt** — şu an 32 TL/litre
- [ ] **Şeker** — 38 TL/kg
- [ ] **Sahlep** — 900 TL/kg
- [ ] **Vanilya** — 1.200 TL *(birimi karışık, aşağıdaki A maddesine bak)*
- [ ] **Aroma - Çikolata** — 480 TL/kg
- [ ] **Aroma - Çilek** — 470 TL/kg
- [ ] **Aroma - Limon** — 460 TL/kg
- [ ] **Diğer 15 aroma** *(Muz, Şeftali, Karadut, Böğürtlen, Yeşil Elma, Mango,
  Damla Sakızı, Karamel, Oreo, Lotus, Fındık, Fındık Ezmesi, Vanilya, Kavun,
  İtalyan Karamel)* — hepsine geçici olarak 470 TL/kg yazıldı, gerçek fiyatlar girilmeli
- Su — şebeke suyu, stok tutulmuyor, fiyat gerekmiyor

### Ürün (satılan ama satın da alınanlar — kap ve külahların alış fiyatı)

- [ ] **Külah** — 2,50 TL/adet
- [ ] **Cornette Külah** — 6 TL/adet
- [ ] **Küçük Kap** — 4 TL/adet
- [ ] **Orta Kap** — 5 TL/adet
- [ ] **Büyük Kap** — 7 TL/adet
- [ ] **Küçük Kağıt Helva** — 12 TL/adet
- [ ] **Büyük Kağıt Helva** — 15 TL/adet
- [ ] **Pet Şişe Su (0,5 lt)** — 6 TL/adet

### Ambalaj ve sarf

- [ ] **Kilo Kabı** — 20 TL/adet
- [ ] **Kaşık** — 0,40 TL/adet
- [ ] **Peçete** — 30 TL/kutu
- [ ] **Islak Mendil** — 1,20 TL/adet

> Yukarıdaki rakamlar 8 Ağustos 2026'daki hâli. Doğrusu her zaman programın
> içindedir; bu liste sadece neyin kaldığını takip etmek için.

---

## Programın bulduğu, karar bekleyenler

Bunlar senin yazdığın maddeler değil; veritabanına bakarken çıktı. Kararı sen ver.

### A. Vanilya'nın birimi kg'dan gram'a çevrilmiş ama fiyat ve reçete çevrilmemiş

Şu an programda:

| | Yazan | Olması gereken |
|---|---|---|
| Birim | gram | gram *(sorun yok)* |
| Alış fiyatı | 1.200 TL **/gram** | 1,20 TL/gram |
| Sade reçetesindeki miktar | 0,005 gram | 5 gram |

İki hata birbirini götürdüğü için bir kazan Sade'nin maliyeti **bugün doğru
çıkıyor** (4.791,50 TL). Ama iki yerden patlar:

1. **İlk vanilya alımını girdiğin an** program fiyatı 1,20 TL/gram'a düzeltir;
   o andan sonra reçetedeki 0,005 gram maliyeti 6 TL'den 0,006 TL'ye düşer ve
   Sade'nin maliyeti yanlış görünmeye başlar.
2. **Vanilya stoğu hiç azalmaz.** Her kazanda 5 gram yerine 0,005 gram düşüyor,
   yani bin katı yavaş. "Vanilya bitmek üzere" uyarısı hiç gelmez.

**Yapılacak:** Ürün & Malzeme → Vanilya → alış fiyatını **1,20** yap; sonra
Dondurma → Sade reçetesindeki Vanilya satırını **5** yap.
*(Alternatif: birimi kg'a geri al, fiyat 1.200 ve reçete 0,005 kalsın — o da doğru.)*

### B. "Sade dondurma" adında yarım kalmış bir kalem var

Üretilir + satılır işaretli, birimi kg, satış fiyatı 0, reçetesi
*Süt 100 lt + Şeker 21 kg + Sahlep 1 kg + Vanilya 5 gram* ve **verimi 1 kg**
yazıyor — yani "bu malzemelerden 1 kg çıkar" diyor. Zaten aynı işi yapan
`Dondurma / Sade` reçetesi var (verimi 122.000 gram, doğru olan bu).

**Karar:** Deneme amaçlı açtıysan sil (Ürün & Malzeme → Sade dondurma → sil).
Kilo ile sade satmak istiyorsan zaten `Kilo` kalemi bunu yapıyor.

### C. "Aroma - Limon"un altında boş bir reçete duruyor

İçinde malzeme yok, bir şey bozmuyor ama ekranı kalabalıklaştırıyor.

**Yapılacak:** Ürün & Malzeme → Aroma - Limon → reçeteyi sil.

---

## 2. Gün sonu satışlarını düzenli girmeye başlamak

Tahmin sistemi kuruldu ve hava verisini şimdiden kaydediyor, ama **öğrenecek satış
verisi yok.** Her akşam **Gün Sonu** sayfasından sayımı girdiğin gün sayısı arttıkça
tahmin kendiliğinden akıllanır:

- [ ] **10 gün** — ciro tahmini başlar
- [ ] **14 gün** — sıcaklık etkisi devreye girer *(havaların birbirinden en az 5 derece farklı olması da gerekiyor)*
- [ ] **28 gün** — hafta içi / hafta sonu ayrımı devreye girer

Bunun için ayrıca bir şey yapman gerekmiyor; sadece satışları gir.

---

## Sonraki oturumlarda konuşulacaklar

Bunların ayrıntısı [ILERLEME.md](ILERLEME.md) sonundaki "Yapılacaklar" bölümünde.

- [x] ~~Hava durumuna göre üretim önerisi~~ — 8 Ağustos 2026'da yapıldı
- [x] ~~Hafta içi / hafta sonu satış tahmini~~ — aynı modelin içinde çözüldü
- [x] ~~Bayram ve resmi tatil etkisi~~ — 14 Ağustos 2026'da yapıldı *(aşağıya bak)*
- [ ] Fındık toplama dönemi — *artık beklemene gerek yok, **Özel Günler**
  ekranından kendin girebilirsin (aşağıya bak)*
- [x] ~~Renkli çeşitlerin eklenmesi~~ — 18 renkli çeşit + Sade, her biri ayrı ürün
- [x] ~~Bir kutu dondurmanın kaç kg olduğunun tartılması~~ — **3 kg** çıktı, programa girildi
- [ ] Sade kazanın veriminin tartılması *(122 kg varsayılıyor)*

---

## 3. 2026 tatil takvimi girildi — bayram tarihlerini bir doğrula

Program artık her açılışta resmi tatilleri ve bayramları takvimine kendisi
yazıyor. 2026'da şu günler işaretli:

| Tarih | Gün | Ne |
|---|---|---|
| 1 Ocak | Perşembe | Yılbaşı |
| **18 Şubat – 19 Mart** | | **Ramazan ayı (30 gün)** |
| **19 Mart** | Perşembe | Ramazan Bayramı arifesi *(yarım gün)* |
| **20–22 Mart** | **Cuma–Pazar** | **Ramazan Bayramı (3 gün)** |
| 23 Nisan | Perşembe | Ulusal Egemenlik ve Çocuk Bayramı |
| 1 Mayıs | Cuma | Emek ve Dayanışma Günü |
| 19 Mayıs | Salı | Gençlik ve Spor Bayramı |
| **26 Mayıs** | Salı | Kurban Bayramı arifesi *(yarım gün)* |
| **27–30 Mayıs** | **Çarşamba–Cumartesi** | **Kurban Bayramı (4 gün)** |
| 15 Temmuz | Çarşamba | Demokrasi ve Millî Birlik Günü |
| 30 Ağustos | Pazar | Zafer Bayramı |
| 28 Ekim | Çarşamba | Cumhuriyet Bayramı arifesi *(yarım gün)* |
| 29 Ekim | Perşembe | Cumhuriyet Bayramı |

- [ ] **İki bayramın tarihini takvimden doğrula** — 20 Mart ve 27 Mayıs.
  Resmi tatiller her yıl aynı gün, onlarda hata olmaz; dini bayramlar hicri
  takvime göre kaydığı için tablodan geliyor ve ileri yıllar tahmin.
  Ramazan'ın başlangıcı bayramdan 30 gün geri sayılarak bulunuyor; Ramazan 29
  gün de sürebildiği için bir gün erken başlamış görünebilir (programda
  18 Şubat, gerçekte 19 Şubat olabilir). Günlük ciro modeli için önemsiz.

### Yeni ekran: Özel Günler

**Tahmin** sayfasının altındaki "Özel gün takvimini aç" bağlantısından açılıyor
*(14 Ağustos 2026'da menü sadeleştirildi, artık üst menüde ayrı durmuyor)*.
Üç işe yarıyor:

1. **Takvimi görürsün** — hangi gün hangi etikete bağlı.
2. **Kapatabilirsin** — dükkânda fark yaratmayan bir günü kapat, model onu
   hiç görmez. *(Programın kendi yazdığı günler silinmez, çünkü ilk açılışta
   geri gelirler; onun yerine kapatılırlar. Kendi eklediklerin silinir.)*
3. **Kendin ekleyebilirsin** — köprü günü, festival, yol çalışması, fındık
   toplama dönemi… Artık bunun için bana ihtiyacın yok.

### Etiket mantığı — asıl anlaşılması gereken yer

Program tek tek günleri değil **etiketleri** öğreniyor: "bu etiketli günlerde
ciro normalin kaç katı". Aynı etiketi taşıyan bütün günler aynı havuza girer.

Bir etiketin katsayısının çıkması için o etiketten **en az 3 gün** satış
girilmiş olmalı. 2026'da her etiketin kaç günü var:

| Etiket | 2026'da | Ne zaman öğrenilir |
|---|---|---|
| Ramazan | 30 gün | En hızlı öğrenilen |
| Resmi Tatil *(7 tatilin ortağı)* | 7 gün | İlk yıl |
| Kurban Bayramı | 4 gün | İlk yıl |
| Ramazan Bayramı | 3 gün | İlk yıl, tam sınırda |
| Yarım Gün *(3 arifenin ortağı)* | 3 gün | İlk yıl, tam sınırda |

Bu yüzden bayramlar **günlere bölünmedi**. "Bayramın 1. günü" ayrı bir etiket
olsaydı yılda 1 gün görecekti, yani katsayısı 2029'dan önce çıkmayacaktı. Kaba
ama bu sezon çalışan bir katsayı, ince ama üç yıl sonra çalışan bir
katsayıdan iyidir. Aynı sebeple üç arife tek "Yarım Gün" etiketi altında.

Yeni bir şey eklerken kural: **tekrar eden bir şeye her yıl aynı etiketi yaz.**
"Fındık Toplama 2026" değil, sadece "Fındık Toplama" — yoksa her yıl sıfırdan
öğrenmeye başlar.

---

## 4. GitHub ve programı internete açma

*14 Ağustos 2026'da başlandı.*

Proje artık GitHub'da: **github.com/Amahea/Kazan** (herkese açık).

### Biten işler

- [x] ~~Git kuruldu, proje GitHub'a yüklendi~~
- [x] ~~`.gitignore`~~ — `*.db` ve `*.csv` hariç tutuldu. **Dükkânın verisi
  GitHub'a gitmiyor:** ciro, kasa, borç, tedarikçiler, alış fiyatları hep
  veritabanının içinde ve o dosya hiç gönderilmiyor. Programın çalışması için
  gerek de yok, veritabanı ilk açılışta kendini kuruyor.
- [x] ~~Giriş şifresi~~ — `guvenlik.py`. Şifre **isteğe bağlı:** kurmazsan
  program bugünkü gibi doğrudan açılır, dükkân içi kullanım değişmez.
  Ayarlar → Güvenlik'ten kurulur. Şifre değişince açık bütün oturumlar kapanır.
- [x] ~~Sunucuda çalışabilme~~ — veritabanı yolu, port ve tarayıcı davranışı
  sunucuya göre ayarlanabilir oldu. `render.yaml` ile kurulum tarifi yazıldı.

### Sıradaki iş: Yedek al / Yedekten dön ekranı

**Deploy etmeden önce bu bitmeli.** Sebebi şu: buluta geçince asıl defter orası
oluyor ve iki sorunun cevabı yok —

1. **Mevcut kayıtlar oraya nasıl çıkacak?** Bilgisayarındaki veritabanında
   55 kalem, 31 reçete, bütün fiyatlar ve tatil takvimi var. Bulut boş başlar,
   elle yeniden girmek günler alır.
2. **Yedek nasıl alınacak?** Defter kirada bir sunucuda olacak. Servis batarsa,
   hesap kapanırsa ya da yanlışlıkla bir şey silersen elinde kopya olmalı.
   Bu, yerelde çalışırken olmayan **yeni** bir risk.

- [ ] **Yedek ekranı yaz** — şifreyle korumalı, veritabanını dosya olarak indir
  / dosyadan geri yükle. İkisini de aynı anda çözüyor.
- [ ] **Yedek alma alışkanlığı** — buluta geçtikten sonra ayda bir indir, kendi
  bilgisayarında sakla.

### Sonra: Render'a kurulum

- [ ] Render'a GitHub hesabıyla gir → **New → Blueprint** → `Kazan` deposunu seç
- [ ] `render.yaml` her şeyi kendi kurar; sadece **şifreyi** panele gir
      *(şifre depoya yazılmıyor, repo herkese açık)*
- [ ] Yerelde "Yedek al" → Render'daki adreste "Yedekten dön"
- [ ] Adres `kazan-xxxx.onrender.com` olur, HTTPS hazır gelir

**Maliyet: aylık ~7 dolar.** Kalıcı disk ücretli plan istiyor. Bedava planda
disk her yeniden başlatmada sıfırlanır, yani veri kalıcı olmaz — o plan bu iş
için kullanılamaz.

**Karar hatırlatması:** buluta geçince yereldeki kopyayı kullanmayı bırakman
gerekiyor. İkisini birden kullanırsan iki ayrı defter tutmuş olursun. Ayrıca
dükkânda internet kesilirse satış giremezsin — yerelde bu sorun yoktu.

### Küçük işler

- [x] ~~**`git push`**~~ — 14 Ağustos 2026'da gönderildi; bekleyen dört kayıt
      da GitHub'a çıktı. Bundan sonra `cd c:\denizciler` sonra `git push`
      demen yeterli, tarayıcı girişi bir daha sorulmaz.
- [ ] **`README.md` yaz** — GitHub repo ana sayfasında `README.md` arıyor,
      sende `OKU-BENI.md` var ve GitHub onu tanımıyor. Şu an jüri repoya
      girince proje anlatımı değil, dosya listesi görüyor.
- [ ] **Bu dosyadaki alış fiyatları** — süt 32, sahlep 900, aromalar 470–480
      artık GitHub'da herkese açık. Rahatsız ederse ya rakamları temizle ya da
      bu dosyayı da `.gitignore`'a ekle.
- [ ] **İsimleri "Kazan"a çevir** — dosyaların içinde hâlâ "Dükkan Takip
      Programı" yazıyor.

---

## 5. Kullanıcı girişi ve çıkışı

*14 Ağustos 2026'da eklendi.*

Şu an tek bir şifre var: bilen girer, giren her şeyi görür ve değiştirir.
Kimin ne yaptığı hiçbir yerde yazmıyor. Dükkânda senden başka biri de satış
giriyorsa bu yetmez.

**Yapılacak:** kullanıcı adı + şifre ile giriş, her kişinin kendi hesabı.

- [ ] **Kullanıcı tablosu** — ad, şifre özeti, rol. `guvenlik.py` zaten şifre
      özetlemeyi ve oturum çerezini biliyor; üstüne kullanıcı kavramı eklenecek.
- [ ] **Giriş ekranı kullanıcı adı da sorsun** — bugün sadece şifre soruyor.
- [ ] **Kayıtlara "kim girdi" bilgisi** — satışı, üretimi, alımı kimin
      girdiği görünsün. Yanlış bir kayıt çıktığında kime soracağın belli olur.
- [ ] **Rol ayrımı** — *çalışan* sadece satış ve üretim girer; *sahibi* kasayı,
      kârı, fiyatları ve ayarları da görür. Asıl faydası bu: çalışanın
      tedarikçi fiyatlarını ve günlük kârı görmesi gerekmiyor.
- [ ] **Çıkış** — bugün de var ama tek şifreli olduğu için "kim çıktı" diye bir
      şey yok; kullanıcı gelince anlamlı hale gelir.

**Not:** Şifre bugün olduğu gibi isteğe bağlı kalmalı. Tek başına çalıştığın
dükkânda her sabah kullanıcı adı yazmak angarya olur.

---

## 6. 1 Ocak'tan itibaren simülasyon verisi girilecek

*14 Ağustos 2026'da eklendi.*

Tahmin çalışmıyor çünkü **öğrenecek satış yok** (bkz. madde 2). Gerçek satışları
girmeye yeni başlıyoruz; bu haliyle ciro tahmini en erken 10 gün, hafta
içi/hafta sonu ayrımı 28 gün sonra devreye girer.

Bunu beklememek için **1 Ocak 2026'dan bugüne kadar** gerçeğe yakın uydurma
(simülasyon) satış verisi girilecek. Model hemen çalışmaya başlar, ekranların
dolu hâli görünür, hava-ciro ilişkisi test edilebilir.

- [ ] **Veri üretecek bir script yaz** — her gün için ciro ve ürün kırılımı.
      Uydurma olsa da tutarlı olmalı: sıcak günde daha çok, yağmurda daha az,
      hafta sonu daha çok, bayramda çok daha çok satış. Hava verisi zaten
      `hava` tablosunda duruyor, arşivden geçmiş günler de çekilebiliyor.
- [ ] **Kararı önce ver: bu veri gerçek defterle karışacak mı?**
      Simülasyon satışları kasayı, ciroyu, kârı ve stok hareketlerini de
      değiştirir. Yani "kasada ne var" sorusunun cevabı artık gerçek olmaz.
      İki yol var:
      1. **Ayrı bir veritabanı** (`simulasyon.db`) — gerçek defter temiz kalır,
         program `DUKKAN_VERITABANI` ile o dosyaya bağlanır. *Önerilen yol.*
      2. **Aynı defter, sonra silinir** — hızlı ama silme işini unutursan
         rakamlar kalıcı olarak yanlış kalır.
- [ ] **Girmeden önce yedek al** — `veri.db` dosyasını kopyala. Program zaten
      `yedek-TARIH.db` diye kopya bırakıyor, ama bu sefer bilerek al.

**Bittiğinde:** simülasyon verisi silinip gerçek satışlarla devam edilecekse,
tahmin modeli sıfırdan öğrenmeye başlar — bu normaldir, veri gidince öğrendiği
de gider.
