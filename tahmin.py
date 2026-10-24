# -*- coding: utf-8 -*-
"""Havaya, haftanin gunune ve ozel gunlere bakarak ileriye donuk satis tahmini.

Model bilerek basit tutuldu, cunku elde az gun var ve karmasik bir model az
veriyle guvenle degil sadece kendinden emin sekilde yanilir. Dort kademe:

    1. Sicaklik  -> gunun cirosuna en cok etki eden sey. Gecmis gunlerin
                    (en yuksek sicaklik, ciro) ciftlerine bir dogru uydurulur.
    2. Yagmur    -> sicaklik modelinin tahmin ettiginden ne kadar sapildigi
                    olculur; yagmurlu gunlerin ortalama sapmasi katsayi olur.
    3. Haftanin gunu -> "hafta sonu mu" ya da her gun icin ayri katsayi.
    4. Ozel gunler -> resmi tatil, dini bayram, findik toplama donemi.
                    Her etiket icin tek katsayi; kalan sapmadan hesaplanir.

Her kademe bir oncekinin **sapmasindan** hesaplandigi icin ayni etki iki kez
sayilmaz: cumartesiye denk gelen bir bayramda hem cumartesi hem bayram
katsayisi carpilir ama ikisi de kendi payini bir kere alir.

**Hangi bilesenin alinacagina model kendisi karar verir.** Eskiden "sicaklik icin
14 gun, gun icin 28 gun" gibi elle konmus esikler vardi; artik her bilesen
bir-disarida capraz dogrulamayla (LOOCV) sinaniyor ve yalnizca gormedigi-veri
hatasini dusuruyorsa aliniyor (bkz. _ozellik_sec, _ham_kur, _loocv). Az veriyle
bir bilesen ezberden oteye gecemezse CV onu reddeder -- "az veriyle durust tahmin"
felsefesinin dogrudan uygulamasi.

Program **tahmin uretmeyi reddedebilir.** Yeterli gun yoksa "su kadar gun daha
lazim" der. Uydurma bir rakam vermektense susmak dogrusu.
"""

import datetime
import math

import hava
import hesap
import takvim

EN_AZ_GUN = 10           # bunun altinda hic tahmin yok (durustluk esigi)
EN_AZ_ETIKET_GUN = 3     # bir ozel gun etiketi aday olabilmek icin en az bu kadar gun
EN_DUSUK_CARPAN = 0.2    # gun + etiket carpanlarinin ortak tabani
EN_YUKSEK_CARPAN = 5.0   # ve tavani (asagidaki _gun_carpani'na bak)

# NOT: Eskiden burada "sicaklik icin 14 gun, haftanin gunu icin 28 gun" gibi elle
# konmus esikler vardi. Artik her bilesen bir-disarida capraz dogrulamayla (LOOCV)
# sinaniyor ve yalnizca gormedigi-veri hatasini dusuruyorsa aliniyor; karari veri
# veriyor (bkz. _ozellik_sec). EN_AZ_GUN yalnizca "hic tahmin verme" esigi olarak
# kaldi; EN_AZ_ETIKET_GUN ise bir etiketin aday sayilmasi icin gereken en az gun.

GUN_ADLARI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def _tarihe_cevir(metin):
    return datetime.datetime.strptime(metin, "%Y-%m-%d").date()


def _simdi():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


YAGMUR_TAU_MM = 3.0   # islaklik olcegi: 1-exp(-mm/tau); 1 mm bile belirgin agirlik


def _yagmur_degeri(mm, ihtimal=None, yagmurlu=0):
    """Surekli 'islaklik' 0..1. Ikili bayrak yerine kullanilir.

    Oncelik gercek yagis miktari (mm): hem gecmis gunlerde hem Open-Meteo
    tahmininde dolu ve gun gune degisiyor. Yoksa yagis ihtimali (%); o da yoksa
    son care eski ikili bayrak. Nedeni: MGM Ordu'da neredeyse her yaz gunune
    sagnak kodu yazdigi icin ikili 'yagmurlu' hep 1 cikiyor ve model icin hicbir
    ayirt edici bilgi tasimiyordu; mm surekli degisken olarak gercek etkiyi verir.

    mm -> 1-exp(-mm/tau): icbukey, doygun bir egri. Hafif yagis (1-2 mm) bile
    belirgin islaklik verir (eski ikilinin yakaladigi 'yagmur var mi' bilgisi
    korunur), siddetli yagista 1'e doyar. Boylece hem 'yagdi mi' hem 'ne kadar'
    tek surekli degiskende.
    """
    if mm is not None:
        return 1.0 - math.exp(-max(mm, 0.0) / YAGMUR_TAU_MM)
    if ihtimal is not None:
        return min(max(ihtimal, 0.0) / 100.0, 1.0)
    return 1.0 if yagmurlu else 0.0


def _kirp(deger, alt, ust):
    return max(alt, min(ust, deger))


# ---------------------------------------------------------------- gazeteci cocuk
# Uretim miktarini tahminin ORTALAMASINA degil DAGILIMINA gore secmek icin
# gereken sabitler ve araclar. Ayrinti: uretim_onerisi ve fire_kiyasi.
NV_Z80 = 1.2816          # %80 tahmin araliginin yari-genisligi ~ 1.28 standart sapma
NV_KRITIK_ALT = 0.05     # kritik oran tabani (z patlamasin)
NV_KRITIK_UST = 0.95     # ve tavani
NV_PENCERE = 14          # hareketli ortalama penceresi (gun)
NV_ISINMA = 7            # bir urun kiyasa girmeden onceki en az gecmis gun sayisi


def _normal_ters(p):
    """Standart normalin ters CDF'i (quantile): P(Z<=z)=p olan z.

    Gazeteci cocukta kritik orana (CR) karsilik gelen 'kac standart sapma
    ustunde/altinda uretmeli' degerini verir. Peter Acklam'in rasyonel
    yaklasiklamasi; dis kutuphane yok, hata ~1e-9.
    """
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return ((((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
                / (((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)))
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
                / ((((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)))
    q = math.sqrt(-2 * math.log(1 - p))
    return (-((((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]))
            / (((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)))


def _kritik_oran(baglanti, kalem_id):
    """Gazeteci cocuk kritik orani CR = Cu / (Cu + Co).

    Co (fazla uretim maliyeti) = bir birim fazla uretip fireye verdiginde kaybedilen
    uretim maliyeti (bozulan dondurma/pastanin hurda degeri 0 sayilir).
    Cu (az uretim maliyeti)    = o birimi satamayinca kaybedilen kar = fiyat - maliyet.
    Boylece CR = (fiyat - maliyet) / fiyat = brut kar orani: kari yuksek urunde 1'e,
    kari ince urunde 0'a yaklasir. Yani model, 'kari yuksek ürünü bolca, ince karli
    urunu ihtiyatli uret' kararini kendiliginden verir.
    """
    k = hesap.kalem(baglanti, kalem_id)
    fiyat = (k["fiyat"] if k else 0.0) or 0.0
    if fiyat <= 0:
        return 0.5
    maliyet = hesap.satis_maliyeti(baglanti, kalem_id)
    return _kirp((fiyat - maliyet) / fiyat, NV_KRITIK_ALT, NV_KRITIK_UST)


def _dogru_uydur(noktalar):
    """En kucuk kareler: y = egim*x + sabit. Uymuyorsa None."""
    adet = len(noktalar)
    if adet < 2:
        return None
    ort_x = sum(x for x, _ in noktalar) / adet
    ort_y = sum(y for _, y in noktalar) / adet
    ustte = sum((x - ort_x) * (y - ort_y) for x, y in noktalar)
    altta = sum((x - ort_x) ** 2 for x, _ in noktalar)
    if altta < 1e-9:
        return None
    egim = ustte / altta
    return egim, ort_y - egim * ort_x


# ---------------------------------------------------------------- gecmis

def gecmis_gunler(baglanti):
    """Hem satisi hem gerceklesen hava kaydi olan gunler, etiketleriyle.

    'ciro' burada NOMINAL (o gunku fiyatla) degil, SABIT-GUNCEL FIYATLI gercek
    cirodur: gunun satis MIKTARLARI, kalemin BUGUNKU fiyatiyla deger bulur
    (Σ miktar × guncel fiyat). Nedeni: fiyat x miktar oldugu icin bir zam
    ( or. 1 Temmuz'da %15) nominal ciroyu siçratir ve model bunu 'talep artti'
    sanir. Miktari guncel fiyatla degerleyince zam serideki basamak olmaktan
    cikar; model gercek talebi (hacmi) ogrenir. Tahminler zaten bugunun
    fiyatinda cikar; ayrica deflate etmeye gerek kalmaz.

    Bugun disarida birakilir: gun bitmeden cirosu eksiktir.
    """
    satirlar = baglanti.execute(
        "SELECT s.tarih, SUM(s.miktar * k.fiyat) AS ciro, h.en_yuksek, h.yagmurlu,"
        " h.yagis, h.yagis_ihtimal"
        " FROM satislar s JOIN kalemler k ON k.id = s.kalem_id"
        " JOIN hava h ON h.tarih = s.tarih"
        " WHERE h.tahmin = 0 AND h.en_yuksek IS NOT NULL AND s.tarih < ?"
        " GROUP BY s.tarih HAVING SUM(s.miktar * k.fiyat) > 0 ORDER BY s.tarih",
        (hesap.bugun(),),
    ).fetchall()
    if not satirlar:
        return []

    harita = takvim.etiket_haritasi(baglanti, satirlar[0]["tarih"], satirlar[-1]["tarih"])
    return [
        {
            "tarih": satir["tarih"],
            "ciro": satir["ciro"],
            "sicaklik": satir["en_yuksek"],
            "yagmurlu": bool(satir["yagmurlu"]),
            "yagmur": _yagmur_degeri(satir["yagis"], satir["yagis_ihtimal"],
                                     satir["yagmurlu"]),
            "gun": _tarihe_cevir(satir["tarih"]).weekday(),
            "etiketler": harita.get(satir["tarih"], set()),
        }
        for satir in satirlar
    ]


# ---------------------------------------------------------------- model

def model_kur(baglanti):
    """Gecmisten katsayilari cikarir. Her zaman bir sozluk doner."""
    return model_kur_gunlerden(gecmis_gunler(baglanti))


def model_kur_gunlerden(gunler):
    """Verilen gun kayit listesinden modeli kurar.

    model_kur bunu butun gecmisle cagirir; geriye donuk test ise ilk N gunle
    cagirip N+1'inci gunu tahmin eder. Boylece 'az veriyle ne kadar isabet'
    sorusu gercek gecmis uzerinde olculebilir. Gun kayitlari gecmis_gunler'in
    dondurdugu bicimdedir (tarih/ciro/sicaklik/yagmurlu/gun/etiketler).
    """
    model = {
        "gun_sayisi": len(gunler),
        "ortalama": 0.0,
        "sicaklik": None,            # (egim, sabit)
        "sicaklik_araligi": 0.0,
        "yagmurlu_gun": 0,
        "yagmur": None,              # (egim, sabit, ort_islaklik) ya da None
        "hafta_sonu_katsayisi": None,
        "gun_katsayilari": {},
        "etiket_katsayilari": {},    # {etiket: (katsayi, gun_sayisi)}
        "hata_payi": 0.0,
        "yeterli": len(gunler) >= EN_AZ_GUN,
        "eksik_gun": max(0, EN_AZ_GUN - len(gunler)),
        "secim": {"sicaklik": False, "yagmur": False, "gun": "yok", "etiketler": set()},
        "cv": None,
    }
    if not gunler:
        return model

    model["ortalama"] = sum(g["ciro"] for g in gunler) / len(gunler)
    sicakliklar = [g["sicaklik"] for g in gunler]
    model["sicaklik_araligi"] = max(sicakliklar) - min(sicakliklar)
    model["yagmurlu_gun"] = sum(1 for g in gunler if g["yagmurlu"])
    if not model["yeterli"]:
        return model

    # Hangi bileseni ekleyecegine model kendisi karar verir: her bileseni
    # bir-disarida capraz dogrulamayla (LOOCV) siner, yalnizca hatayi
    # dusurduyse alir. Elle konmus "sicaklik icin 14 gun, gun icin 28 gun"
    # esiklerinin yerini bu aldi -- karari artik veri veriyor. Az veriyle bir
    # bilesen ezberden oteye gecemezse CV onu zaten reddeder; felsefeyle birebir.
    secim, cv = _ozellik_sec(gunler)
    ham = _ham_kur(gunler, secim)
    model["sicaklik"] = ham["sicaklik"]
    model["yagmur"] = ham["yagmur"]
    model["gun_katsayilari"] = ham["gun_katsayilari"]
    model["hafta_sonu_katsayisi"] = ham["hafta_sonu_katsayisi"]
    model["etiket_katsayilari"] = ham["etiket_katsayilari"]
    model["hata_payi"] = ham["hata_payi"]
    model["secim"] = secim
    model["cv"] = cv
    return model


# ---------------------------------------------------------------- bilesen secimi (CV)

def _ham_kur(gunler, secim):
    """Yalnizca 'secim'de isaretli bilesenlerle bir model kurar.

    Kademeli yapi korunur: her bilesen bir oncekinin SAPMASINDAN hesaplanir,
    boylece ayni etki iki kez sayilmaz. secim: {'sicaklik':bool, 'yagmur':bool,
    'gun':'yok'|'sonu'|'tam', 'etiketler':set}. Bir bilesen 'secili' olsa bile o
    veri parcasinda hesaplanamiyorsa (ornegin hic yagmurlu gun yoksa) sessizce
    notr kalir -- LOOCV katlarinda bu dogaldir.
    """
    m = {"ortalama": 0.0, "sicaklik": None, "yagmur": None,
         "gun_katsayilari": {}, "hafta_sonu_katsayisi": None,
         "etiket_katsayilari": {}, "hata_payi": 0.0}
    n = len(gunler)
    if not n:
        return m
    m["ortalama"] = sum(g["ciro"] for g in gunler) / n

    if secim.get("sicaklik"):
        sic = [g["sicaklik"] for g in gunler]
        if max(sic) - min(sic) > 1e-9:
            uyum = _dogru_uydur([(g["sicaklik"], g["ciro"]) for g in gunler])
            if uyum and uyum[0] > 0:        # yon bilgisi domenden: sicakla artis
                m["sicaklik"] = uyum

    def sapmalar():
        return [(g, g["ciro"] / max(_uygula(m, g["sicaklik"], g["yagmur"],
                                            g["gun"], g["etiketler"]), 1e-9))
                for g in gunler]

    if secim.get("yagmur"):
        # Surekli yagis: islaklik 0..1 ile AGIRLIKLI sapma orani. Islak gunlerin
        # (w agirlikli) ortalama sapmasi ile kurak gunlerin (1-w agirlikli)
        # ortalama sapmasi kiyaslanir. Serbest en-kucuk-kareler egimi birkac
        # siddetli yagis gunune asiri duyarli; agirlikli kontrast gurbuzdur ve
        # w in {0,1} oldugunda eski ikili carpana indirgenir.
        sp = sapmalar()
        ws = [g["yagmur"] for g, _ in sp]
        if ws and (max(ws) - min(ws) > 0.05):
            w_wet = sum(ws)
            w_dry = sum(1.0 - w for w in ws)
            if w_wet > 1e-9 and w_dry > 1e-9:
                islak = sum(w * s for (_, s), w in zip(sp, ws)) / w_wet
                kurak = sum((1.0 - w) * s for (_, s), w in zip(sp, ws)) / w_dry
                if kurak > 1e-9:
                    rel = _kirp(islak / kurak, 0.3, 1.5)
                    m["yagmur"] = (rel, w_wet / len(ws))   # (islak/kurak orani, ort islaklik)

    gun_sec = secim.get("gun", "yok")
    if gun_sec == "tam":
        sp = sapmalar()
        kov = {}
        for g, s in sp:
            kov.setdefault(g["gun"], []).append(s)
        hamg = {gun: sum(d) / len(d) for gun, d in kov.items() if len(d) >= 2}
        if hamg:
            ort = sum(hamg.values()) / len(hamg)
            if ort > 0:
                m["gun_katsayilari"] = {gun: _kirp(v / ort, 0.5, 2.0)
                                        for gun, v in hamg.items()}
    elif gun_sec == "sonu":
        sp = sapmalar()
        sonu = [s for g, s in sp if g["gun"] >= 5]
        ici = [s for g, s in sp if g["gun"] < 5]
        if len(sonu) >= 2 and len(ici) >= 2:
            oran = (sum(sonu) / len(sonu)) / (sum(ici) / len(ici))
            m["hafta_sonu_katsayisi"] = _kirp(oran, 0.4, 2.5)

    secili_et = secim.get("etiketler") or set()
    if secili_et:
        sp = sapmalar()
        islenmis = {takvim.HAFTA_SONU_ETIKET}     # hafta sonu gun bileseninin isi
        kov = {}
        for g, s in sp:
            for e in (g["etiketler"] & secili_et) - islenmis:
                kov.setdefault(e, []).append(s)
        normaller = [s for g, s in sp if not ((g["etiketler"] & secili_et) - islenmis)]
        if len(normaller) >= 2:
            no = sum(normaller) / len(normaller)
            for e, ds in kov.items():
                if len(ds) >= 2 and no > 0:
                    m["etiket_katsayilari"][e] = (_kirp((sum(ds) / len(ds)) / no, 0.2, 4.0),
                                                  len(ds))

    hatalar = [abs(g["ciro"] - _uygula(m, g["sicaklik"], g["yagmur"],
                                       g["gun"], g["etiketler"])) for g in gunler]
    m["hata_payi"] = sum(hatalar) / len(hatalar) if hatalar else 0.0
    return m


def _loocv(gunler, secim):
    """Bir-disarida capraz dogrulama ortalama mutlak hatasi.

    Her gun sirayla disarida birakilir; model kalan gunlerle kurulup disarida
    birakilan gun tahmin edilir. Tahmin edilen gun egitimde olmadigi icin bu
    hata gercek, gormedigi-veri hatasidir -- ezber odullendirilmez.
    """
    n = len(gunler)
    if n < 4:
        return None
    # Cok gun varsa her gunu degil, ~45 temsilci gunu disarida birak: secim
    # karari ortalama hataya dayandigi icin altkume yeterli, maliyet O(n^2)
    # olmaktan cikar (geriye donuk testin ic dongusu bunu cok kez cagiriyor).
    adim = max(1, n // 30)
    indeksler = range(0, n, adim)
    toplam = 0.0
    adet = 0
    for i in indeksler:
        egitim = gunler[:i] + gunler[i + 1:]
        m = _ham_kur(egitim, secim)
        g = gunler[i]
        p = _uygula(m, g["sicaklik"], g["yagmur"], g["gun"], g["etiketler"])
        toplam += abs(g["ciro"] - p)
        adet += 1
    return toplam / adet if adet else None


def _ozellik_sec(gunler):
    """Ileri secim: her bileseni LOOCV ile sinar, hatayi dusurduyse alir.

    Sira kademeli yapiya uyar (sicaklik -> yagmur -> gun -> etiketler). Gun
    bileseninde iki aday vardir (sadece hafta sonu / her gun ayri); hangisi
    hatayi daha cok dusuruyorsa o secilir, ikisi de dusurmuyorsa hicbiri.
    """
    EPS = 1e-6
    secim = {"sicaklik": False, "yagmur": False, "gun": "yok", "etiketler": set()}
    taban = _loocv(gunler, secim)
    cv = {"taban": taban, "adimlar": []}
    cur = taban

    def dene(yeni, etiket):
        nonlocal secim, cur
        h = _loocv(gunler, yeni)
        al = (h is not None and cur is not None and h < cur - EPS)
        cv["adimlar"].append({"bilesen": etiket, "oncesi": cur, "sonrasi": h, "alindi": al})
        if al:
            secim, cur = yeni, h

    dene({**secim, "sicaklik": True}, "sicaklik")
    dene({**secim, "yagmur": True}, "yagmur")

    # Gun: iki adaydan en iyisini (ve tabandan iyiyse) sec.
    en_iyi_v, en_iyi_h = "yok", cur
    for v in ("sonu", "tam"):
        h = _loocv(gunler, {**secim, "gun": v})
        if h is not None and h < en_iyi_h - EPS:
            en_iyi_v, en_iyi_h = v, h
    cv["adimlar"].append({"bilesen": "gun", "oncesi": cur,
                          "sonrasi": en_iyi_h, "alindi": en_iyi_v != "yok",
                          "secenek": en_iyi_v})
    if en_iyi_v != "yok":
        secim["gun"], cur = en_iyi_v, en_iyi_h

    # Etiketler: yeterince gorulen her etiketi tek tek dene (hafta sonu haric,
    # onu gun bileseni tasir).
    sayac = {}
    for g in gunler:
        for e in g["etiketler"]:
            if e != takvim.HAFTA_SONU_ETIKET:
                sayac[e] = sayac.get(e, 0) + 1
    for e in sorted(sayac):
        if sayac[e] < EN_AZ_ETIKET_GUN:
            continue
        dene({**secim, "etiketler": secim["etiketler"] | {e}}, "etiket:" + str(e))

    cv["secili_hata"] = cur
    return secim, cv


def _gun_carpani(model, gun, etiketler):
    """Haftanin gunu ve ozel gun etiketlerinin ortak carpani.

    Etiketler birbiriyle carpilir; cumartesiye denk gelen bir bayramda iki
    katsayi birden isler. Katsayilarin her biri tek basina sinirli ama
    carpimlarinin siniri yoktur: az veriyle ogrenilmis iki-uc katsayi ust uste
    binince "normalin 20 kati" gibi bir rakam cikabilir. Bu yuzden toplam
    carpana da bir taban ve tavan konur - modelin emin olamayacagi kadar uc
    bir tahmini ekrana basmaktansa kirpmak dogrusu.
    """
    carpan = 1.0
    if model["gun_katsayilari"]:
        carpan *= model["gun_katsayilari"].get(gun, 1.0)
    elif model["hafta_sonu_katsayisi"] is not None and gun >= 5:
        carpan *= model["hafta_sonu_katsayisi"]
    for etiket in etiketler or ():
        if etiket in model["etiket_katsayilari"]:
            carpan *= model["etiket_katsayilari"][etiket][0]
    return _kirp(carpan, EN_DUSUK_CARPAN, EN_YUKSEK_CARPAN)


def _yagmur_carpani(model, yagmur):
    """Surekli yagis carpani. model['yagmur'] = (islak/kurak orani, ort_islaklik).
    Ortalama islaklikta carpan ~1'dir; daha islak gun orana dogru, daha kurak
    gun ters yone sapar (ortalamada seviye kaymaz)."""
    bilgi = model.get("yagmur")
    if not bilgi:
        return 1.0
    rel, ort_w = bilgi
    return _kirp(1.0 + (rel - 1.0) * ((yagmur or 0.0) - ort_w), 0.3, 1.5)


def _uygula(model, sicaklik, yagmur, gun, etiketler=()):
    """Katsayilari sirayla uygular. Kismen kurulmus modelde de calisir.

    'yagmur' artik ikili degil surekli islaklik degeri (0..1); bkz _yagmur_degeri.
    """
    if model["sicaklik"] and sicaklik is not None:
        deger = max(model["sicaklik"][0] * sicaklik + model["sicaklik"][1],
                    model["ortalama"] * 0.2)
    else:
        deger = model["ortalama"]

    deger *= _yagmur_carpani(model, yagmur)

    return max(deger * _gun_carpani(model, gun, etiketler), 0.0)


def toplam_katsayi(model, gun, etiketler):
    """Havadan bagimsiz carpan: 'normalin kac kati' demek icin."""
    return _gun_carpani(model, gun, etiketler)


# ---------------------------------------------------------------- urun dagilimi

MEVSIM_ADLARI = ["Kış", "İlkbahar", "Yaz", "Sonbahar"]
_AY_MEVSIM = {12: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1,
              6: 2, 7: 2, 8: 2, 9: 3, 10: 3, 11: 3}
MEVSIM_PRIOR_GUN = 20   # bir mevsimin kendi paylarina guvenilmesi icin ~bu kadar gun


def _mevsim(tarih):
    ay = _tarihe_cevir(tarih).month if isinstance(tarih, str) else tarih.month
    return _AY_MEVSIM[ay]


def urun_paylari(baglanti):
    """Her urunun gercek cirodaki payi: GLOBAL (tum gecmis) + MEVSIMSEL.

    Sorun: ciroyu tum gecmisin SABIT payiyla urunlere bolmek mevsim kaymasini
    kacirir - pastanede kisin borek, yazin tatli artar. Cozum HIYERARSIK:
      - ebeveyn: urunun global payi p_i (tum gecmis)
      - cocuk  : urunun o mevsimdeki payi
    Cocuk, ampirik Bayes ile ebeveyne dogru BUZULUR. Bir mevsimde (ya da az
    satan bir urunde) veri azsa tahmin global paya yaklasir; veri bollastikca
    mevsimin kendi payina guvenilir. Dirichlet-multinom kurali:
        p_hat(i, mevsim) = (gelir[i,mevsim] + K * p_i) / (gelir[.,mevsim] + K)
    Bu, her mevsimde paylarin toplamini kendiliginden 1 yapar. K, ~
    MEVSIM_PRIOR_GUN gunluk ciro kadar alinir (onsel gucu).

    Olcek gecmis_gunler ile ayni: miktar × GUNCEL fiyat (fiyat degisiminden
    etkilenmez; bkz. gecmis_gunler).
    """
    bilgi = {}
    for satir in baglanti.execute(
        "SELECT s.kalem_id, SUM(s.miktar * k.fiyat) AS deger, k.ad, k.birim, k.fiyat"
        " FROM satislar s JOIN kalemler k ON k.id = s.kalem_id"
        " WHERE k.aktif = 1 GROUP BY s.kalem_id"
    ):
        bilgi[satir["kalem_id"]] = {"deger": satir["deger"], "ad": satir["ad"],
                                    "birim": satir["birim"], "fiyat": satir["fiyat"]}
    toplam = sum(b["deger"] for b in bilgi.values())
    if toplam <= 0:
        return {}
    global_pay = {kid: b["deger"] / toplam for kid, b in bilgi.items()}

    # Mevsim bazinda gelir: (kalem, mevsim) -> gercek gelir; ve mevsim toplamlari.
    mev_gelir = {}
    mev_toplam = {}
    for satir in baglanti.execute(
        "SELECT s.kalem_id, CAST(substr(s.tarih, 6, 2) AS INTEGER) AS ay,"
        " SUM(s.miktar * k.fiyat) AS deger"
        " FROM satislar s JOIN kalemler k ON k.id = s.kalem_id"
        " WHERE k.aktif = 1 GROUP BY s.kalem_id, ay"
    ):
        if satir["kalem_id"] not in bilgi or not satir["ay"]:
            continue
        m = _AY_MEVSIM.get(satir["ay"])
        if m is None:
            continue
        mev_gelir[(satir["kalem_id"], m)] = mev_gelir.get((satir["kalem_id"], m), 0.0) + satir["deger"]
        mev_toplam[m] = mev_toplam.get(m, 0.0) + satir["deger"]

    gun_sayisi = baglanti.execute(
        "SELECT COUNT(DISTINCT tarih) c FROM satislar").fetchone()["c"] or 1
    K = (toplam / gun_sayisi) * MEVSIM_PRIOR_GUN      # onsel gucu (gelir birimi)

    paylar = {}
    for kid, b in bilgi.items():
        p_i = global_pay[kid]
        mevsim_pay = {}
        for m, mt in mev_toplam.items():
            gelir = mev_gelir.get((kid, m), 0.0)
            mevsim_pay[m] = (gelir + K * p_i) / (mt + K)   # ebeveyne buzulmus cocuk
        paylar[kid] = {"pay": p_i, "mevsim_pay": mevsim_pay,
                       "ad": b["ad"], "birim": b["birim"], "fiyat": b["fiyat"]}
    return paylar


def _uretim_ihtiyaci(baglanti, urun_miktarlari):
    """Tahmin edilen satislar icin hangi uretilen kalemden ne kadar gerekir."""
    ihtiyac = {}
    for kalem_id, miktar in urun_miktarlari.items():
        kalem = hesap.kalem(baglanti, kalem_id)
        if kalem is None or miktar <= 0:
            continue
        if kalem["uretilir"]:
            ihtiyac[kalem_id] = ihtiyac.get(kalem_id, 0.0) + miktar
            continue
        recete = hesap.ana_recete(baglanti, kalem_id)
        if not recete:
            continue
        for satir in hesap.recete_satirlari(baglanti, recete["id"]):
            malzeme = hesap.kalem(baglanti, satir["kalem_id"])
            if malzeme is not None and malzeme["uretilir"]:
                pay = satir["miktar"] * miktar / (recete["verim"] or 1)
                ihtiyac[satir["kalem_id"]] = ihtiyac.get(satir["kalem_id"], 0.0) + pay
    return ihtiyac


def uretim_onerisi(baglanti, gun_tahminleri):
    """Onumuzdeki gunler icin 'kac parti uretmeli' onerisi (gazeteci cocuk kurali).

    Tahminin yalnizca ORTALAMASINI degil, DAGILIMINI kullanir. Bozulan urunde fazla
    uretim fire, az uretim kacan satistir; ikisinin bedeli esit olmadigi icin en
    karli miktar ortalama degildir. Her SATILAN urun icin kritik orandan
    (CR=(fiyat-maliyet)/fiyat) talebin o yuzdeligi hedeflenir: kari yuksek urunde
    ortalamanin biraz ustu, kari ince urunde alti. Sonra bu hedefler recetelerle
    uretilen kalem ihtiyacina cevrilir. Her oneride 'ortalama' alani da tutulur ki
    ekranda 'nokta tahmin X, en karli uretim Y' farki gosterilebilsin.
    """
    # 1) satilan urun bazinda talep dagilimi: ortalama (mu) ve varyans (gun gun toplanir).
    mu, var = {}, {}
    for tahmin in gun_tahminleri:
        ciro = tahmin.get("ciro") or 0.0
        ust = tahmin.get("ust") or ciro
        rho = (ust - ciro) / ciro if ciro > 0 else 0.15      # tahminin goreli belirsizligi
        rho = max(rho, 0.15)
        for kalem_id, miktar in tahmin["urunler"].items():
            if miktar <= 0:
                continue
            mu[kalem_id] = mu.get(kalem_id, 0.0) + miktar
            sapma = miktar * rho / NV_Z80                     # o gunun standart sapmasi
            var[kalem_id] = var.get(kalem_id, 0.0) + sapma * sapma

    # 2) kritik oran -> hedef miktar (talebin CR yuzdeligi). z>0: ortalamanin ustu.
    nv_hedef, ort_hedef = {}, {}
    for kalem_id, m in mu.items():
        z = _normal_ters(_kritik_oran(baglanti, kalem_id))
        nv_hedef[kalem_id] = max(0.0, m + z * math.sqrt(var.get(kalem_id, 0.0)))
        ort_hedef[kalem_id] = m

    # 3) satilan urun hedeflerini uretilen kalem ihtiyacina cevir (ortalama ve NV ayri).
    nv_ihtiyac = _uretim_ihtiyaci(baglanti, nv_hedef)
    ort_ihtiyac = _uretim_ihtiyaci(baglanti, ort_hedef)

    stok = hesap.stoklar(baglanti)
    oneriler = []
    for kalem_id, gereken in sorted(nv_ihtiyac.items(), key=lambda i: -i[1]):
        kalem = hesap.kalem(baglanti, kalem_id)
        if kalem is None:
            continue
        elde = stok.get(kalem_id, 0.0)
        acik = max(gereken - elde, 0.0)
        # Uretim tam kazanla yapiliyor; yarim/ceyrek parti onerilmez.
        parti = hesap.parti_onerisi(baglanti, kalem_id, acik)
        oneriler.append({
            "kalem": kalem,
            "gereken": gereken,                               # gazeteci cocuk hedefi
            "ortalama": ort_ihtiyac.get(kalem_id, gereken),   # eski nokta (ortalama) hedef
            "elde": elde,
            "acik": acik,
            "parti": parti["sayi"] if parti else 0,
            "parti_ad": parti["parti_ad"] if parti else "parti",
            "cikacak": parti["cikacak"] if parti else 0.0,
            "artacak": parti["artacak"] if parti else 0.0,
        })
    return oneriler


def fire_kiyasi(baglanti, pencere=NV_PENCERE):
    """Gazeteci cocuk kararini hareketli ortalamaya karsi gecmis sezonda sinar.

    Hesap tarafindaki eski kural (siparis/uretim onerisi) son 14 gunun ORTALAMASI
    kadar uret diyordu; tahminin dagilimini ve kar/fire asimetrisini gormezdi. Burada
    her satilan (uretilen/recetesi olan) urun icin gun gun yururuz; o gune kadarki son
    `pencere` gunun gercek talebinden ortalama ve sapma cikarilir:
        - hareketli ortalama  : o gun ORTALAMA kadar uret
        - gazeteci cocuk      : ortalama + z(CR)*sapma kadar uret
    Gerceklesen taleple karsilastirip fire (fazla uretim x maliyet) ve kacan satis
    (eksik uretim x kar) toplanir. Ayni talep tahmini, farkli siparis miktari; yani
    olculen tek sey KARAR KURALI. Not: gerceklesen satis, talebin alt siniridir
    (tukenirse talep gorulmez); simulasyon bol uretimli oldugu icin satis ~ talep.
    """
    satirlar = baglanti.execute(
        "SELECT s.kalem_id, s.tarih, SUM(s.miktar) AS miktar, k.ad, k.birim, k.fiyat,"
        " k.uretilir FROM satislar s JOIN kalemler k ON k.id = s.kalem_id"
        " WHERE k.aktif = 1 GROUP BY s.kalem_id, s.tarih"
        " ORDER BY s.kalem_id, s.tarih"
    ).fetchall()

    seri, bilgi = {}, {}
    for r in satirlar:
        kid = r["kalem_id"]
        seri.setdefault(kid, []).append(r["miktar"])
        if kid not in bilgi:
            bilgi[kid] = {"ad": r["ad"], "birim": r["birim"],
                          "fiyat": r["fiyat"] or 0.0, "uretilir": r["uretilir"]}

    bos = {"fire": 0.0, "kayip": 0.0, "kar": 0.0}
    toplam = {"ma": dict(bos), "nv": dict(bos)}
    urun_sayisi, gun_sayisi = 0, 0
    for kid, talepler in seri.items():
        b = bilgi[kid]
        fiyat = b["fiyat"]
        # Yalnizca uretim kararina tabi urunler: uretilen ya da recetesi olan.
        if fiyat <= 0 or (not b["uretilir"] and hesap.ana_recete(baglanti, kid) is None):
            continue
        maliyet = hesap.satis_maliyeti(baglanti, kid)
        birim_kar = fiyat - maliyet
        if birim_kar <= 0 or len(talepler) < NV_ISINMA + 1:
            continue
        z = _normal_ters(_kirp((fiyat - maliyet) / fiyat, NV_KRITIK_ALT, NV_KRITIK_UST))
        urun_sayisi += 1
        for i in range(NV_ISINMA, len(talepler)):
            gecmis = talepler[max(0, i - pencere):i]
            n = len(gecmis)
            ort = sum(gecmis) / n
            sapma = (math.sqrt(sum((x - ort) ** 2 for x in gecmis) / n) if n > 1 else 0.0)
            gercek = talepler[i]
            gun_sayisi += 1
            for ad, uret in (("ma", ort), ("nv", max(0.0, ort + z * sapma))):
                satilan = min(uret, gercek)
                fire = max(uret - gercek, 0.0)
                kayip = max(gercek - uret, 0.0)
                toplam[ad]["fire"] += fire * maliyet
                toplam[ad]["kayip"] += kayip * birim_kar
                toplam[ad]["kar"] += satilan * birim_kar - fire * maliyet
    return {"ma": toplam["ma"], "nv": toplam["nv"],
            "urun_sayisi": urun_sayisi, "gun_sayisi": gun_sayisi // max(1, urun_sayisi)}


# ---------------------------------------------------------------- tahmin

def gun_tahmini(baglanti, tarih, model, paylar, etiketler=()):
    """Bir gunun tahmini: ciro araligi ve urun kirilimi."""
    hava_satiri = hava.gun(baglanti, tarih)
    gun_no = _tarihe_cevir(tarih).weekday()
    sicaklik = hava_satiri["en_yuksek"] if hava_satiri else None
    yagmurlu = bool(hava_satiri["yagmurlu"]) if hava_satiri else False
    yagmur = (_yagmur_degeri(hava_satiri["yagis"], hava_satiri["yagis_ihtimal"],
                             hava_satiri["yagmurlu"]) if hava_satiri else 0.0)

    ciro = _uygula(model, sicaklik, yagmur, gun_no, etiketler)
    pay_araligi = max(model["hata_payi"], ciro * 0.15)

    # Urun kirilimi hedef gunun MEVSIMsel (ampirik Bayes ile buzulmus) payiyla;
    # o mevsim hic gorulmemisse global paya duser.
    mevsim = _mevsim(tarih)

    def _pay(bilgi):
        return bilgi.get("mevsim_pay", {}).get(mevsim, bilgi["pay"])

    urunler = {
        kalem_id: ciro * _pay(bilgi) / bilgi["fiyat"]
        for kalem_id, bilgi in paylar.items() if bilgi["fiyat"] > 0
    }
    ozel = sorted(e for e in etiketler if e != takvim.HAFTA_SONU_ETIKET)

    return {
        "tarih": tarih,
        "gun_adi": GUN_ADLARI[gun_no],
        "hafta_sonu": gun_no >= 5,
        "ozel_etiketler": ozel,
        "sicaklik": sicaklik,
        "yagmurlu": yagmurlu,
        "hava": hava.ozet(baglanti, tarih),
        "ciro": ciro,
        "alt": max(ciro - pay_araligi, 0.0),
        "ust": ciro + pay_araligi,
        "katsayi": toplam_katsayi(model, gun_no, etiketler),
        "urunler": urunler,
    }


def ileri_tahmin(baglanti, gun_sayisi=7):
    """Bugunden baslayarak gun_sayisi kadar gunun tahmini.

    Doner: (model, [gun tahminleri], uretim onerileri)
    """
    model = model_kur(baglanti)
    if not model["yeterli"]:
        return model, [], []

    paylar = urun_paylari(baglanti)
    bugun = datetime.date.today()
    son = bugun + datetime.timedelta(days=gun_sayisi - 1)
    harita = takvim.etiket_haritasi(
        baglanti, bugun.strftime("%Y-%m-%d"), son.strftime("%Y-%m-%d"))

    tahminler = []
    for kaydirma in range(gun_sayisi):
        tarih = (bugun + datetime.timedelta(days=kaydirma)).strftime("%Y-%m-%d")
        # Hava kaydi olmayan gun icin tahmin uretmek, mevsim ortalamasini
        # bugunun havasi sanmak olur; o gun atlanir.
        if hava.gun(baglanti, tarih) is None:
            continue
        tahminler.append(gun_tahmini(baglanti, tarih, model, paylar,
                                     harita.get(tarih, set())))
    return model, tahminler, uretim_onerisi(baglanti, tahminler)


# ---------------------------------------------------------------- tahmin gunlugu

def gunluk_guncelle(baglanti):
    """Gunun tahminini kaydeder ve gecmis gunlerin gerceklesenini eşleştirir.

    Iki is yapar, ikisi de zararsiz tekrar edilebilir:
      1. Bugune ait bir tahmin satiri yoksa, o anki modelin bugun icin tahminini
         yazar. Model gecmis_gunler'i kullanir ve o **bugunu disarida birakir**;
         yani kaydedilen rakam gun ici satislardan etkilenmez, 'sabah tahmini'dir.
      2. Gecmiste tahmini olup gerceklesen cirosu henuz yazilmamis gunleri,
         satislardan gelen gercek ciroyla doldurur.

    Boylece "sabah ne dedik, aksam ne oldu" ikilisi kendiliginden birikir;
    tahminin durustlugu sonradan olculebilir.
    """
    bugun = hesap.bugun()

    # 2. Gecmisin gerceklesenini doldur (yalnizca satisi girilmis gunler).
    #    Tahminle ayni olcek: miktar × guncel fiyat (sabit-fiyatli gercek ciro).
    baglanti.execute(
        "UPDATE tahmin_kayitlari SET"
        " gercek = (SELECT SUM(s.miktar * k.fiyat) FROM satislar s"
        "           JOIN kalemler k ON k.id = s.kalem_id"
        "           WHERE s.tarih = tahmin_kayitlari.tarih),"
        " gercek_yaz = ?"
        " WHERE tarih < ? AND gercek IS NULL"
        " AND EXISTS (SELECT 1 FROM satislar WHERE tarih = tahmin_kayitlari.tarih)",
        (_simdi(), bugun),
    )

    # 1. Bugunun tahminini bir kez yaz.
    var = baglanti.execute(
        "SELECT 1 FROM tahmin_kayitlari WHERE tarih = ?", (bugun,)
    ).fetchone()
    if not var:
        model = model_kur(baglanti)
        hava_satiri = hava.gun(baglanti, bugun)
        gun_no = _tarihe_cevir(bugun).weekday()
        etiketler = takvim.etiket_haritasi(baglanti, bugun, bugun).get(bugun, set())
        sicaklik = hava_satiri["en_yuksek"] if hava_satiri else None
        yagmurlu = bool(hava_satiri["yagmurlu"]) if hava_satiri else False
        yagmur = (_yagmur_degeri(hava_satiri["yagis"], hava_satiri["yagis_ihtimal"],
                                 hava_satiri["yagmurlu"]) if hava_satiri else 0.0)
        if model["yeterli"]:
            ciro = _uygula(model, sicaklik, yagmur, gun_no, etiketler)
            pay = max(model["hata_payi"], ciro * 0.15)
            tahmin, alt, ust = ciro, max(ciro - pay, 0.0), ciro + pay
        else:
            # Az veriyle tahmin vermeyi reddeder; satir yine de durustluk icin
            # tutulur ama tahmin bos kalir.
            tahmin = alt = ust = None
        baglanti.execute(
            "INSERT INTO tahmin_kayitlari"
            " (tarih, tahmin, alt, ust, model_gun, yeterli, sicaklik, yagmurlu, kaydedildi)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (bugun, tahmin, alt, ust, model["gun_sayisi"],
             1 if model["yeterli"] else 0, sicaklik, 1 if yagmurlu else 0, _simdi()),
        )
    baglanti.commit()


def tahmin_gunlugu(baglanti, limit=60):
    """Tahmin gunlugunu yeni gunden eskiye okur; sapma yuzdesini hesaplar."""
    satirlar = baglanti.execute(
        "SELECT tarih, tahmin, alt, ust, gercek, model_gun, yeterli, sicaklik, yagmurlu"
        " FROM tahmin_kayitlari ORDER BY tarih DESC LIMIT ?", (limit,)
    ).fetchall()
    sonuc = []
    for s in satirlar:
        sapma = None
        if s["tahmin"] is not None and s["gercek"] is not None and s["gercek"] > 0:
            sapma = abs(s["tahmin"] - s["gercek"]) / s["gercek"] * 100
        sonuc.append({
            "tarih": s["tarih"], "tahmin": s["tahmin"], "alt": s["alt"], "ust": s["ust"],
            "gercek": s["gercek"], "model_gun": s["model_gun"],
            "yeterli": bool(s["yeterli"]), "sicaklik": s["sicaklik"],
            "yagmurlu": bool(s["yagmurlu"]), "sapma": sapma,
            # Tahmin, araligin icinde mi tutturdu?
            "isabet": (s["tahmin"] is not None and s["gercek"] is not None
                       and s["alt"] is not None and s["ust"] is not None
                       and s["alt"] <= s["gercek"] <= s["ust"]),
        })
    return sonuc


def geriye_donuk_test(baglanti):
    """Kayan baslangicli geriye donuk test (rolling-origin backtest).

    Modeli ilk N gunle kurar, N+1'inci gunu tahmin eder, N'i bir artirir.
    Her adimda modelin ve basit bir kiyasin (yalnizca gecmisin ortalamasi)
    yuzde hatasi olculur. Dondurulen 'adimlar' listesindeki birikimli ortalama
    hata (ort_m / ort_k), gun sayisina karsi cizilince projenin ana tezinin -
    'az veriyle durust tahmin' - grafik kanitidir.

    Onemli: her adimda model yalnizca o gune kadarki gunleri gorur; tahmin
    edilen gun egitimde yoktur. Gecmise bakip gelecegi bilmek (veri sizmasi) yok.
    """
    gunler = gecmis_gunler(baglanti)
    adimlar = []
    mh_toplam = kh_toplam = 0.0
    say = 0
    for n in range(EN_AZ_GUN, len(gunler)):
        model = model_kur_gunlerden(gunler[:n])
        if not model["yeterli"]:
            continue
        hedef = gunler[n]
        gercek = hedef["ciro"]
        if gercek <= 0:
            continue
        tahmin = _uygula(model, hedef["sicaklik"], hedef["yagmur"],
                         hedef["gun"], hedef["etiketler"])
        kiyas = model["ortalama"]            # saf kiyas: gecmisin ortalamasi
        hata_m = abs(tahmin - gercek) / gercek * 100
        hata_k = abs(kiyas - gercek) / gercek * 100
        say += 1
        mh_toplam += hata_m
        kh_toplam += hata_k
        adimlar.append({
            "n": n, "tarih": hedef["tarih"], "tahmin": tahmin, "gercek": gercek,
            "kiyas": kiyas, "hata_m": hata_m, "hata_k": hata_k,
            "ort_m": mh_toplam / say, "ort_k": kh_toplam / say,
        })
    return {
        "adimlar": adimlar,
        "deger_sayisi": say,
        "toplam_gun": len(gunler),
        "en_az_gun": EN_AZ_GUN,
        "ort_hata_model": (mh_toplam / say) if say else None,
        "ort_hata_kiyas": (kh_toplam / say) if say else None,
    }


# ---------------------------------------------------------------- temel modeller

def _coz(A, b):
    """A x = b'yi Gauss eliminasyonuyla cozer (kucuk, tam-matris; kutuphane yok)."""
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            continue
        M[c], M[piv] = M[piv], M[c]
        d = M[c][c]
        M[c] = [v / d for v in M[c]]
        for r in range(n):
            if r != c and M[r][c]:
                f = M[r][c]
                M[r] = [M[r][k] - f * M[c][k] for k in range(n + 1)]
    return [M[i][n] for i in range(n)]


def _ozellik(g):
    """Regresyon degiskenleri: sicaklik, yagmur(0/1), hafta sonu(0/1)."""
    return [g["sicaklik"], g["yagmur"], 1.0 if g["gun"] >= 5 else 0.0]


def _ridge_fit(egitim, lam=1.0):
    """Ridge cezali coklu dogrusal regresyon; saf Python, normal denklemler.

    Degiskenler standartlastirilir (penaltı adil olsun diye), sabit terim
    cezalandirilmaz. Doner: hedef gunu alip ciro tahmini veren fonksiyon.
    """
    n = len(egitim)
    ham = [_ozellik(g) for g in egitim]
    y = [g["ciro"] for g in egitim]
    p = len(ham[0])
    ort = [sum(r[j] for r in ham) / n for j in range(p)]
    std = []
    for j in range(p):
        var = sum((r[j] - ort[j]) ** 2 for r in ham) / n
        std.append(math.sqrt(var) if var > 1e-12 else 1.0)

    def olcekle(ozellik):
        return [1.0] + [(ozellik[j] - ort[j]) / std[j] for j in range(p)]

    X = [olcekle(r) for r in ham]
    d = p + 1
    XtX = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(d)] for a in range(d)]
    for k in range(1, d):      # sabit terim (indeks 0) cezalandirilmaz
        XtX[k][k] += lam
    Xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(d)]
    beta = _coz(XtX, Xty)

    def tahmin(hedef):
        xs = olcekle(_ozellik(hedef))
        return max(sum(beta[a] * xs[a] for a in range(d)), 0.0)

    return tahmin


def _m_genel(egitim, hedef):
    return sum(g["ciro"] for g in egitim) / len(egitim)


def _m_son7(egitim, hedef):
    son = egitim[-7:]
    return sum(g["ciro"] for g in son) / len(son)


def _m_ayni_gun(egitim, hedef):
    """Gecen haftanin ayni gunu: ayni hafta-gunune sahip en son gun."""
    ayni = [g for g in egitim if g["gun"] == hedef["gun"]]
    if ayni:
        return ayni[-1]["ciro"]
    return _m_genel(egitim, hedef)


def _m_kademeli(egitim, hedef):
    model = model_kur_gunlerden(egitim)
    return _uygula(model, hedef["sicaklik"], hedef["yagmur"],
                   hedef["gun"], hedef["etiketler"])


def _m_ridge(egitim, hedef):
    return _ridge_fit(egitim)(hedef)


# Jurinin istedigi sira: once bizim modeller, sonra naif kiyaslar.
TEMEL_MODELLER = [
    ("kademeli", "Kademeli model (bizim)", _m_kademeli),
    ("ridge", "Çoklu regresyon (ridge)", _m_ridge),
    ("son7", "Son 7 gün ortalaması", _m_son7),
    ("ayni_gun", "Geçen haftanın aynı günü", _m_ayni_gun),
    ("genel", "Genel ortalama", _m_genel),
]
KAPSAMA_HEDEF = 80       # aralik ~%80 icin kuruluyor; kapsama buna yakin cikmali


def _yuzdelik(degerler, oran=0.8):
    if not degerler:
        return None
    s = sorted(degerler)
    k = min(len(s) - 1, max(0, int(math.ceil(oran * len(s)) - 1)))
    return s[k]


# ---------------------------------------------------------------- fire anomalisi
ANOMALI_PENCERE = 30     # kac gunluk fire gecmisine bakilir
ANOMALI_EN_AZ = 8        # bu kadar sayim gunu olmadan istatistik yapilmaz
ANOMALI_IQR_K = 1.5      # Tukey citi: ust cit = Q3 + k*IQR
ANOMALI_Z = 3.0          # dagilim neredeyse sabitse robust z esigi


def _ceyrek(sirali, oran):
    """Dogrusal interpolasyonlu yuzdelik; sirali (kucukten buyuge) liste bekler."""
    if not sirali:
        return 0.0
    if len(sirali) == 1:
        return sirali[0]
    konum = oran * (len(sirali) - 1)
    alt = int(math.floor(konum))
    ust = min(alt + 1, len(sirali) - 1)
    return sirali[alt] + (sirali[ust] - sirali[alt]) * (konum - alt)


def fire_anomalisi(baglanti, kalem_id, tarih, bugunku_fire):
    """Bugunku firenin son ANOMALI_PENCERE gunun dagilimina gore anomali olup
    olmadigini soyler. Sabit esik yerine kalemin KENDI gecmisini olcut alir.

    Yontem - ceyrekler arasi aralik (IQR, Tukey): ust cit = Q3 + 1.5*IQR; bunu
    asan fire 'olagandisi' sayilir. IQR, firenin carpik ve ara sira sicrayan
    dagiliminda ortalama+std'den daha saglamdir (birkac buyuk gun esigi sismez).
    Dagilim neredeyse sabitse (IQR~0) medyandan MAD cinsinden robust z-skoruna
    duser. Aciklama metni icin medyan, ust cit ve z birlikte dondurulur.

    Payda, kalemin son pencere icinde SAYILDIGI gunlerdir (fark cikmayan gun
    fire=0 olarak girer); boylece 'normalde hic fire olmazken bugun cikti' da
    yakalanir. Yeterli sayim gunu yoksa None doner - az veriyle anomali ilan etmek
    tahminin 'az veriyle durust' felsefesine aykiri olurdu.

    Doner: None (yeterli gecmis yok ya da anomali degil) veya
    {'medyan', 'ust_cit', 'z', 'gun', 'yontem'}.
    """
    if bugunku_fire is None or bugunku_fire <= 0:
        return None
    try:
        gun = _tarihe_cevir(tarih)
    except (TypeError, ValueError):
        return None
    baslangic = (gun - datetime.timedelta(days=ANOMALI_PENCERE)).strftime("%Y-%m-%d")

    sayim_gunleri = [r["tarih"] for r in baglanti.execute(
        "SELECT DISTINCT s.tarih FROM sayimlar s"
        " JOIN sayim_satirlari r ON r.sayim_id = s.id"
        " WHERE r.kalem_id = ? AND s.tarih >= ? AND s.tarih < ?",
        (kalem_id, baslangic, tarih)).fetchall()]
    if len(sayim_gunleri) < ANOMALI_EN_AZ:
        return None

    fire_harita = {r["tarih"]: r["fire"] for r in baglanti.execute(
        "SELECT tarih, SUM(-miktar) AS fire FROM stok_hareketleri"
        " WHERE kalem_id = ? AND sebep = 'Sayım farkı' AND miktar < 0"
        "   AND tarih >= ? AND tarih < ? GROUP BY tarih",
        (kalem_id, baslangic, tarih))}
    seri = sorted(fire_harita.get(g, 0.0) for g in sayim_gunleri)

    q1, medyan, q3 = _ceyrek(seri, 0.25), _ceyrek(seri, 0.5), _ceyrek(seri, 0.75)
    iqr = q3 - q1
    ust_cit = q3 + ANOMALI_IQR_K * iqr
    mad = _ceyrek(sorted(abs(x - medyan) for x in seri), 0.5)
    gun = len(sayim_gunleri)

    if iqr > 1e-9:
        # Asil yontem: Tukey citi. Yayginligin saglam olcusu MAD, yoksa std.
        if mad > 1e-9:
            z = 0.6745 * (bugunku_fire - medyan) / mad
        else:
            ort = sum(seri) / len(seri)
            std = (sum((x - ort) ** 2 for x in seri) / len(seri)) ** 0.5
            z = (bugunku_fire - ort) / std if std > 1e-9 else 0.0
        return ({"medyan": medyan, "ust_cit": ust_cit, "z": z, "gun": gun, "yontem": "iqr"}
                if bugunku_fire > ust_cit else None)
    if mad > 1e-9:
        # IQR sifir ama dagilim yine de oynuyor: medyandan MAD cinsinden robust z.
        z = 0.6745 * (bugunku_fire - medyan) / mad
        return ({"medyan": medyan, "ust_cit": ust_cit, "z": z, "gun": gun, "yontem": "z"}
                if z >= ANOMALI_Z else None)
    # Dagilim tamamen sabit ( or. hep ayni/sifir). Materyal sapma anomalidir; cagiran
    # taraf zaten sabit esikle (koli'nin %10'u) on-eledi, bu yuzden z/olcek uretmeyiz.
    if bugunku_fire > medyan + 1e-9:
        return {"medyan": medyan, "ust_cit": medyan, "z": None, "gun": gun, "yontem": "sabit"}
    return None


def karsilastir(baglanti):
    """Temel modellerle karsilastirma (kayan baslangicli, ayni adil kosul).

    Her gun, her model yalnizca kendinden onceki gunlerle tahmin eder. Olculenler:
      - MAE  : ortalama mutlak hata (para birimi)
      - MAPE : ortalama mutlak yuzde hata
      - kapsama: gerceklesenin, modelin ~%80 araliginin icine dustugu gun orani
    Aralik, her modelin o ana kadarki kendi mutlak hatalarinin %80'lik dilimiyle
    kurulur (prequential) - butun modellere ayni, durust kural.
    """
    gunler = gecmis_gunler(baglanti)
    durum = {a: {"ad": ad, "fn": fn, "mae": [], "mape": [], "kapsama": [],
                 "hatalar": [], "egri": []}
             for a, ad, fn in TEMEL_MODELLER}

    # Dis dongu adimi: cok gun varsa her gunu degil, ~120 adimi degerlendirerek
    # kademeli modelin her adimda yeniden CV-secimi yapmasinin maliyetini
    # sinirlar. Kayan baslangic ilkesi bozulmaz, yalnizca daha seyrek olculur.
    adaylar = list(range(EN_AZ_GUN, len(gunler)))
    adim = max(1, (len(adaylar) + 59) // 60)
    n_dizisi = adaylar[::adim]

    for n in n_dizisi:
        egitim = gunler[:n]
        hedef = gunler[n]
        gercek = hedef["ciro"]
        if gercek <= 0:
            continue
        for a, ad, fn in TEMEL_MODELLER:
            d = durum[a]
            try:
                pred = fn(egitim, hedef)
            except Exception:
                continue
            hata = abs(pred - gercek)
            yari = _yuzdelik(d["hatalar"], 0.8) if len(d["hatalar"]) >= 5 else pred * 0.2
            d["mae"].append(hata)
            d["mape"].append(hata / gercek * 100)
            d["kapsama"].append(1.0 if (pred - yari) <= gercek <= (pred + yari) else 0.0)
            d["hatalar"].append(hata)
            # Gun sayisina karsi birikimli ortalama yuzde hata (hata egrisi).
            d["egri"].append((n, sum(d["mape"]) / len(d["mape"])))

    sonuc = []
    for a, ad, fn in TEMEL_MODELLER:
        d = durum[a]
        k = len(d["mae"])
        if not k:
            continue
        sonuc.append({
            "anahtar": a, "ad": ad, "adet": k,
            "mae": sum(d["mae"]) / k,
            "mape": sum(d["mape"]) / k,
            "kapsama": sum(d["kapsama"]) / k * 100,
            "egri": d["egri"],
        })
    return {
        "modeller": sonuc,
        "deger_sayisi": max((m["adet"] for m in sonuc), default=0),
        "toplam_gun": len(gunler),
        "en_az_gun": EN_AZ_GUN,
        "kapsama_hedef": KAPSAMA_HEDEF,
    }


def ozel_gun_beklentisi(baglanti, model, gun_sayisi=90):
    """Yaklasan ozel gunler ve o gunlerde ne beklenmesi gerektigi.

    Hava tahmini sadece bir haftayi kapsar; 30 Agustos'a bir ay varsa o gunun
    sicakligi bilinmez. Bu yuzden burada TL degil **carpan** verilir:
    "normalin 2,1 kati". Hava biliniyorsa TL de eklenir.
    """
    sonuc = []
    for satir in takvim.yaklasan(baglanti, gun_sayisi):
        katsayi_bilgi = model["etiket_katsayilari"].get(satir["etiket"])
        hava_satiri = hava.gun(baglanti, satir["baslangic"])
        gun_no = _tarihe_cevir(satir["baslangic"]).weekday()

        kayit = {
            "ad": satir["ad"],
            "etiket": satir["etiket"],
            "baslangic": satir["baslangic"],
            "bitis": satir["bitis"],
            "gun_sayisi": takvim.gun_araligi(satir["baslangic"], satir["bitis"]),
            "kalan_gun": (_tarihe_cevir(satir["baslangic"])
                          - datetime.date.today()).days,
            "katsayi": katsayi_bilgi[0] if katsayi_bilgi else None,
            "ogrenilen_gun": katsayi_bilgi[1] if katsayi_bilgi else 0,
            "ciro": None,
        }
        if katsayi_bilgi and hava_satiri and model["yeterli"]:
            kayit["ciro"] = _uygula(
                model, hava_satiri["en_yuksek"],
                _yagmur_degeri(hava_satiri["yagis"], hava_satiri["yagis_ihtimal"],
                               hava_satiri["yagmurlu"]),
                gun_no, {satir["etiket"]})
        sonuc.append(kayit)
    return sonuc


# ---------------------------------------------------------------- anlatim

def durum_metni(model, baglanti=None):
    """Modelin ne durumda oldugunu anlatir (secili dile gore)."""
    from diller import C
    if model["gun_sayisi"] == 0:
        return C("Henüz hiç satış kaydı yok. Tahmin, geçmiş günlerin hava durumu ile "
                 "o günün cirosunu karşılaştırarak öğreniyor; en az {en_az} günlük satış "
                 "gerekiyor. Gün sonu satışlarını girmeye başladığında kendiliğinden "
                 "çalışacak — senin ayrıca bir şey yapman gerekmiyor, her günün havası "
                 "şimdiden kaydediliyor.", en_az=EN_AZ_GUN)
    if not model["yeterli"]:
        return C("{gun} günlük veri var, tahmin için en az {en_az} gün gerekiyor. "
                 "{eksik} gün daha satış girildiğinde tahminler burada görünmeye "
                 "başlayacak.", gun=model['gun_sayisi'], en_az=EN_AZ_GUN,
                 eksik=model['eksik_gun'])

    parcalar = [C("{gun} günlük satış geçmişine bakıyor; hangi bileşeni kullanacağına "
                  "çapraz doğrulamayla kendisi karar verdi", gun=model['gun_sayisi'])]

    if model["sicaklik"]:
        deger = f"{model['sicaklik'][0]:,.0f}".replace(",", ".")
        parcalar.append(C("sıcaklığı aldı: her 1 derece günlük ciroyu ortalama {deger} "
                          "birim değiştiriyor", deger=deger))
    else:
        parcalar.append(C("sıcaklığı denedi ama hatayı düşürmedi, kullanmıyor"))

    if model["yagmur"]:
        # Cok yagisli bir gun (10 mm+) kurak gune gore ne kadar fark yaratiyor?
        kuru = _yagmur_carpani(model, 0.0)
        islak = _yagmur_carpani(model, 1.0)
        yuzde = (islak / kuru - 1) * 100 if kuru > 0 else 0.0
        yon = C("artıyor") if yuzde > 0 else C("düşüyor")
        parcalar.append(C("yağış miktarını sürekli ölçüyor: çok yağışlı bir gün "
                          "kurak güne göre satışı %{yuzde} {yon}",
                          yuzde=f"{abs(yuzde):.0f}", yon=yon))
    else:
        parcalar.append(C("yağışı (mm) denedi ama hatayı düşürmedi, kullanmıyor"))

    if model["gun_katsayilari"]:
        en_iyi = max(model["gun_katsayilari"].items(), key=lambda i: i[1])
        parcalar.append(C("en yoğun gün {gun} (normalin {kat} katı)",
                          gun=C(GUN_ADLARI[en_iyi[0]]), kat=f"{en_iyi[1]:.2f}"))
    elif model["hafta_sonu_katsayisi"] is not None:
        kat = model["hafta_sonu_katsayisi"]
        parcalar.append(C("hafta sonu satışı hafta içinin {kat} katı", kat=f"{kat:.2f}"))
    else:
        parcalar.append(C("haftanın gününü denedi ama hatayı düşürmedi, kullanmıyor"))

    if model["etiket_katsayilari"]:
        for etiket, (kat, adet) in sorted(model["etiket_katsayilari"].items()):
            parcalar.append(C("{etiket}: normalin {kat} katı ({adet} güne bakarak)",
                              etiket=etiket, kat=f"{kat:.2f}", adet=adet))
    else:
        parcalar.append(C("özel gün etkisi çapraz doğrulamada seçilmedi"))

    return " · ".join(parcalar) + "."
