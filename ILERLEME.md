# İlerleme Günlüğü

Bu dosya, programda ne yapıldığını ve sırada ne olduğunu tutar. Her çalışma
sonunda buraya bir bölüm eklenir.

---

## 31 Temmuz 2026 — Birinci gün: programın kurulması

### Kararlaştırılanlar

**Yapı iki katmanlı kuruldu: karışım ve satış şekli ayrı.**
Fiyatı aroma değil satış şekli belirlediği için "çikolata" bir ürün değil bir *karışım*,
"cornette külah" ise bir *satış şekli*. Böylece 30 çeşit aroma × 9 satış şekli için
270 ayrı ürün tanımlamak gerekmiyor.

**Malzeme üretimde biter, para satışta girer.**
Akşam hangi kazandan kaç top gittiği sayılamaz, ama kaç külah satıldığı sayılabilir.
Bu yüzden iki ayrı kayıt var: üretim (malzeme düşer) ve satış (para girer).

**Verim reçeteden hesaplanmıyor, elle giriliyor.**
3 lt su + 0,5 kg şeker + 1 kg aroma = 4,5 kg girdi ama 7,5 kg dondurma çıkıyor.
Aradaki fark çırpmada giren hava. Program verimi malzeme toplamından hesaplasaydı
maliyeti %60 yanlış bulurdu.

**Kasa, borç ve kâr üç ayrı rakam.**
Malzeme veresiye alındığı için kasadaki para tek başına yanıltıcı. Veresiye alım
kasayı azaltmaz, borcu artırır.

**Stok bir kolonda değil, hareket kayıtlarında tutuluyor.**
Her stok/kasa/borç değişimi ayrı bir satır. Yanlış kayıt silindiğinde stok ve kasa
kendiliğinden düzeliyor, geçmiş de kaybolmuyor.

**Kurulum gerektirmeyen teknoloji seçildi.**
Python + SQLite, sadece standart kütüphane. `pip install` yok, internet gerekmiyor.
Tarayıcıda çalıştığı için telefondan da açılıyor.

### Yapılanlar

- Veritabanı kuruldu: 16 malzeme, 4 karışım, 12 reçete satırı, 9 satış şekli
- Üretim girişi — reçetedeki malzemeleri stoktan otomatik düşüyor
- Akşam satış girişi — 9 satış şekli tek ekranda, kilo satışında küsurat kabul ediyor
- Alım (veresiye/peşin), gider ve tedarikçi ödemesi girişi
- Stok takibi, kritik seviye uyarıları, sayım düzeltmesi
- "Süt bitmek üzere, 104 litre al" tarzı sipariş önerileri
- Gün sonu özeti: ciro, maliyet, brüt kâr, gider, net kâr, kasa değişimi
- Satış şekillerine göre kârlılık raporu (top başına kâr karşılaştırması)
- Yanlış kayıt silme — stok ve kasa geri alınıyor
- Telefondan erişim, ayarlar ekranı, çift tıkla başlatma

### Test sonuçları

Uçtan uca denendi, rakamlar doğru çıktı: 2 kazan çikolata üretimi aroma stoğunu
15→13 kg, şekeri 100→99 kg düşürdü, 200 top dondurma ekledi. 40 külah + 2,5 kg satış
4.900 TL ciro yazdı, külah stoğunu 40 azalttı. Veresiye alım kasayı değil borcu artırdı.
Silinen kayıtta kasa ve stok geri döndü.

**Bulunan ve düzeltilen hata:** Program şebeke suyunu stok sanıp "Su bitti, 36 litre al"
diyordu. Malzemelere "takip edilsin mi" seçeneği eklendi.

### Açık kalanlar

| Konu | Durum |
|---|---|
| Bir top kaç gram | 75 gram varsayıldı, tartılıp düzeltilecek |
| Malzeme ve satış fiyatları | Hepsi örnek rakam, gerçekleri girilecek |
| Kalan ~26 aroma | Sadece 4 karışım tanımlı |
| Sütlü reçeteler | Hiçbiri girilmedi, süt henüz kullanılmıyor |
| Karışım/malzeme *ekleme* ekranı | Yok, sadece düzenleme var |
| Kullanıcı girişi (şifre) | Yok, yetkili kişi ayrımı yapılmıyor |

---

## 31 Temmuz 2026 — İkinci oturum: satış girişi sayıma çevrildi

### Kararlaştırılanlar

**Akşam artık satış değil, kalan sayılıyor.**
Rafta ne kaldığını yazıyorsun, program farkı satış kabul edip ciroyu ve kârı
hesaplıyor. 3.000 külahtan 2.962 kaldıysa 38 külah satılmış demektir. Böylece
akşam tek iş var: rafları saymak.

**Ambalajlar koli ile takip ediliyor.**
Her malzemeye "bir kolide kaç adet" bilgisi eklendi. Sayımda "5 koli + 462 adet"
yazılabiliyor, alım girişinde de koli ile giriliyor.

**Kaşık, peçete, mendil satılmıyor ama maliyeti kâra yansıyor.**
Bunların günlük tutarı o günün satışlarına paylaştırılıyor, böylece bir külahın
gerçek maliyeti görünüyor.

**Kilo satışı elle giriliyor.**
Bir kaba 1 kg da konuyor 2 kg da; kap sayısından satılan kilo bulunamaz. Kilo kabının
maliyeti de sarf malzeme gibi güne yayılıyor — aksi halde hem otomatik düşülüp hem
sayılacağı için çift düşerdi.

### Yapılanlar

- Gün sonu sayımı ekranı: dondurma kutusu, satılan ambalajlar, kilo satışı, sarf malzeme
- Koli desteği (sayım, alım ve ayarlar ekranlarında)
- Yeni kalemler: pet şişe su (satılıyor), kaşık, peçete, ıslak mendil
- Aynı güne ikinci sayım girilirse önceki silinip baştan hesaplanıyor
- Dondurma sayımında büyük fark çıkarsa uyarı veriliyor (erime / fazla top / unutulan üretim)
- Alım girişinde son alış fiyatı otomatik güncelleniyor ve o günün kârına yansıyor

### Test sonuçları

Uçtan uca denendi: 3 parti üretim + 2 koli külah alımı + gün sonu sayımı → 38 külah,
4 orta kap, 22 pet su ve 2,5 kg kilo satışı doğru türetildi, ciro 5.820 TL çıktı.
Beş malzemenin de stoğu sayılan değere tam oturdu. Sayım silindiğinde kasa, stok ve
satışların hepsi geri döndü.

### Açık kalan

- **8. madde yazılmadan kesildi**, listeye eklenmedi
- Koli adetleri ve pet su / kaşık / peçete / mendil fiyatları örnek rakam
- Bir kutu dondurma 5 kg varsayıldı

---

## 8 Ağustos 2026 — Üçüncü oturum: gerçek reçeteler girildi, hesap grama çevrildi

### Kararlaştırılanlar

**Dondurma artık top ile değil gram ile takip ediliyor.**
Ölçülen gramlar tek bir top ağırlığına oturmuyordu: büyük kap 250 g / 5 top → top
başına 50 g, küçük kap 120 g / 2 top → 60 g, küçük kağıt helva 200 g / 3 top → 66 g.
Program tek bir "bir top kaç gram" ayarı tuttuğu için bunların hepsini aynı anda doğru
düşemezdi ve fark her ay fire gibi görünürdü. Stok, maliyet ve kâr grama bağlandı;
"kaç top" sütunu sadece ekranda kaldı, hiçbir hesaba girmiyor.

**Parti verimi sadece kg ile tutuluyor.**
"Bir parti kaç top" alanı kaldırıldı; kazandan çıkan kg zaten giriliyordu ve gram
hesabı için tek başına yeterli.

**Ölçülen iki reçetenin ikisi de girdi kadar çıktı veriyor.**
Sade: 100 lt süt + 21 kg şeker + 875 gr sahlep + 5 gr vanilya → ~122 kg (girdi 121,9 kg).
Renkli: 6 lt süt + 1 kg şeker + 2 kg aroma → 9 kg (girdi 9 kg). Yani çırpmada
kayda değer hava girmiyor. İlk kurulumdaki 4,5 kg girdi → 7,5 kg çıktı varsayımı
gerçeğe uymuyormuş, düzeltildi.

**33 çeşit CSV'den değil ekrandan ekleniyor.**
Hepsi aynı reçete, sadece aroma değişiyor. Ayarlar'a "yeni çeşit ekle" formu kondu:
mevcut bir çeşidi örnek alıp reçetesini kopyalıyor ve yeni çeşide kendi aromasını
(*Aroma - Kavun* gibi) malzeme olarak açıyor. Böylece 33 çeşit için CSV düzenleyip
veritabanı silmek gerekmiyor.

**Örnek stok rakamları sıfırlandı.**
Uydurma açılış stoğu, gerçek sayım girilene kadar sipariş önerilerini yanıltıyordu.
Artık hepsi sıfır; ilk iş Stok sayfasından gerçek miktarları girmek.

### Yapılanlar

- Sade reçetesi girildi, Sahlep ve Vanilya malzeme olarak eklendi
- Renkli reçete girildi (Çikolata, Çilek, Limon); kalan 30 çeşit ekrandan eklenecek
- Porsiyon gramları: külah 60, cornette 120, küçük kap 120, orta kap 200,
  büyük kap 250, küçük kağıt helva 200, büyük kağıt helva 250
- Kâğıt helva satış fiyatları: küçük 200 TL, büyük 250 TL
- Koli adetleri: külah 450, cornette 180, pet su 24 (0,5 lt)
- Peçete "kutu" birimine çevrildi, kutusu 30 TL
- "Ultra Büyük Kap" kaldırıldı — dükkanda üç kap boyu var
- Eski veritabanını yeni düzene çeviren göç kodu yazıldı (top → gram)
- Ayarlar'daki "bir top kaç gram" alanı kaldırıldı, yerine porsiyon gramı geldi
- Karışım tablosuna kilo maliyeti sütunu eklendi

### Test sonuçları

Uçtan uca denendi: 1 kazan sade + 2 kazan çikolata üretimi süt 200→88, şeker 50→27,
sahlep 5→4,125, vanilya 0,1→0,095, çikolata aroması 10→6 kg düşürdü ve 140 kg
dondurma ekledi (122 + 18, birebir doğru). Ortalama maliyet 51,23 TL/kg çıktı.
Gün sonu sayımı 40 külah, 5 büyük kap, 3 küçük kâğıt helva, 22 pet su ve 2,5 kg kilo
satışını doğru türetti; ciro 6.940 TL, satılan 6,75 kg, kalan dondurma 133,25 kg.
Peçete kutusu ve kilo kabının 70 TL'si günün satışlarına paylaştırıldı. Sayım
silindiğinde kasa, stok ve dondurma tam geri döndü. Yeni çeşit eklendi, aroması
otomatik açıldı, aynı ad ikinci kez eklenmeye çalışılınca reddedildi.

### Açık kalanlar

| Konu | Durum |
|---|---|
| Sade kazanın verimi | 122 kg alındı (120-125 aralığının ortası), tartılıp kesinleşecek |
| Süt kg mı litre mi | Reçeteye 100 **litre** yazıldı; tartılan 100 kg ise ~97 litredir |
| Malzeme alış fiyatları | Sahlep 900, vanilya 1.200, aroma 460-480 TL/kg tahmin |
| Külah / kap / kilo satış fiyatları | Hâlâ örnek rakam (sadece kâğıt helva gerçek) |
| Ambalaj alış fiyatları | Külah, cornette, kap, kaşık, mendil, kilo kabı tahmin |
| Kalan 30 renkli çeşit | Ekrandan eklenecek |
| Bir kutu dondurma kaç kg | 5 kg varsayımı sürüyor |
| Peçete kutusunda kaç adet | Bilinmiyor; stok kutu olarak tutuluyor, adet takibi yok |

---

## 8 Ağustos 2026 — Dördüncü oturum: program her dükkana uyar hale getirildi

### Neden

Amaç programı ileride pastane, fırın ve restoranda da kullanabilmek. Alanları esnetmek
yetmiyordu, çünkü kod **kavram** düzeyinde dondurmacıya gömülüydü: "karışım/kazan",
gram cinsinden tek bir dondurma havuzu, ve satış şeklinin sabit "şu kadar gram + 1
ambalaj" tanımı. Pastanede kazan yok, yaş pasta doğrudan un ve kremadan yapılıyor;
fırında ekmek adetle çıkıyor. Bu yüzden üç kavram tek kavrama indirildi.

### Kararlaştırılanlar

**Her şey bir "kalem".**
Malzeme, karışım ve satış şekli tabloları kaldırıldı; yerine tek bir `kalemler` tablosu
geldi. Dükkanda adı, birimi ve stoğu olan her şey bir kalem: süt de, dondurma da,
külah da. Ne olduğunu kullanıcının işaretlediği üç kutucuk belirler — **alınır**,
**üretilir**, **satılır** — ve bir kalem üçünü birden taşıyabilir.

**Külah artık iki kayıt değil bir kayıt.**
Eskiden "Külah" hem bir ambalaj malzemesiydi hem de bir satış şekliydi; ikisi
`ambalaj_malzeme_id` ile birbirine bağlıydı. Şimdi tek kalem: hem alınır hem satılır.
Gün sonu sayımı da bundan basitleşti — sayılan şeyin kendisi satılan şey olduğu için
aradaki eşleştirme tablosuna gerek kalmadı.

**Reçetenin ne zaman düşeceğini rol belirliyor.**
Kalem "üretilir" işaretliyse reçetesi üretimde düşer (ekmek: un + maya → 120 ekmek).
İşaretli değilse her satışta düşer (külah: satıldıkça 60 gram dondurma gider).
Dondurmacı ile fırıncının farkı artık tek bir kutucuktan ibaret; kodda ne dondurmaya
ne ekmeğe dair bir şey var.

**Reçeteler zincirlenebiliyor ve bir ürünün birden fazla reçetesi olabiliyor.**
Zincir: dilim pasta ← yaş pasta ← pandispanya ← un. Çoklu reçete: Sade, Çikolata ve
Çilek aynı "Dondurma" stoğuna akan üç ayrı reçete — eski karışım tablosunun yerini
tuttu. Maliyet zinciri kendini çağıran bir kurguya karşı korumalı.

**Satış girişi iki modlu.**
Gün sonu sayımı (dondurmacı, market, fırın) ve doğrudan satış girişi (restoran,
pastane) birlikte duruyor; hangisinin menüde görüneceği Ayarlar'dan seçiliyor.

**CSV dosyaları bırakıldı, yerine şablonlar geldi.**
`1-malzemeler.csv` ve arkadaşları zaten ilk açılıştan sonra okunmuyordu, yani dosyayı
düzenlemek hiçbir şeyi değiştirmiyordu — kafa karıştırıcıydı. Yeni bir dükkan ilk
açtığında ekrandan **Dondurmacı / Pastane / Fırın / Restoran / Boş** seçiyor.
Şablonlar sadece başlangıç verisi; program hiçbirini özel olarak tanımıyor.

**Veritabanının adı `dondurma.db` → `veri.db` oldu**, program ilk açılışta kendisi
adlandırıyor. Para birimi de ayar oldu.

### Yapılanlar

- `kalemler`, `receteler`, `recete_satirlari` şeması; `dondurma_hareketleri` tablosu
  kaldırıldı, dondurma da sıradan bir kalem olarak `stok_hareketleri`'ne taşındı
- Eski veriyi taşıyan göç: ambalaj + satış şekli birleştirme, karışımların tek ürünün
  reçetelerine dönüşmesi, bütün hareket kayıtlarının aktarılması. Göç öncesi otomatik
  yedek alınıyor; "top" dönemindeki çok eski veritabanları da destekleniyor
- **Ürün & Malzeme** sayfası: kalem ekleme, silme, bütün alanların düzenlenmesi
- **Reçete düzenleme**: reçete ekle/sil, satır ekle/çıkar, miktar ve verim değiştirme,
  reçete ve birim maliyetinin anlık gösterimi
- Doğrudan satış girişi ekranı ve satış modu ayarı
- Gün sonu sayımı yeniden yazıldı: iki aşamalı (önce satışlar türetilir, sonra kalan
  fark fire/sarf yazılır). Böylece hem kaşık hem dondurma tek kuralla doğru çıkıyor
- Kalem başına "gün sonu sayımı nasıl girilsin" ayarı: sorulmasın / kalanı sayarım /
  bir kolisi bitti / miktarı elle yazarım
- Toplu kabın adı kullanıcıdan alınıyor: koli, çuval, kutu, viyol, tepsi
- Geçmişi olan kalem silinmiyor, kullanım dışına alınıyor
- Beklenmedik bir hatada boş ekran yerine ne olduğunu anlatan sayfa; bozuk form alanı
  artık programı düşürmüyor

### Test sonuçları

Üç ayrı test paketi yazıldı, üçü de temiz geçti.

**Göç (örnek veritabanıyla):** kasa, borç, ciro, maliyet ve 19 kalemin stoğu göç
öncesi ve sonrasında birebir aynı çıktı. 22 kalem, 13 reçete doğru kuruldu.

**Hesap (35 test, dört sektörde):** Dondurmacıda bir kazan Sade 4.791,50 TL, külah
maliyeti 4,86 TL (2,50 külah + 2,36 dondurma); gün sonu sayımı 900→862 külahtan
38 satış türetti, 1.000 kaşığın 400 TL'sini günün satışlarına paylaştırdı.
Fırında 2 tekne = 240 ekmek, ekmek maliyeti 8,35 TL. Pastanede zincir doğru işledi:
dilim pasta 22,21 TL ve 8 dilim satışı bir bütün pastayı stoktan düşürdü. Restoranda
10 adana 1,8 kg kıyma ve 10 lavaş düşürdü; satış silinince hepsi geri geldi.

**Arayüz (40 test, gerçek HTTP):** kalem ekleme/düzenleme/silme, sıfırdan reçete
yazma (virgüllü miktar dahil), alım–üretim–satış zinciri, gün sonu sayımı ve geri
alma, ayar değişikliğinin menüyü değiştirmesi. Ayrıca yeni kurulum akışı: boş
veritabanı kuruluma yönlendiriyor, Pastane şablonu seçilince reçeteler ve ürünler
yerine oturuyor.

### Ek: tür alanı geri geldi

Eski sürümdeki `tur` kolonu (hammadde/ambalaj/sarf) yeni düzende kaldırılmıştı, çünkü
davranışı artık roller ve kutucuklar belirliyor. Ama listeleri düzenlemek için hâlâ
gerekliymiş; geri kondu — bu kez **sabit liste olarak değil, serbest metin olarak.**

Sabit bir hammadde/ambalaj/sarf listesi programı yeniden dondurmacıya bağlardı:
restoranda "Et / Sebze / Kuru gıda / İçecek", pastanede başka başlıklar gerekiyor.
Şimdi kullanıcı kutuya ne yazarsa o; daha önce kullandığı başlıklar öneri olarak
çıkıyor, ayrı bir tür yönetim ekranı yok. Tür hiçbir hesaba girmiyor, sadece:

- Ürün & Malzeme listesi, Stok sayfası ve Ayarlar'daki fiyat tablosu türe göre gruplanır
- Stok sayfasında her tür için ara toplam çıkar
- Alım, sayım düzeltmesi ve reçete malzemesi seçim listeleri bölümlere ayrılır

Göç de düzeltildi: eski `tur` değerleri artık kayboluyordu, şimdi başlık olarak
taşınıyor (ambalaj + satış şeklinden birleşen kalemler "Ürün", dondurma havuzu
"Ara ürün" oluyor). Dondurmacının veritabanı yedekten baştan göçürülüp türleri
dolduruldu — işlem kaydı olmadığı için sonuç birebir aynı çıktı.

24 test daha yazıldı, hepsi geçti: türün kaydedilmesi, yazarak yeni başlık açma, boş
bırakma, beş ekranda gruplama, öneri listesi ve tür değiştirme.

### Açık kalanlar

| Konu | Durum |
|---|---|
| Dondurmacının kendi verisi | Tanımlar korundu; fiyat ve stok rakamları hâlâ tahmin |
| Eski CSV dosyaları | Artık okunmuyor, kayıt olarak duruyor; silinebilir |
| Kullanıcı girişi (şifre) | Yok |
| Çoklu şube / tek veritabanında birden çok dükkan | Yok; her dükkan kendi klasöründe |
| Reçete zincirinde stok yetmezliği uyarısı | Yok; eksiye düşen stok sadece raporda görünür |

---

## 8 Ağustos 2026 — Beşinci oturum: hava durumuna dayalı tahmin sistemi

Yapılacaklar listesindeki **2. madde** (hava durumu) yapıldı. Sırayla 4. madde
(hafta içi/hafta sonu) önerilmişti ama ikisi aynı modelin içinde çözüldü:
haftanın günü etkisi de aynı katsayı mantığıyla hesaplanıyor.

### Kararlaştırılanlar

**İki kaynak, rakip değil tamamlayıcı.**
Tahmin **resmi MGM**'den geliyor (81 il, 6 günlük, servis.mgm.gov.tr). Ama MGM'nin
geçmiş servisi yok; model geçmiş günlerin *gerçekleşen* havasıyla öğrenmek zorunda.
O boşluğu **Open-Meteo arşivi** dolduruyor. MGM'ye ulaşılamazsa tahmin de
Open-Meteo'dan gelir. Kullanıcı isterse Ayarlar'dan "sadece MGM" diyebilir; o
zaman program tercihe uyup yedeğe düşmez.

**Ekran çizimi asla ağ beklemez.**
Bu kural pazarlık dışı: program dükkanda, muhtemelen zayıf bağlantıyla çalışacak.
Sayfalar sadece `hava` tablosunu okur; tabloyu arka planda çalışan bir iş parçacığı
üç saatte bir tazeler. İnternet yoksa program hiçbir şey söylemeden eldeki son
veriyle devam eder. İl seçilene kadar hiçbir şekilde ağa çıkılmaz.

**Model bilerek basit ve reddetmeyi biliyor.**
Üç kademe: sıcaklık doğrusu → yağmur katsayısı → haftanın günü katsayısı. Katsayılar
ham ortalamadan değil, bir önceki kademenin *sapmasından* hesaplanıyor; böylece aynı
etki iki kez sayılmıyor. Hepsi mantıklı aralıklara kırpılıyor.

En önemlisi: **program uydurmayı reddediyor.** 10 günden az veri varsa tahmin
vermiyor, "şu kadar gün daha lazım" diyor. Sıcaklık ilişkisi için 14 gün *ve* en az
5 derecelik fark arıyor; geçmiş günlerin hepsi aynı sıcaklıktaysa ilişki
çıkarılamayacağını söylüyor. Sıcaklık arttıkça satış *düşüyor* gibi görünüyorsa bunu
veri azlığının gürültüsü sayıp modele almıyor. Her tahminin yanında bir aralık var
ve bu aralık modelin geçmişteki ortalama hatasından geliyor.

**Tahmin ciroyu tahmin ediyor, gerisi oradan türüyor.**
Ürün başına ayrı ayrı regresyon az veriyle çok gürültülü olurdu. Onun yerine tek bir
"gün büyüklüğü" tahmin ediliyor, ürünlere geçmiş ciro paylarına göre dağıtılıyor,
sonra reçetelerden geçirilip "kaç kazan üretmeli" çıkarılıyor. Bu son adım tamamen
genel: fırında "kaç tekne", pastanede "kaç tepsi" der.

### Yapılanlar

- `hava.py`: MGM il listesi (önbellekli), 6 günlük tahmin, Open-Meteo yedeği ve
  arşivi, MGM hadise kodlarının Türkçe karşılıkları, `hava` tablosu
- `tahmin.py`: model, ürün kırılımı, üretim önerisi, durum metinleri
- **Tahmin** sayfası: 7 günlük hava kartları, ciro tahmini + aralık, bugün/yarın
  ürün kırılımı, "ne üretmeli" tablosu
- Bugün sayfasına hava ve bugün/yarın tahmin şeridi
- Ayarlar'a "Hava ve tahmin" bölümü: il seçimi, kaynak tercihi, elle güncelleme,
  tahmin sayfasını menüden kaldırma
- Gerçekleşen hava kaydı bir daha tahminle ezilmiyor

### Test sonuçları

**Model (28 test):** Gerçek satış verisi olmadığı için *bilinen bir kurala* göre
sahte geçmiş üretildi (ciro = 400×sıcaklık − 6000, yağmurda ×0,70, cumartesi ×1,40)
ve modelin bu kuralı geri bulup bulamadığına bakıldı. 60 günle: eğim 371 (gerçek
400), yağmur 0,65 (0,70), cumartesi 1,30 (1,40), pazar 1,10 (1,20). Katsayılar
hafifçe 1'e doğru büzülüyor — sıcaklık doğrusu varyansın bir kısmını yuttuğu için
beklenen ve temkinli tarafta olan davranış. Nokta tahmini %12,4 sapmayla, verilen
aralığın içinde. Ters yönlü ilişki kurgusunda model doğru şekilde reddetti.

**Çevrimdışı (15 test):** Tek ağ çıkış noktası kesildiğinde program 0,00 saniyede
pes etti, çökmedi, "son güncelleme" damgasını yazmadı. Sadece MGM çöktüğünde
Open-Meteo devraldı. "Sadece MGM" seçiliyken yedeğe düşmedi.

**Arşiv:** Program 20 gün kapalı kalmış gibi davranıldı; Open-Meteo arşivi 20 günün
gerçekleşen havasını doldurdu ve model o günleri görmeye başladı.

**Gerçek entegrasyon (30 test):** Ordu için MGM'den 6 günlük tahmin geldi
(istNo 95201), sayfalar doğru gösterdi, bilinmeyen il reddedildi, elle güncelleme
çalıştı, tahmin sayfası menüden kaldırılıp geri konabildi.

Önceki 99 test de yeniden koştu, hepsi geçti.

### Açık kalanlar

| Konu | Durum |
|---|---|
| Satış verisi | **Sıfır.** Tahmin altyapısı hazır ama besleyecek veri yok; dükkan çalışmaya başlayınca kendiliğinden devreye girer |
| MGM'nin "yağmurlu" tanımı | Ordu'da yaz günlerinin çoğuna GSY (gök gürültülü sağanak) yazıyor. Neredeyse her gün yağmurlu görünürse model yağmur katsayısını hesaplayamaz ve bunu söyler |
| Tatil ve fındık dönemi | Aynı katsayı mantığıyla eklenebilir, ILERLEME'deki 1. ve 3. maddeler |
| Kalan hava değişkenleri | Nem ve rüzgar kaydediliyor ama modele girmiyor; sıcaklık ve yağmur kadar belirleyici olmadıkları için az veriyle gürültü katarlardı |

---

## Yapılacaklar

### 1. Dini ve resmi tatil etkisi

Ramazan Bayramı, Kurban Bayramı, 23 Nisan, 19 Mayıs, 30 Ağustos, 29 Ekim gibi günler
takvime tanımlanacak. Program bu günlerdeki geçmiş satışları normal günlerle
karşılaştırıp "geçen bayramın ilk günü satış 3 katına çıkmıştı, bu bayrama şu kadar
üretim yap ve şu kadar malzeme al" diyebilecek.

- Dini bayramlar her yıl kayıyor, hicri takvim hesabı gerekiyor
- Bayram öncesi/ilk gün/ikinci gün ayrı ayrı davranıyor, tek katsayı yetmez
- Okul tatili ve yaz sezonu da benzer mantıkla eklenebilir
- **İhtiyaç:** en az bir bayram dönemi geçmiş veri

### 2. Hava durumu — ✅ 8 Ağustos 2026'da yapıldı (beşinci oturum)

Şehrin günlük sıcaklık ve yağış tahmini otomatik çekilecek. Program geçmiş satışlarla
sıcaklık arasındaki ilişkiyi öğrenip "yarın 34 derece, satış %30 artar, bugün fazladan
2 kazan çıkar" diyebilecek.

- **Bu madde internet bağlantısı gerektiriyor** — program şu an tamamen çevrimdışı çalışıyor
- Ücretsiz bir hava durumu servisi seçilecek (Open-Meteo gibi, üyelik istemeyen)
- İnternet yoksa program çalışmaya devam etmeli, sadece bu öneri kapanmalı
- Sıcaklığın yanında yağmur ve rüzgar da satışı etkiliyor, hepsi kaydedilmeli
- **İhtiyaç:** dükkanın şehri; en az bir yaz sezonu veri

### 3. Fındık toplama dönemi

Fındık toplama zamanında şehrin nüfusu azalıyor ve satış düşüyor. Bu dönem takvime
işlenip "önümüzdeki hafta fındık başlıyor, üretimi azalt, aroma siparişini erteleme"
uyarısı verilecek.

- Dönem her yıl aynı tarihlerde başlamıyor, hava ve rekolteye göre kayıyor
- Programa elle "fındık başladı / bitti" işaretlemesi konulabilir, en pratiği bu
- Program dönem boyunca gerçek düşüşü ölçüp gelecek yıl daha isabetli tahmin eder
- **İhtiyaç:** dükkanın şehri; bir sezonluk geçmiş veri

### 4. Hafta içi / hafta sonu ayrımı ve tahmin

Her günün haftanın hangi günü olduğu zaten kayıtlı. Program bunu kullanıp
"cumartesi satışın hafta içinin 2 katı, cuma akşamı 3 kazan hazırla" diyebilecek.

- **Dördü içinde en kolayı ve en erken işe yarayanı bu** — 4-6 haftalık veri yeterli
- Sipariş önerileri de güne göre düzeltilmeli: perşembe alınan malzeme hafta sonunu
  çıkarmalı, pazartesi alınan çıkarmayabilir
- Aynı altyapı üstüne tatil, hava ve fındık katsayıları eklenecek

### Önerilen sıra

**4 → 2 → 1 → 3**

Dördü de geçmiş veriye dayanıyor, yani hiçbiri veri birikmeden çalışmaz. Hafta içi/hafta
sonu ayrımı bir ayda işe yarar hale gelir ve diğer üçünün üstüne kurulacağı iskeleti
oluşturur. Hava durumu ikinci sırada, çünkü dışarıdan veri gelmesi tek başına da fayda
verir. Tatil ve fındık maddeleri bir yıllık döngü görmeden isabetli olamaz.

### Karar bekleyenler

- **Dükkan hangi şehirde?** Hem hava durumu hem fındık dönemi için gerekli.
- **Öneriler ne kadar iddialı olsun?** Program kesin rakam mı versin ("3 kazan yap"),
  yoksa aralık mı ("2-4 kazan arası")? Veri azken ikincisi daha dürüst olur.
