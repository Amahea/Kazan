# -*- coding: utf-8 -*-
"""Denemelik bir sezon uretir. GUNLER UYDURMADIR, OLCULER DUKKANIN KENDISINDEN.

15 Mayis - 21 Agustos 2026 arasi bir sezon yazar: alim, uretim, gun sonu
sayimi, gider, tedarikciye odeme.

Dukkanin calisma sekli (2026 Agustos'ta sahibinden alindi):
  - Satilan sey dondurmanin kendisi. Bir top 60 gram, 60 TL; yani 1.000 TL/kg.
    Kilo ile de ayni fiyattan gidiyor.
  - Kulah, kap ve helva kagidi AMBALAJ. Musteriden ayrica para alinmiyor,
    bir kulaha 2 top da konabiliyor 3 top da. Bu yuzden ciro ambalaj adedinden
    degil, giden kilodan hesaplaniyor.
  - Gun sonunda rafta kalan ambalaj ve her kazanda kalan kilo yaziliyor;
    ne satildigini program aradaki farktan buluyor.
  - Normal bir gunde 30 kg, yogun bir gunde 60 kg dondurma gidiyor.
    Ambalaj birbirine su oranda: 2200 kulah, 500 kap, 50 kagit helva.
  - Hafta sonu hafta icinin 2 kati (yogun gun budur). Yagmurlu gunde satis
    ucte bir duser. Sezon basi ve sonu yaz ortasindan cok farkli degil.
  - Kadro calisanlar tablosunda: usta + iki tezgahtar, biri sezonluk.
    Maas gideri o tablodan uretilir, betikte sabit degildir.

Uydurma olmayan bir sey daha var: hava. Ordu'nun o gunlerdeki gercek olcumleri
Open-Meteo arsivinden cekiliyor, gunluk talep de ona bagli hesaplaniyor.
Boylece tahmin ekrani ogrenecek tutarli bir gecmis buluyor.

Butun kayitlar programin kendi fonksiyonlariyla (hesap.py) yazilir; kasa,
borc, stok ve maliyet tutarliligi programin kendi kurallarina gore olusur.

Calistirmak icin:  python simulasyon.py --onayla
Onaydan once veritabaninin yedegi alinir; dosya adi ekrana yazilir.
"""
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
import veritabani

BASLANGIC = datetime.date(2026, 5, 15)
BITIS = datetime.date(2026, 8, 21)
ENLEM, BOYLAM = 40.9838, 37.8858
KILO_FIYATI = 1000.0     # 1 top = 60 gram = 60 TL, yani kilosu 1.000 TL
TOP_GRAM = 60.0

random.seed(20260822)

SUT, SEKER, SAHLEP, VANILYA = 2, 3, 4, 5
KULAH, CORNETTE, K_KAP, O_KAP, B_KAP, K_HELVA, B_HELVA = 9, 10, 11, 12, 13, 14, 15
KILO_KABI, PET_SU, KASIK, PECETE, MENDIL = 16, 17, 18, 19, 20
SADE_URUN = 56

# Bir kulaha ortalama kac top konuyor. Dukkanda 2 toplu da satiliyor 3 toplu
# da; ortalama buradan degistirilir, gunluk kulah adedi kendiliginden ayarlanir.
KULAH_ORTALAMA_TOP = 2.0

# Ambalajin icine giren gram. Kulahinki top sayisina bagli, kaplarin ve helva
# kagidinin olcusu sabit (ve fiyatlari da bu grama esit: 200 gram = 200 TL).
AMBALAJ_GRAM = {
    KULAH:   TOP_GRAM * KULAH_ORTALAMA_TOP,
    K_KAP:   120,
    O_KAP:   200,
    B_KAP:   250,
    K_HELVA: 200,
    B_HELVA: 250,
}

# Gunluk ambalajin birbirine orani: 2200 kulah, 500 kap, 50 helva.
# Kap ve helvanin kendi icindeki boy dagilimi dukkanin eski satis karisimindan.
KULAH_ORANI = 2200
KAP_ORANI = {K_KAP: 500 * 0.44, O_KAP: 500 * 0.38, B_KAP: 500 * 0.18}
HELVA_ORANI = {K_HELVA: 50 * 0.60, B_HELVA: 50 * 0.40}

# Gunluk dondurmanin bu kadari kap/kulaha girmeden kiloyla eve gidiyor.
KILO_PAYI = 0.08

# Yaz ortasinda sicak, normal bir hafta ici gunu dukkandan cikan dondurma.
# Butun gunluk hesap bunun uzerine kurulu. Yogun gunler (hafta sonu) asagidaki
# HAFTA carpaniyla bunun iki kati olur: normal gun 30 kg, yogun gun 60 kg.
GUNLUK_KG = 30.0

# Gunluk satilan dondurmanin bu kadari sade (dukkan sahibi soyledi). Sadenin
# agirligi asagidaki listeden degil bu paydan hesaplaniyor; cesit eklenip
# cikarilsa bile sade payi yerinde kalir.
SADE_PAYI = 0.40

# Geri kalan cesitler birbirine gore ne kadar gidiyor. Listede olmayan cesit
# 1,5 agirlikla girer. Sade burada yok: payi SADE_PAYI'den geliyor.
AGIRLIKLAR = {
    "Çikolatalı Dondurma": 9, "Çilekli Dondurma": 7,
    "Limonlu Dondurma": 5, "Vişneli Dondurma": 4, "Kavunlu Dondurma": 4,
    "Karadutlu Dondurma": 4, "Fındıklı Dondurma": 4, "Oreolu Dondurma": 4,
    "Kakaolu Dondurma": 3, "Muzlu Dondurma": 3, "Şeftalili Dondurma": 3,
    "Fındık Ezmeli Dondurma": 3, "Karamelli Dondurma": 3, "Lotuslu Dondurma": 3,
    "Nutellalı Dondurma": 3, "Damla Sakızlı Dondurma": 3, "Şirinler Dondurma": 2.5,
    "Böğürtlenli Dondurma": 2, "Yeşil Elmalı Dondurma": 2, "Mangolu Dondurma": 2,
    "Vanilyalı Dondurma": 2, "İtalyan Karamelli Dondurma": 2,
    "Parça Çikolatalı Dondurma": 2, "Bisküvili Dondurma": 2,
}

TEDARIKCILER = {
    SUT: "Ordu Süt", SEKER: "Karadeniz Gıda", SAHLEP: "Karadeniz Gıda",
    VANILYA: "Karadeniz Gıda", PET_SU: "Su Bayii",
}
AMBALAJCI = "Ambalaj Dünyası"
AROMACI = "Aroma Ticaret"

# Ambalaj alimi sabit esiklerle degil gunluk ihtiyaca gore yurur: gunun
# tuketimi bilindigi icin "kac gunluk kaldi" sorusunun cevabi hesaplanabiliyor.
# kalem -> (kac gunluk kalinca siparis verilir, kac gunluk alinir, tedarikci,
#           pesin olasiligi)
AMBALAJ_KURALI = {
    KULAH:     (4, 12, AMBALAJCI, 0.3),
    K_KAP:     (4, 12, AMBALAJCI, 0.3),
    O_KAP:     (4, 12, AMBALAJCI, 0.3),
    B_KAP:     (4, 12, AMBALAJCI, 0.3),
    K_HELVA:   (5, 15, AMBALAJCI, 0.3),
    B_HELVA:   (5, 15, AMBALAJCI, 0.3),
    KILO_KABI: (5, 15, AMBALAJCI, 0.3),
    KASIK:     (4, 12, AMBALAJCI, 0.3),
    PECETE:    (4, 12, AMBALAJCI, 0.8),
    MENDIL:    (5, 15, AMBALAJCI, 0.3),
    PET_SU:    (3, 10, "Su Bayii", 0.9),
}

TABAN_FIYAT = {}     # kalem_id -> sezon basindaki alis fiyati


# ---------------------------------------------------------------- cesit listesi
def cesitleri_kur(baglanti):
    """Uretilen her dondurma cesidi icin recetesini ve aromasini bulur."""
    liste = []
    for urun in baglanti.execute(
        "SELECT id, ad FROM kalemler WHERE uretilir = 1 AND satilir = 1 AND aktif = 1"
        " ORDER BY id"
    ).fetchall():
        recete = hesap.ana_recete(baglanti, urun["id"])
        if recete is None or recete["verim"] <= 0:
            continue
        aroma = baglanti.execute(
            "SELECT r.kalem_id FROM recete_satirlari r JOIN kalemler k ON k.id = r.kalem_id"
            " WHERE r.recete_id = ? AND k.ad LIKE 'Aroma - %'", (recete["id"],)
        ).fetchone()
        liste.append({
            "id": urun["id"], "ad": urun["ad"], "recete": recete["id"],
            "verim": recete["verim"], "aroma": aroma["kalem_id"] if aroma else None,
            "agirlik": AGIRLIKLAR.get(urun["ad"], 1.5),
        })
    # Sadenin agirligi, geri kalanlarin toplamindan SADE_PAYI'yi tutturacak
    # sekilde geriye dogru hesaplaniyor.
    digerleri = sum(c["agirlik"] for c in liste if c["id"] != SADE_URUN)
    for c in liste:
        if c["id"] == SADE_URUN and digerleri > 0:
            c["agirlik"] = digerleri * SADE_PAYI / (1 - SADE_PAYI)

    toplam = sum(c["agirlik"] for c in liste)
    for c in liste:
        c["pay"] = c["agirlik"] / toplam
    return liste


# ---------------------------------------------------------------- hava
def havayi_getir():
    adres = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={ENLEM}&longitude={BOYLAM}"
        f"&start_date={BASLANGIC}&end_date={BITIS}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "windspeed_10m_max,relative_humidity_2m_max&timezone=Europe%2FIstanbul"
    )
    with urllib.request.urlopen(adres, timeout=30) as cevap:
        return json.load(cevap)["daily"]


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


def havayi_yaz(baglanti, gunluk):
    kayit = {}
    for sira, gun in enumerate(gunluk["time"]):
        en_yuksek = gunluk["temperature_2m_max"][sira]
        if en_yuksek is None:
            continue
        yagis = gunluk["precipitation_sum"][sira] or 0.0
        hava.yaz(
            baglanti, gun, "Open-Meteo arşiv", tahmin=0,
            en_yuksek=en_yuksek, en_dusuk=gunluk["temperature_2m_min"][sira],
            yagis=yagis, ruzgar=gunluk["windspeed_10m_max"][sira],
            nem=gunluk["relative_humidity_2m_max"][sira],
            hadise=hadise_kodu(yagis, random.random()),
        )
        kayit[gun] = (en_yuksek, yagis)
    baglanti.commit()
    return kayit


# ---------------------------------------------------------------- talep
# Dukkan sahibi "sezon basi ve sonu yaz ortasindan cok farkli degil" dedi;
# bu yuzden mevsim egrisi neredeyse duz, sadece iki ucta hafif bir inis var.
MEVSIM = [(0, 0.96), (15, 1.00), (90, 1.00), (98, 0.96)]
# Hafta ici gunler esit, cumartesi-pazar 2 kati: 30 kg'lik normal gunun
# karsiligi 60 kg'lik yogun gun.
HAFTA = [1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0]          # Pzt..Paz


def mevsim_carpani(gun_no):
    for sira in range(len(MEVSIM) - 1):
        x1, y1 = MEVSIM[sira]
        x2, y2 = MEVSIM[sira + 1]
        if x1 <= gun_no <= x2:
            return y1 + (y2 - y1) * (gun_no - x1) / (x2 - x1)
    return MEVSIM[-1][1]


def ozel_carpan(baglanti, tarih):
    carpan = 1.0
    for satir in baglanti.execute(
        "SELECT etiket FROM ozel_gunler WHERE aktif = 1 AND ? BETWEEN baslangic AND bitis",
        (tarih,),
    ):
        if satir["etiket"] == "Kurban Bayramı":
            carpan *= 1.38
        elif satir["etiket"] == "Yarım Gün":
            carpan *= 0.72
        elif satir["etiket"] == "Resmi Tatil":
            carpan *= 1.08
    return carpan


def gunun_talebi(baglanti, tarih, gun_no, sicaklik, yagis):
    """O gun dukkandan cikacak toplam dondurma, kilo olarak.

    Cikis noktasi dukkanin kendi olcusu: yaz ortasinda sicak, normal bir hafta
    ici gunu 30 kg, yogun bir gun (hafta sonu) 60 kg. Geri kalani bunun
    uzerine binen carpanlar.
    """
    kg = GUNLUK_KG * mevsim_carpani(gun_no) * HAFTA[tarih.weekday()]
    # Sicaklik etkisi bilerek yumusak: sezon basi ile yaz ortasi arasinda buyuk
    # fark olmadigi soylendi, sert bir sicaklik egrisi bunu bozardi.
    kg *= max(0.88, min(1.12, 1 + 0.014 * (sicaklik - 27.0)))
    # "Yagmurlu gunde ucte bir duser" - saganakta biraz daha fazla.
    if yagis >= 4:
        kg *= 0.60
    elif yagis >= 1:
        kg *= 0.67
    elif yagis >= 0.3:
        kg *= 0.85
    kg *= ozel_carpan(baglanti, tarih.isoformat())
    kg *= random.gauss(1.0, 0.09)
    return max(5.0, round(kg, 1))


def ambalaj_adetleri(servis_kg):
    """Kap/kulaha giren kilodan gunun ambalaj adetlerini cikarir.

    Adetler birbirine sabit oranda (2200 kulah, 500 kap, 50 helva) ama toplami
    o gun giden kiloya oturmali; olcek bu yuzden gramdan hesaplaniyor.
    """
    oranlar = {KULAH: float(KULAH_ORANI)}
    oranlar.update(KAP_ORANI)
    oranlar.update(HELVA_ORANI)
    birim_gram = sum(pay * AMBALAJ_GRAM[k] for k, pay in oranlar.items())
    olcek = servis_kg * 1000.0 / birim_gram if birim_gram else 0.0

    adetler = {}
    for kalem_id, pay in oranlar.items():
        adet = pay * olcek * random.uniform(0.92, 1.08)
        adetler[kalem_id] = max(1, int(round(adet)))
    return adetler


# ---------------------------------------------------------------- alim
def alim_yap(baglanti, tarih, kalem_id, miktar, tedarikci, pesin_olasiligi, gun_no):
    """Alis fiyati sezon basindaki fiyattan yavas yavas artar (yigilmadan)."""
    taban = TABAN_FIYAT[kalem_id]
    fiyat = taban * (1 + 0.0016 * gun_no) * random.uniform(0.985, 1.02)
    tutar = round(miktar * fiyat, 2)
    odeme = "pesin" if random.random() < pesin_olasiligi else "veresiye"
    hesap.alim_ekle(baglanti, tarih, kalem_id, miktar, tutar, odeme, tedarikci)


def alimlari_kontrol_et(baglanti, tarih, gun_no, cesitler, gunluk_kg,
                        gunluk_ihtiyac):
    stok = hesap.stoklar(baglanti)

    gunluk_sut = gunluk_kg * 0.85           # kazanlarin ortalama sut orani
    if stok.get(SUT, 0) < gunluk_sut * 2.5:
        alim_yap(baglanti, tarih, SUT, math.ceil(gunluk_sut * 6 / 20) * 20,
                 TEDARIKCILER[SUT], 0.25, gun_no)
    if stok.get(SEKER, 0) < 30:
        alim_yap(baglanti, tarih, SEKER, 100, TEDARIKCILER[SEKER], 0.5, gun_no)
    if stok.get(SAHLEP, 0) < 2.5:
        alim_yap(baglanti, tarih, SAHLEP, 5, TEDARIKCILER[SAHLEP], 0.4, gun_no)
    if stok.get(VANILYA, 0) < 0.08:
        alim_yap(baglanti, tarih, VANILYA, 0.5, TEDARIKCILER[VANILYA], 0.6, gun_no)

    for cesit in cesitler:
        if cesit["aroma"] is None:
            continue
        # 9 kg kazana 2 kg aroma giriyor: gunluk aroma ihtiyaci
        gunluk_aroma = gunluk_kg * cesit["pay"] * 2 / 9.0
        esik = max(5.0, gunluk_aroma * 8)
        if stok.get(cesit["aroma"], 0) < esik:
            miktar = max(6.0, math.ceil(gunluk_aroma * 25 / 2) * 2)
            alim_yap(baglanti, tarih, cesit["aroma"], miktar, AROMACI, 0.15, gun_no)

    for kalem_id, (esik_gun, alim_gun, tedarikci, pesin) in AMBALAJ_KURALI.items():
        gunluk = gunluk_ihtiyac.get(kalem_id, 0.0)
        if gunluk <= 0 or stok.get(kalem_id, 0) >= gunluk * esik_gun:
            continue
        koli = hesap.kalem(baglanti, kalem_id)["koli_adet"] or 1
        # Tedarikciden koli koli aliniyor; ihtiyac kac koli ediyorsa o kadar.
        miktar = max(koli, math.ceil(gunluk * alim_gun / koli) * koli)
        alim_yap(baglanti, tarih, kalem_id, miktar, tedarikci, pesin, gun_no)


# ---------------------------------------------------------------- uretim
def uretim_yap(baglanti, tarih, cesitler, gunluk_kg):
    """Stogu iki gunluk satisin altina dusen cesit icin kazan cirpilir."""
    stok = hesap.stoklar(baglanti)
    for cesit in cesitler:
        gunluk = max(0.25, gunluk_kg * cesit["pay"])
        eldeki = stok.get(cesit["id"], 0.0)
        if eldeki >= gunluk * 1.5:
            continue
        gereken = gunluk * 3.0 - eldeki
        # Kazan tam doldurulmak zorunda degil; ceyrek kazan da cirpiliyor.
        kazan = max(0.25, round(gereken / cesit["verim"] * 4) / 4)
        hesap.uretim_ekle(baglanti, tarih, cesit["recete"], kazan)


# ---------------------------------------------------------------- gun sonu
def _koli_bol(baglanti, kalem_id, kalan):
    """Rafta kalani, sayim ekranindaki gibi koli + tek adet olarak ayirir."""
    koli_adet = hesap.kalem(baglanti, kalem_id)["koli_adet"] or 0
    if koli_adet > 1:
        koli = math.floor(kalan / koli_adet)
        return koli, round(kalan - koli * koli_adet, 3)
    return 0, round(kalan, 3)


def gun_sonu(baglanti, tarih, cesitler, gunluk_kg, ambalaj, pet_su):
    """Gun sonu sayimi: rafta kalan ambalaj ve her kazanda kalan kilo.

    Ne satildigini program aradaki farktan buluyor. Dondurma satilan kalem
    oldugu icin tuketimi dogrudan ciroya doner (1.000 TL/kg); kulah ve kaplar
    ambalaj oldugu icin tuketimleri 'Sarf' yazilip maliyetleri gunun
    satislarina dagitilir. Musteriden ambalaj icin ayrica para alinmiyor.
    """
    stok = hesap.stoklar(baglanti)
    kalanlar, giden = {}, {}

    for kalem_id, adet in list(ambalaj.items()) + [(PET_SU, pet_su)]:
        eldeki = stok.get(kalem_id, 0.0)
        harcanan = int(min(adet, max(0, math.floor(eldeki))))
        giden[kalem_id] = harcanan
        kalanlar[kalem_id] = _koli_bol(baglanti, kalem_id, eldeki - harcanan)

    # Kazanlardan cikan kilo: cesitlerin gunluk payina gore, elde ne varsa.
    kalan_hedef = gunluk_kg
    for cesit in sorted(cesitler, key=lambda c: -c["pay"]):
        eldeki = stok.get(cesit["id"], 0.0)
        istek = gunluk_kg * cesit["pay"] * random.uniform(0.85, 1.15)
        # Kazan hic dibine kadar bitmiyor; bir miktar hep kaliyor.
        cikan = round(min(istek, max(0.0, eldeki - 0.15), max(0.0, kalan_hedef)), 3)
        kalan_hedef -= cikan
        giden[cesit["id"]] = cikan
        kalanlar[cesit["id"]] = _koli_bol(baglanti, cesit["id"], eldeki - cikan)

    # Kiloyla giden dondurmanin kabi. Ortalama bir buçuk kiloluk paketler.
    kilo_kg = gunluk_kg * KILO_PAYI
    kilo_kabi = int(round(kilo_kg / 1.5))
    eldeki = stok.get(KILO_KABI, 0.0)
    harcanan = int(min(kilo_kabi, max(0, math.floor(eldeki))))
    giden[KILO_KABI] = harcanan
    kalanlar[KILO_KABI] = _koli_bol(baglanti, KILO_KABI, eldeki - harcanan)

    # Kasik, pecete, mendil tek tek sayilmiyor; kolisi bitince isaretleniyor.
    bitenler = []
    kap_adedi = sum(adet for k, adet in ambalaj.items() if k != KULAH)
    if stok.get(KASIK, 0) > 1000 and random.random() < kap_adedi * 1.4 / 1000:
        bitenler.append(KASIK)
    if stok.get(PECETE, 0) > 1 and random.random() < 0.75:
        bitenler.append(PECETE)
    if stok.get(MENDIL, 0) > 1000 and random.random() < kap_adedi * 0.9 / 1000:
        bitenler.append(MENDIL)

    hesap.sayim_kaydet(baglanti, tarih, kalanlar, None, bitenler)
    return giden


# ---------------------------------------------------------------- calisanlar
# Maaslar artik burada sabit degil: calisanlar tablosuna yaziliyor, gider de
# oradan uretiliyor. Boylece "kac kisi calisiyor, kimin maasi ne" sorusunun
# cevabi programin kendi ekraninda duruyor ve degistirilebiliyor.
#
# Rakamlar 2026 asgari ucretine oturuyor: net 28.075 TL, isverene maliyeti
# ~40.200 TL (yani net ucretin ustune kabaca 12.100 TL SGK + vergi biniyor).
CALISANLAR = [
    # (ad, gorev, telefon, net maas, SGK+vergi, ise giris, ayrilis, not)
    ("Metin Aydın", "Dondurma ustası", "0532 418 77 21",
     45000, 15300, "2026-05-15", "", "Kazanları o çekiyor, sabah 6'da geliyor"),
    ("Serkan Duran", "Tezgâhtar", "0537 260 14 08",
     28100, 12150, "2026-05-15", "", ""),
    ("Elif Korkmaz", "Tezgâhtar", "0505 733 96 42",
     28100, 12150, "2026-06-01", "", "Sezonluk — okul açılınca ayrılacak"),
]


def calisanlari_kur(baglanti):
    """Sezonun calisan kadrosunu yazar. Zaten varsa dokunmaz."""
    if baglanti.execute("SELECT COUNT(*) FROM calisanlar").fetchone()[0]:
        return
    for ad, gorev, telefon, maas, sgk, giris, ayrilis, notlar in CALISANLAR:
        yeni = hesap.calisan_ekle(baglanti, ad, gorev, telefon, maas, sgk,
                                  giris, notlar)
        if ayrilis:
            hesap.calisan_kaydet(baglanti, yeni, ayrilis=ayrilis)


# ---------------------------------------------------------------- gider / odeme / banka
def _ayin_cirosu(baglanti, tarih):
    """Icinde bulunulan ayin o gune kadarki cirosu - POS komisyonu buna bagli."""
    return baglanti.execute(
        "SELECT COALESCE(SUM(tutar), 0) FROM satislar WHERE substr(tarih, 1, 7) = ?",
        (tarih.strftime("%Y-%m"),),
    ).fetchone()[0]


def giderleri_yaz(baglanti, tarih, gun_no, aylik_ciro):
    """Bir gunun sabit ve degisken giderleri.

    Maas disindaki kalemler dukkanin buyuklugune gore secildi: 40 m2 dolayinda
    bir dondurmaci, uc derin dondurucu ve iki dolapla yazin ciddi elektrik
    yakiyor. POS komisyonu ciroya bagli oldugu icin ayni gun hesaplaniyor.
    """
    gun, tarih_metni = tarih.day, tarih.isoformat()
    if gun == 1 and tarih.month > 5:
        hesap.gider_ekle(baglanti, tarih_metni, "Dükkân kirası",
                         32000 + 1500 * (tarih.month - 6))
    # Maas: kadro calisanlar tablosundan okunur, herkes icin ayri satir duser.
    if gun == 5 and tarih.month > 5:
        hesap.maas_yaz(baglanti, tarih_metni)
    if gun == 20:
        # Dondurucular yazin gece gunduz calisiyor; agustos faturasi en agiri.
        hesap.gider_ekle(baglanti, tarih_metni, "Elektrik faturası",
                         round(random.uniform(17000, 27000), -2))
        hesap.gider_ekle(baglanti, tarih_metni, "Su faturası",
                         round(random.uniform(1100, 2000), -1))
    if gun == 10:
        hesap.gider_ekle(baglanti, tarih_metni, "İnternet ve telefon", 1150)
    if gun == 25:
        hesap.gider_ekle(baglanti, tarih_metni, "Muhasebeci", 6500)
        # Cironun kabaca ucte ikisi kartla; komisyon o tutarin %1,8'i kadar.
        komisyon = aylik_ciro * 0.66 * 0.018
        if komisyon > 0:
            hesap.gider_ekle(baglanti, tarih_metni, "Kredi kartı / POS komisyonu",
                             round(komisyon, -1))
    # Gecici vergi ve stopaj ucer aylik donemlerde odeniyor.
    if gun == 17 and tarih.month in (5, 8):
        hesap.gider_ekle(baglanti, tarih_metni, "Vergi ve resmî ödemeler",
                         round(random.uniform(48000, 72000), -2))
    if tarih.weekday() == 0:
        hesap.gider_ekle(baglanti, tarih_metni, "Temizlik malzemesi",
                         round(random.uniform(900, 2100), -1))
    if random.random() < 0.10:
        hesap.gider_ekle(baglanti, tarih_metni, "Nakliye / yakıt",
                         round(random.uniform(700, 2500), -1))
    if random.random() < 0.05:
        # Dondurucu ariza, kazan bakimi, tamirat.
        hesap.gider_ekle(baglanti, tarih_metni, "Tamir - bakım",
                         round(random.uniform(2000, 12000), -2))


def odemeleri_yap(baglanti, tarih):
    if tarih.weekday() != 4:            # Cuma gunu tedarikci hesabi gorulur
        return
    for satir in hesap.borc_dagilimi(baglanti):
        if satir["tutar"] < 15000:
            continue
        tutar = round(satir["tutar"] * random.uniform(0.55, 0.92), -2)
        if tutar > 0:
            hesap.odeme_ekle(baglanti, tarih.isoformat(), satir["tedarikci"], tutar)


def bankaya_yatir(baglanti, tarih):
    """Kasada biriken nakit bankaya gider; kar hesabini etkilemez."""
    if tarih.weekday() != 6:
        return
    nakit = hesap.kasa(baglanti)
    if nakit < 90000:
        return
    tutar = round(nakit - 60000, -3)
    baglanti.execute(
        "INSERT INTO kasa_hareketleri (tarih, tutar, aciklama, kaynak_tur)"
        " VALUES (?, ?, ?, 'banka')",
        (tarih.isoformat(), -tutar, "Bankaya yatırıldı"),
    )
    baglanti.commit()


# ---------------------------------------------------------------- ana akis
# Sezon yazilmadan once bosaltilan tablolar. Kalemler, receteler, ozel gunler
# ve ayarlar duruyor: onlar dukkanin kurulumu, gunluk hareket degil.
TEMIZLENECEK = ("satislar", "sayim_satirlari", "sayimlar", "uretimler",
                "alimlar", "giderler", "odemeler", "stok_hareketleri",
                "kasa_hareketleri", "borc_hareketleri", "calisanlar")


def eskiyi_temizle(baglanti):
    """Onceki sezonu siler; betik ikinci kez calisinca ustune yigilmasin."""
    for tablo in TEMIZLENECEK:
        baglanti.execute(f"DELETE FROM {tablo}")
    baglanti.commit()


def yapiyi_kur(baglanti):
    """Kalemleri dukkanin gercek satis seklime gore ayarlar.

    Satilan sey dondurma; kulah, kap ve helva kagidi ambalaj. Ambalaj
    'dagit' isaretli oldugu icin gun sonunda harcanan miktarin tutari o gunun
    satislarina paylastiriliyor - yani bir kulahin parasi musteriden ayrica
    alinmasa da maliyeti kara yansiyor.

    Ayrica kap ve kulahlarin eski receteleri siliniyor: icindeki dondurmayi
    aromalara gecmeden onceki olu 'Dondurma' kaleminden dusuyorlardi. Artik
    dondurma tuketimi kazanlarin gun sonu sayimindan olculuyor, receteyle
    tahmin edilmiyor.
    """
    ambalajlar = list(AMBALAJ_GRAM) + [KILO_KABI]
    for kalem_id in ambalajlar:
        baglanti.execute(
            "UPDATE kalemler SET satilir = 0, dagit = 1, sayim_tarzi = 'say'"
            " WHERE id = ?", (kalem_id,))
        for recete in baglanti.execute(
                "SELECT id FROM receteler WHERE urun_id = ?", (kalem_id,)).fetchall():
            baglanti.execute("DELETE FROM recete_satirlari WHERE recete_id = ?",
                             (recete["id"],))
            baglanti.execute("DELETE FROM receteler WHERE id = ?", (recete["id"],))

    # Her kazan gun sonunda ayri sayiliyor; cesitler sayim ekranina cikmali.
    baglanti.execute(
        "UPDATE kalemler SET sayim_tarzi = 'say', fiyat = ?"
        " WHERE uretilir = 1 AND satilir = 1 AND aktif = 1", (KILO_FIYATI,))

    # Aromalara gecerken geride kalan eski 'Dondurma' kalemi artik hicbir
    # receteye bagli degil; goze gorunmesin diye kapali kaliyor.
    baglanti.execute("UPDATE kalemler SET aktif = 0, satilir = 0 WHERE ad = 'Dondurma'")
    baglanti.commit()


def hazirlik(baglanti, cesitler):
    for kalem_id in list(AMBALAJ_KURALI) + [SUT, SEKER, SAHLEP, VANILYA]:
        TABAN_FIYAT[kalem_id] = hesap.kalem(baglanti, kalem_id)["birim_fiyat"]
    for cesit in cesitler:
        if cesit["aroma"]:
            TABAN_FIYAT[cesit["aroma"]] = hesap.kalem(baglanti, cesit["aroma"])["birim_fiyat"]

    baglanti.execute(
        "INSERT INTO kasa_hareketleri (tarih, tutar, aciklama, kaynak_tur)"
        " VALUES (?, ?, ?, 'devir')",
        (BASLANGIC.isoformat(), 250000.0, "Sezon açılış kasası"),
    )
    baglanti.commit()


DUKKAN = 1   # betik hangi dukkanin dosyasina yazsin


def yedek_al():
    """Uzerine yazmadan once veritabanini kopyalar."""
    damga = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    kaynak = veritabani.db_yolu(DUKKAN)
    yedek = os.path.join(veritabani.VERI_KLASORU,
                         f"yedek-{damga}-simulasyon-oncesi.db")
    shutil.copy2(kaynak, yedek)
    return yedek


def main():
    if "--onayla" not in sys.argv:
        print(__doc__)
        print("Bu betik veritabanina UYDURMA kayitlar yazar. Gercek satislarin")
        print("varsa once onlari kaybetmeyecegine emin ol.")
        print("Yine de calistirmak icin:  python simulasyon.py --onayla")
        return
    print("yedek alindi:", yedek_al())

    baglanti = veritabani.baglan(DUKKAN)
    eskiyi_temizle(baglanti)
    yapiyi_kur(baglanti)
    calisanlari_kur(baglanti)
    gunluk_hava = havayi_yaz(baglanti, havayi_getir())
    cesitler = cesitleri_kur(baglanti)
    hazirlik(baglanti, cesitler)
    print("çeşit sayısı:", len(cesitler))

    tarih, gun_no = BASLANGIC, 0
    while tarih <= BITIS:
        anahtar = tarih.isoformat()
        sicaklik, yagis = gunluk_hava.get(anahtar, (24.0, 0.0))
        gunluk_kg = gunun_talebi(baglanti, tarih, gun_no, sicaklik, yagis)
        # Kilonun bir kismi kap/kulaha girmeden dogrudan eve gidiyor.
        ambalaj = ambalaj_adetleri(gunluk_kg * (1 - KILO_PAYI))
        pet_su = int(round(sum(ambalaj.values()) * 0.09 * random.uniform(0.7, 1.3)))

        # Ambalaj siparisi gunluk ihtiyaca gore veriliyor.
        ihtiyac = dict(ambalaj)
        ihtiyac[PET_SU] = pet_su
        ihtiyac[KILO_KABI] = max(1, gunluk_kg * KILO_PAYI / 1.5)
        ihtiyac[KASIK] = sum(a for k, a in ambalaj.items() if k != KULAH) * 1.4
        ihtiyac[PECETE] = 0.75
        ihtiyac[MENDIL] = sum(a for k, a in ambalaj.items() if k != KULAH) * 0.9

        alimlari_kontrol_et(baglanti, anahtar, gun_no, cesitler, gunluk_kg, ihtiyac)
        uretim_yap(baglanti, anahtar, cesitler, gunluk_kg)
        gun_sonu(baglanti, anahtar, cesitler, gunluk_kg, ambalaj, pet_su)
        giderleri_yaz(baglanti, tarih, gun_no, _ayin_cirosu(baglanti, tarih))
        odemeleri_yap(baglanti, tarih)
        bankaya_yatir(baglanti, tarih)

        tarih += datetime.timedelta(days=1)
        gun_no += 1

    baglanti.commit()
    ciro = baglanti.execute("SELECT COALESCE(SUM(tutar),0) FROM satislar").fetchone()[0]
    kg = baglanti.execute(
        "SELECT COALESCE(SUM(s.miktar),0) FROM satislar s JOIN kalemler k ON k.id=s.kalem_id"
        " WHERE k.birim = 'kg'").fetchone()[0]
    gun = (BITIS - BASLANGIC).days + 1
    print(f"kasa: {hesap.kasa(baglanti):,.0f}  borç: {hesap.borc(baglanti):,.0f}")
    print(f"toplam ciro: {ciro:,.0f} TL   dondurma: {kg:,.0f} kg"
          f"   günlük ortalama: {kg/gun:,.1f} kg / {ciro/gun:,.0f} TL")


if __name__ == "__main__":
    main()
