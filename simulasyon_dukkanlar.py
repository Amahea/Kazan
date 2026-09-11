# -*- coding: utf-8 -*-
"""Uc yeni dukkan icin denemelik veri uretir. GUNLER UYDURMADIR.

    Kugu Pastanesi  - sabah uretir, aksam vitrinde kalani sayar (gun sonu sayimi)
    Samata Cafe     - ev yemekleri: tencerede pisirir, porsiyon satar
    Susu Manti      - tepsi tepsi manti yapar, porsiyon ve paket satar

1 Ocak 2026'dan dune kadar her gun icin alim, uretim, satis, fire, gider,
maas ve tedarikci odemesi yazar. Butun kayitlar programin kendi
fonksiyonlariyla (hesap.py) yazilir; kasa, borc, stok ve maliyet programin
kendi kurallarina gore tutarli olusur.

Olculer - menuler, fiyatlar, gunluk adetler, kadro, kira - 11 Eylul 2026'da
taslak olarak sunulup onaylandi. Hicbiri bu dukkanlarin gercek rakami degil.
Asagidaki fiyatlarin hepsi EYLUL 2026 fiyatidir:
  - Satis fiyatlari ocakta ZAM_ORANI kadar dusuk baslar, ZAM_TARIHI'nde zamlanir.
  - Hammadde alis fiyatlari ocaktan eylule her gun ENFLASYON kadar artar.
Hava uydurma degil: Ordu merkezin o gunlerdeki olcumleri (Open-Meteo arsivi).

Dukkanlarin hesaplari (kullanici adi + sifre) once acilmis olmali; betik
dukkani kullanici adindan bulur. Sifreler bilerek bu dosyada yok - kod
GitHub'a gidiyor. Her dukkanin veri dosyasi yedeklenip bastan yazilir.
Dukkan 1 ve 2'ye hic dokunulmaz.

Calistirmak icin:  python simulasyon_dukkanlar.py --onayla
Sadece birini:     python simulasyon_dukkanlar.py --onayla kugu
"""
import collections
import datetime
import json
import math
import os
import random
import shutil
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hava
import hesap
import hesaplar
import menuler
import takvim
import veritabani

BASLANGIC = datetime.date(2026, 1, 1)
BITIS = datetime.date.today() - datetime.timedelta(days=1)   # bugun henuz bitmedi

FIYAT_GUNU = datetime.date(2026, 9, 11)   # asagidaki fiyatlarin ait oldugu gun
ENFLASYON = 0.0009                        # alis fiyatlarinin gunluk artisi
ZAM_TARIHI = datetime.date(2026, 7, 1)    # menu fiyatlarinin zamlandigi gun
ZAM_ORANI = 0.15                          # ocak fiyati = eylul fiyati / 1,15

ENLEM, BOYLAM = 40.9838, 37.8858          # Ordu merkez
ACILIS_KASASI = 300000.0                  # 2025'ten devreden nakit

# Uretim sabahki tahmin kadar yapilir, fazlasi degil: sans yaver gitmeyen
# gunde aksam biraz artar, iyi gunde ogleden sonra "bitti" denir. Tahmin
# yeterince tutarsa ikisi de kucuk kalir; fazla uretim karini dogrudan yer.
FAZLA_URETIM = 0.0

# Sabahki tahminin tutmama payi: gunun geneli ve tek tek urunler icin.
GUN_SAPMASI = 0.06
URUN_SAPMASI = 0.09


# ---------------------------------------------------------------- tedarikciler
UNCU = "Ordu Un Değirmeni"
TOPTANCI = "Karadeniz Gıda Toptan"
SUTCU = "Ordu Süt"
KASAP = "Altınordu Kasabı"
PILICCI = "Ordu Piliç"
HAL = "Ordu Sebze Hali"
FIRINCI = "Fırıncı Hasan"
BALIKCI = "Balıkçı Recep"
AMBALAJCI = "Ambalaj Dünyası"
ICECEKCI = "Karadeniz İçecek Bayii"
KAHVECI = "Ordu Kahve ve Kuruyemiş"

# Pesin odenme olasiligi. Halde ve balikcida nakit doner, toptanci veresiye
# yazar, firinci ekmek parasini haftada bir toplu alir.
PESIN = {
    UNCU: 0.2, TOPTANCI: 0.25, SUTCU: 0.3, KASAP: 0.3, PILICCI: 0.3,
    HAL: 0.85, FIRINCI: 0.1, BALIKCI: 0.9, AMBALAJCI: 0.3, ICECEKCI: 0.3,
    KAHVECI: 0.6,
}


# ---------------------------------------------------------------- tanim yardimcilari
def hammadde(ad, birim, fiyat, tedarikci, tazelik="kuru", koli=0, koli_ad="koli",
             tur="Hammadde", sayim="yok", dagit=0):
    """Satin alinan malzeme. fiyat EYLUL alis fiyatidir.

    tazelik alimin sikligini belirler:
      gunluk : her sabah o gunun ihtiyaci kadar (ekmek, taze balik)
      taze   : 2-3 gunde bir (sut, et, sebze)
      kuru   : iki haftada bir, koli koli (un, seker, bakliyat)
    """
    return {"ad": ad, "birim": birim, "eylul": fiyat, "tedarikci": tedarikci,
            "tazelik": tazelik, "koli": koli, "koli_ad": koli_ad, "tur": tur,
            "sayim": sayim, "dagit": dagit}


def urun(ad, birim, fiyat, gunluk, grup, tur, recete=None, parti=None, raf=None,
         alis=None, tedarikci="", sayim="yok", adim=0.5, vitrin=0, satis_adim=1):
    """Satilan kalem. fiyat EYLUL satis fiyatidir, gunluk hafta ici bir gunde
    ne kadar gittigi.

    parti  : (parti adi, bir partiden kac birim cikar) - uretilen kalemler.
             recete bu durumda BIR PARTININ malzemesidir.
    parti yoksa ve recete varsa kalem siparis aninda hazirlanir (cay, cacik);
             recete BIR BIRIMIN malzemesidir, satilinca stoktan duser.
    alis   : hazir alinip oldugu gibi satilanlarin (ayran, su) EYLUL alis fiyati.
    raf    : kac gun satilabilir. 1 = aksam artan atilir, 3 = uc gun satilir,
             ucuncu aksam hala duruyorsa atilir. None = uzun dayanir (kurabiye).
    adim   : uretimin en kucuk parcasi, parti cinsinden (yarim tepsi = 0.5).
    vitrin : vitrinde en az bu kadar durur (butun pasta).
    """
    return {"ad": ad, "birim": birim, "eylul": fiyat, "gunluk": gunluk, "grup": grup,
            "tur": tur, "recete": recete or [], "parti": parti, "raf": raf,
            "alis": alis, "tedarikci": tedarikci, "sayim": sayim, "adim": adim,
            "vitrin": vitrin, "satis_adim": satis_adim}


def ara_urun(ad, birim, tur, recete, parti, adim=0.5, stok_gun=(1.5, 3.0),
             aciklama="", gunde_en_cok=None):
    """Uretilip satilmayan, baska urunun icine giren kalem (manti hamuru).

    stok_gun: stok (esik) gunluk ihtiyacin altina dusunce (hedef) gunluk uretilir.
    gunde_en_cok: bir gunde en fazla kac parti yapilabilir (usta sayisi sinirlar).
    """
    return {"ad": ad, "birim": birim, "tur": tur, "recete": recete, "parti": parti,
            "adim": adim, "stok_gun": stok_gun, "aciklama": aciklama,
            "gunde_en_cok": gunde_en_cok}


def calisan(ad, gorev, maas, sgk, giris, notlar=""):
    return (ad, gorev, maas, sgk, giris, notlar)


def mevsim(tarih, kis=1.0, yaz=1.0, gecis=1.0):
    """Aralik-subat kis, haziran-agustos yaz, mart ve kasim gecis ayi."""
    if tarih.month in (12, 1, 2):
        return kis
    if tarih.month in (6, 7, 8):
        return yaz
    if tarih.month in (3, 11):
        return gecis
    return 1.0


def bayram_mi(etiketler):
    return "Ramazan Bayramı" in etiketler or "Kurban Bayramı" in etiketler


def sicaklik_etkisi(sicaklik, egim=0.012, orta=20.0):
    """Soguk icecekler havayla artar: 20 derecenin her ustu %1,2."""
    return max(0.8, min(1.35, 1 + egim * (sicaklik - orta)))


# ================================================================ KUGU PASTANESI
KUGU = {
    "kullanici": "kugu",
    "ad": "Kuğu Pastanesi",
    "satis_girisi": "sayim",
    "hammaddeler": [
        hammadde("Un", "kg", 39, UNCU, koli=50, koli_ad="çuval"),
        hammadde("Toz Şeker", "kg", 34, TOPTANCI, koli=50, koli_ad="çuval"),
        hammadde("Nişasta", "kg", 80, TOPTANCI),
        hammadde("Kakao", "kg", 650, TOPTANCI),
        hammadde("Bitter Çikolata", "kg", 850, TOPTANCI),
        hammadde("Maya", "kg", 110, TOPTANCI, "taze"),
        hammadde("Sıvı Yağ", "litre", 110, TOPTANCI, koli=18, koli_ad="teneke"),
        hammadde("Margarin", "kg", 160, TOPTANCI),
        hammadde("Tereyağı", "kg", 720, SUTCU, "taze"),
        hammadde("Süt", "litre", 45, SUTCU, "taze"),
        hammadde("Sıvı Krema", "litre", 260, SUTCU, "taze"),
        hammadde("Beyaz Peynir", "kg", 380, SUTCU, "taze"),
        hammadde("Yumurta", "adet", 11, TOPTANCI, "taze", koli=30, koli_ad="viyol"),
        hammadde("Meyve (çilek, muz)", "kg", 150, HAL, "taze"),
        hammadde("Dökme Çay", "kg", 380, KAHVECI),
        hammadde("Çekilmiş Kahve", "kg", 1100, KAHVECI),
        # Ambalaj: musteriden ayrica para alinmiyor; gun sonunda sayilir,
        # harcanan tutar o gunun satislarina paylastirilir.
        hammadde("Pasta Kutusu", "adet", 18, AMBALAJCI, koli=100, tur="Ambalaj",
                 sayim="say", dagit=1),
        hammadde("Kurabiye Kutusu", "adet", 12, AMBALAJCI, koli=100, tur="Ambalaj",
                 sayim="say", dagit=1),
        hammadde("Kese Kağıdı", "adet", 0.9, AMBALAJCI, koli=1000, tur="Ambalaj",
                 sayim="koli", dagit=1),
        hammadde("Peçete", "kutu", 30, AMBALAJCI, koli=1, tur="Ambalaj",
                 sayim="koli", dagit=1),
    ],
    "urunler": [
        urun("Poğaça", "adet", 30, 120, "hamur", "Hamur işi", raf=1, sayim="say",
             parti=("tepsi", 40), adim=0.25,
             recete=[("Un", 2.0), ("Margarin", 0.5), ("Süt", 0.5), ("Yumurta", 2),
                     ("Maya", 0.04), ("Beyaz Peynir", 0.4), ("Sıvı Yağ", 0.2)]),
        urun("Açma", "adet", 30, 80, "hamur", "Hamur işi", raf=1, sayim="say",
             parti=("tepsi", 40), adim=0.25,
             recete=[("Un", 2.2), ("Margarin", 0.6), ("Süt", 0.6), ("Yumurta", 2),
                     ("Maya", 0.05), ("Toz Şeker", 0.1), ("Sıvı Yağ", 0.2)]),
        urun("Su Böreği", "porsiyon", 140, 20, "borek", "Hamur işi", raf=1,
             sayim="say", parti=("tepsi", 24), adim=0.25,
             recete=[("Un", 1.5), ("Yumurta", 10), ("Tereyağı", 0.5),
                     ("Beyaz Peynir", 1.2), ("Süt", 0.3)]),
        urun("Ekler", "adet", 35, 50, "tatli", "Tatlı", raf=2, sayim="say",
             parti=("tepsi", 60),
             recete=[("Un", 0.5), ("Tereyağı", 0.25), ("Yumurta", 10), ("Süt", 1.5),
                     ("Toz Şeker", 0.4), ("Nişasta", 0.15), ("Bitter Çikolata", 0.25),
                     ("Sıvı Krema", 0.3)]),
        urun("Profiterol", "kase", 160, 15, "tatli", "Tatlı", raf=2, sayim="say",
             parti=("tepsi", 20),
             recete=[("Un", 0.3), ("Tereyağı", 0.15), ("Yumurta", 6), ("Süt", 2.0),
                     ("Toz Şeker", 0.4), ("Nişasta", 0.15), ("Kakao", 0.1),
                     ("Bitter Çikolata", 0.3), ("Sıvı Krema", 0.4)]),
        urun("Dilim Pasta", "dilim", 160, 35, "pasta", "Pasta", raf=2, sayim="say",
             parti=("tepsi", 24),
             recete=[("Yumurta", 15), ("Un", 0.6), ("Toz Şeker", 0.8),
                     ("Sıvı Krema", 1.5), ("Süt", 0.75), ("Meyve (çilek, muz)", 0.75),
                     ("Bitter Çikolata", 0.25), ("Nişasta", 0.08)]),
        urun("Yaş Pasta (8 kişilik)", "adet", 1000, 3, "butun_pasta", "Pasta", raf=2,
             sayim="say", parti=("parti", 4), adim=0.25, vitrin=3,
             recete=[("Yumurta", 20), ("Un", 0.8), ("Toz Şeker", 1.1),
                     ("Sıvı Krema", 2.0), ("Süt", 1.0), ("Meyve (çilek, muz)", 1.0),
                     ("Bitter Çikolata", 0.3), ("Nişasta", 0.1)]),
        urun("Kurabiye", "kg", 650, 4, "kurabiye", "Kurabiye", raf=None, sayim="say",
             parti=("tepsi", 3), adim=1, satis_adim=0.1,
             recete=[("Un", 1.6), ("Tereyağı", 0.5), ("Margarin", 0.4),
                     ("Toz Şeker", 0.5), ("Yumurta", 2), ("Nişasta", 0.2)]),
        urun("Çay", "bardak", 20, 100, "sicak", "İçecek", sayim="elle",
             recete=[("Dökme Çay", 0.006), ("Toz Şeker", 0.008)]),
        urun("Türk Kahvesi", "fincan", 80, 15, "sicak", "İçecek", sayim="elle",
             recete=[("Çekilmiş Kahve", 0.007), ("Toz Şeker", 0.005)]),
    ],
    "ara_urunler": [],
    "hafta": [1.0, 1.0, 1.0, 1.0, 1.1, 1.4, 1.4],     # Pzt..Paz
    "calisanlar": [
        calisan("Hüseyin Kaya", "Pasta ustası", 48000, 16300, "2019-04-01",
                "Sabah 5'te fırını o yakıyor"),
        calisan("Emre Çelik", "Usta yardımcısı", 30000, 12500, "2023-09-15"),
        calisan("Ayşe Yılmaz", "Tezgâhtar", 28100, 12150, "2022-03-01"),
        calisan("Zeynep Arslan", "Tezgâhtar", 28100, 12150, "2025-06-01"),
        calisan("Burak Şahin", "Servis elemanı", 28100, 12150, "2024-11-01"),
    ],
    "giderler": {"kira": 45000, "elektrik": 20000, "dogalgaz": 15000, "su": 3000,
                 "kart_payi": 0.65},
}


def kugu_ozel_gunler(baglanti):
    """Pastanenin satisini degistiren, takvimde olmayan gunler.

    Model her etiket icin ayri katsayi ogrenir; bunlar takvime yazilinca
    tahmin ekrani da "Anneler Gunu'nde pasta 3 kati gidiyor" diye ogrenir.
    """
    takvim.ekle(baglanti, "Sevgililer Günü (2026)", "Sevgililer Günü",
                "2026-02-14", "2026-02-14")
    takvim.ekle(baglanti, "Anneler Günü (2026)", "Anneler Günü",
                "2026-05-10", "2026-05-10")
    takvim.ekle(baglanti, "Babalar Günü (2026)", "Babalar Günü",
                "2026-06-21", "2026-06-21")
    # Bayramdan once kurabiye ve pasta alinir: arife dahil son uc gun.
    for satir in baglanti.execute(
            "SELECT ad, baslangic FROM ozel_gunler WHERE etiket IN"
            " ('Ramazan Bayramı', 'Kurban Bayramı') AND baslangic LIKE '2026-%'"
    ).fetchall():
        basi = datetime.date.fromisoformat(satir["baslangic"])
        takvim.ekle(baglanti, f"{satir['ad'].split(' (')[0]} Öncesi (2026)",
                    "Bayram Öncesi",
                    (basi - datetime.timedelta(days=3)).isoformat(),
                    (basi - datetime.timedelta(days=1)).isoformat())
    baglanti.commit()


def kugu_carpan(tarih, etiketler, u, gun_hava, menu_adi=None):
    sicaklik, yagis = gun_hava
    g = u["grup"]
    c = KUGU["hafta"][tarih.weekday()]
    # Temmuz-agustos gurbetci ve tatilci ayi; ocak-subat sakin.
    c *= {1: 0.95, 2: 0.95, 7: 1.08, 8: 1.08}.get(tarih.month, 1.0)
    if g in ("sicak", "borek"):
        c *= mevsim(tarih, kis=1.2, yaz=0.8)
    if g == "tatli":
        c *= mevsim(tarih, yaz=1.1)
    if "Ramazan" in etiketler:
        # Gunduz oruc: pogaca ve cay duser; iftar sofrasina tatli, pasta gider.
        c *= 0.6 if g in ("hamur", "borek", "sicak") else 1.2
    if "Bayram Öncesi" in etiketler:
        c *= {"kurabiye": 4.0, "butun_pasta": 1.5}.get(g, 1.0)
    if bayram_mi(etiketler):
        c *= 1.3 if g == "butun_pasta" else 0.8
    if "Sevgililer Günü" in etiketler:
        c *= {"butun_pasta": 3.0, "pasta": 1.5}.get(g, 1.0)
    if "Anneler Günü" in etiketler:
        c *= {"butun_pasta": 3.0, "pasta": 1.3}.get(g, 1.0)
    if "Babalar Günü" in etiketler:
        c *= 1.8 if g == "butun_pasta" else 1.0
    if "Resmi Tatil" in etiketler:
        c *= 1.1
    if yagis >= 8:
        c *= 0.8
    elif yagis >= 1:
        c *= 0.9
    return c


def kugu_ambalaj(talep):
    """Gunun ambalaji. Lokantalarinki (paket kabi) recetenin icinde."""
    poset = (talep["Poğaça"] + talep["Açma"] + talep["Ekler"]) * 0.6 / 3
    return {
        "Pasta Kutusu": talep["Yaş Pasta (8 kişilik)"],
        "Kurabiye Kutusu": round(talep["Kurabiye"] / 0.6),   # kutu ortalama 600 gr
        "Kese Kağıdı": round(poset),
        "Peçete": 0.7 if sum(talep.values()) > 0 else 0.0,
    }


KUGU["ozel_gunler"] = kugu_ozel_gunler
KUGU["ambalaj"] = kugu_ambalaj
KUGU["carpan"] = kugu_carpan
KUGU["acik_mi"] = lambda tarih, etiketler: True
KUGU["menude_mi"] = lambda tarih, ad, menu_adi: True
KUGU["menuler"] = []


# ================================================================ SAMATA CAFE
# Esnaf lokantasi: her gun bir corba, bir baklagil, bir et yemegi, bir
# sebze yemegi. Pilav, tatlilar, cacik, salata her gun var.
SAMATA_MENU = {
    0: ("Mercimek Çorbası", "Kuru Fasulye", "Tavuk Sote"),
    1: ("Ezogelin Çorbası", "Etli Nohut", "Karnıyarık"),
    2: ("Mercimek Çorbası", "Kuru Fasulye", "İzmir Köfte"),
    3: ("Tarhana Çorbası", "Etli Nohut", "Sulu Köfte"),
    4: ("Mercimek Çorbası", "Kuru Fasulye", "Tavuk Sote"),
    5: ("Ezogelin Çorbası", "Etli Nohut", "Karnıyarık"),
}
# Sebze yemegi mevsime gore: hangi menu gecerliyse onun uc yemegi haftada
# ikiser kez doner (pazartesi-persembe, sali-cuma, carsamba-cumartesi).
# Menulere gecisi dukkan programin onerisiyle yapar (menuler.py): hava uc gun
# ust uste esigi gecince.
SAMATA_MENULER = [
    # (ad, kosul, esik, menude yalnizca bu donemde olan urunler)
    ("Yaz sebzeleri", "sicak", 22,
     ["Zeytinyağlı Taze Fasulye", "Biber Dolma", "Türlü"]),
    ("Kış sebzeleri", "soguk", 15,
     ["Zeytinyağlı Pırasa", "Ispanak Yemeği", "Karalahana Sarması",
      "Karalahana Çorbası", "Hamsi Tava"]),
]
SAMATA_SEBZE = {ad: urunler[:3] for ad, _, _, urunler in SAMATA_MENULER}
# Tatlilar gunden gune donmuyor: tepsi bitene kadar (en cok uc gun) vitrinde.
SAMATA_HER_GUN = ("Pirinç Pilavı", "Sütlaç", "Revani", "İrmik Helvası", "Cacık",
                  "Çoban Salata", "Ayran", "Çay", "Türk Kahvesi", "Su")


def hamsi_mevsimi(tarih):
    """Karadeniz'de hamsi eylulden nisan ortasina; sonra av yasagi. Mart
    sonunda hamsi hem azalir hem kalitesi duser; lokanta mart sonu birakir."""
    return tarih.month <= 3 or tarih.month >= 9


def samata_menude_mi(tarih, ad, menu_adi):
    if ad in SAMATA_HER_GUN:
        return True
    kis = menu_adi == "Kış sebzeleri"
    if ad == "Hamsi Tava":
        return kis and hamsi_mevsimi(tarih)
    gun = tarih.weekday()
    sebzeler = SAMATA_SEBZE.get(menu_adi, ())
    if gun < 6 and sebzeler and ad == sebzeler[gun % 3]:
        return True
    gunun = SAMATA_MENU.get(gun, ())
    # Kis menusunde persembe tarhana yerine karalahana corbasi pisiyor.
    if kis and gun == 3:
        if ad == "Karalahana Çorbası":
            return True
        if ad == "Tarhana Çorbası":
            return False
    return ad in gunun


def samata_acik_mi(tarih, etiketler):
    if tarih.weekday() == 6:
        return False            # pazar kapali
    # Bayramin ilk gunu esnaf lokantasi kapali.
    for etiket in ("Ramazan Bayramı", "Kurban Bayramı"):
        if etiket in etiketler and etiketler.get(etiket) == tarih.isoformat():
            return False
    return True


def samata_carpan(tarih, etiketler, u, gun_hava, menu_adi=None):
    sicaklik, yagis = gun_hava
    g = u["grup"]
    c = [1.0, 1.0, 1.0, 1.0, 1.0, 0.8, 0.0][tarih.weekday()]
    c *= 0.95 if tarih.month == 8 else 1.0        # agustosta esnaf da tatilde
    if g == "corba":
        c *= mevsim(tarih, kis=1.3, yaz=0.65, gecis=1.1)
    elif g == "soguk":
        c *= mevsim(tarih, kis=0.7, yaz=1.5)
    elif g == "zeytinyagli":
        c *= mevsim(tarih, yaz=1.2)     # sicakta soguk yenen yemek
    elif g in ("baklagil", "et"):
        c *= mevsim(tarih, yaz=0.9)
    elif g == "ayran":
        c *= mevsim(tarih, kis=0.8, yaz=1.4) * sicaklik_etkisi(sicaklik, 0.006)
    elif g == "sicak":
        c *= mevsim(tarih, kis=1.2, yaz=0.8)
    if g == "et" and samata_menude_mi(tarih, "Hamsi Tava", menu_adi):
        c *= 0.8                # hamsi varken et yemegi biraz az gidiyor
    if "Ramazan" in etiketler:
        c *= 0.65
    if bayram_mi(etiketler):
        c *= 0.5
    elif "Yarım Gün" in etiketler:
        c *= 0.8
    if "Resmi Tatil" in etiketler:
        c *= 0.6                # musterisi esnaf ve memur; tatilde gelmiyor
    if yagis >= 8:
        c *= 0.9
    return c


SAMATA = {
    "kullanici": "samata",
    "ad": "Şamata Cafe",
    "satis_girisi": "dogrudan",
    "hammaddeler": [
        hammadde("Kırmızı Mercimek", "kg", 85, TOPTANCI),
        hammadde("Bulgur", "kg", 55, TOPTANCI),
        hammadde("Pirinç", "kg", 90, TOPTANCI, koli=25, koli_ad="çuval"),
        hammadde("Şehriye", "kg", 70, TOPTANCI),
        hammadde("Kuru Fasulye (çiğ)", "kg", 120, TOPTANCI),
        hammadde("Nohut", "kg", 95, TOPTANCI),
        hammadde("Tarhana", "kg", 250, TOPTANCI),
        hammadde("Mısır Unu", "kg", 40, TOPTANCI),
        hammadde("Un", "kg", 39, UNCU),
        hammadde("İrmik", "kg", 60, TOPTANCI),
        hammadde("Toz Şeker", "kg", 34, TOPTANCI, koli=50, koli_ad="çuval"),
        hammadde("Nişasta", "kg", 80, TOPTANCI),
        hammadde("Salça", "kg", 130, TOPTANCI),
        hammadde("Baharat", "kg", 400, TOPTANCI),
        hammadde("Sıvı Yağ", "litre", 110, TOPTANCI, koli=18, koli_ad="teneke"),
        hammadde("Zeytinyağı", "litre", 450, TOPTANCI, koli=5, koli_ad="bidon"),
        hammadde("Soğan", "kg", 25, HAL, koli=20, koli_ad="çuval"),
        hammadde("Patates", "kg", 25, HAL, koli=25, koli_ad="çuval"),
        hammadde("Sarımsak", "kg", 200, HAL),
        hammadde("Karalahana", "kg", 40, HAL, "taze"),
        hammadde("Pırasa", "kg", 40, HAL, "taze"),
        hammadde("Ispanak", "kg", 50, HAL, "taze"),
        hammadde("Patlıcan", "kg", 40, HAL, "taze"),
        hammadde("Taze Fasulye", "kg", 60, HAL, "taze"),
        hammadde("Dolmalık Biber", "kg", 60, HAL, "taze"),
        hammadde("Domates", "kg", 35, HAL, "taze"),
        hammadde("Havuç", "kg", 30, HAL, "taze"),
        hammadde("Kabak", "kg", 35, HAL, "taze"),
        hammadde("Salatalık", "kg", 35, HAL, "taze"),
        hammadde("Limon", "kg", 60, HAL, "taze"),
        hammadde("Dana Kuşbaşı", "kg", 900, KASAP, "taze"),
        hammadde("Dana Kıyma", "kg", 820, KASAP, "taze"),
        hammadde("Tavuk But", "kg", 220, PILICCI, "taze"),
        hammadde("Hamsi", "kg", 280, BALIKCI, "gunluk"),
        hammadde("Yoğurt", "kg", 100, SUTCU, "taze"),
        hammadde("Tereyağı", "kg", 720, SUTCU, "taze"),
        hammadde("Süt", "litre", 45, SUTCU, "taze"),
        hammadde("Yumurta", "adet", 11, TOPTANCI, "taze", koli=30, koli_ad="viyol"),
        hammadde("Ekmek", "adet", 15, FIRINCI, "gunluk"),
        hammadde("Dökme Çay", "kg", 380, KAHVECI),
        hammadde("Çekilmiş Kahve", "kg", 1100, KAHVECI),
    ],
    "urunler": [
        # --- corbalar: gunluk = "gunun corbasi" ne kadar gidiyor
        urun("Mercimek Çorbası", "porsiyon", 100, 45, "corba", "Çorba", raf=1,
             parti=("tencere", 40), adim=0.125,
             recete=[("Kırmızı Mercimek", 2.5), ("Soğan", 1.0), ("Havuç", 0.6),
                     ("Patates", 0.5), ("Tereyağı", 0.3), ("Un", 0.2), ("Salça", 0.15),
                     ("Baharat", 0.03), ("Ekmek", 8)]),
        urun("Ezogelin Çorbası", "porsiyon", 100, 45, "corba", "Çorba", raf=1,
             parti=("tencere", 40), adim=0.125,
             recete=[("Kırmızı Mercimek", 2.0), ("Bulgur", 0.5), ("Pirinç", 0.3),
                     ("Soğan", 1.0), ("Tereyağı", 0.3), ("Salça", 0.2),
                     ("Baharat", 0.04), ("Ekmek", 8)]),
        urun("Tarhana Çorbası", "porsiyon", 100, 45, "corba", "Çorba", raf=1,
             parti=("tencere", 40), adim=0.125,
             recete=[("Tarhana", 1.6), ("Tereyağı", 0.3), ("Salça", 0.15), ("Ekmek", 8)]),
        urun("Karalahana Çorbası", "porsiyon", 100, 45, "corba", "Çorba", raf=1,
             parti=("tencere", 40), adim=0.125,
             recete=[("Karalahana", 3.0), ("Kuru Fasulye (çiğ)", 1.0), ("Mısır Unu", 0.5),
                     ("Soğan", 1.0), ("Tereyağı", 0.3), ("Ekmek", 8)]),
        # --- pilav ve ana yemekler
        urun("Pirinç Pilavı", "porsiyon", 80, 50, "pilav", "Ana yemek", raf=1,
             parti=("tencere", 40), adim=0.125,
             recete=[("Pirinç", 3.2), ("Tereyağı", 0.35), ("Şehriye", 0.3)]),
        urun("Kuru Fasulye", "porsiyon", 190, 30, "baklagil", "Ana yemek", raf=1,
             parti=("tencere", 40), adim=0.125,
             recete=[("Kuru Fasulye (çiğ)", 3.2), ("Dana Kuşbaşı", 1.2), ("Soğan", 1.2),
                     ("Salça", 0.3), ("Tereyağı", 0.3), ("Sıvı Yağ", 0.2),
                     ("Baharat", 0.04), ("Ekmek", 12)]),
        urun("Etli Nohut", "porsiyon", 190, 30, "baklagil", "Ana yemek", raf=1,
             parti=("tencere", 40), adim=0.125,
             recete=[("Nohut", 3.0), ("Dana Kuşbaşı", 1.2), ("Soğan", 1.2),
                     ("Salça", 0.3), ("Tereyağı", 0.3), ("Sıvı Yağ", 0.2),
                     ("Baharat", 0.04), ("Ekmek", 12)]),
        urun("Tavuk Sote", "porsiyon", 240, 30, "et", "Ana yemek", raf=1,
             parti=("tencere", 40), adim=0.125,
             recete=[("Tavuk But", 7.0), ("Dolmalık Biber", 1.5), ("Domates", 2.0),
                     ("Soğan", 1.0), ("Sıvı Yağ", 0.3), ("Baharat", 0.05),
                     ("Ekmek", 12)]),
        urun("Karnıyarık", "porsiyon", 240, 30, "et", "Ana yemek", raf=1,
             parti=("tepsi", 40), adim=0.125,
             recete=[("Patlıcan", 10.0), ("Dana Kıyma", 2.4), ("Soğan", 1.5),
                     ("Domates", 2.0), ("Dolmalık Biber", 1.0), ("Sıvı Yağ", 2.0),
                     ("Salça", 0.2), ("Ekmek", 12)]),
        urun("İzmir Köfte", "porsiyon", 240, 30, "et", "Ana yemek", raf=1,
             parti=("tepsi", 40), adim=0.125,
             recete=[("Dana Kıyma", 3.2), ("Patates", 5.0), ("Domates", 2.0),
                     ("Dolmalık Biber", 1.0), ("Soğan", 0.8), ("Yumurta", 4),
                     ("Salça", 0.2), ("Sıvı Yağ", 0.5), ("Baharat", 0.05),
                     ("Ekmek", 16)]),
        urun("Sulu Köfte", "porsiyon", 240, 30, "et", "Ana yemek", raf=1,
             parti=("tencere", 40), adim=0.125,
             recete=[("Dana Kıyma", 2.4), ("Pirinç", 0.4), ("Patates", 3.0),
                     ("Havuç", 1.0), ("Soğan", 0.8), ("Un", 0.2), ("Yumurta", 4),
                     ("Salça", 0.2), ("Tereyağı", 0.2), ("Ekmek", 12)]),
        urun("Hamsi Tava", "porsiyon", 280, 20, "hamsi", "Ana yemek",
             recete=[("Hamsi", 0.3), ("Mısır Unu", 0.04), ("Sıvı Yağ", 0.08),
                     ("Soğan", 0.05), ("Ekmek", 0.3)]),
        # --- zeytinyaglilar
        urun("Zeytinyağlı Taze Fasulye", "porsiyon", 150, 15, "zeytinyagli",
             "Zeytinyağlı", raf=1, parti=("tencere", 30), adim=0.125,
             recete=[("Taze Fasulye", 5.0), ("Domates", 2.0), ("Soğan", 1.0),
                     ("Zeytinyağı", 0.6), ("Toz Şeker", 0.05)]),
        urun("Biber Dolma", "porsiyon", 150, 15, "zeytinyagli", "Zeytinyağlı", raf=1,
             parti=("tencere", 30), adim=0.125,
             recete=[("Dolmalık Biber", 6.0), ("Pirinç", 1.2), ("Soğan", 1.0),
                     ("Zeytinyağı", 0.5), ("Domates", 1.0), ("Salça", 0.1),
                     ("Baharat", 0.04)]),
        urun("Zeytinyağlı Pırasa", "porsiyon", 150, 15, "kis_sebze", "Zeytinyağlı",
             raf=1, parti=("tencere", 30), adim=0.125,
             recete=[("Pırasa", 6.0), ("Havuç", 1.0), ("Pirinç", 0.5), ("Zeytinyağı", 0.5),
                     ("Limon", 0.2), ("Toz Şeker", 0.05)]),
        urun("Ispanak Yemeği", "porsiyon", 150, 15, "kis_sebze", "Zeytinyağlı", raf=1,
             parti=("tencere", 30), adim=0.125,
             recete=[("Ispanak", 7.0), ("Soğan", 1.0), ("Pirinç", 0.4), ("Salça", 0.1),
                     ("Zeytinyağı", 0.4), ("Yoğurt", 1.5)]),
        urun("Karalahana Sarması", "porsiyon", 150, 15, "kis_sebze", "Zeytinyağlı",
             raf=1, parti=("tepsi", 30), adim=0.125,
             recete=[("Karalahana", 4.0), ("Pirinç", 1.5), ("Dana Kıyma", 1.0),
                     ("Soğan", 1.0), ("Salça", 0.2), ("Tereyağı", 0.2), ("Baharat", 0.03)]),
        urun("Türlü", "porsiyon", 150, 15, "zeytinyagli", "Zeytinyağlı", raf=1,
             parti=("tencere", 30), adim=0.125,
             recete=[("Patlıcan", 2.0), ("Kabak", 2.0), ("Patates", 2.0),
                     ("Taze Fasulye", 1.5), ("Dolmalık Biber", 1.0), ("Domates", 2.0),
                     ("Soğan", 1.0), ("Zeytinyağı", 0.5)]),
        # --- tatlilar: dolapta uc gun dayanir; ceyrek tepsi de yapilir
        urun("Sütlaç", "kase", 110, 6, "tatli", "Tatlı", raf=3,
             parti=("tepsi", 30), adim=0.25,
             recete=[("Süt", 6.0), ("Pirinç", 0.5), ("Toz Şeker", 1.0),
                     ("Nişasta", 0.2)]),
        urun("Revani", "dilim", 110, 3, "tatli", "Tatlı", raf=3,
             parti=("tepsi", 30), adim=0.25,
             recete=[("İrmik", 1.0), ("Un", 0.3), ("Yumurta", 8), ("Toz Şeker", 2.0),
                     ("Yoğurt", 0.3), ("Sıvı Yağ", 0.2)]),
        urun("İrmik Helvası", "porsiyon", 110, 3, "tatli", "Tatlı", raf=3,
             parti=("tepsi", 30), adim=0.25,
             recete=[("İrmik", 1.5), ("Tereyağı", 0.4), ("Süt", 2.0),
                     ("Toz Şeker", 1.2)]),
        # --- siparis aninda hazirlananlar ve icecekler
        urun("Cacık", "porsiyon", 70, 10, "soguk", "Meze ve salata",
             recete=[("Yoğurt", 0.15), ("Salatalık", 0.1), ("Sarımsak", 0.005),
                     ("Zeytinyağı", 0.01)]),
        urun("Çoban Salata", "porsiyon", 70, 10, "salata", "Meze ve salata",
             recete=[("Domates", 0.15), ("Salatalık", 0.1), ("Dolmalık Biber", 0.05),
                     ("Soğan", 0.03), ("Zeytinyağı", 0.015), ("Limon", 0.02)]),
        urun("Ayran", "adet", 35, 45, "ayran", "İçecek", alis=11, tedarikci=ICECEKCI),
        urun("Çay", "bardak", 20, 70, "sicak", "İçecek",
             recete=[("Dökme Çay", 0.006), ("Toz Şeker", 0.008)]),
        urun("Türk Kahvesi", "fincan", 80, 8, "sicak", "İçecek",
             recete=[("Çekilmiş Kahve", 0.007), ("Toz Şeker", 0.005)]),
        urun("Su", "adet", 15, 15, "su", "İçecek", alis=6, tedarikci=ICECEKCI),
    ],
    "ara_urunler": [],
    "calisanlar": [
        calisan("Fatma Öztürk", "Aşçı", 45000, 15300, "2018-02-01",
                "Tencereleri o kuruyor, menüyü o yazıyor"),
        calisan("Hatice Demir", "Aşçı yardımcısı", 30000, 12500, "2021-10-01"),
        calisan("Murat Aydın", "Garson", 28100, 12150, "2023-05-01"),
        calisan("Kemal Yıldız", "Garson", 28100, 12150, "2025-01-15"),
        calisan("Osman Koç", "Bulaşıkçı", 28100, 12150, "2024-08-01"),
    ],
    "giderler": {"kira": 45000, "elektrik": 12000, "dogalgaz": 20000, "su": 4000,
                 "kart_payi": 0.6},
    "ozel_gunler": lambda baglanti: None,
    "ambalaj": lambda talep: {},
    "carpan": samata_carpan,
    "acik_mi": samata_acik_mi,
    "menude_mi": samata_menude_mi,
    "menuler": SAMATA_MENULER,
    "ilk_menu": "Kış sebzeleri",       # 1 Ocak'ta kis
}


# ================================================================ SUSU MANTI
def susu_carpan(tarih, etiketler, u, gun_hava, menu_adi=None):
    sicaklik, yagis = gun_hava
    g = u["grup"]
    c = [1.0, 1.0, 1.0, 1.0, 1.05, 1.4, 1.6][tarih.weekday()]   # pazar ogleni dolu
    c *= mevsim(tarih, kis=1.15, yaz=0.85, gecis=1.05)            # sicak yemek, kis isi
    if g == "corba":
        c *= mevsim(tarih, kis=1.15, yaz=0.8)
    elif g == "soguk":
        c *= mevsim(tarih, kis=0.8, yaz=1.4) * sicaklik_etkisi(sicaklik, 0.006)
    if "Ramazan" in etiketler:
        c *= 0.85               # oglen bos, iftarda dolu
    if "Kurban Bayramı" in etiketler:
        c *= 0.6                # herkes evde et yiyor
    elif "Ramazan Bayramı" in etiketler:
        c *= 0.9
    elif "Yarım Gün" in etiketler:
        c *= 0.9
    if "Resmi Tatil" in etiketler:
        c *= 1.2                # aileler disarida yiyor
    if yagis >= 8:
        c *= 0.9
    if sicaklik < 8 and g == "manti":
        c *= 1.05
    return c


SUSU = {
    "kullanici": "susu",
    "ad": "Şuşu Mantı",
    "satis_girisi": "dogrudan",
    "hammaddeler": [
        hammadde("Un", "kg", 39, UNCU, koli=50, koli_ad="çuval"),
        hammadde("Yumurta", "adet", 11, TOPTANCI, "taze", koli=30, koli_ad="viyol"),
        hammadde("Dana Kıyma", "kg", 820, KASAP, "taze"),
        hammadde("Soğan", "kg", 25, HAL, koli=20, koli_ad="çuval"),
        hammadde("Sarımsak", "kg", 200, HAL),
        hammadde("Havuç", "kg", 30, HAL, "taze"),
        hammadde("Patates", "kg", 25, HAL, koli=25, koli_ad="çuval"),
        hammadde("Baharat", "kg", 400, TOPTANCI),
        hammadde("Salça", "kg", 130, TOPTANCI),
        hammadde("Sıvı Yağ", "litre", 110, TOPTANCI, koli=18, koli_ad="teneke"),
        hammadde("Kırmızı Mercimek", "kg", 85, TOPTANCI),
        hammadde("Pirinç", "kg", 90, TOPTANCI),
        hammadde("Toz Şeker", "kg", 34, TOPTANCI, koli=50, koli_ad="çuval"),
        hammadde("Nişasta", "kg", 80, TOPTANCI),
        hammadde("Yoğurt", "kg", 100, SUTCU, "taze"),
        hammadde("Tereyağı", "kg", 720, SUTCU, "taze"),
        hammadde("Süt", "litre", 45, SUTCU, "taze"),
        hammadde("Ekmek", "adet", 15, FIRINCI, "gunluk"),
        hammadde("Dökme Çay", "kg", 380, KAHVECI),
        hammadde("Paket Kabı", "adet", 8, AMBALAJCI, koli=100, tur="Ambalaj"),
    ],
    "ara_urunler": [
        # Manti tepside yapilip dondurucuya konuyor; porsiyon da paket de
        # buradan cikiyor. Stok 1,5 gunluge dusunce 3 gunluk yapilir.
        ara_urun("Mantı", "kg", "Ara ürün", parti=("tepsi", 5), adim=0.5,
                 aciklama="Dondurucuda bekleyen hazır mantı", gunde_en_cok=10,
                 recete=[("Un", 2.25), ("Yumurta", 5), ("Dana Kıyma", 2.0),
                         ("Soğan", 0.5), ("Baharat", 0.05)]),
    ],
    "urunler": [
        urun("Mantı (porsiyon)", "porsiyon", 400, 38, "manti", "Mantı",
             recete=[("Mantı", 0.25), ("Yoğurt", 0.15), ("Tereyağı", 0.02),
                     ("Salça", 0.01), ("Sarımsak", 0.005), ("Baharat", 0.003)]),
        urun("Çıtır Mantı", "porsiyon", 420, 6, "manti", "Mantı",
             recete=[("Mantı", 0.25), ("Sıvı Yağ", 0.06), ("Yoğurt", 0.15),
                     ("Tereyağı", 0.02), ("Salça", 0.01), ("Sarımsak", 0.005),
                     ("Baharat", 0.003)]),
        urun("Çiğ Mantı (paket)", "kg", 900, 3, "paket", "Mantı", satis_adim=0.5,
             recete=[("Mantı", 1.0), ("Paket Kabı", 1)]),
        urun("Mercimek Çorbası", "porsiyon", 120, 20, "corba", "Çorba", raf=1,
             parti=("tencere", 40), adim=0.125,
             recete=[("Kırmızı Mercimek", 2.5), ("Soğan", 1.0), ("Havuç", 0.6),
                     ("Patates", 0.5), ("Tereyağı", 0.3), ("Un", 0.2), ("Salça", 0.15),
                     ("Baharat", 0.03), ("Ekmek", 8)]),
        urun("Sütlaç", "kase", 120, 8, "tatli", "Tatlı", raf=3,
             parti=("tepsi", 30), adim=0.25,
             recete=[("Süt", 6.0), ("Pirinç", 0.5), ("Toz Şeker", 1.0),
                     ("Nişasta", 0.2)]),
        urun("Ayran", "adet", 40, 35, "soguk", "İçecek", alis=11, tedarikci=ICECEKCI),
        urun("Çay", "bardak", 20, 50, "sicak", "İçecek",
             recete=[("Dökme Çay", 0.006), ("Toz Şeker", 0.008)]),
        urun("Kola (kutu)", "adet", 60, 12, "soguk", "İçecek", alis=26,
             tedarikci=ICECEKCI),
        urun("Su", "adet", 15, 12, "soguk", "İçecek", alis=6, tedarikci=ICECEKCI),
    ],
    "calisanlar": [
        calisan("Ali Kurt", "Aşçı", 40000, 14000, "2020-03-01"),
        calisan("Emine Aksoy", "Mantı ustası", 30000, 12500, "2019-09-01",
                "Hamuru o açıyor; günde 8-10 tepsi"),
        calisan("Songül Polat", "Mantı ustası", 30000, 12500, "2022-01-10"),
        calisan("Serkan Uçar", "Garson", 28100, 12150, "2023-04-01"),
        calisan("Cem Erdoğan", "Garson", 28100, 12150, "2025-03-01"),
        calisan("Recep Tunç", "Bulaşıkçı", 28100, 12150, "2024-02-01"),
    ],
    "giderler": {"kira": 40000, "elektrik": 12000, "dogalgaz": 18000, "su": 4000,
                 "kart_payi": 0.7},
    "ozel_gunler": lambda baglanti: None,
    "ambalaj": lambda talep: {},
    "carpan": susu_carpan,
    "acik_mi": lambda tarih, etiketler: True,
    "menude_mi": lambda tarih, ad, menu_adi: True,
    "menuler": [],
}

DUKKANLAR = [KUGU, SAMATA, SUSU]


# ---------------------------------------------------------------- fiyatlar
def fiyat_yuvarla(tutar):
    """Menude 347 TL yazmaz: 50 TL'nin ustu 5'e yuvarlanir."""
    return float(round(tutar)) if tutar < 50 else float(round(tutar / 5) * 5)


def ocak_fiyati(eylul):
    return fiyat_yuvarla(eylul / (1 + ZAM_ORANI))


def taban_fiyat(eylul):
    """Eylul fiyatindan geriye: 1 Ocak'taki alis fiyati."""
    return eylul / (1 + ENFLASYON * (FIYAT_GUNU - BASLANGIC).days)


# ---------------------------------------------------------------- hava
def hadise_kodu(yagis, tohum):
    if yagis >= 8:
        return "KSY"
    if yagis >= 3:
        return "SY"
    if yagis >= 1:
        return "HY"
    if yagis >= 0.2:
        return "CB"
    return "PB" if tohum < 0.45 else "AB"


def _openmeteo(adres):
    with urllib.request.urlopen(adres, timeout=30) as cevap:
        return json.load(cevap)["daily"]


def havayi_getir():
    """Ordu merkezin gunluk olcumleri. Arsiv son birkac gunu henuz bilmez;
    o gunler hava tahmini servisinin 'gecmis gunler' kismindan tamamlanir."""
    alanlar = ("temperature_2m_max,temperature_2m_min,precipitation_sum,"
               "windspeed_10m_max,relative_humidity_2m_max")
    ortak = f"latitude={ENLEM}&longitude={BOYLAM}&daily={alanlar}&timezone=Europe%2FIstanbul"
    gunler = {}
    for kaynak in (
        f"https://archive-api.open-meteo.com/v1/archive?{ortak}"
        f"&start_date={BASLANGIC}&end_date={BITIS}",
        f"https://api.open-meteo.com/v1/forecast?{ortak}&past_days=14&forecast_days=1",
    ):
        gunluk = _openmeteo(kaynak)
        for sira, gun in enumerate(gunluk["time"]):
            if gun in gunler or gun > BITIS.isoformat():
                continue
            en_yuksek = gunluk["temperature_2m_max"][sira]
            if en_yuksek is None:
                continue
            gunler[gun] = {
                "en_yuksek": en_yuksek,
                "en_dusuk": gunluk["temperature_2m_min"][sira],
                "yagis": gunluk["precipitation_sum"][sira] or 0.0,
                "ruzgar": gunluk["windspeed_10m_max"][sira],
                "nem": gunluk["relative_humidity_2m_max"][sira],
            }
    return gunler


def havayi_yaz(baglanti, gunler, zar):
    for gun, olcum in sorted(gunler.items()):
        hava.yaz(baglanti, gun, "Open-Meteo arşiv", tahmin=0,
                 hadise=hadise_kodu(olcum["yagis"], zar.random()), **olcum)
    baglanti.commit()


# ---------------------------------------------------------------- kurulum
def yuvarla_yukari(miktar, adim):
    return math.ceil(miktar / adim - 1e-9) * adim


def dosyayi_sifirla(dukkan_id):
    """Dukkanin veri dosyasini yedekleyip siler; hazirla() bos olarak kurar."""
    yol = veritabani.db_yolu(dukkan_id)
    if os.path.exists(yol):
        damga = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        yedek = os.path.join(veritabani.VERI_KLASORU,
                             f"yedek-{damga}-dukkan-{dukkan_id}-simulasyon-oncesi.db")
        shutil.copy2(yol, yedek)
        try:
            os.remove(yol)
        except PermissionError:
            sys.exit(f"{yol} silinemedi - program acik olabilir. Kapatip tekrar dene.")
        print(f"  yedek: {os.path.basename(yedek)}")
    return veritabani.hazirla(dukkan_id)


def sehri_yaz(baglanti):
    """Sehir ayarlari dukkan 1'den alinir; program Ordu'yu orada zaten secmis."""
    degerler = {"sehir": "Ordu", "mgm_istno": "", "enlem": str(ENLEM),
                "boylam": str(BOYLAM)}
    if os.path.exists(veritabani.db_yolu(1)):
        birinci = veritabani.baglan(1)
        for anahtar in degerler:
            deger = veritabani.ayar(birinci, anahtar, "")
            if deger:
                degerler[anahtar] = deger
        birinci.close()
    for anahtar, deger in degerler.items():
        veritabani.ayar_yaz(baglanti, anahtar, deger)


def kalem_yaz(baglanti, **alanlar):
    kolonlar = ", ".join(alanlar)
    isaretler = ", ".join("?" * len(alanlar))
    return baglanti.execute(
        f"INSERT INTO kalemler ({kolonlar}) VALUES ({isaretler})",
        tuple(alanlar.values()),
    ).lastrowid


def recete_yaz(baglanti, kimlik, urun_id, satirlar, verim=1, parti_ad="porsiyon",
               ad=""):
    recete_id = baglanti.execute(
        "INSERT INTO receteler (urun_id, ad, verim, parti_ad) VALUES (?, ?, ?, ?)",
        (urun_id, ad, verim, parti_ad),
    ).lastrowid
    for malzeme, miktar in satirlar:
        baglanti.execute(
            "INSERT INTO recete_satirlari (recete_id, kalem_id, miktar) VALUES (?, ?, ?)",
            (recete_id, kimlik[malzeme], miktar),
        )
    return recete_id


def yapiyi_kur(baglanti, tanim):
    """Kalemler, receteler, ayarlar, kadro. Doner: {ad: kalem_id}, {ad: recete_id}."""
    kimlik, receteler = {}, {}
    sira = 0
    for h in tanim["hammaddeler"]:
        kimlik[h["ad"]] = kalem_yaz(
            baglanti, ad=h["ad"], birim=h["birim"], tur=h["tur"], alinir=1,
            birim_fiyat=round(taban_fiyat(h["eylul"]), 2), koli_adet=h["koli"],
            koli_ad=h["koli_ad"] or "koli", tedarikci=h["tedarikci"],
            sayim_tarzi=h["sayim"], dagit=h["dagit"])
    for a in tanim["ara_urunler"]:
        kimlik[a["ad"]] = kalem_yaz(
            baglanti, ad=a["ad"], birim=a["birim"], tur=a["tur"], uretilir=1,
            aciklama=a["aciklama"])
    for u in tanim["urunler"]:
        sira += 1
        uretilir = 1 if u["parti"] else 0
        alinir = 1 if u["alis"] is not None else 0
        # Siparis aninda hazirlanan (cay, cacik) rafta durmaz; stogu tutulmaz.
        takip = 1 if (uretilir or alinir) else 0
        kimlik[u["ad"]] = kalem_yaz(
            baglanti, ad=u["ad"], birim=u["birim"], tur=u["tur"], alinir=alinir,
            uretilir=uretilir, satilir=1, takip=takip, fiyat=ocak_fiyati(u["eylul"]),
            birim_fiyat=round(taban_fiyat(u["alis"]), 2) if alinir else 0.0,
            koli_adet=24 if alinir else 0, tedarikci=u["tedarikci"],
            sayim_tarzi=u["sayim"], sira=sira)

    for a in tanim["ara_urunler"]:
        receteler[a["ad"]] = recete_yaz(baglanti, kimlik, kimlik[a["ad"]], a["recete"],
                                        a["parti"][1], a["parti"][0], a["ad"])
    for u in tanim["urunler"]:
        if u["recete"]:
            if u["parti"]:
                receteler[u["ad"]] = recete_yaz(baglanti, kimlik, kimlik[u["ad"]],
                                                u["recete"], u["parti"][1],
                                                u["parti"][0], u["ad"])
            else:
                receteler[u["ad"]] = recete_yaz(baglanti, kimlik, kimlik[u["ad"]],
                                                u["recete"], parti_ad=u["birim"])

    veritabani.ayar_yaz(baglanti, "dukkan_adi", tanim["ad"])
    veritabani.ayar_yaz(baglanti, "satis_girisi", tanim["satis_girisi"])
    veritabani.ayar_yaz(baglanti, "kurulum_bitti", "1")
    sehri_yaz(baglanti)
    baglanti.commit()

    for ad, gorev, maas, sgk, giris, notlar in tanim["calisanlar"]:
        hesap.calisan_ekle(baglanti, ad, gorev, "", maas, sgk, giris, notlar)
    tanim["ozel_gunler"](baglanti)

    # Menu donemleri: programin kendi menuler ekrani ne yaziyorsa o.
    for ad, kosul, esik, urunler in tanim["menuler"]:
        menu_id = menuler.ekle(baglanti, ad, kosul, esik, [kimlik[u] for u in urunler])
        if ad == tanim.get("ilk_menu"):
            menuler.gec(baglanti, menu_id, BASLANGIC.isoformat())
    return kimlik, receteler


# ---------------------------------------------------------------- bir dukkanin gunleri
class Simulasyon:
    """Bir dukkanin 1 Ocak'tan dune kadarki gunleri."""

    def __init__(self, tanim, baglanti, kimlik, receteler, zar):
        self.t = tanim
        self.b = baglanti
        self.id = kimlik
        self.recete_id = receteler
        self.zar = zar
        self.hammaddeler = {h["ad"]: h for h in tanim["hammaddeler"]}
        self.taban = {h["ad"]: taban_fiyat(h["eylul"]) for h in tanim["hammaddeler"]}
        for u in tanim["urunler"]:
            if u["alis"] is not None:
                self.hammaddeler[u["ad"]] = {"tedarikci": u["tedarikci"],
                                             "tazelik": "kuru", "koli": 24}
                self.taban[u["ad"]] = taban_fiyat(u["alis"])
        self.gecmis = collections.defaultdict(lambda: collections.deque(maxlen=14))
        # Raftaki her urunun partileri, eskiden yeniye: [kac gunluk, miktar].
        self.raf = collections.defaultdict(list)
        gecerli = menuler.gecerli(baglanti)
        self.menu_adi = gecerli["ad"] if gecerli else None
        self.fire_tutari = 0.0
        self.istenen = 0.0        # musterinin istedigi (TL)
        self.karsilanamayan = 0.0  # "bitti" denen (TL)

    # ---- yardimcilar
    def alis_fiyati(self, ad, gun_no):
        return self.taban[ad] * (1 + ENFLASYON * gun_no) * self.zar.uniform(0.98, 1.02)

    def etiket_haritasi(self):
        """Tarih -> {etiket: o etiketin ilk gunu}. Bayramin ilk gununu bilmek icin."""
        harita = collections.defaultdict(dict)
        for satir in self.b.execute(
                "SELECT etiket, baslangic, bitis FROM ozel_gunler WHERE aktif = 1"):
            gun = datetime.date.fromisoformat(satir["baslangic"])
            son = datetime.date.fromisoformat(satir["bitis"])
            while gun <= son:
                harita[gun.isoformat()][satir["etiket"]] = satir["baslangic"]
                gun += datetime.timedelta(days=1)
        return harita

    # ---- talep
    def talepler(self, tarih, etiketler, gun_hava, beklenen=False):
        """Her satilan kalem icin o gunun talebi.

        beklenen=True dukkanin sabah tahmin ettigi: gun, mevsim, bayram ve
        pencereden gorunen hava. Uretim buna gore yapilir. Gercek talep bunun
        uzerine rastgele bir sapma ekler.
        """
        sonuc = {}
        if not self.t["acik_mi"](tarih, etiketler):
            return {u["ad"]: 0.0 for u in self.t["urunler"]}
        gun_sapmasi = 1.0 if beklenen else max(0.5, self.zar.gauss(1.0, GUN_SAPMASI))
        for u in self.t["urunler"]:
            if not self.t["menude_mi"](tarih, u["ad"], self.menu_adi):
                sonuc[u["ad"]] = 0.0
                continue
            miktar = u["gunluk"] * self.t["carpan"](tarih, etiketler, u, gun_hava,
                                                    self.menu_adi)
            if not beklenen:
                miktar *= gun_sapmasi * max(0.3, self.zar.gauss(1.0, URUN_SAPMASI))
                miktar = round(miktar / u["satis_adim"]) * u["satis_adim"]
            sonuc[u["ad"]] = max(0.0, miktar)
        return sonuc

    # ---- uretim plani
    def uretim_plani(self, beklenen, stok):
        """Sabah kac tepsi/tencere yapilacak: {ad: parti sayisi}."""
        plan = {}
        for u in self.t["urunler"]:
            if not u["parti"] or beklenen[u["ad"]] <= 0:
                continue
            verim = u["parti"][1]
            eldeki = stok.get(self.id[u["ad"]], 0.0)
            if u["raf"] is None:
                # Uzun dayanan (kurabiye): bugunun satisi + normal uc gunluk.
                # Bayram oncesinin dort kati satisi ileriye tasinmaz; bayram
                # bitince elde yigin kalmasin.
                hedef = beklenen[u["ad"]] + u["gunluk"] * 3
                if eldeki >= beklenen[u["ad"]] + u["gunluk"]:
                    continue
                gereken = hedef - eldeki
            else:
                gereken = beklenen[u["ad"]] * (1 + FAZLA_URETIM) - eldeki
                gereken = max(gereken, u["vitrin"] - eldeki)
            if gereken > 0:
                # En yakin parcaya yuvarlanir, ama en az bir parca yapilir.
                parca = round(gereken / verim / u["adim"]) * u["adim"]
                plan[u["ad"]] = max(u["adim"], parca)

        # Ara urun (manti): icine girdigi urunlerin beklenen satisindan.
        for a in self.t["ara_urunler"]:
            gunluk = sum(
                beklenen[u["ad"]] * miktar
                for u in self.t["urunler"] for malzeme, miktar in u["recete"]
                if malzeme == a["ad"] and not u["parti"]
            )
            if gunluk <= 0:
                continue
            esik, hedef = a["stok_gun"]
            eldeki = stok.get(self.id[a["ad"]], 0.0)
            if eldeki < gunluk * esik:
                parti = yuvarla_yukari((gunluk * hedef - eldeki) / a["parti"][1], a["adim"])
                if a["gunde_en_cok"]:
                    parti = min(parti, a["gunde_en_cok"])
                plan[a["ad"]] = parti
        return plan

    def normal_ihtiyac(self, tarih, etiketler, gun_hava):
        """Uretim hic parti parti olmasaydi bir gunde ne kadar malzeme giderdi.

        Alimlar "son 14 gunde gunde ne harcandi" ortalamasina bakarak verilir.
        Dukkan bos stokla actigi ilk gunlerde bu ortalama olmadigi icin,
        ilk iki hafta icin ortalamayi buradan besliyoruz; yoksa ilk sabahin
        uc gunluk manti uretimi "gunluk ihtiyac" sanilip iki haftalik et alinir.
        """
        beklenen = self.talepler(tarih, etiketler, gun_hava, beklenen=True)
        gereken = collections.defaultdict(float)
        ara = {a["ad"]: a for a in self.t["ara_urunler"]}
        for u in self.t["urunler"]:
            adet = beklenen[u["ad"]]
            if u["alis"] is not None:
                gereken[u["ad"]] += adet
            bolen = u["parti"][1] if u["parti"] else 1
            for malzeme, miktar in u["recete"]:
                if malzeme in self.hammaddeler:
                    gereken[malzeme] += miktar * adet / bolen
                elif malzeme in ara:
                    a = ara[malzeme]
                    for alt, alt_miktar in a["recete"]:
                        gereken[alt] += alt_miktar * miktar * adet / a["parti"][1]
        for ad, adet in self.t["ambalaj"](beklenen).items():
            gereken[ad] += adet
        return gereken

    # ---- malzeme ihtiyaci ve alim
    def ihtiyac(self, plan, talep, ambalaj):
        """Bugunun uretimi ve siparisle hazirlanan satislar icin hammadde."""
        gereken = collections.defaultdict(float)
        tarifler = {a["ad"]: a["recete"] for a in self.t["ara_urunler"]}
        tarifler.update({u["ad"]: u["recete"] for u in self.t["urunler"] if u["parti"]})
        for ad, parti in plan.items():
            for malzeme, miktar in tarifler[ad]:
                if malzeme in self.hammaddeler:
                    gereken[malzeme] += miktar * parti
        for u in self.t["urunler"]:
            if u["parti"]:
                continue
            if u["alis"] is not None:
                gereken[u["ad"]] += talep[u["ad"]]
            for malzeme, miktar in u["recete"]:
                if malzeme in self.hammaddeler:
                    gereken[malzeme] += miktar * talep[u["ad"]]
        for ad, adet in ambalaj.items():
            gereken[ad] += adet
        return gereken

    def alim_miktari(self, ad, ham):
        koli = self.hammaddeler[ad]["koli"]
        if koli and koli > 1:
            return max(koli, yuvarla_yukari(ham, koli))
        if ham < 2:
            return max(0.25, yuvarla_yukari(ham, 0.25))
        if ham < 20:
            return float(math.ceil(ham))
        return yuvarla_yukari(ham, 5)

    def alimlari_yap(self, tarih, gun_no, gereken, stok):
        """Tazelige gore alim: ekmek her sabah, et-sut 2-3 gunde bir, kuru
        malzeme iki haftada bir. Ortalama tuketim son 14 gunun ihtiyacindan."""
        for ad, bilgi in self.hammaddeler.items():
            bugun = gereken.get(ad, 0.0)
            self.gecmis[ad].append(bugun)
            ortalama = (sum(self.gecmis[ad]) / len(self.gecmis[ad])) if self.gecmis[ad] else 0.0
            if ortalama <= 0:
                continue
            eldeki = stok.get(self.id[ad], 0.0)
            kalan = eldeki - bugun
            if bilgi["tazelik"] == "gunluk":
                if kalan >= 0:
                    continue
                miktar = self.alim_miktari(ad, -kalan * 1.03)
            elif bilgi["tazelik"] == "taze":
                if kalan >= ortalama * 1.0:
                    continue
                miktar = self.alim_miktari(ad, bugun - eldeki + ortalama * 3)
            else:
                if kalan >= ortalama * 4:
                    continue
                miktar = self.alim_miktari(ad, bugun - eldeki + ortalama * 12)
            tedarikci = bilgi["tedarikci"]
            tutar = round(miktar * self.alis_fiyati(ad, gun_no), 2)
            odeme = "pesin" if self.zar.random() < PESIN.get(tedarikci, 0.3) else "veresiye"
            hesap.alim_ekle(self.b, tarih, self.id[ad], miktar, tutar, odeme, tedarikci)
            stok[self.id[ad]] = eldeki + miktar

    # ---- satis
    def satilabilir(self, u, istenen, stok):
        """Rafta ne kadar varsa o kadar satilir; manti bitince porsiyon da biter."""
        sinir = istenen
        if u["parti"] or u["alis"] is not None:
            sinir = min(sinir, stok.get(self.id[u["ad"]], 0.0))
        for a in self.t["ara_urunler"]:
            for malzeme, miktar in u["recete"]:
                if malzeme == a["ad"] and not u["parti"]:
                    sinir = min(sinir, stok.get(self.id[a["ad"]], 0.0) / miktar)
        adim = u["satis_adim"]
        return max(0.0, math.floor(sinir / adim + 1e-9) * adim)

    def satislari_yaz(self, tarih, talep, stok):
        """Dogrudan satis girilen dukkan: gunun toplami kalem kalem."""
        satilan = {}
        for u in self.t["urunler"]:
            miktar = self.satilabilir(u, talep[u["ad"]], stok)
            if miktar <= 0:
                continue
            hesap.satis_ekle(self.b, tarih, self.id[u["ad"]], miktar)
            satilan[u["ad"]] = miktar
            if u["parti"] or u["alis"] is not None:
                stok[self.id[u["ad"]]] = stok.get(self.id[u["ad"]], 0.0) - miktar
            for malzeme, oran in u["recete"]:
                if not u["parti"] and malzeme in self.id:
                    stok[self.id[malzeme]] = stok.get(self.id[malzeme], 0.0) - oran * miktar
        return satilan

    def gun_sonu_sayimi(self, tarih, talep, stok, ambalaj):
        """Sayimla calisan dukkan (pastane): vitrinde kalan yazilir, program
        ne satildigini aradaki farktan bulur. Cay-kahve sayilamaz, elle girilir."""
        kalanlar, elle, satilan = {}, {}, {}
        for u in self.t["urunler"]:
            kalem_id = self.id[u["ad"]]
            miktar = self.satilabilir(u, talep[u["ad"]], stok)
            satilan[u["ad"]] = miktar
            if u["sayim"] == "say":
                kalanlar[kalem_id] = (0, round(stok.get(kalem_id, 0.0) - miktar, 3))
                stok[kalem_id] = stok.get(kalem_id, 0.0) - miktar
            elif u["sayim"] == "elle" and miktar > 0:
                elle[kalem_id] = miktar
        bitenler = []
        for h in self.t["hammaddeler"]:
            kalem_id = self.id[h["ad"]]
            harcanan = ambalaj.get(h["ad"], 0.0)
            eldeki = stok.get(kalem_id, 0.0)
            if h["sayim"] == "say":
                kalan = max(0.0, eldeki - harcanan)
                koli = math.floor(kalan / h["koli"]) if h["koli"] > 1 else 0
                kalanlar[kalem_id] = (koli, round(kalan - koli * h["koli"], 3))
                stok[kalem_id] = kalan
            elif h["sayim"] == "koli" and harcanan > 0 and eldeki >= h["koli"]:
                # Tek tek sayilmiyor; bir kolisi bitince isaretleniyor.
                if self.zar.random() < harcanan / h["koli"]:
                    bitenler.append(kalem_id)
                    stok[kalem_id] = eldeki - h["koli"]
        hesap.sayim_kaydet(self.b, tarih, kalanlar, elle, bitenler)
        return satilan

    # ---- fire
    def fireyi_yaz(self, tarih, uretilen, satilan, stok):
        """Aksam: raf omru dolan urun atilir.

        Her urunun raftaki partileri yaslariyla tutulur. Satis once en eski
        partiden yapilir (ilk giren ilk cikar). Aksam her parti bir gun
        yaslanir; raf omrunu dolduran atilir. raf=1 olanin bugun artani
        hemen, raf=3 olaninki ucuncu aksam atilir.
        """
        for u in self.t["urunler"]:
            if not u["parti"] or u["raf"] is None:
                continue
            kalem_id = self.id[u["ad"]]
            partiler = self.raf[u["ad"]]
            if uretilen.get(u["ad"], 0.0) > 0:
                partiler.append([0, uretilen[u["ad"]]])
            satis = satilan.get(u["ad"], 0.0)
            for parti in partiler:
                alinan = min(parti[1], satis)
                parti[1] -= alinan
                satis -= alinan
            atilacak, kalanlar = 0.0, []
            for yas, miktar in partiler:
                if miktar <= 1e-9:
                    continue
                if yas + 1 >= u["raf"]:
                    atilacak += miktar
                else:
                    kalanlar.append([yas + 1, miktar])
            self.raf[u["ad"]] = kalanlar
            eldeki = max(0.0, stok.get(kalem_id, 0.0))
            atilacak = min(atilacak, eldeki)
            if atilacak <= 1e-9:
                continue
            self.fire_tutari += atilacak * hesap.birim_maliyet(self.b, kalem_id)
            sebep = "Fire: akşam artan" if u["raf"] == 1 else "Fire: bayatladı"
            hesap.sayim_duzelt(self.b, tarih, kalem_id, eldeki - atilacak, sebep)
            stok[kalem_id] = eldeki - atilacak

    # ---- menu
    def menu_gecisi(self, tarih):
        """Dukkan sahibi programin gecis onerisine uyar: onerilen gun gelince
        gecer. Oneri ana menudeki ile ayni hesap (menuler.oneri); tek fark,
        burada hava tahmini yerine o gunlerin gerceklesen havasi var."""
        if not self.t["menuler"]:
            return
        plan = menuler.oneri(self.b, bugun=tarih)
        if plan and plan["tarih"] <= tarih:
            menuler.gec(self.b, plan["menu"]["id"], tarih.isoformat())
            self.menu_adi = plan["menu"]["ad"]
            print(f"  {tarih}: {self.menu_adi} ({_neden(plan)})")

    # ---- fiyat, gider, odeme
    def zam_yap(self):
        for u in self.t["urunler"]:
            self.b.execute("UPDATE kalemler SET fiyat = ? WHERE id = ?",
                           (float(u["eylul"]), self.id[u["ad"]]))
        self.b.commit()

    def ciro(self, bas, son):
        return self.b.execute(
            "SELECT COALESCE(SUM(tutar), 0) FROM satislar WHERE tarih BETWEEN ? AND ?",
            (bas, son)).fetchone()[0]

    def giderleri_yaz(self, tarih):
        g = self.t["giderler"]
        gun, t = tarih.day, tarih.isoformat()
        z = self.zar
        if gun == 1:
            hesap.gider_ekle(self.b, t, "Dükkân kirası", g["kira"])
        if gun == 3 and tarih.month > 1:
            # Gecen ayin kartli satislarinin komisyonu bu ay hesaptan kesilir.
            onceki_son = tarih.replace(day=1) - datetime.timedelta(days=1)
            onceki = self.ciro(onceki_son.replace(day=1).isoformat(), onceki_son.isoformat())
            hesap.gider_ekle(self.b, t, "Kredi kartı / POS komisyonu",
                             round(onceki * g["kart_payi"] * 0.018, -1))
        if gun == 5:
            hesap.maas_yaz(self.b, t)
        if gun == 10:
            hesap.gider_ekle(self.b, t, "İnternet ve telefon", 1150)
        if gun == 20:
            hesap.gider_ekle(self.b, t, "Elektrik faturası",
                             round(g["elektrik"] * mevsim(tarih, yaz=1.1)
                                   * z.uniform(0.9, 1.1), -2))
            hesap.gider_ekle(self.b, t, "Su faturası",
                             round(g["su"] * z.uniform(0.85, 1.15), -1))
        if gun == 22:
            # Kisin hem ocak hem kalorifer; yazin sadece ocak.
            carpan = mevsim(tarih, kis=1.6, yaz=0.7, gecis=1.2)
            if tarih.month in (5, 9):
                carpan = 0.7
            elif tarih.month in (4, 10):
                carpan = 0.9
            hesap.gider_ekle(self.b, t, "Doğalgaz faturası",
                             round(g["dogalgaz"] * carpan * z.uniform(0.9, 1.1), -2))
        if gun == 25:
            hesap.gider_ekle(self.b, t, "Muhasebeci", 6500)
        if gun == 28:
            # KDV ve stopaj her ay; tutar son 30 gunun cirosuyla orantili.
            bas = (tarih - datetime.timedelta(days=29)).isoformat()
            son30 = self.ciro(bas, t) * 30 / max(1, min(30, (tarih - BASLANGIC).days + 1))
            hesap.gider_ekle(self.b, t, "KDV ve vergi ödemesi",
                             round(son30 * z.uniform(0.05, 0.07), -2))
        if tarih.weekday() == 0:
            hesap.gider_ekle(self.b, t, "Temizlik malzemesi",
                             round(z.uniform(800, 1800), -1))
        if z.random() < 0.04:
            hesap.gider_ekle(self.b, t, "Tamir - bakım", round(z.uniform(1500, 9000), -2))
        if z.random() < 0.08:
            hesap.gider_ekle(self.b, t, "Nakliye / yakıt", round(z.uniform(500, 2000), -1))

    def odemeleri_yap(self, tarih):
        if tarih.weekday() != 4:            # cuma gunu tedarikci hesabi gorulur
            return
        for satir in hesap.borc_dagilimi(self.b):
            if satir["tutar"] < 8000:
                continue
            tutar = round(satir["tutar"] * self.zar.uniform(0.6, 0.95), -2)
            if tutar > 0:
                hesap.odeme_ekle(self.b, tarih.isoformat(), satir["tedarikci"], tutar)

    def bankaya_yatir(self, tarih):
        """Kasada biriken nakit bankaya gider; kar hesabini etkilemez. Maas
        ve kira kasadan cikiyor, o yuzden kasada hep bir aylik yuk kadar kalir."""
        if tarih.weekday() != 6:
            return
        nakit = hesap.kasa(self.b)
        if nakit < 400000:
            return
        tutar = round(nakit - 300000, -3)
        self.b.execute(
            "INSERT INTO kasa_hareketleri (tarih, tutar, aciklama, kaynak_tur)"
            " VALUES (?, ?, ?, 'banka')", (tarih.isoformat(), -tutar, "Bankaya yatırıldı"))
        self.b.commit()

    # ---- ana dongu
    def calistir(self, gunluk_hava):
        self.b.execute(
            "INSERT INTO kasa_hareketleri (tarih, tutar, aciklama, kaynak_tur)"
            " VALUES (?, ?, ?, 'devir')",
            (BASLANGIC.isoformat(), ACILIS_KASASI, "2025'ten devreden kasa"))
        self.b.commit()
        etiket_haritasi = self.etiket_haritasi()

        def gunun_havasi(tarih):
            olcum = gunluk_hava.get(tarih.isoformat(), {"en_yuksek": 15.0, "yagis": 0.0})
            return olcum["en_yuksek"], olcum["yagis"]

        # Alim ortalamasini ilk iki haftanin normal ihtiyaciyla besle.
        for gun in range(14):
            tarih = BASLANGIC + datetime.timedelta(days=gun)
            etiketler = etiket_haritasi.get(tarih.isoformat(), {})
            if not self.t["acik_mi"](tarih, etiketler):
                continue
            normal = self.normal_ihtiyac(tarih, etiketler, gunun_havasi(tarih))
            for ad in self.hammaddeler:
                self.gecmis[ad].append(normal.get(ad, 0.0))

        tarih, gun_no = BASLANGIC, 0
        while tarih <= BITIS:
            t = tarih.isoformat()
            if tarih == ZAM_TARIHI:
                self.zam_yap()
            gun_hava = gunun_havasi(tarih)
            etiketler = etiket_haritasi.get(t, {})
            self.menu_gecisi(tarih)

            beklenen = self.talepler(tarih, etiketler, gun_hava, beklenen=True)
            talep = self.talepler(tarih, etiketler, gun_hava)
            stok = hesap.stoklar(self.b)
            plan = self.uretim_plani(beklenen, stok)
            ambalaj = self.t["ambalaj"](talep)
            if plan or any(talep.values()):      # kapali gunde alim da yok
                self.alimlari_yap(t, gun_no, self.ihtiyac(plan, talep, ambalaj), stok)

            # Once ara urun (manti), sonra onu kullananlar.
            verimler = {a["ad"]: a["parti"][1] for a in self.t["ara_urunler"]}
            verimler.update({u["ad"]: u["parti"][1] for u in self.t["urunler"] if u["parti"]})
            uretilen = {}
            for ad in sorted(plan, key=lambda ad: ad not in
                             {a["ad"] for a in self.t["ara_urunler"]}):
                if hesap.uretim_ekle(self.b, t, self.recete_id[ad], plan[ad]) is None:
                    eksik = hesap.recete_eksikleri(self.b, self.recete_id[ad], plan[ad])
                    print(f"  ! {t} {ad}: uretilemedi, eksik {eksik}")
                    continue
                uretilen[ad] = plan[ad] * verimler[ad]
            stok = hesap.stoklar(self.b)

            if self.t["satis_girisi"] == "sayim":
                satilan = self.gun_sonu_sayimi(t, talep, stok, ambalaj)
            else:
                satilan = self.satislari_yaz(t, talep, stok)
            fiyatlar = {u["ad"]: u["eylul"] for u in self.t["urunler"]}
            for ad, istenen in talep.items():
                self.istenen += istenen * fiyatlar[ad]
                self.karsilanamayan += max(0.0, istenen - satilan.get(ad, 0.0)) * fiyatlar[ad]
            self.fireyi_yaz(t, uretilen, satilan, stok)

            self.giderleri_yaz(tarih)
            self.odemeleri_yap(tarih)
            self.bankaya_yatir(tarih)
            tarih += datetime.timedelta(days=1)
            gun_no += 1
        self.b.commit()


def _neden(plan):
    return ", ".join(f"{gun:%d.%m} {derece:.0f}°" for gun, derece in plan["dizi"])


# ---------------------------------------------------------------- rapor
def ozet_yaz(tanim, baglanti, sim):
    print(f"\n  {tanim['ad']}")
    print(f"  {'Ay':<8}{'Ciro':>12}{'Malzeme':>12}{'Gider':>12}{'Net kâr':>12}{'Net %':>7}")
    toplam = {"ciro": 0, "maliyet": 0, "gider": 0}
    ay = BASLANGIC.replace(day=1)
    while ay <= BITIS:
        sonraki = (ay + datetime.timedelta(days=32)).replace(day=1)
        son = min(BITIS, sonraki - datetime.timedelta(days=1))
        o = hesap.aralik_ozeti(baglanti, ay.isoformat(), son.isoformat())
        yuzde = 100 * o["net_kar"] / o["ciro"] if o["ciro"] else 0
        print(f"  {ay:%Y-%m}{o['ciro']:>12,.0f}{o['satis_maliyeti']:>12,.0f}"
              f"{o['gider']:>12,.0f}{o['net_kar']:>12,.0f}{yuzde:>6.1f}%")
        toplam["ciro"] += o["ciro"]
        toplam["maliyet"] += o["satis_maliyeti"]
        toplam["gider"] += o["gider"]
        ay = sonraki
    net = toplam["ciro"] - toplam["maliyet"] - toplam["gider"]
    c = toplam["ciro"] or 1
    print(f"  toplam ciro {toplam['ciro']:,.0f} TL | malzeme %{100*toplam['maliyet']/c:.1f}"
          f" | gider %{100*toplam['gider']/c:.1f} | net kâr {net:,.0f} TL (%{100*net/c:.1f})")
    print(f"  fire (kâra yansımayan): {sim.fire_tutari:,.0f} TL (%{100*sim.fire_tutari/c:.1f})"
          f" | 'bitti' denen talep: %{100*sim.karsilanamayan/max(sim.istenen, 1):.1f}"
          f" | kasa {hesap.kasa(baglanti):,.0f} | borç {hesap.borc(baglanti):,.0f}")


# ---------------------------------------------------------------- ana akis
def main():
    if "--onayla" not in sys.argv:
        print(__doc__)
        print("Bu betik uc dukkanin veri dosyasini SILIP uydurma kayitlarla yeniden yazar.")
        print("Yine de calistirmak icin:  python simulasyon_dukkanlar.py --onayla")
        return
    secilen = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    defter = hesaplar.hazirla()

    print(f"hava cekiliyor: {BASLANGIC} - {BITIS}")
    gunluk_hava = havayi_getir()
    print(f"  {len(gunluk_hava)} gunluk olcum")

    for sira, tanim in enumerate(DUKKANLAR):
        if secilen and tanim["kullanici"] not in secilen:
            continue
        kayit = hesaplar.kullanici_bul(defter, tanim["kullanici"])
        if kayit is None:
            print(f"\n'{tanim['kullanici']}' kullanicisi yok; once {tanim['ad']} "
                  "hesabini ac (giris ekranindaki 'yeni dukkan').")
            continue
        dukkan_id = kayit["dukkan_id"]
        if dukkan_id in (1, 2):
            sys.exit(f"'{tanim['kullanici']}' dukkan {dukkan_id}'e bagli - dokunulmadi.")
        print(f"\n{tanim['ad']} -> dukkan {dukkan_id}")

        # Her dukkan kendi zarini atar: birini yeniden uretmek otekileri degistirmez.
        zar = random.Random(20260911 + sira)
        baglanti = dosyayi_sifirla(dukkan_id)
        kimlik, receteler = yapiyi_kur(baglanti, tanim)
        havayi_yaz(baglanti, gunluk_hava, zar)
        sim = Simulasyon(tanim, baglanti, kimlik, receteler, zar)
        sim.calistir(gunluk_hava)
        ozet_yaz(tanim, baglanti, sim)
        baglanti.close()


if __name__ == "__main__":
    main()
