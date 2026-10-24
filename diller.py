# Iki dilli site: Turkce (tr) ve Ingilizce (en).
#
# Program bastan Turkce yazildi. Buradaki ceviri fonksiyonu C() bu yuzden
# Turkce'de metni OLDUGU GIBI dondurur (kimlik gibi davranir); Ingilizce'de
# asagidaki SOZLUK'ten karsiligini bulur. Karsilik yoksa yine Turkce gorunur -
# ekran bozulmaz, yalnizca o parca henuz cevrilmemis demektir. Boylece siteyi
# ekran ekran, hicbir yeri kirmadan cevirebiliyoruz.
#
# Araya deger giren cumleler icin adli yer tutucu kullanilir:
#     C("Elde {n} {birim}", n=mik(x), birim="kg")
# Sozlukteki Ingilizce karsilikta ayni yer tutucular baska sirada olabilir:
#     "Elde {n} {birim}" -> "{n} {birim} in stock"

import threading

DESTEKLENEN = ("tr", "en")
VARSAYILAN = "tr"

_istek = threading.local()


def ayarla(dil):
    """Bu istegin dilini belirler. Her istegin basinda bir kez cagrilir."""
    _istek.dil = dil if dil in DESTEKLENEN else VARSAYILAN


def simdiki():
    return getattr(_istek, "dil", VARSAYILAN)


def _en_oncelikli(accept_language):
    """Tarayicinin 'Accept-Language' basligindan en yuksek oncelikli dilin
    iki harfli kokunu dondurur. Ornek: 'tr-TR,tr;q=0.9,en;q=0.8' -> 'tr'.
    Bilgi yoksa bos dizge doner."""
    en_iyi, en_iyi_q = "", -1.0
    for parca in (accept_language or "").split(","):
        parca = parca.strip()
        if not parca:
            continue
        ad, _, nitelik = parca.partition(";")
        q = 1.0
        if nitelik.strip().startswith("q="):
            try:
                q = float(nitelik.strip()[2:])
            except ValueError:
                q = 0.0
        if q > en_iyi_q:
            en_iyi, en_iyi_q = ad.strip().lower()[:2], q
    return en_iyi


def coz(cerez_dili, accept_language):
    """Hangi dil gosterilecek?

    1. Kisi ustteki TR/EN dugmesiyle bir secim yaptiysa (cerez), o gecerli.
    2. Yoksa tarayici dili: 'tr' ise Turkce, baska her sey Ingilizce.
    3. Tarayici hic bilgi vermediyse Turkce (dukkanlar Turkiye'de)."""
    if cerez_dili in DESTEKLENEN:
        return cerez_dili
    kok = _en_oncelikli(accept_language)
    if not kok:
        return VARSAYILAN
    return "tr" if kok == "tr" else "en"


def C(tr_metin, **yer_tutucu):
    """Ceviri. Turkce'de metni oldugu gibi, Ingilizce'de sozlukten dondurur."""
    dil = simdiki()
    metin = tr_metin if dil == "tr" else SOZLUK.get(tr_metin, tr_metin)
    return metin.format(**yer_tutucu) if yer_tutucu else metin


# ---------------------------------------------------------------------------
# Ingilizce sozluk: {Turkce metin: Ingilizce karsilik}
# Yeni ekran cevirdikce buraya eklenir. Burada OLMAYAN her Turkce metin
# Ingilizce'de de Turkce gorunur (gecici, bozuk degil).
# ---------------------------------------------------------------------------
SOZLUK = {
    # --- ust menu + kabuk ---
    "Ana Menü": "Home",
    "Satış": "Sales",
    "Üretim": "Production",
    "Stok": "Stock",
    "Alım / Gider": "Purchases / Expenses",
    "Raporlar": "Reports",
    "Ayarlar": "Settings",
    "Çıkış": "Log out",
    "Çalışanlar": "Staff",
    "Ürün & Malzeme": "Products & Materials",
    "Menüler": "Menus",
    "Kalem": "Item",
    "Tahmin": "Forecast",
    "Özel Günler": "Special Days",
    "Kurulum": "Setup",
    "Dükkanım": "My Shop",

    # --- giris / kayit / kapak ---
    "Kasa, stok ve satış tek yerde": "Cash, stock and sales in one place",
    "Giriş": "Sign in",
    "Giriş yap": "Sign in",
    "Dükkanının kayıtlarına ulaşmak için.": "To reach your shop's records.",
    "Kullanıcı adı": "Username",
    "Şifre": "Password",
    "Gir": "Sign in",
    "Dükkanın burada kayıtlı değil mi? <a href=\"/kayit\">Yeni dükkan aç</a>":
        "Shop not registered here? <a href=\"/kayit\">Open a new shop</a>",
    "Program ne işe yarıyor? <a href=\"/tanitim\">Tanıtımı gör</a>":
        "What does the program do? <a href=\"/tanitim\">See the intro</a>",
    "Kullanıcı adı ya da şifre yanlış.": "Wrong username or password.",
    "Yeni dükkan": "New shop",
    "Yeni dükkan aç": "Open a new shop",
    "Kayıtların kendi dosyasında tutulur; başka hiçbir dükkan onları göremez.":
        "Your records are kept in their own file; no other shop can see them.",
    "Dükkanın adı": "Shop name",
    "Adın soyadın": "Your full name",
    "Kullanıcı adı (girişte bunu yazacaksın)": "Username (you'll type this to sign in)",
    "Şifre (tekrar)": "Password (again)",
    "Şifre (en az {n} karakter)": "Password (at least {n} characters)",
    "Dükkanı aç": "Open shop",
    "Hesabın zaten var mı? <a href=\"/giris\">Giriş yap</a>":
        "Already have an account? <a href=\"/giris\">Sign in</a>",

    # --- Ana Menü / Bugün ekrani ---
    "Kasadaki nakit": "Cash on hand",
    "Tedarikçilere borç": "Debt to suppliers",
    "Bugünün cirosu": "Today's revenue",
    "Bugünün net kârı": "Today's net profit",
    "Hazır": "Ready",
    "yaklaşık {n} {koli}": "about {n} {koli}",
    "Yapman gerekenler": "What you need to do",
    "Şu an acil bir şey yok, stoklar yeterli.":
        "Nothing urgent right now — stock is sufficient.",
    "{ad} BİTTİ": "{ad} OUT OF STOCK",
    "{ad} bitmek üzere — yaklaşık {gun} günlük kaldı":
        "{ad} almost out — about {gun} days left",
    "{ad} kritik seviyenin altında": "{ad} is below the critical level",
    "Elde {stok} {birim}": "{stok} {birim} in stock",
    "günde ortalama {gunluk} {birim} gidiyor":
        "about {gunluk} {birim} used per day",
    "{sayi} {parti} üret": "produce {sayi} {parti}",
    "({cikacak} {birim} çıkar, yaklaşık {tutar})":
        "(yields {cikacak} {birim}, about {tutar})",
    "{miktar} {birim} {eylem}": "{eylem} {miktar} {birim}",
    "(yaklaşık {tutar})": "(about {tutar})",
    "Bugün girilen satışlar": "Sales entered today",
    "Ürün": "Product",
    "Miktar": "Quantity",
    "Tutar": "Amount",
    "Henüz giriş yapılmadı.": "No entries yet.",

    # --- sag/yan panel (ana menu) ---
    "{sehir} — hava": "{sehir} — weather",
    "Tahmin sayfasını aç": "Open the forecast page",
    "Ne üretmeli": "What to produce",
    "{miktar} {birim} açık": "{miktar} {birim} short",
    "Tahmine göre eldeki stok bu kadar yetmiyor. Kazan tam çırpıldığı için "
    "öneri her zaman tam sayıdır.":
        "Based on the forecast, current stock won't cover this. Since a batch "
        "is churned whole, the suggestion is always a whole number.",
    "Hava ve satış tahmini için <a href=\"/ayarlar\">Ayarlar</a> sayfasından "
    "ilini seç.":
        "For weather and sales forecasts, pick your city on the "
        "<a href=\"/ayarlar\">Settings</a> page.",
    "Bugün": "Today",
    "Yarın": "Tomorrow",
    "Pazartesi": "Monday",
    "Salı": "Tuesday",
    "Çarşamba": "Wednesday",
    "Perşembe": "Thursday",
    "Cuma": "Friday",
    "Cumartesi": "Saturday",
    "Pazar": "Sunday",

    # --- islem sonrasi mesajlar (bildirimler) ---
    "Şablon bulunamadı.": "Template not found.",
    "{ad} şablonu yüklendi.": "{ad} template loaded.",
    "Menünün adını yaz.": "Enter a name for the menu.",
    "Menü bulunamadı.": "Menu not found.",
    "{ad} eklendi. Ürünlerini işaretleyip kaydet.":
        "{ad} added. Check its products and save.",
    "{ad} adında başka bir menü var.": "Another menu named {ad} already exists.",
    "{ad} adında bir menü zaten var.": "A menu named {ad} already exists.",
    "{ad} kaydedildi.": "{ad} saved.",
    "{ad} geçerli: {kapanan} ürün kapandı, {acilan} ürün açıldı.":
        "{ad} is active: {kapanan} products closed, {acilan} opened.",
    "Tamam, {gun} gün sormayacağım.": "OK, I won't ask for {gun} days.",
    "{ad} silindi. Ürünler olduğu gibi duruyor.":
        "{ad} deleted. The products are unchanged.",
    "İl adı yazılmamış.": "No city entered.",
    "'{il}' MGM il listesinde bulunamadı. İl adını tam yaz (ilçe değil, il).":
        "'{il}' isn't in the MGM province list. Write the full province name "
        "(province, not district).",
    "{il} kaydedildi ama hava verisi alınamadı — internet bağlantını kontrol et.":
        "{il} saved, but weather data couldn't be fetched — check your "
        "internet connection.",
    "{il} kaydedildi. {kaynak} kaynağından {ileri} günlük tahmin alındı.":
        "{il} saved. Got a {ileri}-day forecast from {kaynak}.",
    "Önce il seç.": "Pick a city first.",
    "Hava verisi alınamadı; internet bağlantısını kontrol et.":
        "Couldn't get weather data; check your internet connection.",
    "Sayım silindi, satışlar geri alındı.": "Count deleted, sales reverted.",
    "Hiçbir alan doldurulmamış.": "No fields were filled in.",
    "Hiçbir miktar yazılmamış.": "No amounts were entered.",
    "{girilen} satış kaydedildi. Günün cirosu {ciro}.":
        "{girilen} sales recorded. Today's revenue {ciro}.",
    "Üretim yapılmadı, malzeme yetmiyor: {detay}":
        "Nothing produced — not enough material: {detay}",
    "Üretim kaydedildi, malzemeler stoktan düşüldü.":
        "Production recorded, materials deducted from stock.",
    "Üretim kaydedilemedi; parti sayısını kontrol et.":
        "Production couldn't be recorded; check the batch count.",
    "Kalem seçilmemiş.": "No item selected.",
    "Miktar yazılmamış.": "No quantity entered.",
    "Alım kaydedildi ({miktar} {birim} stoğa girdi).":
        "Purchase recorded ({miktar} {birim} added to stock).",
    "Gider kaydedildi.": "Expense recorded.",
    "Çalışanın adı yazılmamış.": "No employee name entered.",
    "Kayıt bulunamadı.": "Record not found.",
    "{ad} listeye eklendi.": "{ad} added to the list.",
    "{ad} güncellendi.": "{ad} updated.",
    "Maaş yazılmadı: bu ay zaten yazılmış ya da maaşı olan çalışan yok.":
        "No salary posted: already posted this month, or no staff have a salary.",
    "{adet} kişinin maaşı gidere yazıldı ({tutar}).":
        "Salaries for {adet} people posted as expense ({tutar}).",
    "Ödeme kaydedildi.": "Payment recorded.",
    "Stok düzeltildi ({fark} fark kaydedildi).":
        "Stock adjusted ({fark} difference recorded).",
    "Kalemin adını yaz.": "Enter a name for the item.",
    "{ad} zaten kayıtlı.": "{ad} is already registered.",
    "{ad} eklendi. Şimdi ayrıntılarını doldur.": "{ad} added. Now fill in its details.",
    "{ad} adında başka bir kalem var.": "Another item named {ad} already exists.",
    "Bu kalemin geçmiş kayıtları var, tamamen silinmedi; kullanım dışı yapıldı "
    "ve listelerden kalktı.":
        "This item has past records, so it wasn't fully deleted; it was "
        "deactivated and removed from the lists.",
    "Kalem silindi.": "Item deleted.",
    "Boş reçete eklendi, malzemelerini yaz.":
        "Empty recipe added — enter its materials.",
    "Reçete kaydedildi.": "Recipe saved.",
    "Reçete silindi.": "Recipe deleted.",
    "Malzeme çıkarıldı.": "Material removed.",
    "Kayıt silindi, stok ve kasa geri alındı.":
        "Entry deleted, stock and cash reverted.",
    "Kayıt silinemedi.": "Entry couldn't be deleted.",
    "Ad ve başlangıç tarihi gerekli.": "Name and start date are required.",
    "Tarih anlaşılamadı.": "Date not understood.",
    "Bitiş tarihi başlangıçtan önce olamaz.":
        "The end date can't be before the start date.",
    "{ad} takvime eklendi.": "{ad} added to the calendar.",
    "Değiştirildi.": "Updated.",
    "Silindi.": "Deleted.",
    "Bu kaydı program üretiyor; silinmez, kapatılabilir.":
        "The program generates this record; it can't be deleted, only turned off.",
    "Kaydedildi.": "Saved.",
    "Kaydedildi. Kullanım dışı olduğu için menülerden de çıkarıldı.":
        "Saved. Since it's deactivated, it was also removed from the menus.",
    "Tüm zamanlar": "All time",

    # --- Satis ekrani ---
    "Rafta kalanı say": "Count what's left",
    "Tek tek gir": "Enter one by one",
    "Gün sonu sayımı": "End-of-day count",
    "Kapanışta rafta ne kaldığını yaz. Program kaç sattığını, ciroyu ve kârı "
    "kendisi hesaplar. Malzeme aldıysan <b>önce</b> Alım sayfasından gir, sonra "
    "buradan say.":
        "At closing, enter what's left on the shelf. The program works out how "
        "much you sold, the revenue and the profit. If you bought materials, "
        "enter them on the Purchases page <b>first</b>, then count here.",
    "rafta olması gereken": "should be on the shelf",
    "elde yaklaşık": "about",
    "bir {koli} bitti": "a {koli} ran out",
    "Satılan ürünler — rafta kalanı yaz":
        "Products sold — enter what's left on the shelf",
    "Miktarı elle girilenler": "Entered by hand",
    "Bunlar sayımdan bulunamaz, kaç sattığını sen yazarsın.":
        "These can't be worked out from a count — you enter how much you sold.",
    "Diğer sayılanlar": "Other counted items",
    "Bunlar satılmıyor ama stokları gerçeğe eşitlensin diye sayılıyor; fark fire "
    "yazılır.":
        "These aren't sold but are counted so their stock matches reality; the "
        "difference is recorded as waste.",
    "Verilen malzemeler": "Supplies handed out",
    "Bunlar tek tek sayılmıyor. O gün bir kolisi bittiyse işaretle; program bir "
    "koli düşer ve tutarını günün satışlarına paylaştırır.":
        "These aren't counted one by one. If a case ran out that day, check it; "
        "the program deducts one case and spreads its cost across the day's sales.",
    'Sayılacak kalem yok. <b>Ürün &amp; Malzeme</b> sayfasından kalemlerin "gün '
    'sonu sayımı" ayarını doldur.':
        'Nothing to count. Set each item\'s "end-of-day count" option on the '
        '<b>Products &amp; Materials</b> page.',
    "Sayımı kaydet ve hesapla": "Save count and calculate",
    "Hiçbir şey satılmamış görünüyor.": "Looks like nothing was sold.",
    "{ad} sayımı {miktar} {birim} eksik çıktı":
        "{ad} count came up {miktar} {birim} short",
    "Bu miktar fire olarak yazıldı ve kâra yansımadı. Fire, ikram ya da kaplara "
    "fazla konulmuş olabilir. Sürekli aynı yönde çıkıyorsa reçetedeki miktarı düzelt.":
        "This amount was recorded as waste and didn't affect profit. It could be "
        "spoilage, giveaways, or over-filled cups. If it always goes the same way, "
        "fix the amount in the recipe.",
    "{ad} sayımı {miktar} {birim} fazla çıktı":
        "{ad} count came up {miktar} {birim} over",
    "Kayıtta olması gerekenden fazla var. Üretim ya da alım girmeyi unutmuş olabilirsin.":
        "There's more than the records expect. You may have forgotten to enter a "
        "production or a purchase.",
    "Satılmayan malzemeler için {tutar} harcanmış; bu tutar yukarıdaki kârlardan "
    "düşülmüş durumda.":
        "{tutar} was spent on non-sold supplies; that amount is already deducted "
        "from the profits above.",
    "{tarih} — sayımdan hesaplananlar": "{tarih} — calculated from the count",
    "Satılan": "Sold",
    "Ciro": "Revenue",
    "Kâr": "Profit",
    "TOPLAM": "TOTAL",
    "Bu günün sayımını sil ve baştan gir":
        "Delete this day's count and start over",
    "elde {stok} {birim}": "{stok} {birim} in stock",
    'Satılacak ürün yok. <b>Ürün &amp; Malzeme</b> sayfasından bir kaleme '
    '"satılır" işareti koy.':
        'Nothing to sell. Mark an item as "sold" on the <b>Products &amp; '
        'Materials</b> page.',
    "Bu tarihe satış girilmemiş.": "No sales entered for this date.",
    "Satış girişi": "Sales entry",
    "Sattığın kadarını yaz — tek tek de girebilirsin, gün sonunda toplu da. "
    "Ürünün reçetesi varsa malzemeler stoktan otomatik düşer.":
        "Enter how much you sold — one at a time, or all at once at day's end. If "
        "the product has a recipe, its materials are deducted from stock automatically.",
    "Satışları kaydet": "Save sales",
    "{tarih} satışları": "Sales for {tarih}",
    "sil": "delete",

    # --- Uretim ekrani ---
    "MALZEME YOK": "NO MATERIAL",
    "en fazla {n} parti": "at most {n} batches",
    'Üretilen ürün yok. <b>Ürün &amp; Malzeme</b> sayfasından bir kaleme '
    '"üretilir" işareti koyup reçetesini yaz.':
        'No produced items. Mark an item as "produced" on the <b>Products &amp; '
        'Materials</b> page and write its recipe.',
    "Ne üretildi": "What was produced",
    "Kaç parti": "How many batches",
    "Üretimi kaydet": "Save production",
    "parti": "batch",
    "{tarih} üretimi": "Production for {tarih}",
    "Çıkan": "Output",
    "Malzeme maliyeti": "Material cost",
    "Bu tarihe üretim girilmemiş.": "No production entered for this date.",
    "Üretim girişi": "Production entry",
    "Kaç parti yaptığını yaz; reçetedeki malzemeler stoktan otomatik düşer, çıkan "
    "ürün stoğa girer. Malzeme yetmiyorsa program üretimi kaydetmez.":
        "Enter how many batches you made; the recipe's materials are deducted from "
        "stock and the output is added to stock. If there isn't enough material, "
        "the program won't record the production.",
    "stok takibi yok, sınırsız": "no stock tracking, unlimited",
    "üretilemez": "can't produce",
    "{kisit} bitti": "{kisit} ran out",
    "önce {kisit} biter": "{kisit} runs out first",
    "{n} ürün şu an üretilemiyor": "{n} products can't be produced right now",
    'Malzemesi bitmiş. <a href="/para">Alım / Gider</a> sayfasından eksik malzemeyi '
    'girince buradan üretebilirsin.':
        'Out of material. Once you enter the missing material on the <a href="/para">'
        'Purchases / Expenses</a> page, you can produce it here.',
    "Eldeki malzemeyle ne kadar üretebilirsin":
        "How much you can produce with materials on hand",
    "En fazla": "At most",
    "Sınırlayan malzeme": "Limiting material",

    # --- Stok ekrani ---
    "stok tutulmuyor": "not tracked",
    "{n} gün": "{n} days",
    "{ad} (kayıtta {stok} {birim})": "{ad} (recorded {stok} {birim})",
    "Stoğun toplam değeri": "Total stock value",
    "Stoklar": "Stock",
    "Kalem": "Item",
    "Eldeki": "In stock",
    "Kritik": "Critical",
    "Kaç gün yeter": "Days left",
    "Değeri": "Value",
    "Sayım düzeltmesi": "Stock correction",
    "Elle saydığında gerçek miktarı buraya yaz; program farkı fire olarak kaydeder "
    "ve stoğu gerçeğe eşitler.":
        "When you count by hand, enter the real amount here; the program records "
        "the difference as waste and matches stock to reality.",
    "Gerçekte ne kadar var": "How much there really is",
    "Stoğu düzelt": "Correct stock",

    # --- Alim / Gider ekrani ---
    "Belirtilmemiş": "Unspecified",
    "Borç yok": "No debt",
    "Borcun yok.": "You have no debt.",
    "peşin": "cash",
    "veresiye": "on credit",
    "Henüz alım girilmemiş.": "No purchases entered yet.",
    "Henüz çalışan girilmemiş": "No staff entered yet",
    "{n} kişi — aylık {tutar} maaş yükü": "{n} people — {tutar} monthly salary load",
    "bu ayın maaşı henüz yazılmadı": "this month's salary not posted yet",
    "Henüz gider girilmemiş.": "No expenses entered yet.",
    "Toplam borç": "Total debt",
    "Malzeme alımı": "Material purchase",
    'Koli/çuval ile aldıysan "kaç koli" kutusuna yaz, program adede çevirir.':
        'If you bought by case/sack, enter "how many cases" and the program '
        'converts it to units.',
    "Kaç koli / çuval": "How many cases / sacks",
    "Üstüne kaç birim": "Plus how many units",
    "Ödenecek tutar ({para})": "Amount to pay ({para})",
    "Ödeme": "Payment",
    "Veresiye (borca yazılsın)": "On credit (add to debt)",
    "Peşin (kasadan çıksın)": "Cash (take from till)",
    "Alımı kaydet": "Save purchase",
    "Kimler çalışıyor, maaşları ne kadar. Ay başında hepsinin maaşını tek tuşla "
    "gidere yazdırmak için burası — tek tek girmene gerek yok.":
        "Who works here and what they earn. Post everyone's salary as an expense "
        "with one tap at the start of the month — no need to enter them one by one.",
    "Çalışanlar sayfasını aç": "Open the staff page",
    "Gider": "Expense",
    "Kira, elektrik, personel, yakıt gibi malzeme dışı harcamalar. Maaşlar için "
    "yukarıdaki Çalışanlar sayfasını kullan.":
        "Non-material spending like rent, electricity, staff, fuel. For salaries, "
        "use the Staff page above.",
    "Açıklama": "Description",
    "Elektrik faturası": "Electricity bill",
    "Tutar ({para})": "Amount ({para})",
    "Gideri kaydet": "Save expense",
    "Tedarikçiye ödeme": "Payment to supplier",
    "Tedarikçi": "Supplier",
    "Ödenen tutar ({para})": "Amount paid ({para})",
    "Ödemeyi kaydet": "Save payment",
    "Kime ne kadar borçlusun": "Who you owe and how much",
    "Son alımlar": "Recent purchases",
    "Tarih": "Date",
    "Son giderler": "Recent expenses",

    # --- Calisanlar ekrani ---
    "Dondurma ustası": "Ice cream maker",
    "Tezgâhtar": "Counter staff",
    "Kasiyer": "Cashier",
    "Bulaşıkçı": "Dishwasher",
    "Temizlik": "Cleaner",
    "Kurye": "Courier",
    "Çırak": "Apprentice",
    "Değişikliği kaydet": "Save changes",
    "Çalışanı ekle": "Add employee",
    'Doldurursan listede "ayrıldı" görünür ve maaşı bir daha yazılmaz.':
        'If you fill it in, they show as "left" in the list and their salary is '
        'no longer posted.',
    "Ayrılış tarihi": "Leaving date",
    "Adı soyadı": "Full name",
    "Ahmet Yılmaz": "John Smith",
    "Görevi": "Role",
    "Telefon": "Phone",
    "Eline geçen aylık maaş ({para})": "Net monthly salary ({para})",
    "Üstüne SGK + vergi ({para})": "Plus social security + tax ({para})",
    "İşe giriş tarihi": "Start date",
    "Not": "Note",
    "Hafta sonları geliyor": "Comes on weekends",
    "çalışıyor": "working",
    "ayrıldı": "left",
    "düzenle": "edit",
    "Henüz çalışan girilmemiş. Aşağıdaki formdan ekle.":
        "No staff entered yet. Add them with the form below.",
    "Bu ayın maaşları <b>zaten gidere yazılmış</b>. Yanlışsa aşağıdaki listeden ya "
    "da Alım / Gider ekranından tek tek silebilirsin.":
        "This month's salaries are <b>already posted as expenses</b>. If that's "
        "wrong, you can delete them one by one from the list below or the "
        "Purchases / Expenses screen.",
    "Önce çalışan ekle.": "Add an employee first.",
    "Tek tuşla, halen çalışan {n} kişinin her biri için ayrı bir gider satırı "
    "yazılır (net maaş + SGK). Toplam <b>{tutar}</b> kasadan düşer. Aynı ay ikinci "
    "kez yazılmaz.":
        "With one tap, a separate expense line is posted for each of the {n} "
        "current staff (net salary + social security). A total of <b>{tutar}</b> "
        "comes out of the till. It won't be posted twice in the same month.",
    "Bu ayın maaşlarını gidere yaz": "Post this month's salaries as expense",
    "Henüz maaş gideri yazılmamış.": "No salary expense posted yet.",
    "{ad} — bilgileri düzenle": "{ad} — edit details",
    "vazgeç": "cancel",
    "Çalışan sayısı": "Headcount",
    "{n} kişi": "{n} people",
    "Aylık maaş yükü": "Monthly salary load",
    "{net} net + {sgk} SGK/vergi": "{net} net + {sgk} social security/tax",
    'Bu liste bir kayıt defteri — buraya yazmak tek başına kasadan para çıkarmaz. '
    'Maaş ancak aşağıdaki <b>"maaşları gidere yaz"</b> tuşuna basınca gider olur.':
        'This list is a register — writing here alone takes no money from the '
        'till. A salary becomes an expense only when you press the <b>"post '
        'salaries as expense"</b> button below.',
    "Ad": "Name",
    "Görev": "Role",
    "Net maaş": "Net salary",
    "SGK/vergi": "Social security/tax",
    "Dükkâna maliyeti": "Cost to shop",
    "Durum": "Status",
    "Bu ayın maaşları": "This month's salaries",
    "Yeni çalışan ekle": "Add new employee",
    "SGK/vergi kutusunu bilmiyorsan muhasebecine sor; asgari ücretli bir çalışanda "
    "2026'da net maaşın üstüne kabaca 12.000 {para} biniyor.":
        "If you don't know the social security/tax figure, ask your accountant; "
        "for a minimum-wage worker in 2026 it adds roughly 12,000 {para} on top "
        "of the net salary.",
    "Yazılmış maaş giderleri": "Posted salary expenses",
    "Kim": "Who",

    # --- ay adlari (uzun / kisa) ---
    "Ocak": "January", "Şubat": "February", "Mart": "March", "Nisan": "April",
    "Mayıs": "May", "Haziran": "June", "Temmuz": "July", "Ağustos": "August",
    "Eylül": "September", "Ekim": "October", "Kasım": "November", "Aralık": "December",
    "Oca": "Jan", "Şub": "Feb", "Nis": "Apr", "Haz": "Jun", "Tem": "Jul",
    "Ağu": "Aug", "Eyl": "Sep", "Eki": "Oct", "Kas": "Nov", "Ara": "Dec",

    # --- Raporlar ekrani ---
    "Gün": "Day", "Hafta": "Week", "Ay": "Month", "Tümü": "All",
    "{hafta} haftası": "week of {hafta}",
    "Son günler": "Recent days", "Son haftalar": "Recent weeks",
    "Son aylar": "Recent months", "Aylara göre": "By month",
    "Bugüne kadar girilmiş bütün kayıtlar.": "All records entered so far.",
    "Göster": "Show",
    "bu dönemde satılan": "sold this period",
    "{gun} günde · günde ortalama {ort}": "over {gun} days · {ort} per day avg",
    "Satılanların maliyeti": "Cost of goods sold",
    "Giderler": "Expenses",
    "Net kâr": "Net profit",
    "Ciro {ciro}; bunun %{m}'i satılanların maliyeti, %{g}'i giderler, %{n}'i net kâr.":
        "Revenue {ciro}; of this {m}% is cost of goods sold, {g}% expenses, {n}% net profit.",
    "Ciro burada bitiyor: {ciro}": "Revenue ends here: {ciro}",
    'Maliyet ve gider cironun üstünde: bu dönem <b style="color:#c1392b">{zarar} zarar</b>.':
        'Cost and expenses exceed revenue: a <b style="color:#c1392b">{zarar} loss</b> this period.',
    "Maliyet ve giderler toplamı {toplam}, ciro {ciro}; aradaki fark {zarar} zarar.":
        "Cost and expenses total {toplam}, revenue {ciro}; the gap is a {zarar} loss.",
    "Para nereye gitti?": "Where did the money go?",
    "satıştan gelen para": "money from sales",
    "satılan ürünlerin içine giren malzeme":
        "materials that went into the products sold",
    "Brüt kâr": "Gross profit",
    "kira, elektrik, personel, vergi…": "rent, electricity, staff, tax…",
    "Alımlar ve ödemeler": "Purchases and payments",
    "Bunlar yukarıdaki kâr hesabına girmez: alınan malzeme stoğa yazılır, kâr "
    "ancak o malzeme satıldığında ortaya çıkar. Buradaki rakamlar paranın kasadan "
    "ne zaman çıktığını gösterir.":
        "These don't enter the profit calculation above: bought material is added "
        "to stock, and profit appears only when it's sold. The figures here show "
        "when money left the till.",
    "Peşin alımlar": "Cash purchases",
    "Veresiye alımlar": "Credit purchases",
    "(borca yazıldı)": "(added to debt)",
    "Tedarikçiye ödenen": "Paid to supplier",
    "Üretime giren malzeme": "Material used in production",
    "{ad} — {miktar} {birim} satıldı, ciro {ciro}, kâr {kar}":
        "{ad} — {miktar} {birim} sold, revenue {ciro}, profit {kar}",
    "Ürünler kâra göre sıralı; çubuk uzunluğu en çok kazandırana oranla.":
        "Products ranked by profit; bar length relative to the top earner.",
    "En çok kazandıran ürünler": "Most profitable products",
    "Bu dönemde satış kaydı yok.": "No sales recorded this period.",
    "Satılan": "Sold",
    "{n} ürünün tamamını tablo olarak gör": "See all {n} products as a table",
    "{etiket} — ciro {ciro}, brüt kâr {kar}":
        "{etiket} — revenue {ciro}, gross profit {kar}",
    "{baslik}: ciro sütunları, eskiden yeniye.":
        "{baslik}: revenue bars, oldest to newest.",
    "Koyu sütun şu an baktığın dönem. Sütuna tıklayınca o dönemin raporu açılır.":
        "The dark bar is the period you're viewing. Click a bar to open that "
        "period's report.",
    "Henüz satış kaydı yok.": "No sales recorded yet.",
    "Rakamları tablo olarak gör": "See the figures as a table",
    "Kasa değişimi": "Till change",
    "giderler düşüldükten sonra": "after expenses",
    "kâr değil; kasaya net giren para": "not profit; net cash into the till",
    "İleriye bakmak için": "To look ahead",
    "Buradaki rakamlar olan biteni anlatır. Önümüzdeki günlerde ne kadar "
    "satacağını ve ne üretmen gerektiğini tahmin sayfası söyler.":
        "These figures tell you what happened. The forecast page tells you how "
        "much you'll sell and what to produce in the coming days.",
    "Yedi günlük hava, ciro tahmini ve üretim önerisi":
        "Seven-day weather, revenue forecast and production suggestion",
    # Gider ayrintisi
    "Gider ne demek?": "What is an expense?",
    "Bu dönemde hiç gider girilmemiş.": "No expenses entered this period.",
    "Gider, malzeme alımı dışında kalan harcamalardır: kira, elektrik, su, "
    "personel, bakım, vergi gibi. Süt, külah, kakao gibi malzemeye ödenen para "
    "gidere değil, “Alımlar ve ödemeler” bölümüne yazılır.":
        "An expense is spending other than buying materials: rent, electricity, "
        "water, staff, maintenance, tax, etc. Money paid for materials like milk, "
        "cones or cocoa goes to the “Purchases and payments” section, "
        "not to expenses.",
    "Gider kalemleri, büyükten küçüğe; çubuk uzunluğu toplam gider içindeki payı.":
        "Expense items, largest to smallest; bar length is the share of total expenses.",
    "Neye harcanmış": "What it went on",
    "Toplam": "Total",
    "Tek tek kayıtlar": "Individual records",
    "Giderler neye harcandı?": "What were expenses spent on?",
    "Ne için": "What for",
    'Gider eklemek ya da silmek için <a href="/para">Alım / Gider</a> sayfasını kullan.':
        'To add or delete an expense, use the <a href="/para">Purchases / '
        'Expenses</a> page.',

    # --- Tahmin ekrani ---
    "Özel günler": "Special days",
    "Bayram, festival, okul tatili gibi günleri takvime yazarsan tahmin o günleri "
    "ayrı öğrenir.":
        "If you add days like holidays, festivals and school breaks to the "
        "calendar, the forecast learns them separately.",
    "Özel gün takvimini aç": "Open the special-days calendar",
    "Bayram, festival, tatil — girilen günler ve öğrenilenler":
        "Holidays, festivals, breaks — entered days and what's learned",
    "Önce şehri seç": "Pick your city first",
    'Tahmin, resmi MGM hava verisine dayanıyor. Hangi ildesin? <a href="/ayarlar">'
    'Ayarlar</a> sayfasının en altındaki "Hava ve tahmin" bölümünden ilini seç, '
    'gerisi kendiliğinden gelir.':
        'The forecast is based on official MGM weather data. Which province are '
        'you in? Pick it in the "Weather and forecast" section at the bottom of '
        'the <a href="/ayarlar">Settings</a> page, and the rest follows.',
    "henüz alınmadı": "not fetched yet",
    "Hava verisi henüz alınamadı. İnternet bağlantını kontrol edip aşağıdaki "
    "düğmeye bas.":
        "Weather data couldn't be fetched yet. Check your internet connection and "
        "press the button below.",
    "Kaynak: resmi MGM tahmini · yağış ihtimali: Open-Meteo · son güncelleme: {son}":
        "Source: official MGM forecast · rain chance: Open-Meteo · last update: {son}",
    "Havayı şimdi güncelle": "Update weather now",
    "Satış tahmini": "Sales forecast",
    "Tahmin henüz çalışmıyor": "Forecast isn't working yet",
    'Sistem şu anda arka planda çalışıyor: her günün havası kaydediliyor. Sen gün '
    'sonu satışlarını girdikçe program "sıcaklık şu kadar olduğunda ciro şu kadar '
    'oluyor" ilişkisini kendisi çıkaracak. Bunun için senin bir şey yapman gerekmiyor.':
        'The system is working in the background: each day\'s weather is recorded. '
        'As you enter end-of-day sales, the program works out the "when the '
        'temperature is this, revenue is that" relationship by itself. You don\'t '
        'need to do anything for it.',
    "{gun} — ne kadar satılır": "{gun} — how much will sell",
    "elde yeterli var ({n} {birim})": "enough on hand ({n} {birim})",
    ", {n} {birim} artar": ", {n} {birim} left over",
    "{acik} {birim} açık → {cikacak} {birim} çıkar":
        "{acik} {birim} short → yields {cikacak} {birim}",
    "Önümüzdeki {n} gün için ne üretmeli": "What to produce for the next {n} days",
    "Tahmin edilen satışların reçetelerden hesaplanan malzeme ihtiyacı, eldeki "
    "stokla karşılaştırıldı.":
        "The material needs from forecast sales (via the recipes) compared with "
        "stock on hand.",
    "Gereken": "Needed",
    "Öneri": "Suggestion",
    "Alttaki küçük rakamlar tahminin gerçekleşebileceği aralık. Program geçmişte "
    "ortalama {hata} yanılmış; aralık buradan çıkıyor. Veri arttıkça aralık daralır.":
        "The small figures below are the range the forecast may land in. The "
        "program has been off by {hata} on average in the past; that's where the "
        "range comes from. It narrows as data grows.",
    "Hava": "Weather",
    "Tahmini ciro": "Forecast revenue",
    "yağışlı": "rainy",
    "yağış ihtimali": "chance of rain",

    # --- Ozel gunler ekrani ---
    "({n} gün)": "({n} days)",
    "kapat": "close",
    "aç": "open",
    "kapalı": "closed",
    "normalin {kat} katı": "{kat}× normal",
    "{n} günlük satıştan çıktı": "from {n} days of sales",
    "henüz öğrenilmedi — bu etiketten en az {n} gün satış girilmeli":
        "not learned yet — needs sales from at least {n} days of this tag",
    "Takvim boş.": "Calendar is empty.",
    "Bayram tarihi eksik": "Holiday date missing",
    "{liste} takvimde yok. Dini bayramlar her yıl kaydığı için elle giriliyor; "
    "aşağıdaki formdan ekle.":
        "{liste} not in the calendar. Religious holidays shift each year, so "
        "they're entered by hand; add them with the form below.",
    "Etiketler": "Tags",
    'Program her <b>etiket</b> için tek bir katsayı öğrenir: "bu etiketli günlerde '
    'ciro normalin kaç katı". Aynı etiketi taşıyan günler aynı havuza girer — 29 '
    'Ekim ile 23 Nisan birlikte "Resmi Tatil" katsayısını besler, o yüzden tek '
    'başına bir güne göre çok daha çabuk öğrenilir.':
        'The program learns a single factor for each <b>tag</b>: "on days with '
        'this tag, how many times normal is revenue". Days sharing a tag go into '
        'the same pool — Oct 29 and Apr 23 together feed the "Public Holiday" '
        'factor, so it\'s learned far faster than a single day on its own.',
    "Etiket": "Tag",
    "{yil}'da": "in {yil}",
    "Etiket yok.": "No tags.",
    "Takvim": "Calendar",
    "Resmi tatiller, bayramlar, arifeler ve Ramazan ayı her açılışta kendiliğinden "
    "yazılır. Bunlar silinmez — dükkânda fark yaratmıyorsa <b>kapat</b>, model o "
    "günleri hiç görmez.":
        "Public holidays, religious holidays, eves and the month of Ramadan are "
        "added automatically on each launch. They can't be deleted — if they make "
        "no difference in your shop, <b>close</b> them and the model never sees them.",
    "Ne": "What",
    "Yeni özel gün ya da dönem ekle": "Add a new special day or period",
    "Köprü günü, festival, yol çalışması, fındık toplama dönemi… Satışı normalden "
    "farklı yapan her şey buraya girilebilir. Tek günlükse bitiş tarihini boş bırak.":
        "A bridge day, festival, road works, the hazelnut harvest… anything that "
        "makes sales differ from normal can go here. For a single day, leave the "
        "end date empty.",
    "Adı": "Name",
    "Fındık toplama 2026": "Hazelnut harvest 2026",
    "Fındık Toplama": "Hazelnut Harvest",
    "Başlangıç": "Start",
    "Bitiş": "End",
    "Takvime ekle": "Add to calendar",
    '<b>Etiketi nasıl seçmeli:</b> tekrar eden bir şeyse her yıl <u>aynı</u> '
    'etiketi yaz — "Fındık Toplama 2026" değil, sadece "Fındık Toplama". Program '
    'yılları birleştirip tek katsayı öğrenir. Yılda {n} günün altında kalan '
    'etiketler öğrenilemez.':
        '<b>How to choose a tag:</b> if it recurs, write the <u>same</u> tag every '
        'year — not "Hazelnut Harvest 2026", just "Hazelnut Harvest". The program '
        'merges the years and learns one factor. Tags with fewer than {n} days a '
        'year can\'t be learned.',
    "bugün": "today",
    "yarın": "tomorrow",

    # --- Menuler ekrani ---
    "altında": "below",
    "üstünde": "above",
    "{gunler} — {n} gün üst üste en yüksek sıcaklık {esik}°C'nin {yon}.":
        "{gunler} — high temperature {yon} {esik}°C for {n} days in a row.",
    "Şimdi geç": "Switch now",
    "Planın tamamı": "Full plan",
    "Şimdi değil": "Not now",
    "Neden": "Reason",
    "Kapanacak çeşitlerden yeni üretim yapma.": "Don't produce more of closing varieties.",
    "Elde": "In stock",
    " ve {n} çeşit daha": " and {n} more varieties",
    "var.": "on hand.",
    "Almadan geçme": "Don't switch without buying",
    "{kapanan} ürün kapanacak, {acilan} ürün açılacak.":
        "{kapanan} products will close, {acilan} will open.",
    "Menü geçişi önerisi: {ad} — {ne_zaman}": "Menu switch suggestion: {ad} — {ne_zaman}",
    "Menü geçişi önerisi: {ad} — {ne_zaman}{ek}":
        "Menu switch suggestion: {ad} — {ne_zaman}{ek}",
    "(normalde {ort}, {gun} gün)": "(normally {ort}, {gun} days)",
    "üretme": "don't produce",
    "Bitmesi": "Runs out in",
    "Son 14 gün, günde": "Last 14 days, per day",
    "Geçmişte bu havada, günde": "Historically in this weather, per day",
    "Bugünkü satış hızıyla {gun} günde bitmeyecekler: ":
        "At today's sales pace they won't run out in {gun} days: ",
    ". Geçişten sonra da satılabilirler; ürün kapanınca stoğu silinmez.":
        ". They can still be sold after the switch; closing a product doesn't delete its stock.",
    "ilk kez açılıyor": "opening for the first time",
    "stokta yok": "out of stock",
    "son {gun} günde {eski} → {yeni} (%{artis} arttı)":
        "over the last {gun} days {eski} → {yeni} (up {artis}%)",
    "Kararı sen verirsin. Geçince kapanan ürünler satış ve üretim ekranlarından "
    "kalkar; geçmiş kayıtları ve stokları silinmez.":
        "The decision is yours. After switching, closed products drop off the "
        "sales and production screens; their history and stock aren't deleted.",
    "Açılacak ürünlerin ilk {gun} günü için. Geçen sefer satışı olan ürünlerde "
    "miktar o satıştan hesaplanır; ilk kez açılanda sadece stokta olmayan malzeme "
    "söylenir.":
        "For the first {gun} days of the opening products. For products sold last "
        "time, the amount is from those sales; for first-time ones, only the "
        "out-of-stock material is listed.",
    "Kapanacak ürünler ({n})": "Closing products ({n})",
    "Kapanacak ürün yok.": "No products closing.",
    "Açılacak ürünler ({n})": "Opening products ({n})",
    "Geçen sefer günde": "Last time, per day",
    "Açılacak ürün yok.": "No products opening.",
    "Malzeme": "Material",
    "Al": "Buy",
    "Eksik malzeme yok.": "No missing materials.",
    "Pahalanan malzemeler": "Materials that got pricier",
    "şu an geçerli": "currently active",
    "Bu menüye şimdi geç": "Switch to this menu now",
    "Menünün adı": "Menu name",
    "Geçiş önerisi": "Switch suggestion",
    "Eşik (en yüksek sıcaklık, °C)": "Threshold (high temperature, °C)",
    "Bu menüde satılan ürünleri işaretle. Hiçbir menüde işaretli olmayan ürün her "
    "zaman satılır. Malzemeleri işaretlemen gerekmez: sadece kapanan ürünlerde "
    "geçen malzeme (bir çeşidin aroması gibi) ürünle birlikte kendiliğinden kapanır.":
        "Check the products sold in this menu. A product not checked in any menu "
        "is always sold. You don't need to check materials: only a material used "
        "in a closing product (like a variety's flavor) closes with it automatically.",
    "Kaydet": "Save",
    "Menüyü sil": "Delete menu",
    "Şu an <b>{ad}</b> geçerli — {tarih} tarihinden beri.":
        "<b>{ad}</b> is active now — since {tarih}.",
    "Henüz hiçbir menüye geçilmedi; bütün ürünler olduğu gibi duruyor.":
        "No menu has been switched to yet; all products stay as they are.",
    "Geçmiş geçişler": "Past switches",
    "Menü dönemleri": "Menu periods",
    "Mevsime göre değişen menüler: dondurmacının yaz ve kış menüsü, lokantanın yaz "
    "ve kış sebzeleri. Menüye geçince o menüde olmayan ürünler satış, sayım ve "
    "üretim ekranlarından kalkar; geri dönünce yerine gelir. Hiçbir kayıt silinmez.":
        "Menus that change with the season: an ice cream shop's summer and winter "
        "menus, a restaurant's summer and winter vegetables. When you switch, "
        "products not in that menu drop off the sales, count and production "
        "screens; they return when you switch back. No record is deleted.",
    'Bir menüye "hava soğuyunca öner" dersen program 7 günlük hava tahminine bakar: '
    "en yüksek sıcaklık {gun} gün üst üste eşiğin altına inecekse ana menüde bir "
    "geçiş planı çıkarır — hangi gün, kapanacak ürünlerden elde ne kaldığı, ne "
    "alınması gerektiği. Geçişi sen yaparsın.":
        'If you set a menu to "suggest when it gets cold", the program checks the '
        "7-day forecast: if the high temperature will stay below the threshold for "
        "{gun} days in a row, it puts a switch plan on the home screen — which day, "
        "what's left of the closing products, what needs buying. You make the switch.",
    "Yeni menü": "New menu",
    "Kış menüsü": "Winter menu",
    "Şu an satılan ürünlerle başlasın": "Start with the currently sold products",
    "Menüyü ekle": "Add menu",
    # menuler.KOSULLAR
    "Kendim geçerim, öneri istemem": "I'll switch myself, no suggestions",
    "Hava soğuyunca öner": "Suggest when it gets cold",
    "Hava ısınınca öner": "Suggest when it gets warm",

    # --- rozetler ---
    "alınır": "bought",
    "üretilir": "produced",
    "satılır": "sold",
    "stok tutulmaz": "no stock",
    "mevsim dışı": "off-season",
    "rolsüz": "no role",

    # --- Urun & Malzeme (kalemler) ekrani ---
    "Henüz kalem yok.": "No items yet.",
    "Yeni kalem ekle": "Add new item",
    "Dükkanda adı, birimi ve stoğu olan her şey bir kalemdir: un da, hamur da, "
    "ekmek de. Ne olduğunu işaretlediğin kutucuklar belirler.":
        "Anything in the shop with a name, unit and stock is an item: flour, dough, "
        "bread. What it is is set by the boxes you check.",
    "Un": "Flour",
    "Birimi": "Unit",
    "Türü (listeleri gruplar)": "Type (groups the lists)",
    "Satın alınır": "Bought",
    "Üretilir (reçetesi var)": "Produced (has a recipe)",
    "Satılır": "Sold",
    "Ekle ve düzenlemeye geç": "Add and go to edit",
    "Bütün kalemler": "All items",
    "Türe göre gruplanmış. Tür sadece düzen içindir, hiçbir hesaba girmez — "
    "istediğin başlığı yazabilirsin.":
        "Grouped by type. Type is just for organisation and enters no calculation "
        "— you can write any heading.",
    "Birim": "Unit",
    "Alış": "Buy",
    "Satış": "Sell",
    "Stok": "Stock",
    # Sayim tarzlari
    "Gün sonu sayımında sorulmasın": "Don't ask in the end-of-day count",
    "Rafta kalanı sayarım": "I count what's left on the shelf",
    "Tek tek saymam, 'bir kolisi bitti' derim":
        "I don't count individually, I say 'a case ran out'",
    "Sattığım miktarı elle yazarım": "I enter the amount sold by hand",

    # --- Kalem (urun ayrinti) ekrani ---
    "Kalem bulunamadı.": "Item not found.",
    "{rozet} · stokta {stok} {birim} · birim maliyeti {maliyet}":
        "{rozet} · {stok} {birim} in stock · unit cost {maliyet}",
    "Adı": "Name",
    "Sıra (küçük olan üstte)": "Order (smaller on top)",
    "Üretilir (reçetesi üretimde düşer)":
        "Produced (its recipe is deducted at production)",
    "Stoğu tutulsun": "Track stock",
    "Kullanımda": "In use",
    "Alış fiyatı (bir {birim} için, {para})": "Buy price (per {birim}, {para})",
    "Satış fiyatı (bir {birim} için, {para})": "Sell price (per {birim}, {para})",
    "Kritik seviye (altına düşünce uyarır)":
        "Critical level (warns when it drops below)",
    "Toplu kabın adı": "Bulk container name",
    "koli": "case",
    "Bir {koli} kaç {birim}": "How many {birim} in one {koli}",
    "Açıklama (sadece ekranda görünür)": "Description (shown on screen only)",
    "Satılmaz ama harcanır — tutarını günün satışlarına paylaştır (kaşık, peçete)":
        "Not sold but consumed — spread its cost across the day's sales (spoons, napkins)",
    "Bu kalemi sil": "Delete this item",
    # Recete karti
    "Bu kalem üretiliyor: aşağıdaki malzemeler <b>üretim girdiğinde</b> stoktan "
    "düşer. Birden fazla reçete yazabilirsin — dondurmada olduğu gibi aynı stoğa "
    "farklı karışımlar akabilir.":
        "This item is produced: the materials below are deducted from stock "
        "<b>when you enter production</b>. You can write more than one recipe — as "
        "with ice cream, different mixes can flow into the same stock.",
    "Bu kalem üretilmiyor: aşağıdaki malzemeler <b>her satışta</b> stoktan düşer. "
    "Külahın içine konan dondurma, porsiyonun içine giren et böyle yazılır.":
        "This item isn't produced: the materials below are deducted from stock "
        "<b>on every sale</b>. The ice cream put in a cone, the meat in a portion, "
        "are written this way.",
    "çıkar": "remove",
    "Reçete boş.": "Recipe is empty.",
    "Reçete": "Recipe",
    "Reçetenin adı": "Recipe name",
    "Sade": "Plain",
    "Bir üretime verdiğin ad": "Name you give one production run",
    "kazan": "batch",
    "1 {parti} kaç {birim} çıkarır": "How many {birim} does 1 {parti} yield",
    "Çıkan bir {birim} başına malzeme maliyeti: <b>{maliyet}</b>":
        "Material cost per {birim} produced: <b>{maliyet}</b>",
    "Reçeteyi kaydet": "Save recipe",
    "reçeteyi sil": "delete recipe",
    "Malzeme ekle": "Add material",
    "Satır ekle": "Add row",
    "Bu kalemin reçetesi yok.": "This item has no recipe.",
    "Yeni reçete ekle": "Add new recipe",

    # --- Ayarlar ekrani ---
    "Gün sonu sayımı (rafta kalanı sayarım)":
        "End-of-day count (I count what's left on the shelf)",
    "Doğrudan satış girişi (kaç sattığımı yazarım)":
        "Direct sales entry (I enter how much I sold)",
    "İkisi de dursun, sekmeyle geçeyim": "Keep both, let me switch with a tab",
    "Ürün ve malzemeler": "Products and materials",
    "Yeni ürün eklemek, reçete yazmak, bir kalemin birimini ya da kolisini "
    "değiştirmek için burası.":
        "This is where you add a new product, write a recipe, or change an item's "
        "unit or case.",
    "Ürün &amp; Malzeme sayfasını aç": "Open the Products &amp; Materials page",
    "Kalem listesi, reçeteler ve satış şekilleri":
        "Item list, recipes and sale types",
    "Menü dönemlerini aç": "Open menu periods",
    "Yaz ve kış menüsü, mevsim geçişi ve geçiş önerisi":
        "Summer and winter menus, seasonal switch and suggestion",
    "Genel ayarlar": "General settings",
    "Dükkan adı": "Shop name",
    "Para birimi": "Currency",
    "Satış nasıl girilsin": "How to enter sales",
    "Kaç günlük kalınca uyarayım": "Warn when this many days are left",
    "Alırken kaç günlük alınsın": "How many days' worth to buy",
    "Günlük tüketim kaç günün ortalaması olsun":
        "Daily use is averaged over how many days",
    "Ayarları kaydet": "Save settings",
    "Fiyatlar": "Prices",
    'Hepsini tek ekrandan güncellemek için. Alım girdiğinde alış fiyatı zaten '
    'kendiliğinden güncellenir. Bir kalemin diğer ayarları için <a href="/kalemler">'
    'Ürün &amp; Malzeme</a> sayfasına git.':
        'To update them all from one screen. Entering a purchase updates the buy '
        'price automatically. For an item\'s other settings, go to the '
        '<a href="/kalemler">Products &amp; Materials</a> page.',
    "Alış fiyatı": "Buy price",
    "Satış fiyatı": "Sell price",
    "Kritik seviye": "Critical level",
    "Fiyatları kaydet": "Save prices",
    # Guvenlik / hesap
    "Hesabın": "Your account",
    "{ad} olarak girdin": "Signed in as {ad}",
    "Kullanıcı adın: <b>{eposta}</b> &nbsp;·&nbsp; Dükkanın: <b>{dukkan}</b><br>Bu "
    "dükkanın kayıtları kendi dosyasında tutulur; başka hiçbir dükkan onları "
    "göremez, sen de başka dükkanınkini göremezsin.":
        "Your username: <b>{eposta}</b> &nbsp;·&nbsp; Your shop: <b>{dukkan}</b><br>"
        "This shop's records are kept in their own file; no other shop can see "
        "them, and you can't see another shop's.",
    "Yeni şifre (en az {n} karakter)": "New password (at least {n} characters)",
    "Şifreyi değiştir": "Change password",
    "Şifreni değiştirince başka bir cihazda açık kalmış oturumlar etkilenmez; "
    "oradan çıkmak için o cihazda Çıkış'a bas.":
        "Changing your password doesn't affect sessions left open on another "
        "device; to sign out there, press Log out on that device.",
    "Güvenlik": "Security",
    "Şu an giriş yok: programı açan herkes doğrudan giriyor. <b>Dükkân içinde, "
    "kendi wifi'inde çalışırken bunun sakıncası yok</b> — dışarıdan kimse o ağda "
    "değil. Ama programı internete açarsan adresi bilen herkes kasayı, ciroyu ve "
    "tedarikçileri görür ve değiştirebilir. O durumda hesap şart.":
        "There's no login right now: anyone who opens the program gets straight "
        "in. <b>Inside the shop, on your own wifi, that's fine</b> — no one "
        "outside is on that network. But if you put the program on the internet, "
        "anyone who knows the address can see and change the till, revenue and "
        "suppliers. In that case an account is essential.",
    "Aşağıdan hesap kurarsan <b>bu dükkanın şu anki bütün kayıtları olduğu gibi "
    "kalır</b>, sadece önüne giriş ekranı gelir.":
        "If you set up an account below, <b>all of this shop's current records "
        "stay as they are</b> — a login screen just appears in front of them.",
    "Hesabı kur ve girişi aç": "Set up account and enable login",
    # Hava ayar karti
    "MGM (resmi) + geçmiş boşlukları Open-Meteo'dan":
        "MGM (official) + past gaps from Open-Meteo",
    "Sadece MGM (resmi)": "MGM only (official)",
    "Sadece Open-Meteo": "Open-Meteo only",
    "Seçili il: <b>{il}</b> · son güncelleme: {son}":
        "Selected province: <b>{il}</b> · last update: {son}",
    "Henüz il seçilmedi. Şehir seçilene kadar program hiçbir şekilde internete çıkmaz.":
        "No province selected yet. Until a city is chosen, the program never goes "
        "online in any way.",
    "Program hava verisini <b>resmi MGM servisinden</b> çeker ve onu geçmiş "
    "satışlarla karşılaştırıp ileriye dönük tahmin üretir. İnternet yoksa program "
    "normal çalışmaya devam eder, sadece tahmin susar.":
        "The program fetches weather from the <b>official MGM service</b> and "
        "compares it with past sales to produce a forward forecast. With no "
        "internet the program keeps working normally; only the forecast goes quiet.",
    "İl": "Province",
    "Hava verisi nereden gelsin": "Where weather data comes from",
    "İli kaydet ve havayı çek": "Save province and fetch weather",
    "Tahmin açık olsun (ana menünün solunda ve raporlarda görünür)":
        "Keep forecast on (shown on the home sidebar and in reports)",
    "Geçmişteki {geri} günün gerçekleşen havası tamamlandı.":
        "Actual weather for the past {geri} days was filled in.",
    # Kurulum
    "Hoş geldin — dükkanını seç": "Welcome — choose your shop",
    "Seçtiğin şablon sana hazır bir malzeme, ürün ve reçete listesi verir. Hepsi "
    "örnektir: sonradan <b>Ürün &amp; Malzeme</b> sayfasından silebilir, "
    "değiştirebilir, yenisini ekleyebilirsin. Program hiçbir ürünü özel olarak tanımaz.":
        "The template you pick gives you a ready list of materials, products and "
        "recipes. They're all examples: you can later delete, change or add to "
        "them on the <b>Products &amp; Materials</b> page. The program knows no "
        "product specially.",

    # --- hava durumu (hava.py HADISELER) ---
    "açık": "clear",
    "az bulutlu": "few clouds",
    "parçalı bulutlu": "partly cloudy",
    "çok bulutlu": "mostly cloudy",
    "hafif yağmurlu": "light rain",
    "yağmurlu": "rainy",
    "kuvvetli yağmurlu": "heavy rain",
    "sağanak yağışlı": "showers",
    "hafif sağanak yağışlı": "light showers",
    "kuvvetli sağanak yağışlı": "heavy showers",
    "mevzii sağanak yağışlı": "scattered showers",
    "gök gürültülü sağanak yağışlı": "thundery showers",
    "kuvvetli gök gürültülü sağanak": "strong thundery showers",
    "karla karışık yağmurlu": "sleet",
    "hafif kar yağışlı": "light snow",
    "kar yağışlı": "snow",
    "yoğun kar yağışlı": "heavy snow",
    "dolu": "hail",
    "sisli": "foggy",
    "puslu": "misty",
    "dumanlı": "hazy",
    "toz taşınımı": "dust",
    "rüzgarlı": "windy",
    "güneyli kuvvetli rüzgar": "strong southerly wind",
    "kuzeyli kuvvetli rüzgar": "strong northerly wind",
    "sıcak": "hot",
    "soğuk": "cold",
    "hava az bulutlu": "few clouds",

    # --- hesap.py eylem + tahmin.py durum metni ---
    "al": "buy",
    "üret": "produce",
    "Henüz hiç satış kaydı yok. Tahmin, geçmiş günlerin hava durumu ile o günün "
    "cirosunu karşılaştırarak öğreniyor; en az {en_az} günlük satış gerekiyor. Gün "
    "sonu satışlarını girmeye başladığında kendiliğinden çalışacak — senin ayrıca "
    "bir şey yapman gerekmiyor, her günün havası şimdiden kaydediliyor.":
        "No sales recorded yet. The forecast learns by comparing each past day's "
        "weather with that day's revenue; at least {en_az} days of sales are "
        "needed. It starts working on its own once you begin entering end-of-day "
        "sales — you don't need to do anything extra, each day's weather is "
        "already being recorded.",
    "{gun} günlük veri var, tahmin için en az {en_az} gün gerekiyor. {eksik} gün "
    "daha satış girildiğinde tahminler burada görünmeye başlayacak.":
        "There are {gun} days of data; the forecast needs at least {en_az}. Once "
        "{eksik} more days of sales are entered, forecasts will start showing here.",
    "{gun} günlük satış geçmişine bakıyor": "looking at {gun} days of sales history",
    "her 1 derece sıcaklık günlük ciroyu ortalama {deger} birim değiştiriyor":
        "each 1 degree of temperature changes daily revenue by about {deger} units",
    "sıcaklık etkisi için {n} gün daha gerekiyor":
        "{n} more days needed for the temperature effect",
    "geçmiş günlerin hepsi birbirine yakın sıcaklıkta ({fark} derece fark); "
    "sıcaklığın etkisini görmek için en az {en_az} derecelik fark gerekiyor":
        "all past days are at similar temperatures ({fark} degrees apart); at "
        "least {en_az} degrees of spread is needed to see the temperature effect",
    "sıcaklık ile satış arasında güvenilir bir ilişki bulunamadı, şimdilik günlük "
    "ortalama kullanılıyor":
        "no reliable relationship found between temperature and sales; using the "
        "daily average for now",
    "yağmurlu günlerde satış %{yuzde} {yon}":
        "on rainy days sales {yon} {yuzde}%",
    "artıyor": "rise",
    "düşüyor": "fall",
    "yağmur etkisi için yeterli yağmurlu gün geçmedi":
        "not enough rainy days yet for the rain effect",
    "neredeyse bütün günler yağışlı geçmiş, karşılaştıracak kuru gün yok":
        "almost all days were rainy, no dry days to compare",
    "en yoğun gün {gun} (normalin {kat} katı)":
        "busiest day is {gun} ({kat}× normal)",
    "hafta sonu satışı hafta içinin {kat} katı (her güne ayrı katsayı için {n} gün "
    "gerekiyor)":
        "weekend sales are {kat}× weekdays (a separate factor per day needs {n} days)",
    "hafta sonu etkisi için {n} gün gerekiyor":
        "{n} days needed for the weekend effect",
    "{etiket}: normalin {kat} katı ({adet} güne bakarak)":
        "{etiket}: {kat}× normal (based on {adet} days)",
    "özel gün etkisi için henüz o günlerden geçilmedi":
        "no special days have occurred yet for their effect",

    # --- Kurulum sablonlari (veritabani.py SABLONLAR ad/aciklama) ---
    "Dondurmacı": "Ice Cream Shop",
    "Kazanda dondurma üretimi, külah/kap ile satış, gün sonu sayımı.":
        "Batch ice cream production, sales by cone/cup, end-of-day counting.",
    "Pastane": "Patisserie",
    "Pandispanya/krema gibi ara ürünler, dilim ve bütün pasta satışı.":
        "Intermediate products like sponge/cream, sales of slices and whole cakes.",
    "Fırın": "Bakery",
    "Hamurdan ekmek/simit/poğaça üretimi, raftaki kalanı sayarak satış.":
        "Bread/simit/pastry production from dough, sales by counting what's left.",
    "Restoran": "Restaurant",
    "Porsiyon reçeteleri; satışlar adisyondan doğrudan girilir.":
        "Portion recipes; sales entered directly from the check.",
    "Boş başla": "Start empty",
    "Hiçbir şey eklenmez; malzemeleri ve ürünleri sen girersin.":
        "Nothing is added; you enter the materials and products yourself.",

    # --- Sablon seed verisi (veritabani.py SABLONLAR) ---
    # Sadece YENI dukkan acilirken, secili dile gore yazilir. Mevcut veriler
    # (kullanicinin kendi girdikleri) degismez.
    # Dukkan adlari
    "Dondurma Dükkanı": "Ice Cream Shop",
    # Birimler
    "adet": "pcs", "litre": "L", "gram": "g", "kutu": "box", "dilim": "slice",
    "kase": "bowl", "paket": "pack", "porsiyon": "portion",
    # Turler
    "Hammadde": "Raw material", "Ara ürün": "Intermediate", "Ürün": "Product",
    "Ambalaj": "Packaging", "Sarf": "Supplies", "Et": "Meat", "Sebze": "Vegetables",
    "Kuru gıda": "Dry goods", "İçecek": "Beverages", "Yemek": "Dishes",
    # Toplu kap adlari
    "çuval": "sack", "viyol": "tray",
    # Parti adlari
    "tepsi": "tray", "tekne": "trough", "fırın": "oven", "tencere": "pot",
    # Kalem adlari
    "Su": "Water", "Süt": "Milk", "Şeker": "Sugar", "Toz Şeker": "Caster Sugar",
    "Sahlep": "Salep", "Vanilya": "Vanilla",
    "Aroma - Çikolata": "Flavor - Chocolate", "Aroma - Çilek": "Flavor - Strawberry",
    "Aroma - Limon": "Flavor - Lemon", "Dondurma": "Ice Cream", "Külah": "Cone",
    "Cornette Külah": "Cornetto Cone", "Küçük Kap": "Small Cup", "Orta Kap": "Medium Cup",
    "Büyük Kap": "Large Cup", "Kilo Dondurma": "Ice Cream by the Kilo",
    "Pet Şişe Su (0,5 lt)": "Bottled Water (0.5 L)", "Kilo Kabı": "Kilo Tub",
    "Kaşık": "Spoon", "Peçete": "Napkin", "Islak Mendil": "Wet Wipe",
    "Pandispanya": "Sponge Cake", "Krema": "Cream", "Çikolatalı Krema": "Chocolate Cream",
    "Kakao": "Cocoa", "Yaş Pasta": "Layer Cake", "Dilim Yaş Pasta": "Cake Slice",
    "Kurabiye": "Cookie", "Pasta Kutusu": "Cake Box", "Yumurta": "Egg",
    "Tereyağı": "Butter", "Un": "Flour", "Ekmek": "Bread", "Simit": "Simit",
    "Peynirli Poğaça": "Cheese Pastry", "Maya": "Yeast", "Tuz": "Salt",
    "Susam": "Sesame", "Pekmez": "Molasses", "Ekmek Poşeti": "Bread Bag",
    "Mercimek": "Lentils", "Mercimek Çorbası": "Lentil Soup", "Pirinç": "Rice",
    "Soğan": "Onion", "Domates": "Tomato", "Kıyma": "Minced Meat",
    "Tavuk But": "Chicken Thigh", "Tavuk Şiş": "Chicken Skewer",
    "Adana Porsiyon": "Adana Portion", "Lavaş": "Lavash", "Ayran (kutu)": "Ayran (carton)",
    "Ayçiçek Yağı": "Sunflower Oil", "Çilek": "Strawberry", "Çikolata": "Chocolate",
    "Peynir": "Cheese", "Limon": "Lemon",
    # Recete adlari (kucuk harf varyantlari)
    "Çikolatalı krema": "Chocolate cream", "Yaş pasta": "Layer cake",
    "Ekmek hamuru": "Bread dough", "Simit hamuru": "Simit dough", "Poğaça": "Pastry",
    # Aciklamalar
    "Dolapta bekleyen hazır dondurma": "Ready ice cream waiting in the freezer",
    "Kaba konan miktar değişken; kaç kg sattığın elle yazılır":
        "The amount per cup varies; you enter how many kg you sold by hand",
    "Pastanın tabanı": "The base of the cake",

    # --- Tahmin gunlugu ve geriye donuk test ---
    "Tahmin günlüğü": "Forecast log",
    "Tahmin ne kadar tutuyor?": "How accurate is the forecast?",
    "Her gün verdiği tahmini kaydedip akşam gerçekleşenle karşılaştırır; ayrıca "
    "geçmişin tamamında 'az veriyle ne kadar isabet' testini yapar.":
        "It records each day's forecast and compares it with the evening's actual; "
        "it also runs a 'how accurate with little data' test across all history.",
    "Tahmin günlüğü ve geriye dönük test": "Forecast log and backtest",
    "Sabah ne dedik, akşam ne oldu · gün sayısına karşı hata eğrisi":
        "What we said in the morning vs the evening · error curve by day count",
    "Model": "Model",
    "Düz ortalama (kıyas)": "Flat average (baseline)",
    "%{t} hata": "{t}% error",
    "Gün sayısına karşı ortalama yüzde hata; model ve düz ortalama kıyası.":
        "Average percent error by day count; model vs flat-average baseline.",
    "Yatay eksen: modelin gördüğü gün sayısı. Dikey eksen: o güne kadarki ortalama "
    "yüzde hata. Veri arttıkça hata oturuyor — tezin kanıtı bu eğri.":
        "Horizontal axis: days the model has seen. Vertical axis: average percent "
        "error up to that point. As data grows the error settles — this curve is "
        "the proof of the thesis.",
    "Geçmişin tamamında model ortalama <b>%{m}</b> yanıldı; yalnızca ortalamaya "
    "bakan kıyas <b>%{k}</b>. {n} gün tek tek, sadece kendinden önceki günlerle "
    "tahmin edildi.":
        "Across all history the model was off by <b>{m}%</b> on average; the "
        "baseline that only looks at the average, <b>{k}%</b>. {n} days were each "
        "predicted using only the days before them.",
    "Geriye dönük test için yeterli geçmiş gün yok (en az {n} günden sonrası gerekir).":
        "Not enough past days for a backtest (needs more than {n} days).",
    "tahmin yok": "no forecast",
    "Tahmin (aralık)": "Forecast (range)",
    "Gerçekleşen": "Actual",
    "Sapma": "Deviation",
    "Model günü": "Model days",
    "Henüz tahmin günlüğü oluşmadı. Program her gün açıldığında o günün tahminini "
    "buraya yazar.":
        "No forecast log yet. Each day the program is opened, it records that day's "
        "forecast here.",
    "Bu sayfa tahminin ne kadar güvenilir olduğunu gösterir. Üstte, modeli ilk N "
    "günle kurup N+1'inci günü tahmin eden, sonra N'i birer birer artıran bir test "
    "var (gün tahmin edilirken o gün modelde yoktur, yani geleceğe bakma yok). "
    "Altta, günlük tutulan 'sabah tahmini — akşam gerçekleşen' kayıtları.":
        "This page shows how reliable the forecast is. Above is a test that builds "
        "the model from the first N days, predicts day N+1, then increases N one by "
        "one (the day being predicted is never in the model, so there's no peeking "
        "at the future). Below are the daily 'morning forecast — evening actual' records.",
    "Gün sayısına karşı hata eğrisi": "Error curve by day count",
    "Az veriyle dürüst tahmin iddiasının grafiksel kanıtı: gün biriktikçe ortalama "
    "hata düşüp oturuyor mu?":
        "Graphical proof of the 'honest forecasting with little data' claim: as days "
        "accumulate, does the average error drop and settle?",
    "Sabah ne dedik, akşam ne oldu": "What we said in the morning vs the evening",
    "Her gün sabah üretilen tahmin ve o akşam gerçekleşen ciro. Sapma %20'nin "
    "altındaysa yeşil; ✓ işareti gerçekleşenin tahmin aralığına düştüğünü gösterir.":
        "Each day's morning forecast and that evening's actual revenue. Deviation "
        "under 20% is green; a ✓ means the actual fell within the forecast range.",

    # --- Temel modellerle karsilastirma ---
    "Temel modellerle karşılaştırma": "Comparison with baseline models",
    "Beş model aynı adil koşulda yarışır (her gün yalnızca kendinden önceki "
    "günlerle). Üç ölçüt: MAE (ortalama mutlak hata), MAPE (yüzde hata) ve aralık "
    "kapsama (gerçekleşenin ~%{h} tahmin aralığına düşme oranı).":
        "Five models compete on equal footing (each day using only the days "
        "before it). Three metrics: MAE (mean absolute error), MAPE (percent "
        "error) and interval coverage (how often the actual fell within the "
        "~{h}% forecast range).",
    "Model": "Model",
    "Kapsama (~%{h})": "Coverage (~{h}%)",
    "Kademeli model (bizim)": "Tiered model (ours)",
    "Çoklu regresyon (ridge)": "Multiple regression (ridge)",
    "Son 7 gün ortalaması": "Last 7 days' average",
    "Geçen haftanın aynı günü": "Same day last week",
    "Genel ortalama": "Overall average",
    "{ad}: MAPE %{mape}, MAE {mae}, kapsama %{kap}":
        "{ad}: MAPE {mape}%, MAE {mae}, coverage {kap}%",
    "Modellere göre ortalama yüzde hata (MAPE); kısa çubuk iyidir.":
        "Average percent error (MAPE) by model; shorter bar is better.",
    "En iyi modelimiz <b>{a}</b> (MAPE %{am}); en iyi naif kıyas <b>{b}</b> (%{bm}). "
    "Aralık ~%{h} için kuruldu; kapsama buna ne kadar yakınsa belirsizlik o kadar dürüst.":
        "Our best model is <b>{a}</b> (MAPE {am}%); the best naive baseline is "
        "<b>{b}</b> ({bm}%). The interval is built for ~{h}%; the closer coverage "
        "is to that, the more honest the uncertainty.",
    "Karşılaştırma için yeterli geçmiş gün yok.":
        "Not enough past days for a comparison.",

    # --- gazeteci cocuk (newsvendor) ---
    "Tahmin edilen satışların dağılımından, her ürünün kârına göre en kârlı "
    "üretim miktarı hesaplandı (gazeteci çocuk kuralı): kârı yüksek üründe "
    "ortalamanın biraz üstü, kârı ince üründe altı. Eldeki stokla karşılaştırıldı.":
        "From the distribution of forecast sales, the most profitable production "
        "amount is computed per product by its margin (the newsvendor rule): a bit "
        "above the mean for high-margin items, below it for thin-margin ones. "
        "Compared with stock on hand.",
    "ortalama {n}": "mean {n}",
    "Fire mi, kaçan satış mı? — gazeteci çocuk sınaması":
        "Waste or lost sales? — the newsvendor test",
    "Dondurma ve pasta bozulur: fazla üretim fire, az üretim kaçan satış. "
    "Tahminin dağılımı elde olduğu için, her ürünün kârına göre en kârlı "
    "üretim miktarı seçilir (gazeteci çocuk / newsvendor). Bu kural, hesap "
    "tarafındaki eski 14 günlük ortalamaya karşı geçmiş sezonda sınandı.":
        "Ice cream and cake spoil: overproduction is waste, underproduction is a "
        "lost sale. Since the forecast distribution is in hand, the most profitable "
        "production amount is chosen per product by its margin (the newsvendor rule). "
        "This rule was tested over the past season against the old 14-day average on "
        "the accounting side.",
    "Fire kıyası için yeterli geçmiş satış yok.":
        "Not enough past sales for a waste comparison.",
    "Üretim kuralı": "Production rule",
    "14 günlük ortalama": "14-day average",
    "Fire": "Waste",
    "Kaçan satış": "Lost sales",
    "Gazeteci çocuk (tahmin dağılımı)": "Newsvendor (forecast distribution)",
    "azaldı": "down",
    "arttı": "up",
    "Gazeteci çocuk kuralı, 14 günlük hareketli ortalamaya karşı bir sezonda: "
    "net kâr {kar}, fire {fire}, kaçan satış {satis}. "
    "{n} ürün, ürün başına ~{g} gün üzerinde ölçüldü. Aynı talep tahmini, "
    "farklı üretim miktarı — ölçülen tek şey karar kuralı.":
        "Over one season, versus the 14-day moving average: net profit {kar}, "
        "waste {fire}, lost sales {satis}. Measured over {n} products, ~{g} days "
        "each. Same demand forecast, different production amount — the only thing "
        "measured is the decision rule.",

    # --- fire anomali tespiti ---
    "Anomali tespiti": "Anomaly detection",
    "Son 30 günün fire dağılımına göre sıra dışı bulunan kalemler "
    "(çeyrekler arası aralık yöntemi). Sabit bir eşik değil, kalemin "
    "kendi geçmişi ölçüt alındı.":
        "Items found unusual against the last 30 days' waste distribution "
        "(interquartile range method). Not a fixed threshold — the item's own "
        "history is the yardstick.",
    "{ad}: fire olağandışı yüksek — {miktar} {birim}":
        "{ad}: unusually high waste — {miktar} {birim}",
    "Son {gun} günde bu kalemde neredeyse hiç fire yokken bugün {miktar} {birim} "
    "çıktı. Bir sayım/üretim hatası ya da olağandışı bir kayıp olabilir; kontrol "
    "etmekte fayda var.":
        "Over the last {gun} days this item had almost no waste, yet today it was "
        "{miktar} {birim}. It may be a counting/production error or an unusual loss; "
        "worth checking.",
    "son {gun} günde genelde {medyan} {birim} civarı; normal üst "
    "sınır {ust} {birim}":
        "usually around {medyan} {birim} over the last {gun} days; normal upper "
        "bound {ust} {birim}",
    "Bu kalemde fire {normal}. Bugün {miktar} {birim} çıktı — "
    "dağılımdan {z} kat sapma. Bir sayım/üretim hatası ya da "
    "olağandışı bir kayıp olabilir; kontrol etmekte fayda var.":
        "Waste for this item is {normal}. Today it was {miktar} {birim} — {z}× the "
        "spread away. It may be a counting/production error or an unusual loss; "
        "worth checking.",

    # --- durum_metni (capraz dogrulamali secim) ---
    "{gun} günlük satış geçmişine bakıyor; hangi bileşeni kullanacağına çapraz "
    "doğrulamayla kendisi karar verdi":
        "looks at {gun} days of sales history; it decided which component to use "
        "by cross-validation itself",
    "sıcaklığı aldı: her 1 derece günlük ciroyu ortalama {deger} birim değiştiriyor":
        "took temperature: each 1 degree changes daily revenue by about {deger} units",
    "sıcaklığı denedi ama hatayı düşürmedi, kullanmıyor":
        "tried temperature but it didn't lower the error, so not using it",
    "yağmuru denedi ama hatayı düşürmedi, kullanmıyor":
        "tried rain but it didn't lower the error, so not using it",
    "hafta sonu satışı hafta içinin {kat} katı": "weekend sales are {kat}× weekdays",
    "haftanın gününü denedi ama hatayı düşürmedi, kullanmıyor":
        "tried day-of-week but it didn't lower the error, so not using it",
    "özel gün etkisi çapraz doğrulamada seçilmedi":
        "special-day effect was not selected by cross-validation",
    "yağış miktarını sürekli ölçüyor: çok yağışlı bir gün kurak güne göre satışı "
    "%{yuzde} {yon}":
        "measures rainfall continuously: a very wet day {yon} sales by {yuzde}% "
        "versus a dry day",
    "yağışı (mm) denedi ama hatayı düşürmedi, kullanmıyor":
        "tried rainfall (mm) but it didn't lower the error, so not using it",
}
