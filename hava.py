# -*- coding: utf-8 -*-
"""Hava verisi: resmi MGM tahmini ve gecmisi tamamlayan Open-Meteo arsivi.

Program cevrimdisi de calisir. Aga cikan tek yer burasi ve bir kural var:
**ekran ciziminde asla ag beklenmez.** Sayfalar sadece `hava` tablosunu okur;
tabloyu arka planda calisan bir is parcacigi tazeler. Internet yoksa program
hicbir sey soylemeden eldeki son veriyle devam eder.

Iki kaynak birbirinin rakibi degil, tamamlayicisi:

    MGM        -> resmi, 5-6 gunluk ileri tahmin. Gecmis servisi yok.
    Open-Meteo -> gecmiste gerceklesen havayi verir. Program birkac gun
                  acilmazsa o gunlerin bosluklarini bu doldurur, boylece
                  satis tahmini modeli deliksiz bir gecmis uzerinde ogrenir.
"""

import datetime
import json
import urllib.error
import urllib.parse
import urllib.request

from veritabani import ayar, ayar_yaz, sayi

ZAMAN_ASIMI = 8          # saniye; ag yavassa program bekletilmez
GECMIS_GUN = 60          # arsivden en fazla bu kadar geriye bakilir

MGM_KOK = "https://servis.mgm.gov.tr/web"
MGM_BASLIK = {
    "Origin": "https://www.mgm.gov.tr",
    "Referer": "https://www.mgm.gov.tr/",
    "User-Agent": "Mozilla/5.0",
}

# MGM'nin hadise kisaltmalari. Listede olmayan bir kod gelirse kodun kendisi
# yazilir; program bilmedigi bir koda takilmaz.
HADISELER = {
    "A": "açık", "AB": "az bulutlu", "PB": "parçalı bulutlu", "CB": "çok bulutlu",
    "HY": "hafif yağmurlu", "Y": "yağmurlu", "KY": "kuvvetli yağmurlu",
    "SY": "sağanak yağışlı", "HSY": "hafif sağanak yağışlı",
    "KSY": "kuvvetli sağanak yağışlı", "MSY": "mevzii sağanak yağışlı",
    "GSY": "gök gürültülü sağanak yağışlı", "KGY": "kuvvetli gök gürültülü sağanak",
    "KKY": "karla karışık yağmurlu", "HKY": "hafif kar yağışlı",
    "KYY": "kar yağışlı", "YKY": "yoğun kar yağışlı", "DY": "dolu",
    "SIS": "sisli", "PUS": "puslu", "DMN": "dumanlı", "TOZ": "toz taşınımı",
    "R": "rüzgarlı", "GKR": "güneyli kuvvetli rüzgar", "KKR": "kuzeyli kuvvetli rüzgar",
    "SCK": "sıcak", "SGK": "soğuk", "HHY": "hava az bulutlu",
}
YAGMURLU_KODLAR = {
    "HY", "Y", "KY", "SY", "HSY", "KSY", "MSY", "GSY", "KGY", "KKY",
    "HKY", "KYY", "YKY", "DY",
}


def hadise_metni(kod):
    return HADISELER.get((kod or "").upper(), (kod or "").lower())


def _bugun():
    return datetime.date.today()


def _gun_yaz(tarih):
    return tarih.strftime("%Y-%m-%d")


def _simdi():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _getir(adres, basliklar=None):
    """JSON ceker. Basarisiz olursa None doner - cagiran taraf sessizce devam eder."""
    istek = urllib.request.Request(adres, headers=basliklar or {"User-Agent": "DukkanTakip"})
    try:
        with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI) as cevap:
            return json.loads(cevap.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


# ---------------------------------------------------------------- sehir secimi

def il_listesi():
    """MGM'nin 81 il kaydi: ad, tahmin istasyon numarasi, enlem, boylam."""
    ham = _getir(f"{MGM_KOK}/merkezler/iller", MGM_BASLIK)
    if not ham:
        return []
    iller = [
        {
            "ad": kayit.get("il", ""),
            "ilce": kayit.get("ilce", ""),
            "istno": kayit.get("gunlukTahminIstNo"),
            "enlem": kayit.get("enlem"),
            "boylam": kayit.get("boylam"),
        }
        for kayit in ham
        if kayit.get("gunlukTahminIstNo")
    ]
    return sorted(iller, key=lambda il: il["ad"])


def il_listesi_onbellek(baglanti, tazele=False):
    """Il listesini bir kere ceker, ayarlarda saklar.

    Ayarlar sayfasi her acildiginda aga cikmasin diye; liste zaten yilda bir
    degismez. Ag yoksa saklanan liste kullanilir.
    """
    saklanan = ayar(baglanti, "il_listesi", "")
    if saklanan and not tazele:
        try:
            return json.loads(saklanan)
        except ValueError:
            pass
    iller = il_listesi()
    if iller:
        ayar_yaz(baglanti, "il_listesi", json.dumps(iller, ensure_ascii=False))
        baglanti.commit()
    elif saklanan:
        try:
            return json.loads(saklanan)
        except ValueError:
            pass
    return iller


def sehir_kaydet(baglanti, il_adi):
    """Secilen ilin istasyon numarasini ve konumunu ayarlara yazar."""
    for il in il_listesi_onbellek(baglanti):
        if il["ad"].casefold() == (il_adi or "").casefold():
            ayar_yaz(baglanti, "sehir", il["ad"])
            ayar_yaz(baglanti, "mgm_istno", str(il["istno"]))
            ayar_yaz(baglanti, "enlem", str(il["enlem"]))
            ayar_yaz(baglanti, "boylam", str(il["boylam"]))
            baglanti.commit()
            return il
    return None


def sehir_secili_mi(baglanti):
    return bool(ayar(baglanti, "sehir", "")) and bool(ayar(baglanti, "mgm_istno", ""))


# ---------------------------------------------------------------- kayit

def yaz(baglanti, tarih, kaynak, tahmin=1, **degerler):
    """Bir gunun havasini yazar.

    Gerceklesen kayit tahminin uzerine yazilir; tersi olmaz. Boylece dun
    icin cekilen tahmin, bugun gelen gercek olcumle degistirilir ama
    gerceklesmis bir gun yeniden tahmine donmez.
    """
    mevcut = baglanti.execute("SELECT tahmin FROM hava WHERE tarih = ?", (tarih,)).fetchone()
    if mevcut is not None and not mevcut["tahmin"] and tahmin:
        return

    hadise = degerler.get("hadise", "") or ""
    yagis = degerler.get("yagis")
    yagmurlu = int(
        hadise.upper() in YAGMURLU_KODLAR or (yagis is not None and yagis >= 1.0)
    )
    baglanti.execute(
        "INSERT INTO hava (tarih, en_yuksek, en_dusuk, yagis, ruzgar, nem, hadise,"
        " yagmurlu, tahmin, kaynak, guncelleme)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(tarih) DO UPDATE SET en_yuksek = excluded.en_yuksek,"
        " en_dusuk = excluded.en_dusuk, yagis = excluded.yagis,"
        " ruzgar = excluded.ruzgar, nem = excluded.nem, hadise = excluded.hadise,"
        " yagmurlu = excluded.yagmurlu, tahmin = excluded.tahmin,"
        " kaynak = excluded.kaynak, guncelleme = excluded.guncelleme",
        (tarih, degerler.get("en_yuksek"), degerler.get("en_dusuk"), yagis,
         degerler.get("ruzgar"), degerler.get("nem"), hadise, yagmurlu,
         1 if tahmin else 0, kaynak, _simdi()),
    )


def gun(baglanti, tarih):
    return baglanti.execute("SELECT * FROM hava WHERE tarih = ?", (tarih,)).fetchone()


def gunler(baglanti, baslangic, bitis):
    return baglanti.execute(
        "SELECT * FROM hava WHERE tarih BETWEEN ? AND ? ORDER BY tarih",
        (baslangic, bitis),
    ).fetchall()


# ---------------------------------------------------------------- kaynaklar

def _mgm_tahmini(baglanti):
    """MGM gunluk tahmini: bugun dahil 6 gun. Kayit sayisini dondurur."""
    istno = ayar(baglanti, "mgm_istno", "")
    if not istno:
        return 0
    ham = _getir(f"{MGM_KOK}/tahminler/gunluk?istno={istno}", MGM_BASLIK)
    if not ham:
        return 0

    kayit = ham[0]
    adet = 0
    for sira in range(0, 6):
        tarih = kayit.get(f"tarihGun{sira}")
        en_yuksek = kayit.get(f"enYuksekGun{sira}")
        if not tarih or en_yuksek is None:
            continue
        yaz(
            baglanti, tarih[:10], "MGM", tahmin=1,
            en_yuksek=en_yuksek,
            en_dusuk=kayit.get(f"enDusukGun{sira}"),
            ruzgar=kayit.get(f"ruzgarHizGun{sira}"),
            nem=kayit.get(f"enYuksekNemGun{sira}"),
            hadise=kayit.get(f"hadiseGun{sira}") or "",
        )
        adet += 1
    return adet


def _acikhava_adresi(baglanti, kok, ek):
    enlem = sayi(ayar(baglanti, "enlem", ""), 0)
    boylam = sayi(ayar(baglanti, "boylam", ""), 0)
    if not enlem or not boylam:
        return None
    return (f"{kok}?latitude={enlem}&longitude={boylam}&{ek}"
            "&timezone=Europe%2FIstanbul")


def _openmeteo_tahmini(baglanti):
    """MGM'ye ulasilamadiginda yedek tahmin kaynagi."""
    adres = _acikhava_adresi(
        baglanti, "https://api.open-meteo.com/v1/forecast",
        "daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "windspeed_10m_max,relative_humidity_2m_max&forecast_days=7",
    )
    ham = _getir(adres) if adres else None
    if not ham or "daily" not in ham:
        return 0
    gunluk = ham["daily"]
    for sira, tarih in enumerate(gunluk["time"]):
        yaz(
            baglanti, tarih, "Open-Meteo", tahmin=1,
            en_yuksek=gunluk["temperature_2m_max"][sira],
            en_dusuk=gunluk["temperature_2m_min"][sira],
            yagis=gunluk["precipitation_sum"][sira],
            ruzgar=gunluk["windspeed_10m_max"][sira],
            nem=gunluk.get("relative_humidity_2m_max", [None] * 99)[sira],
        )
    return len(gunluk["time"])


def _gecmisi_tamamla(baglanti):
    """Gerceklesmis ama kaydi olmayan/hala 'tahmin' olan gunleri arsivden doldurur.

    Satis tahmini gecmis gunlerin GERCEK havasiyla ogrenmeli; dun icin cekilmis
    bir tahminle degil. Bu yuzden gecmis gunler arsiv verisiyle tazelenir.
    """
    bugun = _bugun()
    baslangic = bugun - datetime.timedelta(days=GECMIS_GUN)

    # Sadece satis olan ya da kaydi eksik gunler icin ugrasmaya deger.
    satis_gunleri = {
        satir["tarih"] for satir in baglanti.execute(
            "SELECT DISTINCT tarih FROM satislar WHERE tarih >= ?", (_gun_yaz(baslangic),)
        )
    }
    tamamlanmis = {
        satir["tarih"] for satir in baglanti.execute(
            "SELECT tarih FROM hava WHERE tahmin = 0 AND tarih >= ?", (_gun_yaz(baslangic),)
        )
    }
    eksikler = sorted(satis_gunleri - tamamlanmis)
    if not eksikler:
        return 0

    adres = _acikhava_adresi(
        baglanti, "https://archive-api.open-meteo.com/v1/archive",
        f"start_date={eksikler[0]}&end_date={_gun_yaz(bugun - datetime.timedelta(days=1))}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "windspeed_10m_max,relative_humidity_2m_max",
    )
    ham = _getir(adres) if adres else None
    if not ham or "daily" not in ham:
        return 0

    gunluk = ham["daily"]
    adet = 0
    for sira, tarih in enumerate(gunluk["time"]):
        en_yuksek = gunluk["temperature_2m_max"][sira]
        if en_yuksek is None:
            continue
        yaz(
            baglanti, tarih, "Open-Meteo arşiv", tahmin=0,
            en_yuksek=en_yuksek,
            en_dusuk=gunluk["temperature_2m_min"][sira],
            yagis=gunluk["precipitation_sum"][sira],
            ruzgar=gunluk["windspeed_10m_max"][sira],
            nem=gunluk.get("relative_humidity_2m_max", [None] * 999)[sira],
        )
        adet += 1
    return adet


# ---------------------------------------------------------------- disariya acilan

def guncelle(baglanti):
    """Tahmini ve gecmisi tazeler. Ag yoksa sessizce 0 doner.

    Doner: (tahmin_gun_sayisi, gecmis_gun_sayisi, kullanilan_kaynak)
    """
    if not sehir_secili_mi(baglanti):
        return 0, 0, ""

    tercih = ayar(baglanti, "hava_kaynak", "mgm+arsiv")
    ileri, kaynak = 0, ""

    if tercih in ("mgm", "mgm+arsiv"):
        ileri = _mgm_tahmini(baglanti)
        kaynak = "MGM" if ileri else ""
    if not ileri and tercih != "mgm":
        ileri = _openmeteo_tahmini(baglanti)
        kaynak = "Open-Meteo" if ileri else ""

    geri = _gecmisi_tamamla(baglanti) if tercih in ("mgm+arsiv", "openmeteo") else 0

    if ileri or geri:
        ayar_yaz(baglanti, "hava_son_kontrol", _simdi())
    baglanti.commit()
    return ileri, geri, kaynak


def ozet(baglanti, tarih):
    """Bir gunun havasini tek satirlik okunur metne cevirir."""
    satir = gun(baglanti, tarih)
    if satir is None or satir["en_yuksek"] is None:
        return ""
    metin = f"{satir['en_yuksek']:.0f}°"
    if satir["en_dusuk"] is not None:
        metin = f"{satir['en_dusuk']:.0f}° - {metin}"
    if satir["hadise"]:
        metin += f", {hadise_metni(satir['hadise'])}"
    elif satir["yagmurlu"]:
        metin += ", yağışlı"
    return metin
