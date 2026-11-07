# -*- coding: utf-8 -*-
"""Denemelik bir sezon uretir. GUNLER UYDURMADIR, OLCULER DUKKANIN KENDISINDEN.

1 Ocak - 10 Eylul 2026 arasi TAM bir sezon yazar: kis + yaz. Alim, uretim, gun
sonu sayimi, gider, tedarikciye odeme.

Dukkanin calisma sekli (2026 Agustos'ta sahibinden alindi):
  - Satilan sey dondurmanin kendisi. Bir top 60 gram, 60 TL; yani 1.000 TL/kg.
    Kilo ile de ayni fiyattan gidiyor.
  - Kulah, kap ve helva kagidi AMBALAJ. Musteriden ayrica para alinmiyor,
    bir kulaha 2 top da konabiliyor 3 top da. Bu yuzden ciro ambalaj adedinden
    degil, giden kilodan hesaplaniyor.
  - Gun sonunda rafta kalan ambalaj ve her kazanda kalan kilo yaziliyor;
    ne satildigini program aradaki farktan buluyor.
  - Yaz ortasinda normal bir gunde 30 kg, yogun bir gunde 60 kg dondurma gidiyor.
    Ambalaj birbirine su oranda: 2200 kulah, 500 kap, 50 kagit helva.
  - Hafta sonu hafta icinin 2 kati (yogun gun budur). Yagmurlu gunde satis
    ucte bir duser.

Mevsim - bu betigin can alici yeri: talep havaya baglidir, takvime degil.
  - Dondurma, gunluk EN YUKSEK SICAKLIGA gore iner cikar: yaz ortasi (27C)
    tam hacim, kis (8C) bunun ucte biri kadar. Boylece ocaktan agustosa dogal
    bir yukselis, sonbahara dogru inis cikar - tahmin modelinin mevsimselligi
    ogrenecegi gercek bir egri.
  - Kis menusu: soguk gunlerde yalnizca KIS_CESITLERI (6 cesit) cirpilir,
    gerisi o gun hic uretilmez/satilmaz (menuler tablosundaki esikle uyumlu).
  - Sahlep (bardak, 150 TL) kis icecegi: soguk arttikca satisi artar, yazin
    neredeyse sifir. Bardak bardak, dogrudan (elle) satilir.
  - 1 Temmuz'da fiyatlara ~%15 zam var; ondan onceki satislar daha ucuz fiyatla
    yazilir. Nominal ciro zamla sicrar ama gercek (sabit fiyatli) talep duz
    kalir - tahmin ekranindaki 'gercek talep' bunu ayikladigini gosterir.
  - Kadro calisanlar tablosunda: kisin usta + 1 tezgahtar, yazin + sezonluk.
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

BASLANGIC = datetime.date(2026, 1, 1)
BITIS = datetime.date(2026, 9, 10)
ENLEM, BOYLAM = 40.9838, 37.8858
KILO_FIYATI = 1000.0     # 1 top = 60 gram = 60 TL, yani kilosu 1.000 TL (GUNCEL/final fiyat)
TOP_GRAM = 60.0

# 1 Temmuz zammi: ondan onceki gunler fiyatlarin ONCE_FIYAT_ORANI kati ile
# yazilir (~%15 daha ucuz). Nominal ciro 1 Temmuz'da sicrar; gercek talep duz.
ZAM_TARIHI = datetime.date(2026, 7, 1)
ONCE_FIYAT_ORANI = 0.87

random.seed(20260822)

SUT, SEKER, SAHLEP, VANILYA = 2, 3, 4, 5
KULAH, CORNETTE, K_KAP, O_KAP, B_KAP, K_HELVA, B_HELVA = 9, 10, 11, 12, 13, 14, 15
KILO_KABI, PET_SU, KASIK, PECETE, MENDIL = 16, 17, 18, 19, 20
SADE_URUN = 56

# Kis icecegi sahlep (bardak) ve recetesinin malzemeleri.
SAHLEP_BARDAK = 96
TARCIN, KARTON_BARDAK, HAZIR_SAHLEP = 93, 94, 95
SAHLEP_BARDAK_FIYAT = 150.0          # GUNCEL fiyat; zamdan once ONCE_ORANI ile
HAZIR_SAHLEP_FIYAT = 360.0           # litre basi alis (uydurma, gecici)

# Kis menusu: soguk gunlerde yalnizca bu 6 cesit cirpilir, sahlep acilir.
KIS_CESITLERI = {
    "Sade Dondurma", "Çikolatalı Dondurma", "Çilekli Dondurma",
    "Fındıklı Dondurma", "Karamelli Dondurma", "Vişneli Dondurma",
}

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
# Hafta ici gunler esit, cumartesi-pazar 2 kati: 30 kg'lik normal gunun
# karsiligi 60 kg'lik yogun gun.
HAFTA = [1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0]          # Pzt..Paz


def _kirp(deger, alt, ust):
    return max(alt, min(ust, deger))


def dondurma_mevsim(sicaklik):
    """Dondurma talebinin mevsim carpani, gunluk EN YUKSEK SICAKLIGA bagli.

    Takvime degil havaya bakar: yaz ortasi (~27C) tam hacim (1.0), kis (~8C)
    bunun ucte biri (0.33). Arada dogrusal; cok sicak/soguk uclarda yumusak
    sinir. Ordu'nun gercek sicaklik serisiyle carpilinca ocaktan agustosa
    dogal bir yukselis cikar - 'orta' yogunlukta, kisin da canli bir tezgah.
    """
    return _kirp(0.33 + (1.0 - 0.33) * (sicaklik - 8.0) / (27.0 - 8.0), 0.30, 1.10)


def menu_rejimi(gunluk_hava, baslangic, bitis):
    """Her gun kis menusu mu, SUREKLI bir rejim olarak. Takvim gununden degil,
    10 gunluk kayan ortalama sicakliktan karar verir; histerezisle tek bir
    bahar gecisi ve tek bir sonbahar gecisi olur (menuler tablosundaki esikler:
    yaza >= 20'de gecilir, kisa <= 17'de donulur).

    Neden gunluk degil: dukkan tek bir ilik kis gununde butun menuyu acmaz.
    Talebin HACMI gune gore oynar (dondurma_mevsim), ama hangi cesitlerin
    acildigi mevsimlik bir karardir - menu feature'inin yaptigi da bu.
    """
    pencere, kis, seri, sonuc = 10, True, [], {}
    tarih = baslangic
    son_sic = 12.0
    while tarih <= bitis:
        anahtar = tarih.isoformat()
        son_sic = gunluk_hava.get(anahtar, (son_sic, 0.0))[0]
        seri.append(son_sic)
        ort = sum(seri[-pencere:]) / len(seri[-pencere:])
        if kis and ort >= 20.0:
            kis = False
        elif not kis and ort <= 17.0:
            kis = True
        sonuc[anahtar] = kis
        tarih += datetime.timedelta(days=1)
    return sonuc


def sahlep_talebi(sicaklik, weekday, yagis):
    """O gun satilan sahlep bardagi. Soguk arttikca artar, 16C ustu ~0.

    En soguk gunde (~4C) ortalama ~55 bardak; hafta sonu biraz daha, yagmurlu
    soguk gunde sicak icecek biraz daha cok gider. Yazin sahlep satilmaz.
    """
    taban = _kirp((16.0 - sicaklik) / (16.0 - 4.0), 0.0, 1.0)
    if taban <= 0:
        return 0
    bardak = 55.0 * taban
    bardak *= 1.0 + 0.5 * (HAFTA[weekday] - 1.0)     # hafta sonu ~1.5 kat
    if yagis >= 1:
        bardak *= 1.15
    bardak *= random.gauss(1.0, 0.14)
    return max(0, int(round(bardak)))


def gunun_cesitleri(cesitler, kis):
    """O gunun aktif cesitleri ve (o gune gore) normalize edilmis paylari.

    Kis gunlerinde yalnizca KIS_CESITLERI cirpilir; paylar bu altkume icinde
    yeniden normalize edilir ki toplam yine 1 olsun. Yaz gunlerinde tam liste.
    """
    if kis:
        alt = [c for c in cesitler if c["ad"] in KIS_CESITLERI]
    else:
        alt = list(cesitler)
    toplam = sum(c["pay"] for c in alt) or 1.0
    return [dict(c, pay=c["pay"] / toplam) for c in alt]


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
    ici gunu 30 kg, yogun bir gun (hafta sonu) 60 kg. Mevsim carpani artik
    takvimden degil o gunun sicakligindan geliyor (dondurma_mevsim); kisin
    hacim dogal olarak ucte bire kadar iner.
    """
    kg = GUNLUK_KG * dondurma_mevsim(sicaklik) * HAFTA[tarih.weekday()]
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
    # Gunluk ~%0,11 artis: ocaktan eylule kabaca %28 (2026 enflasyonuna yakin).
    fiyat = taban * (1 + 0.0011 * gun_no) * random.uniform(0.985, 1.02)
    tutar = round(miktar * fiyat, 2)
    odeme = "pesin" if random.random() < pesin_olasiligi else "veresiye"
    hesap.alim_ekle(baglanti, tarih, kalem_id, miktar, tutar, odeme, tedarikci)


def alimlari_kontrol_et(baglanti, tarih, gun_no, cesitler, gunluk_kg,
                        gunluk_ihtiyac, sahlep_bardak=0):
    stok = hesap.stoklar(baglanti)

    gunluk_sut = gunluk_kg * 0.85           # kazanlarin ortalama sut orani
    if stok.get(SUT, 0) < gunluk_sut * 2.5:
        alim_yap(baglanti, tarih, SUT, math.ceil(gunluk_sut * 6 / 20) * 20,
                 TEDARIKCILER[SUT], 0.25, gun_no)

    # Kis icecegi sahlep bardaginin malzemeleri: satiliyorsa ~15 gunluk tut.
    if sahlep_bardak > 0:
        for kalem_id, gunluk, tedarikci, koli_bazli in (
            (HAZIR_SAHLEP, sahlep_bardak * 0.2, "Karadeniz Gıda", False),
            (KARTON_BARDAK, sahlep_bardak * 1.0, AMBALAJCI, True),
            (TARCIN, sahlep_bardak * 0.0005, "Karadeniz Gıda", False),
        ):
            if gunluk <= 0 or stok.get(kalem_id, 0) >= gunluk * 5:
                continue
            if koli_bazli:
                koli = hesap.kalem(baglanti, kalem_id)["koli_adet"] or 1
                miktar = max(koli, math.ceil(gunluk * 15 / koli) * koli)
            else:
                miktar = max(0.5, round(gunluk * 15, 2))
            alim_yap(baglanti, tarih, kalem_id, miktar, tedarikci, 0.4, gun_no)
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


def gun_sonu(baglanti, tarih, cesitler, gunluk_kg, ambalaj, pet_su, sahlep_bardak=0):
    """Gun sonu sayimi: rafta kalan ambalaj ve her kazanda kalan kilo.

    Ne satildigini program aradaki farktan buluyor. Dondurma satilan kalem
    oldugu icin tuketimi dogrudan ciroya doner (1.000 TL/kg); kulah ve kaplar
    ambalaj oldugu icin tuketimleri 'Sarf' yazilip maliyetleri gunun
    satislarina dagitilir. Musteriden ambalaj icin ayrica para alinmiyor.
    Sahlep bardagi (varsa) takip disi, dogrudan (elle) satis olarak islenir;
    recetesi (hazir sahlep + karton bardak + tarcin) satista stoktan duser.
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

    elle = {SAHLEP_BARDAK: sahlep_bardak} if sahlep_bardak > 0 else None
    hesap.sayim_kaydet(baglanti, tarih, kalanlar, elle, bitenler)
    if sahlep_bardak > 0:
        giden[SAHLEP_BARDAK] = sahlep_bardak
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
     45000, 15300, "2026-01-01", "", "Kazanları o çekiyor, sabah 6'da geliyor"),
    ("Serkan Duran", "Tezgâhtar", "0537 260 14 08",
     28100, 12150, "2026-01-01", "", "Yıl boyu; kışın sahlep tezgâhına da bakıyor"),
    ("Elif Korkmaz", "Tezgâhtar", "0505 733 96 42",
     28100, 12150, "2026-06-01", "", "Sezonluk — yaz için alındı"),
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
    if gun == 1:
        # Kira tum yil boyunca; yil icinde hafif artar.
        hesap.gider_ekle(baglanti, tarih_metni, "Dükkân kirası",
                         30000 + 1200 * (tarih.month - 1))
    # Maas: kadro calisanlar tablosundan okunur, herkes icin ayri satir duser.
    if gun == 5:
        hesap.maas_yaz(baglanti, tarih_metni)
    if gun == 20:
        # Dondurucular yazin gece gunduz calisiyor; agustos faturasi en agiri.
        # Kisin yuk dusuyor ama dolaplar yine de calisiyor.
        if tarih.month in (6, 7, 8):
            elektrik = random.uniform(17000, 27000)
        elif tarih.month in (5, 9):
            elektrik = random.uniform(13000, 20000)
        else:
            elektrik = random.uniform(8000, 15000)
        hesap.gider_ekle(baglanti, tarih_metni, "Elektrik faturası",
                         round(elektrik, -2))
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
    if gun == 17 and tarih.month in (2, 5, 8):
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
    """Kasa ile banka arasinda iki yonlu transfer; kasayi makul bir bantta tutar.

    Kasa CEIL'i asarsa fazlasi bankaya yatirilir; FLOOR'un altina duserse (maas
    gunu + ilkbahar aroma tazelemesi gibi buyuk cikis gunlerinde) bankadaki
    birikimden geri cekilir. Boylece kasa ne gereksiz siser ne de eksiye duser.
    Iki hesap arasi transfer oldugu icin kar/zarar hesabini etkilemez.
    """
    FLOOR, CEIL, HEDEF = 250000.0, 600000.0, 400000.0
    nakit = hesap.kasa(baglanti)
    # Bankadaki birikim: 'banka' hareketlerinin toplaminin tersi (yatirma eksi,
    # cekme arti yazilir; dolayisiyla birikim = -toplam).
    banka = -(baglanti.execute(
        "SELECT COALESCE(SUM(tutar), 0) FROM kasa_hareketleri WHERE kaynak_tur = 'banka'"
    ).fetchone()[0])

    if nakit > CEIL:
        delta, aciklama = -round(nakit - HEDEF, -3), "Bankaya yatırıldı"
    elif nakit < FLOOR and banka > 0:
        delta, aciklama = round(min(banka, HEDEF - nakit), -3), "Bankadan çekildi"
    else:
        return
    if abs(delta) < 1:
        return
    baglanti.execute(
        "INSERT INTO kasa_hareketleri (tarih, tutar, aciklama, kaynak_tur)"
        " VALUES (?, ?, ?, 'banka')",
        (tarih.isoformat(), delta, aciklama),
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


def taban_fiyatlari_sabitle(baglanti):
    """Alis fiyatlarinin KANONIK tabanini saklar ve her kosuda geri yukler.

    Neden gerekli: alim_ekle her alimda kalemin birim_fiyat'ini son alis fiyatina
    gunceller. Betik de enflasyon tabanini (TABAN_FIYAT) bu birim_fiyat'tan okur.
    Dolayisiyla betik ikinci kez calisinca taban, bir onceki sezonun sismis
    fiyatindan baslar ve her kosuda ustune biner - COGS katlanarak sisirdi.
    Cozum: ilk (temiz) kosuda birim_fiyatlar bir kez saklanir; sonraki her kosu
    once bu tabandan geri yukler. Boylece betik kac kez calisirsa calissin ayni
    sonucu verir (idempotent).
    """
    baglanti.execute(
        "CREATE TABLE IF NOT EXISTS sim_taban_fiyat ("
        " kalem_id INTEGER PRIMARY KEY, fiyat REAL)")
    if baglanti.execute("SELECT COUNT(*) FROM sim_taban_fiyat").fetchone()[0]:
        baglanti.execute(
            "UPDATE kalemler SET birim_fiyat = ("
            " SELECT fiyat FROM sim_taban_fiyat WHERE kalem_id = kalemler.id)"
            " WHERE id IN (SELECT kalem_id FROM sim_taban_fiyat)")
    else:
        baglanti.execute(
            "INSERT INTO sim_taban_fiyat (kalem_id, fiyat)"
            " SELECT id, birim_fiyat FROM kalemler WHERE birim_fiyat > 0")
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
    # Fiyat 1 Temmuz zammindan ONCE: guncel fiyatin ONCE_FIYAT_ORANI kati.
    baglanti.execute(
        "UPDATE kalemler SET sayim_tarzi = 'say', fiyat = ?"
        " WHERE uretilir = 1 AND satilir = 1 AND aktif = 1",
        (round(KILO_FIYATI * ONCE_FIYAT_ORANI, 2),))

    # Kis icecegi sahlep (bardak) ve recetesinin malzemeleri acilir. Hazir
    # sahlep alinabilir yapilir ve alis fiyati verilir; bardak+tarcin zaten
    # alinabilir. Bardak dogrudan (elle) satilir, stogu tutulmaz.
    baglanti.execute(
        "UPDATE kalemler SET aktif = 1 WHERE id IN (?, ?, ?, ?)",
        (TARCIN, KARTON_BARDAK, HAZIR_SAHLEP, SAHLEP_BARDAK))
    baglanti.execute(
        "UPDATE kalemler SET alinir = 1, birim_fiyat = ? WHERE id = ?",
        (HAZIR_SAHLEP_FIYAT, HAZIR_SAHLEP))
    baglanti.execute(
        "UPDATE kalemler SET fiyat = ? WHERE id = ?",
        (round(SAHLEP_BARDAK_FIYAT * ONCE_FIYAT_ORANI, 2), SAHLEP_BARDAK))

    # Aromalara gecerken geride kalan eski 'Dondurma' kalemi artik hicbir
    # receteye bagli degil; goze gorunmesin diye kapali kaliyor.
    baglanti.execute("UPDATE kalemler SET aktif = 0, satilir = 0 WHERE ad = 'Dondurma'")
    baglanti.commit()


def zammi_uygula(baglanti):
    """1 Temmuz zammi: satis fiyatlari guncel (final) seviyeye cekilir.

    Zamdan onceki satislar daha ucuz fiyatla yazildi; bu gunden sonra guncel
    fiyat gecerli. urun_paylari/gecmis_gunler GUNCEL fiyatla 'gercek talep'
    hesapladigi icin bu zam nominal ciroyu sicratir ama talebi degil - tahmin
    ekranindaki deflasyon tam da bunu ayikliyor."""
    baglanti.execute(
        "UPDATE kalemler SET fiyat = ?"
        " WHERE uretilir = 1 AND satilir = 1 AND aktif = 1", (KILO_FIYATI,))
    baglanti.execute("UPDATE kalemler SET fiyat = ? WHERE id = ?",
                     (SAHLEP_BARDAK_FIYAT, SAHLEP_BARDAK))
    baglanti.commit()


def hazirlik(baglanti, cesitler):
    for kalem_id in (list(AMBALAJ_KURALI)
                     + [SUT, SEKER, SAHLEP, VANILYA,
                        HAZIR_SAHLEP, KARTON_BARDAK, TARCIN]):
        TABAN_FIYAT[kalem_id] = hesap.kalem(baglanti, kalem_id)["birim_fiyat"]
    for cesit in cesitler:
        if cesit["aroma"]:
            TABAN_FIYAT[cesit["aroma"]] = hesap.kalem(baglanti, cesit["aroma"])["birim_fiyat"]

    # Tum yilin isletme sermayesi: kis sakin gecerken bile kira+maas doner ve
    # ilkbaharda butun cesitlerin aromasi birden tazelenir; acilis kasasi buna
    # gore (yaz-only surumdeki 250k degil) daha genis.
    baglanti.execute(
        "INSERT INTO kasa_hareketleri (tarih, tutar, aciklama, kaynak_tur)"
        " VALUES (?, ?, ?, 'devir')",
        (BASLANGIC.isoformat(), 450000.0, "Sezon açılış kasası"),
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
    taban_fiyatlari_sabitle(baglanti)   # re-run'larda fiyat sismesini onler
    yapiyi_kur(baglanti)
    calisanlari_kur(baglanti)
    gunluk_hava = havayi_yaz(baglanti, havayi_getir())
    cesitler = cesitleri_kur(baglanti)
    hazirlik(baglanti, cesitler)
    print("çeşit sayısı:", len(cesitler))

    rejim_kis = menu_rejimi(gunluk_hava, BASLANGIC, BITIS)

    tarih, gun_no, zam_yapildi = BASLANGIC, 0, False
    while tarih <= BITIS:
        anahtar = tarih.isoformat()
        # 1 Temmuz zammi: o gun gelince guncel fiyatlara gecilir (bir kez).
        if not zam_yapildi and tarih >= ZAM_TARIHI:
            zammi_uygula(baglanti)
            zam_yapildi = True
        sicaklik, yagis = gunluk_hava.get(anahtar, (15.0, 0.0))

        kis = rejim_kis.get(anahtar, False)               # surekli menu rejimi
        bugun_cesit = gunun_cesitleri(cesitler, kis)      # o gunun aktif cesitleri
        gunluk_kg = gunun_talebi(baglanti, tarih, gun_no, sicaklik, yagis)
        # Sahlep yalnizca kis menusu acikken satilir (malzeme alimi da ona gore).
        sahlep = sahlep_talebi(sicaklik, tarih.weekday(), yagis) if kis else 0
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

        alimlari_kontrol_et(baglanti, anahtar, gun_no, bugun_cesit, gunluk_kg,
                            ihtiyac, sahlep)
        uretim_yap(baglanti, anahtar, bugun_cesit, gunluk_kg)
        gun_sonu(baglanti, anahtar, bugun_cesit, gunluk_kg, ambalaj, pet_su, sahlep)
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
