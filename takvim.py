# -*- coding: utf-8 -*-
"""Ozel gunler ve donemler: resmi tatiller, dini bayramlar, findik toplama.

Hepsi tek bir kavrama oturuyor: bir **etiket** ve o etiketin gecerli oldugu
tarih araligi. Model her etiket icin tek bir katsayi ogrenir - "Ramazan
Bayrami gunlerinde satis normalin 2,3 kati" gibi. Etiket paylasan satirlar
ayni havuza girer, boylece 29 Ekim ile 23 Nisan birlikte "Resmi Tatil"
katsayisini besler ve iki yilda bir gozlem yerine daha cok gozlem olur.

Hepsi ayni mekanizma:
    Resmi tatil    -> tek gun,  etiket "Resmi Tatil"
    Dini bayram    -> 3-4 gun,  etiket bayramin kendi adi (etkisi cok farkli)
    Arife/yarim gun-> tek gun,  etiket "Yarım Gün"
    Ramazan ayi    -> ~30 gun,  etiket "Ramazan"
    Findik toplama -> haftalar, etiket "Fındık Toplama"

Etiketin ne kadar ince bolunecegini tek bir sey belirler: model bir etiketin
katsayisini cikarmak icin o etiketten EN_AZ_ETIKET_GUN (3) gun satis gormek
zorunda. Yilda 3 gunun altina dusen her boluntu ancak uc yilda ogrenilir, o
yuzden bilerek bolunmuyor - bayramin 1. gunu ile 3. gunu ayri etiket degildir,
uc arife de ayri ayri degil tek "Yarım Gün" etiketi altindadir.

Sabit tarihli tatiller her yil kendiliginden uretilir. Dini bayramlar hicri
takvime gore kaydigi icin tablodan gelir; arife ve Ramazan ayi o tarihten
hesaplanir. Tablodaki yillar bitince program uyarir ve kullanici Ozel Gunler
ekranindan elle ekler.
"""

import datetime

TARIH_BICIMI = "%Y-%m-%d"

# Her yil ayni tarihte olan resmi tatiller (tam gun tatil olanlar).
SABIT_TATILLER = [
    ((1, 1), "Yılbaşı"),
    ((4, 23), "23 Nisan Ulusal Egemenlik ve Çocuk Bayramı"),
    ((5, 1), "1 Mayıs Emek ve Dayanışma Günü"),
    ((5, 19), "19 Mayıs Atatürk'ü Anma, Gençlik ve Spor Bayramı"),
    ((7, 15), "15 Temmuz Demokrasi ve Millî Birlik Günü"),
    ((8, 30), "30 Ağustos Zafer Bayramı"),
    ((10, 29), "29 Ekim Cumhuriyet Bayramı"),
]

# Dini bayramlarin ilk gunu. Hicri takvim her yil ~11 gun kaydigi icin
# hesapla degil tabloyla tutuluyor; Diyanet'in ilan ettigi tarihler esastir.
# BU TARIHLER KONTROL EDILMELI - ozellikle ileri yillar tahminidir.
DINI_BAYRAMLAR = {
    "Ramazan Bayramı": {
        2025: "2025-03-30", 2026: "2026-03-20",
        2027: "2027-03-09", 2028: "2028-02-26",
    },
    "Kurban Bayramı": {
        2025: "2025-06-06", 2026: "2026-05-27",
        2027: "2027-05-16", 2028: "2028-05-05",
    },
}
BAYRAM_UZUNLUGU = {"Ramazan Bayramı": 3, "Kurban Bayramı": 4}

# Ogleden sonrasi resmi olarak tatil olan, her yil ayni tarihe dusen gunler.
# Bayram arifeleri de yarim gundur ama tarihleri bayramdan hesaplanir.
SABIT_YARIM_GUNLER = [
    ((10, 28), "28 Ekim Cumhuriyet Bayramı Arifesi"),
]

# Ramazan 29 ya da 30 gun surer; hangisi oldugu ancak ay goruldugunde belli
# olur. Bayramin ilk gununden 30 gun geriye sayiyoruz - en fazla bir gun
# sapar, gunluk ciro modeli icin bu fark onemsiz.
RAMAZAN_GUN = 30

RESMI_ETIKET = "Resmi Tatil"
ARIFE_ETIKET = "Yarım Gün"
RAMAZAN_ETIKET = "Ramazan"
HAFTA_SONU_ETIKET = "Hafta Sonu"   # takvimden degil, gunun kendisinden gelir


def _tarih(metin):
    return datetime.datetime.strptime(metin, TARIH_BICIMI).date()


def _yaz(gun):
    return gun.strftime(TARIH_BICIMI)


# ---------------------------------------------------------------- kayitlar

def ekle(baglanti, ad, etiket, baslangic, bitis, kaynak="elle"):
    """Ozel gun/donem ekler. Ayni ad ve baslangic varsa tekrar yazmaz."""
    baglanti.execute(
        "INSERT OR IGNORE INTO ozel_gunler (ad, etiket, baslangic, bitis, kaynak)"
        " VALUES (?, ?, ?, ?, ?)",
        (ad, etiket, baslangic, bitis, kaynak),
    )


def liste(baglanti, sadece_aktif=False):
    ek = " WHERE aktif = 1" if sadece_aktif else ""
    return baglanti.execute(
        f"SELECT * FROM ozel_gunler{ek} ORDER BY baslangic, ad"
    ).fetchall()


def etiketler(baglanti):
    """Kullanimda olan etiket adlari - yeni kayit eklerken oneri olarak cikar."""
    return [satir[0] for satir in baglanti.execute(
        "SELECT DISTINCT etiket FROM ozel_gunler ORDER BY etiket")]


def durum_degistir(baglanti, kayit_id):
    """Bir ozel gunu acar/kapatir. Kapali olan modele hic girmez."""
    baglanti.execute(
        "UPDATE ozel_gunler SET aktif = 1 - aktif WHERE id = ?", (kayit_id,))
    baglanti.commit()


def sil(baglanti, kayit_id):
    """Sadece elle eklenenler silinebilir.

    Programin urettigi resmi/dini satirlar silinse bile ilk acilista geri
    gelir - onlari kapatmak gerekir, silmek degil. Bu yuzden burada engellenir.
    """
    satir = baglanti.execute(
        "SELECT kaynak FROM ozel_gunler WHERE id = ?", (kayit_id,)).fetchone()
    if satir is None or satir["kaynak"] != "elle":
        return False
    baglanti.execute("DELETE FROM ozel_gunler WHERE id = ?", (kayit_id,))
    baglanti.commit()
    return True


def tatilleri_uret(baglanti, ilk_yil=None, son_yil=None):
    """Sabit tatilleri ve bilinen dini bayramlari takvime yazar.

    Her acilista cagrilir; zaten varsa hicbir sey yapmaz. Boylece yil
    donunce program kendi takvimini kendisi uzatir.
    """
    bugun = datetime.date.today()
    ilk_yil = ilk_yil or bugun.year - 1
    son_yil = son_yil or bugun.year + 1

    for yil in range(ilk_yil, son_yil + 1):
        for (ay, gun), ad in SABIT_TATILLER:
            tarih = _yaz(datetime.date(yil, ay, gun))
            ekle(baglanti, f"{ad} ({yil})", RESMI_ETIKET, tarih, tarih, "resmi")

        for (ay, gun), ad in SABIT_YARIM_GUNLER:
            tarih = _yaz(datetime.date(yil, ay, gun))
            ekle(baglanti, f"{ad} ({yil})", ARIFE_ETIKET, tarih, tarih, "resmi")

        for bayram, yillar in DINI_BAYRAMLAR.items():
            if yil not in yillar:
                continue
            basi = _tarih(yillar[yil])
            sonu = basi + datetime.timedelta(days=BAYRAM_UZUNLUGU[bayram] - 1)
            ekle(baglanti, f"{bayram} ({yil})", bayram, _yaz(basi), _yaz(sonu), "dini")

            # Arife bayramin bir onceki gunu; tam tatil degil, yarim gun.
            arife = _yaz(basi - datetime.timedelta(days=1))
            ekle(baglanti, f"{bayram} Arifesi ({yil})", ARIFE_ETIKET,
                 arife, arife, "dini")

            # Ramazan ayi bayramla biter. Oruclu ayda gunun ritmi degistigi
            # icin ayri etiket; yilda ~30 gun oldugundan en cabuk ogrenilen
            # etiket budur.
            if bayram == "Ramazan Bayramı":
                ekle(baglanti, f"Ramazan ({yil})", RAMAZAN_ETIKET,
                     _yaz(basi - datetime.timedelta(days=RAMAZAN_GUN)),
                     _yaz(basi - datetime.timedelta(days=1)), "dini")
    baglanti.commit()


def eksik_bayram_yillari(baglanti):
    """Tabloda karsiligi olmayan yakin yillar. Ekranda uyari icin."""
    bugun = datetime.date.today()
    eksikler = []
    for yil in (bugun.year, bugun.year + 1):
        for bayram, yillar in DINI_BAYRAMLAR.items():
            if yil not in yillar:
                eksikler.append((bayram, yil))
    return eksikler


# ---------------------------------------------------------------- etiketler

def etiket_haritasi(baglanti, baslangic, bitis):
    """Tarih -> etiket kumesi. Hafta sonu da buraya eklenir.

    Model bu haritayla "bu gun ozel miydi" sorusunu tek sozluk aramasiyla
    cevaplar; her gun icin veritabanina gitmez.
    """
    harita = {}
    ilk, son = _tarih(baslangic), _tarih(bitis)

    gun = ilk
    while gun <= son:
        if gun.weekday() >= 5:
            harita.setdefault(_yaz(gun), set()).add(HAFTA_SONU_ETIKET)
        gun += datetime.timedelta(days=1)

    for satir in baglanti.execute(
        "SELECT etiket, baslangic, bitis FROM ozel_gunler"
        " WHERE aktif = 1 AND bitis >= ? AND baslangic <= ?", (baslangic, bitis)
    ):
        gun = max(_tarih(satir["baslangic"]), ilk)
        bitti = min(_tarih(satir["bitis"]), son)
        while gun <= bitti:
            harita.setdefault(_yaz(gun), set()).add(satir["etiket"])
            gun += datetime.timedelta(days=1)
    return harita


def gunun_etiketleri(baglanti, tarih):
    return etiket_haritasi(baglanti, tarih, tarih).get(tarih, set())


def yaklasan(baglanti, gun_sayisi=60):
    """Onumuzdeki gunlerdeki ozel gun/donemler, tarih sirasinda."""
    bugun = datetime.date.today()
    son = bugun + datetime.timedelta(days=gun_sayisi)
    return baglanti.execute(
        "SELECT * FROM ozel_gunler WHERE aktif = 1 AND bitis >= ? AND baslangic <= ?"
        " ORDER BY baslangic", (_yaz(bugun), _yaz(son))
    ).fetchall()


def gun_araligi(baslangic, bitis):
    """Bir donemin kac gun surdugu."""
    return (_tarih(bitis) - _tarih(baslangic)).days + 1
