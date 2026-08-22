# -*- coding: utf-8 -*-
"""Denemelik bir sezon uretir. GERCEK VERI DEGILDIR.

Ekranlar bos dururken programin ne yaptigi gorunmuyordu; bu betik veritabanina
15 Mayis - 21 Agustos 2026 arasi uydurma bir sezon yaziyor: alim, uretim, gun
sonu sayimi, kilo satisi, gider, tedarikciye odeme.

Uydurma olmayan tek sey hava: Ordu'nun o gunlerdeki gercek olcumleri
Open-Meteo arsivinden cekiliyor, gunluk talep de ona bagli hesaplaniyor -
sicakta cok, yagmurda az, hafta sonu yogun, bayramda daha yogun. Boylece
tahmin ekrani ogrenecek tutarli bir gecmis buluyor.

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
KILO_FIYATI = 1000.0

random.seed(20260822)

SUT, SEKER, SAHLEP, VANILYA = 2, 3, 4, 5
KULAH, CORNETTE, K_KAP, O_KAP, B_KAP, K_HELVA, B_HELVA = 9, 10, 11, 12, 13, 14, 15
KILO_KABI, PET_SU, KASIK, PECETE, MENDIL = 16, 17, 18, 19, 20
SADE_URUN = 56

# Satis karisimi: (kalem_id, servis payi, bir serviste kac gram dondurma)
KARISIM = [
    (KULAH,    0.40, 60),
    (CORNETTE, 0.10, 120),
    (K_KAP,    0.15, 120),
    (O_KAP,    0.13, 200),
    (B_KAP,    0.06, 250),
    (K_HELVA,  0.06, 200),
    (B_HELVA,  0.04, 250),
]

# Hangi cesit ne kadar gidiyor. Listede olmayan cesit 1,5 agirlikla girer.
AGIRLIKLAR = {
    "Sade Dondurma": 26, "Çikolatalı Dondurma": 9, "Çilekli Dondurma": 7,
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

# kalem -> (esik, alinacak miktar, tedarikci, pesin olasiligi)
AMBALAJ_KURALI = {
    KULAH:     (900, 450 * 6, AMBALAJCI, 0.3),
    CORNETTE:  (360, 180 * 4, AMBALAJCI, 0.3),
    K_KAP:     (300, 250 * 4, AMBALAJCI, 0.3),
    O_KAP:     (250, 200 * 4, AMBALAJCI, 0.3),
    B_KAP:     (150, 150 * 3, AMBALAJCI, 0.3),
    K_HELVA:   (120, 100 * 3, AMBALAJCI, 0.3),
    B_HELVA:   (100, 100 * 2, AMBALAJCI, 0.3),
    KILO_KABI: (60,  50 * 4,  AMBALAJCI, 0.3),
    KASIK:     (1000, 1000 * 5, AMBALAJCI, 0.3),
    PECETE:    (5,   20,      AMBALAJCI, 0.8),
    MENDIL:    (500, 1000 * 3, AMBALAJCI, 0.3),
    PET_SU:    (48,  24 * 15, "Su Bayii", 0.9),
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
MEVSIM = [(0, 0.42), (12, 0.55), (17, 0.72), (30, 0.80), (47, 1.00),
          (60, 1.12), (78, 1.22), (92, 1.10), (98, 1.02)]
HAFTA = [0.88, 0.86, 0.90, 0.95, 1.12, 1.32, 1.26]   # Pzt..Paz


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
    carpan = 200.0 * mevsim_carpani(gun_no) * HAFTA[tarih.weekday()]
    carpan *= max(0.55, min(1.65, 1 + 0.062 * (sicaklik - 24.0)))
    if yagis >= 4:
        carpan *= 0.58
    elif yagis >= 1:
        carpan *= 0.72
    elif yagis >= 0.3:
        carpan *= 0.90
    carpan *= ozel_carpan(baglanti, tarih.isoformat())
    carpan *= random.gauss(1.0, 0.09)
    return max(20, int(round(carpan)))


# ---------------------------------------------------------------- alim
def alim_yap(baglanti, tarih, kalem_id, miktar, tedarikci, pesin_olasiligi, gun_no):
    """Alis fiyati sezon basindaki fiyattan yavas yavas artar (yigilmadan)."""
    taban = TABAN_FIYAT[kalem_id]
    fiyat = taban * (1 + 0.0016 * gun_no) * random.uniform(0.985, 1.02)
    tutar = round(miktar * fiyat, 2)
    odeme = "pesin" if random.random() < pesin_olasiligi else "veresiye"
    hesap.alim_ekle(baglanti, tarih, kalem_id, miktar, tutar, odeme, tedarikci)


def alimlari_kontrol_et(baglanti, tarih, gun_no, cesitler, gunluk_kg):
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

    for kalem_id, (esik, miktar, tedarikci, pesin) in AMBALAJ_KURALI.items():
        if stok.get(kalem_id, 0) < esik:
            alim_yap(baglanti, tarih, kalem_id, miktar, tedarikci, pesin, gun_no)


# ---------------------------------------------------------------- uretim
def uretim_yap(baglanti, tarih, cesitler, gunluk_kg):
    """Stogu iki gunluk satisin altina dusen cesit icin kazan cirpilir."""
    stok = hesap.stoklar(baglanti)
    for cesit in cesitler:
        gunluk = max(0.25, gunluk_kg * cesit["pay"])
        eldeki = stok.get(cesit["id"], 0.0)
        if eldeki >= gunluk * 2:
            continue
        gereken = gunluk * 4.5 - eldeki
        if cesit["id"] == SADE_URUN:
            # 122 kg'lik kazan bu dukkana buyuk geliyor: ceyrek kazan cirpiliyor.
            kazan = max(0.25, round(gereken / cesit["verim"] * 4) / 4)
        else:
            kazan = max(1, min(2, math.ceil(gereken / cesit["verim"])))
        hesap.uretim_ekle(baglanti, tarih, cesit["recete"], kazan)


# ---------------------------------------------------------------- gun sonu
def servisleri_dagit(adet):
    """Gunun servislerini kap/kulah cesitlerine paylastirir.

    Paylar her gun biraz oynar ama toplam sabit kalsin diye once agirliklar
    normallenir; yuvarlamadan artan tek tek en cok satana eklenir.
    """
    agirliklar = {kalem_id: pay * random.uniform(0.85, 1.15)
                  for kalem_id, pay, _gram in KARISIM}
    toplam = sum(agirliklar.values())
    dagilim = {kalem_id: int(adet * agirlik / toplam)
               for kalem_id, agirlik in agirliklar.items()}
    artan = adet - sum(dagilim.values())
    sirali = sorted(agirliklar, key=lambda k: -agirliklar[k])
    for sira in range(artan):
        dagilim[sirali[sira % len(sirali)]] += 1
    return dagilim


def kilo_satisi(baglanti, tarih, cesitler, kilo_kg):
    """Kilo ile satis: programin 'Tek tek gir' ekranindan girilmis gibi."""
    stok = hesap.stoklar(baglanti)
    kalan = kilo_kg
    satilan = 0.0
    for cesit in sorted(cesitler, key=lambda c: -c["pay"] * random.uniform(0.5, 1.5)):
        if kalan < 0.2:
            break
        istek = kilo_kg * cesit["pay"] * random.uniform(0.4, 2.0)
        miktar = round(min(istek, max(0.0, stok.get(cesit["id"], 0.0) - 0.5), kalan), 2)
        if miktar < 0.2:
            continue
        hesap.satis_ekle(baglanti, tarih, cesit["id"], miktar)
        kalan -= miktar
        satilan += miktar
    return satilan


def gun_sonu(baglanti, tarih, servis_adedi, kilo_adedi):
    stok = hesap.stoklar(baglanti)
    dagilim = servisleri_dagit(servis_adedi)
    dagilim[PET_SU] = int(round(servis_adedi * 0.11 * random.uniform(0.7, 1.3)))
    dagilim[KILO_KABI] = kilo_adedi          # her kilo satisinda bir kap gider

    kalanlar, gercek = {}, {}
    for kalem_id, satilan in dagilim.items():
        eldeki = stok.get(kalem_id, 0.0)
        satilan = int(min(satilan, max(0, math.floor(eldeki))))
        gercek[kalem_id] = satilan
        kalan = eldeki - satilan
        koli_adet = hesap.kalem(baglanti, kalem_id)["koli_adet"] or 0
        if koli_adet > 1:
            koli = math.floor(kalan / koli_adet)
            kalanlar[kalem_id] = (koli, round(kalan - koli * koli_adet, 3))
        else:
            kalanlar[kalem_id] = (0, round(kalan, 3))

    bitenler = []
    if stok.get(KASIK, 0) > 1000 and random.random() < servis_adedi * 1.15 / 1000:
        bitenler.append(KASIK)
    if stok.get(PECETE, 0) > 1 and random.random() < 0.75:
        bitenler.append(PECETE)
    if stok.get(MENDIL, 0) > 1000 and random.random() < servis_adedi * 0.55 / 1000:
        bitenler.append(MENDIL)

    hesap.sayim_kaydet(baglanti, tarih, kalanlar, None, bitenler)
    return gercek


def kepceyi_dus(baglanti, tarih, cesitler, gercek):
    """Kap ve kulahlara cikan dondurmayi cesitlerin stogundan duser.

    Program bugun kulahin icindeki dondurmayi, aromalara gecmeden onceki eski
    'Dondurma' kaleminden dusuyor; aromali cesitlerin stogu kendiliginden
    azalmiyor. Aksam kazanlarda kalani yazmis gibi burada elle dusuyoruz.
    """
    toplam_kg = sum(gercek.get(k, 0) * gram for k, _pay, gram in KARISIM) / 1000.0
    if toplam_kg <= 0:
        return
    stok = hesap.stoklar(baglanti)
    kalan = toplam_kg
    for cesit in cesitler:
        istek = toplam_kg * cesit["pay"] * random.uniform(0.85, 1.15)
        miktar = round(min(istek, max(0.0, stok.get(cesit["id"], 0.0) - 0.2), kalan), 3)
        if miktar < 0.05:
            continue
        kalan -= miktar
        baglanti.execute(
            "INSERT INTO stok_hareketleri (tarih, kalem_id, miktar, sebep, kaynak_tur)"
            " VALUES (?, ?, ?, ?, 'elle_sayim')",
            (tarih, cesit["id"], -miktar, "Kap ve külahlara çıkan"),
        )
    baglanti.commit()


# ---------------------------------------------------------------- gider / odeme / banka
def giderleri_yaz(baglanti, tarih, gun_no):
    gun, tarih_metni = tarih.day, tarih.isoformat()
    zam = 1 + 0.0016 * gun_no
    if gun == 1 and tarih.month > 5:
        hesap.gider_ekle(baglanti, tarih_metni, "Dükkân kirası",
                         30000 + 1000 * (tarih.month - 6))
    if gun == 5 and tarih.month > 5:
        hesap.gider_ekle(baglanti, tarih_metni, "Personel maaşı (2 kişi)",
                         round(64000 * zam, -2))
    if gun == 20:
        hesap.gider_ekle(baglanti, tarih_metni, "Elektrik faturası",
                         round(random.uniform(9000, 17000), -2))
        hesap.gider_ekle(baglanti, tarih_metni, "Su faturası",
                         round(random.uniform(900, 1600), -1))
    if gun == 10:
        hesap.gider_ekle(baglanti, tarih_metni, "İnternet ve telefon", 890)
    if gun == 25:
        hesap.gider_ekle(baglanti, tarih_metni, "Muhasebeci", 4500)
    if tarih.weekday() == 0:
        hesap.gider_ekle(baglanti, tarih_metni, "Temizlik malzemesi",
                         round(random.uniform(700, 1800), -1))
    if random.random() < 0.10:
        hesap.gider_ekle(baglanti, tarih_metni, "Nakliye / yakıt",
                         round(random.uniform(600, 2200), -1))
    if random.random() < 0.04:
        hesap.gider_ekle(baglanti, tarih_metni, "Tamir - bakım",
                         round(random.uniform(1500, 9000), -2))


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
def hazirlik(baglanti, cesitler):
    for kalem_id in list(AMBALAJ_KURALI) + [SUT, SEKER, SAHLEP, VANILYA]:
        TABAN_FIYAT[kalem_id] = hesap.kalem(baglanti, kalem_id)["birim_fiyat"]
    for cesit in cesitler:
        if cesit["aroma"]:
            TABAN_FIYAT[cesit["aroma"]] = hesap.kalem(baglanti, cesit["aroma"])["birim_fiyat"]

    baglanti.execute(
        "UPDATE kalemler SET fiyat = ? WHERE uretilir = 1 AND satilir = 1 AND fiyat = 0",
        (KILO_FIYATI,),
    )
    baglanti.execute(
        "INSERT INTO kasa_hareketleri (tarih, tutar, aciklama, kaynak_tur)"
        " VALUES (?, ?, ?, 'devir')",
        (BASLANGIC.isoformat(), 40000.0, "Sezon açılış kasası"),
    )
    baglanti.commit()


def yedek_al():
    """Uzerine yazmadan once veritabanini kopyalar."""
    damga = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    yedek = os.path.join(os.path.dirname(veritabani.DB_YOLU),
                         f"yedek-{damga}-simulasyon-oncesi.db")
    shutil.copy2(veritabani.DB_YOLU, yedek)
    return yedek


def main():
    if "--onayla" not in sys.argv:
        print(__doc__)
        print("Bu betik veritabanina UYDURMA kayitlar yazar. Gercek satislarin")
        print("varsa once onlari kaybetmeyecegine emin ol.")
        print("Yine de calistirmak icin:  python simulasyon.py --onayla")
        return
    print("yedek alindi:", yedek_al())

    baglanti = veritabani.baglan()
    gunluk_hava = havayi_yaz(baglanti, havayi_getir())
    cesitler = cesitleri_kur(baglanti)
    hazirlik(baglanti, cesitler)
    print("çeşit sayısı:", len(cesitler))

    tarih, gun_no = BASLANGIC, 0
    while tarih <= BITIS:
        anahtar = tarih.isoformat()
        sicaklik, yagis = gunluk_hava.get(anahtar, (24.0, 0.0))
        servis = gunun_talebi(baglanti, tarih, gun_no, sicaklik, yagis)
        kilo_kg = round(servis * 0.042 * random.uniform(0.7, 1.35), 1)
        gunluk_kg = sum(pay * gram for _k, pay, gram in KARISIM) * servis / 1000.0 + kilo_kg

        alimlari_kontrol_et(baglanti, anahtar, gun_no, cesitler, gunluk_kg)
        uretim_yap(baglanti, anahtar, cesitler, gunluk_kg)
        satilan_kg = kilo_satisi(baglanti, anahtar, cesitler, kilo_kg)
        gercek = gun_sonu(baglanti, anahtar, servis, max(1, int(round(satilan_kg))))
        kepceyi_dus(baglanti, anahtar, cesitler, gercek)
        giderleri_yaz(baglanti, tarih, gun_no)
        odemeleri_yap(baglanti, tarih)
        bankaya_yatir(baglanti, tarih)

        tarih += datetime.timedelta(days=1)
        gun_no += 1

    baglanti.commit()
    ciro = baglanti.execute("SELECT COALESCE(SUM(tutar),0) FROM satislar").fetchone()[0]
    print("kasa:", round(hesap.kasa(baglanti)), "borç:", round(hesap.borc(baglanti)))
    print("toplam ciro:", round(ciro))


if __name__ == "__main__":
    main()
