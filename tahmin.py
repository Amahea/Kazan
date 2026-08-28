# -*- coding: utf-8 -*-
"""Havaya, haftanin gunune ve ozel gunlere bakarak ileriye donuk satis tahmini.

Model bilerek basit tutuldu, cunku elde az gun var ve karmasik bir model az
veriyle guvenle degil sadece kendinden emin sekilde yanilir. Dort kademe:

    1. Sicaklik  -> gunun cirosuna en cok etki eden sey. Gecmis gunlerin
                    (en yuksek sicaklik, ciro) ciftlerine bir dogru uydurulur.
    2. Yagmur    -> sicaklik modelinin tahmin ettiginden ne kadar sapildigi
                    olculur; yagmurlu gunlerin ortalama sapmasi katsayi olur.
    3. Haftanin gunu -> once sadece "hafta sonu mu" (14 gunde ogrenilir),
                    yeterli veri birikince her gun icin ayri katsayi (28 gun).
    4. Ozel gunler -> resmi tatil, dini bayram, findik toplama donemi.
                    Her etiket icin tek katsayi; kalan sapmadan hesaplanir.

Her kademe bir oncekinin **sapmasindan** hesaplandigi icin ayni etki iki kez
sayilmaz: cumartesiye denk gelen bir bayramda hem cumartesi hem bayram
katsayisi carpilir ama ikisi de kendi payini bir kere alir.

Program **tahmin uretmeyi reddedebilir.** Yeterli gun yoksa "su kadar gun daha
lazim" der. Uydurma bir rakam vermektense susmak dogrusu.
"""

import datetime

import hava
import hesap
import takvim

EN_AZ_GUN = 10           # bunun altinda hic tahmin yok
SICAKLIK_ICIN = 14       # sicaklik-ciro dogrusu icin gereken gun
HAFTA_SONU_ICIN = 14     # "hafta sonu mu" katsayisi icin gereken gun
HAFTA_GUNU_ICIN = 28     # her gune ayri katsayi icin gereken gun
EN_AZ_SICAKLIK_ARALIGI = 5.0   # gecmiste bu kadar derece fark yoksa dogru guvenilmez
EN_AZ_ETIKET_GUN = 3     # bir ozel gun etiketinin katsayisi icin gereken gun
EN_AZ_KARSILASTIRMA = 3  # katsayinin kiyaslanacagi normal gun sayisi
EN_DUSUK_CARPAN = 0.2    # gun + etiket carpanlarinin ortak tabani
EN_YUKSEK_CARPAN = 5.0   # ve tavani (asagidaki _gun_carpani'na bak)

GUN_ADLARI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def _tarihe_cevir(metin):
    return datetime.datetime.strptime(metin, "%Y-%m-%d").date()


def _kirp(deger, alt, ust):
    return max(alt, min(ust, deger))


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

    Bugun disarida birakilir: gun bitmeden cirosu eksiktir, modele katilirsa
    her gun kendi sabahiyla ogrenmis olur.
    """
    satirlar = baglanti.execute(
        "SELECT s.tarih, SUM(s.tutar) AS ciro, h.en_yuksek, h.yagmurlu"
        " FROM satislar s JOIN hava h ON h.tarih = s.tarih"
        " WHERE h.tahmin = 0 AND h.en_yuksek IS NOT NULL AND s.tarih < ?"
        " GROUP BY s.tarih HAVING SUM(s.tutar) > 0 ORDER BY s.tarih",
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
            "gun": _tarihe_cevir(satir["tarih"]).weekday(),
            "etiketler": harita.get(satir["tarih"], set()),
        }
        for satir in satirlar
    ]


# ---------------------------------------------------------------- model

def model_kur(baglanti):
    """Gecmisten katsayilari cikarir. Her zaman bir sozluk doner."""
    gunler = gecmis_gunler(baglanti)
    model = {
        "gun_sayisi": len(gunler),
        "ortalama": 0.0,
        "sicaklik": None,            # (egim, sabit)
        "sicaklik_araligi": 0.0,
        "yagmurlu_gun": 0,
        "yagmur_katsayisi": 1.0,
        "hafta_sonu_katsayisi": None,
        "gun_katsayilari": {},
        "etiket_katsayilari": {},    # {etiket: (katsayi, gun_sayisi)}
        "hata_payi": 0.0,
        "yeterli": len(gunler) >= EN_AZ_GUN,
        "eksik_gun": max(0, EN_AZ_GUN - len(gunler)),
    }
    if not gunler:
        return model

    model["ortalama"] = sum(g["ciro"] for g in gunler) / len(gunler)
    sicakliklar = [g["sicaklik"] for g in gunler]
    model["sicaklik_araligi"] = max(sicakliklar) - min(sicakliklar)
    model["yagmurlu_gun"] = sum(1 for g in gunler if g["yagmurlu"])
    if not model["yeterli"]:
        return model

    # 1. Sicaklik dogrusu
    if (len(gunler) >= SICAKLIK_ICIN
            and model["sicaklik_araligi"] >= EN_AZ_SICAKLIK_ARALIGI):
        uyum = _dogru_uydur([(g["sicaklik"], g["ciro"]) for g in gunler])
        # Sicaklik arttikca satis dusuyorsa bu veri azliginin gurultusudur;
        # dondurmaci icin de firinci icin de yon bilgisi modele zorlanmaz.
        if uyum and uyum[0] > 0:
            model["sicaklik"] = uyum

    def sapmalar():
        """Her gun icin (gun, o ana kadarki modelin kac katini tutturdugu)."""
        return [(g, g["ciro"] / max(_uygula(model, g["sicaklik"], g["yagmurlu"],
                                            g["gun"], g["etiketler"]), 1e-9))
                for g in gunler]

    # 2. Yagmur
    ilk_sapma = sapmalar()
    yagmurlu = [s for g, s in ilk_sapma if g["yagmurlu"]]
    kuru = [s for g, s in ilk_sapma if not g["yagmurlu"]]
    if len(yagmurlu) >= EN_AZ_KARSILASTIRMA and len(kuru) >= EN_AZ_KARSILASTIRMA:
        oran = (sum(yagmurlu) / len(yagmurlu)) / (sum(kuru) / len(kuru))
        model["yagmur_katsayisi"] = _kirp(oran, 0.3, 1.5)

    # 3. Haftanin gunu. Once ince ayar (her gun ayri), olmuyorsa kaba ayar
    #    (sadece hafta sonu). Ikisi birden uygulanmaz.
    ikinci_sapma = sapmalar()
    if len(gunler) >= HAFTA_GUNU_ICIN:
        kovalar = {}
        for g, sapma in ikinci_sapma:
            kovalar.setdefault(g["gun"], []).append(sapma)
        ham = {gun: sum(d) / len(d) for gun, d in kovalar.items()
               if len(d) >= EN_AZ_KARSILASTIRMA}
        if ham:
            # Ortalamalari 1'e olceklenir; yoksa gun katsayisi sicaklik
            # modelinin seviyesini topluca kaydirir.
            ortalama = sum(ham.values()) / len(ham)
            if ortalama > 0:
                model["gun_katsayilari"] = {
                    gun: _kirp(deger / ortalama, 0.5, 2.0) for gun, deger in ham.items()
                }
    if not model["gun_katsayilari"] and len(gunler) >= HAFTA_SONU_ICIN:
        sonu = [s for g, s in ikinci_sapma if g["gun"] >= 5]
        ici = [s for g, s in ikinci_sapma if g["gun"] < 5]
        if len(sonu) >= EN_AZ_KARSILASTIRMA and len(ici) >= EN_AZ_KARSILASTIRMA:
            oran = (sum(sonu) / len(sonu)) / (sum(ici) / len(ici))
            model["hafta_sonu_katsayisi"] = _kirp(oran, 0.4, 2.5)

    # 4. Ozel gun etiketleri. Hafta sonu yukarida islendiyse burada tekrar
    #    sayilmaz; islenmediyse etiket olarak buradan gecer.
    ucuncu_sapma = sapmalar()
    islenmis = set()
    if model["gun_katsayilari"] or model["hafta_sonu_katsayisi"] is not None:
        islenmis.add(takvim.HAFTA_SONU_ETIKET)

    kovalar = {}
    for g, sapma in ucuncu_sapma:
        for etiket in g["etiketler"] - islenmis:
            kovalar.setdefault(etiket, []).append(sapma)
    normaller = [s for g, s in ucuncu_sapma if not (g["etiketler"] - islenmis)]
    if len(normaller) >= EN_AZ_KARSILASTIRMA:
        normal_ortalama = sum(normaller) / len(normaller)
        for etiket, degerler in kovalar.items():
            if len(degerler) < EN_AZ_ETIKET_GUN or normal_ortalama <= 0:
                continue
            oran = (sum(degerler) / len(degerler)) / normal_ortalama
            model["etiket_katsayilari"][etiket] = (
                _kirp(oran, 0.2, 4.0), len(degerler))

    # Modelin gecmiste ne kadar yanildigi -> tahmin araligi bundan cikar
    hatalar = [abs(g["ciro"] - _uygula(model, g["sicaklik"], g["yagmurlu"],
                                       g["gun"], g["etiketler"]))
               for g in gunler]
    model["hata_payi"] = sum(hatalar) / len(hatalar) if hatalar else 0.0
    return model


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


def _uygula(model, sicaklik, yagmurlu, gun, etiketler=()):
    """Katsayilari sirayla uygular. Kismen kurulmus modelde de calisir."""
    if model["sicaklik"] and sicaklik is not None:
        deger = max(model["sicaklik"][0] * sicaklik + model["sicaklik"][1],
                    model["ortalama"] * 0.2)
    else:
        deger = model["ortalama"]

    if yagmurlu:
        deger *= model["yagmur_katsayisi"]

    return max(deger * _gun_carpani(model, gun, etiketler), 0.0)


def toplam_katsayi(model, gun, etiketler):
    """Havadan bagimsiz carpan: 'normalin kac kati' demek icin."""
    return _gun_carpani(model, gun, etiketler)


# ---------------------------------------------------------------- urun dagilimi

def urun_paylari(baglanti):
    """Her satilan urunun toplam cirodaki payi."""
    toplam = baglanti.execute(
        "SELECT COALESCE(SUM(tutar), 0) FROM satislar").fetchone()[0]
    if toplam <= 0:
        return {}
    return {
        satir["kalem_id"]: {
            "pay": satir["tutar"] / toplam,
            "ad": satir["ad"],
            "birim": satir["birim"],
            "fiyat": satir["fiyat"],
        }
        for satir in baglanti.execute(
            "SELECT s.kalem_id, SUM(s.tutar) AS tutar, k.ad, k.birim, k.fiyat"
            " FROM satislar s JOIN kalemler k ON k.id = s.kalem_id"
            " WHERE k.aktif = 1 GROUP BY s.kalem_id"
        )
    }


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
    """Onumuzdeki gunler icin 'kac parti uretmeli' onerisi."""
    toplam_ihtiyac = {}
    for tahmin in gun_tahminleri:
        for kalem_id, miktar in _uretim_ihtiyaci(baglanti, tahmin["urunler"]).items():
            toplam_ihtiyac[kalem_id] = toplam_ihtiyac.get(kalem_id, 0.0) + miktar

    stok = hesap.stoklar(baglanti)
    oneriler = []
    for kalem_id, gereken in sorted(toplam_ihtiyac.items(), key=lambda i: -i[1]):
        kalem = hesap.kalem(baglanti, kalem_id)
        if kalem is None:
            continue
        elde = stok.get(kalem_id, 0.0)
        acik = max(gereken - elde, 0.0)
        # Uretim tam kazanla yapiliyor; yarim/ceyrek parti onerilmez.
        parti = hesap.parti_onerisi(baglanti, kalem_id, acik)
        oneriler.append({
            "kalem": kalem,
            "gereken": gereken,
            "elde": elde,
            "acik": acik,
            "parti": parti["sayi"] if parti else 0,
            "parti_ad": parti["parti_ad"] if parti else "parti",
            "cikacak": parti["cikacak"] if parti else 0.0,
            "artacak": parti["artacak"] if parti else 0.0,
        })
    return oneriler


# ---------------------------------------------------------------- tahmin

def gun_tahmini(baglanti, tarih, model, paylar, etiketler=()):
    """Bir gunun tahmini: ciro araligi ve urun kirilimi."""
    hava_satiri = hava.gun(baglanti, tarih)
    gun_no = _tarihe_cevir(tarih).weekday()
    sicaklik = hava_satiri["en_yuksek"] if hava_satiri else None
    yagmurlu = bool(hava_satiri["yagmurlu"]) if hava_satiri else False

    ciro = _uygula(model, sicaklik, yagmurlu, gun_no, etiketler)
    pay_araligi = max(model["hata_payi"], ciro * 0.15)

    urunler = {
        kalem_id: ciro * bilgi["pay"] / bilgi["fiyat"]
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
                model, hava_satiri["en_yuksek"], bool(hava_satiri["yagmurlu"]),
                gun_no, {satir["etiket"]})
        sonuc.append(kayit)
    return sonuc


# ---------------------------------------------------------------- anlatim

def durum_metni(model, baglanti=None):
    """Modelin ne durumda oldugunu duz Turkce anlatir."""
    if model["gun_sayisi"] == 0:
        return (f"Henüz hiç satış kaydı yok. Tahmin, geçmiş günlerin hava durumu ile "
                f"o günün cirosunu karşılaştırarak öğreniyor; en az {EN_AZ_GUN} günlük "
                f"satış gerekiyor. Gün sonu satışlarını girmeye başladığında "
                f"kendiliğinden çalışacak — senin ayrıca bir şey yapman gerekmiyor, "
                f"her günün havası şimdiden kaydediliyor.")
    if not model["yeterli"]:
        return (f"{model['gun_sayisi']} günlük veri var, tahmin için en az {EN_AZ_GUN} "
                f"gün gerekiyor. {model['eksik_gun']} gün daha satış girildiğinde "
                f"tahminler burada görünmeye başlayacak.")

    parcalar = [f"{model['gun_sayisi']} günlük satış geçmişine bakıyor"]

    if model["sicaklik"]:
        parcalar.append(f"her 1 derece sıcaklık günlük ciroyu ortalama "
                        f"{model['sicaklik'][0]:,.0f} birim değiştiriyor"
                        .replace(",", "."))
    elif model["gun_sayisi"] < SICAKLIK_ICIN:
        parcalar.append(f"sıcaklık etkisi için {SICAKLIK_ICIN - model['gun_sayisi']} "
                        f"gün daha gerekiyor")
    elif model["sicaklik_araligi"] < EN_AZ_SICAKLIK_ARALIGI:
        parcalar.append(f"geçmiş günlerin hepsi birbirine yakın sıcaklıkta "
                        f"({model['sicaklik_araligi']:.1f} derece fark); sıcaklığın "
                        f"etkisini görmek için en az {EN_AZ_SICAKLIK_ARALIGI:.0f} "
                        f"derecelik fark gerekiyor")
    else:
        parcalar.append("sıcaklık ile satış arasında güvenilir bir ilişki bulunamadı, "
                        "şimdilik günlük ortalama kullanılıyor")

    if abs(model["yagmur_katsayisi"] - 1.0) > 0.01:
        yuzde = (model["yagmur_katsayisi"] - 1) * 100
        parcalar.append(f"yağmurlu günlerde satış %{abs(yuzde):.0f} "
                        f"{'artıyor' if yuzde > 0 else 'düşüyor'}")
    elif model["yagmurlu_gun"] < EN_AZ_KARSILASTIRMA:
        parcalar.append("yağmur etkisi için yeterli yağmurlu gün geçmedi")
    elif model["gun_sayisi"] - model["yagmurlu_gun"] < EN_AZ_KARSILASTIRMA:
        parcalar.append("neredeyse bütün günler yağışlı geçmiş, "
                        "karşılaştıracak kuru gün yok")

    if model["gun_katsayilari"]:
        en_iyi = max(model["gun_katsayilari"].items(), key=lambda i: i[1])
        parcalar.append(f"en yoğun gün {GUN_ADLARI[en_iyi[0]]} "
                        f"(normalin {en_iyi[1]:.2f} katı)")
    elif model["hafta_sonu_katsayisi"] is not None:
        kat = model["hafta_sonu_katsayisi"]
        parcalar.append(f"hafta sonu satışı hafta içinin {kat:.2f} katı"
                        f" (her güne ayrı katsayı için {HAFTA_GUNU_ICIN} gün gerekiyor)")
    else:
        parcalar.append(f"hafta sonu etkisi için {HAFTA_SONU_ICIN} gün gerekiyor")

    if model["etiket_katsayilari"]:
        for etiket, (kat, adet) in sorted(model["etiket_katsayilari"].items()):
            parcalar.append(f"{etiket}: normalin {kat:.2f} katı ({adet} güne bakarak)")
    else:
        parcalar.append("özel gün etkisi için henüz o günlerden geçilmedi")

    return " · ".join(parcalar) + "."
