# -*- coding: utf-8 -*-
"""Veritabani kurulumu, eski surumden goc ve hazir dukkan sablonlari.

Program tek bir kavram uzerine kurulu: KALEM. Dukkanda adi, birimi ve stogu
olan her sey bir kalemdir - sut de, dondurma da, kulah da, ekmek de.
Her kalemin uc rolu vardir, kullanici bunlari ekrandan isaretler:

    alinir   -> satin aliniyor   (Alim ekraninda cikar)
    uretilir -> recetesi var     (Uretim ekraninda cikar)
    satilir  -> satis fiyati var (Satis ekraninda cikar)

Bir kalem bunlarin birkacini birden tasiyabilir; kulah hem alinir hem satilir.
Recete = "bu kalemin bir biriminin icine hangi kalemlerden ne kadar giriyor".
Recetedeki malzemelerin ne zaman dusecegini rol belirler:

    uretilir isaretli  -> malzemeler URETIM girildiginde duser
    isaretli degil     -> malzemeler HER SATISTA duser

Boylece firinci ekmegi once uretir sonra satar, dondurmaci ise kulahi
satarken icine 60 gram dondurmayi ayni anda duser. Kod ikisini de bilmez;
farki kullanicinin isaretledigi kutucuk yaratir.

Stok, kasa ve borc hicbir zaman dogrudan bir kolonda tutulmaz; hepsi
"hareket" tablolarindaki satirlarin toplamidir. Boylece yanlis girilen bir
kayit silindiginde stok/kasa kendiliginden duzelir, gecmis de kaybolmaz.
"""

import datetime
import os
import shutil
import sqlite3

import takvim

KLASOR = os.path.dirname(os.path.abspath(__file__))

# Veritabani normalde kodun yanindaki klasorde durur - kendi bilgisayarinda
# calisirken dogrusu budur. Ama bir sunucuda kod klasoru her yeni surumde
# sifirdan kurulur; veritabani orada kalirsa her guncellemede butun kayitlar
# silinir. KAZAN_VERI ile kalici diskteki klasor gosterilir.
VERI_KLASORU = os.environ.get("KAZAN_VERI") or KLASOR

# Her dukkanin verisi KENDI dosyasindadir: dukkanlar/dukkan-1.db, dukkan-2.db...
# Iki dukkanin kaydi ayni dosyada hic bulunmadigi icin, koddaki bir hata
# yuzunden birinin otekinin cirosunu gormesi mumkun degildir. Kimin hangi
# dukkana girebilecegi hesaplar.py'deki ayri defterde tutulur.
DUKKAN_KLASORU = os.path.join(VERI_KLASORU, "dukkanlar")

# Tek dukkanli surumlerden kalan dosyalar. Ilk acilista dukkan 1'e tasinirlar.
TEK_DB_YOLU = os.path.join(VERI_KLASORU, "veri.db")
ESKI_DB_YOLU = os.path.join(VERI_KLASORU, "dondurma.db")


def db_yolu(dukkan_id):
    return os.path.join(DUKKAN_KLASORU, f"dukkan-{int(dukkan_id)}.db")

SEMA = """
CREATE TABLE IF NOT EXISTS kalemler (
    id            INTEGER PRIMARY KEY,
    ad            TEXT NOT NULL UNIQUE,
    birim         TEXT NOT NULL DEFAULT 'adet',
    aciklama      TEXT NOT NULL DEFAULT '',
    -- Sadece duzen icin: listeler bu basliklara gore gruplanir. Hicbir hesaba
    -- girmez, serbest metindir - dukkan kendi basliklarini yazar.
    tur           TEXT NOT NULL DEFAULT '',
    -- roller: kalem hangi ekranlarda gorunsun
    alinir        INTEGER NOT NULL DEFAULT 0,
    uretilir      INTEGER NOT NULL DEFAULT 0,
    satilir       INTEGER NOT NULL DEFAULT 0,
    -- 0 ise stogu tutulmaz: sebeke suyu gibi tukenmeyenler, ya da "kilo dondurma"
    -- gibi rafta durmayan, siparis aninda hazirlanan urunler.
    takip         INTEGER NOT NULL DEFAULT 1,
    birim_fiyat   REAL NOT NULL DEFAULT 0,   -- alis fiyati (bir birim icin)
    fiyat         REAL NOT NULL DEFAULT 0,   -- satis fiyati (bir birim icin)
    -- Toplu kap: "1 koli = 450 adet", "1 kutu = 5000 gram", "1 cuval = 50 kg".
    koli_adet     REAL NOT NULL DEFAULT 0,
    koli_ad       TEXT NOT NULL DEFAULT 'koli',
    kritik_seviye REAL NOT NULL DEFAULT 0,
    tedarikci     TEXT NOT NULL DEFAULT '',
    -- Gun sonu sayiminda bu kalem nasil girilsin:
    --   yok  : sayimda hic sorulmaz
    --   say  : rafta kalan miktar yazilir
    --   koli : "bir koli bitti" kutucugu (tek tek sayilmayanlar)
    --   elle : satilan miktar dogrudan yazilir (kilo ile satis gibi)
    sayim_tarzi   TEXT NOT NULL DEFAULT 'yok',
    -- Satilmayan ama harcanan malzeme (kasik, pecete): tutari o gunun
    -- satislarina paylastirilsin mi.
    dagit         INTEGER NOT NULL DEFAULT 0,
    sira          INTEGER NOT NULL DEFAULT 0,
    aktif         INTEGER NOT NULL DEFAULT 1,
    -- 1: kalemi menu gecisi kapatti (kis menusunde kavunlu gibi). Menu
    -- degisince yalnizca bunlar geri acilir; elle kapatilan kapali kalir.
    mevsim_disi   INTEGER NOT NULL DEFAULT 0
);

-- Bir kalemin birden fazla recetesi olabilir: dondurma ayni stoga girer ama
-- Sade/Cikolata/Cilek farkli malzemelerden yapilir.
CREATE TABLE IF NOT EXISTS receteler (
    id       INTEGER PRIMARY KEY,
    urun_id  INTEGER NOT NULL REFERENCES kalemler(id) ON DELETE CASCADE,
    ad       TEXT NOT NULL DEFAULT '',
    -- Bir uretimden kac birim cikar. Recete toplamindan hesaplanmaz; cirpmada
    -- hava girer, firinda su ucar. Satilan (uretilmeyen) kalemlerde 1'dir.
    verim    REAL NOT NULL DEFAULT 1,
    -- Bir uretime dukkanin verdigi ad: kazan, tepsi, firin, tencere.
    parti_ad TEXT NOT NULL DEFAULT 'parti',
    sira     INTEGER NOT NULL DEFAULT 0,
    aktif    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS recete_satirlari (
    id        INTEGER PRIMARY KEY,
    recete_id INTEGER NOT NULL REFERENCES receteler(id) ON DELETE CASCADE,
    kalem_id  INTEGER NOT NULL REFERENCES kalemler(id),
    miktar    REAL NOT NULL,
    UNIQUE (recete_id, kalem_id)
);

CREATE TABLE IF NOT EXISTS uretimler (
    id           INTEGER PRIMARY KEY,
    tarih        TEXT NOT NULL,
    recete_id    INTEGER REFERENCES receteler(id),
    kalem_id     INTEGER NOT NULL REFERENCES kalemler(id),
    sayi         REAL NOT NULL,     -- kac parti/kazan/tepsi
    miktar       REAL NOT NULL,     -- kalemin biriminden kac birim cikti
    maliyet      REAL NOT NULL,
    kayit_zamani TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS satislar (
    id           INTEGER PRIMARY KEY,
    tarih        TEXT NOT NULL,
    kalem_id     INTEGER NOT NULL REFERENCES kalemler(id),
    miktar       REAL NOT NULL,
    tutar        REAL NOT NULL,
    maliyet      REAL NOT NULL,
    -- Gun sonu sayimindan turetildiyse hangi sayimdan geldigi
    sayim_id     INTEGER REFERENCES sayimlar(id),
    kayit_zamani TEXT NOT NULL
);

-- Gun sonu sayimi: raflarda ne kaldigini yazarsin, program ne satildigini bulur.
CREATE TABLE IF NOT EXISTS sayimlar (
    id           INTEGER PRIMARY KEY,
    tarih        TEXT NOT NULL UNIQUE,
    kayit_zamani TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sayim_satirlari (
    id       INTEGER PRIMARY KEY,
    sayim_id INTEGER NOT NULL REFERENCES sayimlar(id) ON DELETE CASCADE,
    kalem_id INTEGER NOT NULL REFERENCES kalemler(id),
    koli     REAL NOT NULL DEFAULT 0,
    adet     REAL NOT NULL DEFAULT 0,
    kalan    REAL NOT NULL DEFAULT 0,
    tuketim  REAL NOT NULL DEFAULT 0,
    UNIQUE (sayim_id, kalem_id)
);

CREATE TABLE IF NOT EXISTS alimlar (
    id           INTEGER PRIMARY KEY,
    tarih        TEXT NOT NULL,
    kalem_id     INTEGER NOT NULL REFERENCES kalemler(id),
    miktar       REAL NOT NULL,
    tutar        REAL NOT NULL,
    odeme        TEXT NOT NULL DEFAULT 'veresiye',
    tedarikci    TEXT NOT NULL DEFAULT '',
    kayit_zamani TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS giderler (
    id           INTEGER PRIMARY KEY,
    tarih        TEXT NOT NULL,
    aciklama     TEXT NOT NULL DEFAULT '',
    tutar        REAL NOT NULL,
    kayit_zamani TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS odemeler (
    id           INTEGER PRIMARY KEY,
    tarih        TEXT NOT NULL,
    tedarikci    TEXT NOT NULL DEFAULT '',
    tutar        REAL NOT NULL,
    kayit_zamani TEXT NOT NULL
);

-- Dukkanda calisanlar. Bu tablo bir kayit defteri; kendi basina para
-- hareketi dogurmaz. Maas ancak "maaslari gidere yaz" dendiginde giderler
-- tablosuna dusen normal bir gider satiri olur - boylece bir ay iki kere
-- yazilmaz, silinen maas da kasadan kendiliginden geri doner.
CREATE TABLE IF NOT EXISTS calisanlar (
    id        INTEGER PRIMARY KEY,
    ad        TEXT NOT NULL,
    gorev     TEXT NOT NULL DEFAULT '',
    telefon   TEXT NOT NULL DEFAULT '',
    -- Calisanin eline gecen aylik net ucret.
    maas      REAL NOT NULL DEFAULT 0,
    -- Ustune isverenin odedigi SGK + vergi payi. Ikisinin toplami dukkana
    -- aylik gercek maliyettir; gidere de bu toplam yazilir.
    sgk       REAL NOT NULL DEFAULT 0,
    baslangic TEXT NOT NULL DEFAULT '',   -- ise giris
    ayrilis   TEXT NOT NULL DEFAULT '',   -- bos ise hala calisiyor
    notlar    TEXT NOT NULL DEFAULT '',
    aktif     INTEGER NOT NULL DEFAULT 1,
    sira      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stok_hareketleri (
    id         INTEGER PRIMARY KEY,
    tarih      TEXT NOT NULL,
    kalem_id   INTEGER NOT NULL REFERENCES kalemler(id),
    miktar     REAL NOT NULL,
    sebep      TEXT NOT NULL DEFAULT '',
    kaynak_tur TEXT NOT NULL DEFAULT '',
    kaynak_id  INTEGER
);

CREATE TABLE IF NOT EXISTS kasa_hareketleri (
    id         INTEGER PRIMARY KEY,
    tarih      TEXT NOT NULL,
    tutar      REAL NOT NULL,
    aciklama   TEXT NOT NULL DEFAULT '',
    kaynak_tur TEXT NOT NULL DEFAULT '',
    kaynak_id  INTEGER
);

CREATE TABLE IF NOT EXISTS borc_hareketleri (
    id         INTEGER PRIMARY KEY,
    tarih      TEXT NOT NULL,
    tedarikci  TEXT NOT NULL DEFAULT '',
    tutar      REAL NOT NULL,
    aciklama   TEXT NOT NULL DEFAULT '',
    kaynak_tur TEXT NOT NULL DEFAULT '',
    kaynak_id  INTEGER
);

-- Gunluk hava kaydi. Ileri tarihler tahmin, gecmis tarihler gerceklesen deger;
-- gun gectikce tahmin satirinin uzerine gerceklesen yazilir. Satis tahmini bu
-- tablodaki gecmis satirlarla o gunun cirosunu karsilastirarak ogrenir.
CREATE TABLE IF NOT EXISTS hava (
    tarih       TEXT PRIMARY KEY,
    en_yuksek   REAL,
    en_dusuk    REAL,
    yagis       REAL,          -- mm; MGM mm vermedigi icin bos olabilir
    ruzgar      REAL,          -- km/s
    nem         REAL,          -- %
    hadise      TEXT NOT NULL DEFAULT '',   -- 'A', 'PB', 'GSY' gibi MGM kodu
    yagmurlu    INTEGER NOT NULL DEFAULT 0,
    yagis_ihtimal REAL,        -- %; MGM vermez, Open-Meteo'dan gelir
    tahmin      INTEGER NOT NULL DEFAULT 1, -- 1: henuz gerceklesmedi
    kaynak      TEXT NOT NULL DEFAULT '',
    guncelleme  TEXT NOT NULL DEFAULT ''
);

-- Ozel gunler ve donemler: resmi tatiller, dini bayramlar, findik toplama gibi
-- satisi normalden farkli yapan zamanlar. Model her ETIKET icin tek bir katsayi
-- ogrenir; ayni etiketi paylasan satirlar ayni havuza girer.
CREATE TABLE IF NOT EXISTS ozel_gunler (
    id        INTEGER PRIMARY KEY,
    ad        TEXT NOT NULL,
    etiket    TEXT NOT NULL,
    baslangic TEXT NOT NULL,
    bitis     TEXT NOT NULL,
    aktif     INTEGER NOT NULL DEFAULT 1,
    -- 'resmi' ve 'dini' satirlari program uretir, 'elle' olanlar kullanicinin
    kaynak    TEXT NOT NULL DEFAULT 'elle',
    UNIQUE (ad, baslangic)
);

CREATE INDEX IF NOT EXISTS ix_ozel_tarih ON ozel_gunler (baslangic, bitis);

CREATE TABLE IF NOT EXISTS ayarlar (
    anahtar TEXT PRIMARY KEY,
    deger   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_stok_kalem   ON stok_hareketleri (kalem_id);
CREATE INDEX IF NOT EXISTS ix_stok_kaynak  ON stok_hareketleri (kaynak_tur, kaynak_id);
CREATE INDEX IF NOT EXISTS ix_satis_tarih  ON satislar (tarih);
CREATE INDEX IF NOT EXISTS ix_uretim_tarih ON uretimler (tarih);
CREATE INDEX IF NOT EXISTS ix_recete_urun  ON receteler (urun_id);

-- Menu donemleri: "Yaz menusu", "Kis menusu". Bir menu, o donemde satilan
-- urunlerin listesidir. Hicbir menude olmayan urun her zaman satilir (kulah,
-- pet su); bir menude olan urun ancak o menu gecerliyken acik kalir.
-- kosul/esik gecis onerisi icindir: 'soguk' menu hava esigin altina inince,
-- 'sicak' menu ustune cikinca onerilir. Bos kosul "sadece elle gecerim".
CREATE TABLE IF NOT EXISTS menuler (
    id    INTEGER PRIMARY KEY,
    ad    TEXT NOT NULL UNIQUE,
    kosul TEXT NOT NULL DEFAULT '',
    esik  REAL NOT NULL DEFAULT 0,
    sira  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS menu_kalemleri (
    menu_id  INTEGER NOT NULL REFERENCES menuler(id) ON DELETE CASCADE,
    kalem_id INTEGER NOT NULL REFERENCES kalemler(id) ON DELETE CASCADE,
    PRIMARY KEY (menu_id, kalem_id)
);

-- Hangi gun hangi menuye gecildi. Gecerli menu en son satirdir; gecmis de
-- durur ki "gecen yil kisa ne zaman gecmistik" sorusu cevaplanabilsin.
CREATE TABLE IF NOT EXISTS menu_gecisleri (
    id           INTEGER PRIMARY KEY,
    tarih        TEXT NOT NULL,
    menu_id      INTEGER NOT NULL REFERENCES menuler(id) ON DELETE CASCADE,
    kayit_zamani TEXT NOT NULL DEFAULT ''
);
"""

VARSAYILAN_AYARLAR = {
    "dukkan_adi": "Dükkanım",
    "para_birimi": "TL",
    # 'sayim'    : gun sonunda rafta kalan sayilir, satis oradan bulunur
    # 'dogrudan' : satislar tek tek / toplu olarak elle girilir
    # 'ikisi'    : iki ekran da menude durur
    "satis_girisi": "ikisi",
    "uyari_gun": "2",         # kac gunluk kalinca "Yapman gerekenler"e dussun
    "dolum_gun": "7",         # alim/uretim onerisi kac gunluk olsun
    "ortalama_gun": "14",     # gunluk tuketim kac gunun ortalamasindan hesaplansin
    "kurulum_bitti": "0",
    # Hava ve tahmin. Sehir secilmeden hicbir aga cikilmaz; program tamamen
    # cevrimdisi calismaya devam eder.
    "sehir": "",
    "mgm_istno": "",
    "enlem": "",
    "boylam": "",
    "hava_kaynak": "mgm+arsiv",   # 'mgm+arsiv' | 'mgm' | 'openmeteo'
    "hava_son_kontrol": "",
    "tahmin_acik": "1",
}


# ---------------------------------------------------------------- yardimcilar

def baglan(dukkan_id=1):
    """Bir dukkanin veri dosyasini acar.

    Programin geri kalani bu baglantiyi parametre olarak alir ve hangi
    dukkanda oldugunu hic bilmez. Cok dukkanli calismanin butun sirri
    burada: dogru dosyayi acmak yeterli, sorgularin hicbiri degismez.
    """
    baglanti = sqlite3.connect(db_yolu(dukkan_id))
    baglanti.row_factory = sqlite3.Row
    baglanti.execute("PRAGMA foreign_keys = ON")
    return baglanti


def sayi(metin, varsayilan=0.0):
    """'7,5' ve '7.5' yazimlarinin ikisini de kabul eder."""
    if metin is None:
        return varsayilan
    if isinstance(metin, (int, float)):
        return float(metin)
    temiz = str(metin).strip().replace(" ", "").replace(",", ".")
    if not temiz:
        return varsayilan
    try:
        return float(temiz)
    except ValueError:
        return varsayilan


def ayar(baglanti, anahtar, varsayilan=""):
    satir = baglanti.execute(
        "SELECT deger FROM ayarlar WHERE anahtar = ?", (anahtar,)
    ).fetchone()
    return satir["deger"] if satir else varsayilan


def ayar_yaz(baglanti, anahtar, deger):
    baglanti.execute(
        "INSERT INTO ayarlar (anahtar, deger) VALUES (?, ?)"
        " ON CONFLICT(anahtar) DO UPDATE SET deger = excluded.deger",
        (anahtar, str(deger)),
    )


# Yeni surumlerde eklenen kolonlar. Mevcut veritabanlari acilirken tamamlanir;
# CREATE TABLE IF NOT EXISTS eski tabloya kolon eklemez.
SONRADAN_EKLENENLER = {
    "kalemler": {"tur": "TEXT NOT NULL DEFAULT ''",
                 "mevsim_disi": "INTEGER NOT NULL DEFAULT 0"},
    "hava": {"yagis_ihtimal": "REAL"},
}


def _tablolar(baglanti):
    return {
        satir["name"]
        for satir in baglanti.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


def _kolonlar(baglanti, tablo):
    return {satir["name"] for satir in baglanti.execute(f"PRAGMA table_info({tablo})")}


def _kolonlari_tamamla(baglanti):
    """Onceki surumlerde olusturulmus tablolara yeni kolonlari ekler."""
    for tablo, kolonlar in SONRADAN_EKLENENLER.items():
        if tablo not in _tablolar(baglanti):
            continue
        mevcut = _kolonlar(baglanti, tablo)
        for kolon, tanim in kolonlar.items():
            if kolon not in mevcut:
                baglanti.execute(f"ALTER TABLE {tablo} ADD COLUMN {kolon} {tanim}")
    baglanti.commit()


# ---------------------------------------------------------------- hazir sablonlar

def _k(ad, birim="adet", **ek):
    """Bir kalem tanimi; yazilmayan alanlar varsayilaninda kalir."""
    kayit = {
        "ad": ad, "birim": birim, "aciklama": "", "tur": "", "alinir": 0, "uretilir": 0,
        "satilir": 0, "takip": 1, "birim_fiyat": 0.0, "fiyat": 0.0,
        "koli_adet": 0.0, "koli_ad": "koli", "kritik_seviye": 0.0, "tedarikci": "",
        "sayim_tarzi": "yok", "dagit": 0, "sira": 0, "aktif": 1,
    }
    kayit.update(ek)
    return kayit


# Sablonlar sadece baslangic verisidir. Kullanici her seyi ekrandan degistirir,
# siler, yenisini ekler; program hicbirini ozel olarak tanimaz.
SABLONLAR = {
    "dondurmaci": {
        "ad": "Dondurmacı",
        "dukkan": "Dondurma Dükkanı",
        "aciklama": "Kazanda dondurma üretimi, külah/kap ile satış, gün sonu sayımı.",
        "satis_girisi": "sayim",
        "kalemler": [
            _k("Su", "litre", tur="Hammadde", alinir=1, takip=0),
            _k("Süt", "litre", tur="Hammadde", alinir=1, birim_fiyat=32, kritik_seviye=100),
            _k("Şeker", "kg", tur="Hammadde", alinir=1, birim_fiyat=38, kritik_seviye=25,
               koli_adet=50, koli_ad="çuval"),
            _k("Sahlep", "kg", tur="Hammadde", alinir=1, birim_fiyat=900, kritik_seviye=1),
            _k("Vanilya", "kg", tur="Hammadde", alinir=1, birim_fiyat=1200, kritik_seviye=0.05),
            _k("Aroma - Çikolata", "kg", tur="Hammadde", alinir=1, birim_fiyat=480,
               kritik_seviye=2),
            _k("Aroma - Çilek", "kg", tur="Hammadde", alinir=1, birim_fiyat=470,
               kritik_seviye=2),
            _k("Aroma - Limon", "kg", tur="Hammadde", alinir=1, birim_fiyat=460,
               kritik_seviye=2),
            _k("Dondurma", "gram", tur="Ara ürün", uretilir=1, koli_adet=5000,
               koli_ad="kutu", sayim_tarzi="say",
               aciklama="Dolapta bekleyen hazır dondurma"),
            _k("Külah", tur="Ürün", alinir=1, satilir=1, birim_fiyat=2.5, fiyat=60,
               koli_adet=450, kritik_seviye=900, sayim_tarzi="say", sira=1),
            _k("Cornette Külah", tur="Ürün", alinir=1, satilir=1, birim_fiyat=6, fiyat=70,
               koli_adet=180, kritik_seviye=360, sayim_tarzi="say", sira=2),
            _k("Küçük Kap", tur="Ürün", alinir=1, satilir=1, birim_fiyat=4, fiyat=120,
               koli_adet=250, kritik_seviye=500, sayim_tarzi="say", sira=3),
            _k("Orta Kap", tur="Ürün", alinir=1, satilir=1, birim_fiyat=5, fiyat=150,
               koli_adet=200, kritik_seviye=400, sayim_tarzi="say", sira=4),
            _k("Büyük Kap", tur="Ürün", alinir=1, satilir=1, birim_fiyat=7, fiyat=200,
               koli_adet=150, kritik_seviye=300, sayim_tarzi="say", sira=5),
            _k("Kilo Dondurma", "kg", tur="Ürün", satilir=1, takip=0, fiyat=1000,
               sayim_tarzi="elle", sira=6,
               aciklama="Kaba konan miktar değişken; kaç kg sattığın elle yazılır"),
            _k("Pet Şişe Su (0,5 lt)", tur="Ürün", alinir=1, satilir=1, birim_fiyat=6,
               fiyat=20, koli_adet=24, kritik_seviye=48, sayim_tarzi="say", sira=7),
            _k("Kilo Kabı", tur="Ambalaj", alinir=1, birim_fiyat=20, koli_adet=50,
               kritik_seviye=50, sayim_tarzi="say", dagit=1),
            _k("Kaşık", tur="Sarf", alinir=1, birim_fiyat=0.4, koli_adet=1000,
               kritik_seviye=1000, sayim_tarzi="koli", dagit=1),
            _k("Peçete", "kutu", tur="Sarf", alinir=1, birim_fiyat=30, koli_adet=1,
               kritik_seviye=3, sayim_tarzi="koli", dagit=1),
            _k("Islak Mendil", tur="Sarf", alinir=1, birim_fiyat=1.2, koli_adet=1000,
               kritik_seviye=1000, sayim_tarzi="koli", dagit=1),
        ],
        "receteler": [
            {"urun": "Dondurma", "ad": "Sade", "verim": 122000, "parti_ad": "kazan",
             "satirlar": [("Süt", 100), ("Şeker", 21), ("Sahlep", 0.875), ("Vanilya", 0.005)]},
            {"urun": "Dondurma", "ad": "Çikolata", "verim": 9000, "parti_ad": "kazan",
             "satirlar": [("Süt", 6), ("Şeker", 1), ("Aroma - Çikolata", 2)]},
            {"urun": "Dondurma", "ad": "Çilek", "verim": 9000, "parti_ad": "kazan",
             "satirlar": [("Süt", 6), ("Şeker", 1), ("Aroma - Çilek", 2)]},
            {"urun": "Dondurma", "ad": "Limon", "verim": 9000, "parti_ad": "kazan",
             "satirlar": [("Süt", 6), ("Şeker", 1), ("Aroma - Limon", 2)]},
            {"urun": "Külah", "satirlar": [("Dondurma", 60)]},
            {"urun": "Cornette Külah", "satirlar": [("Dondurma", 120)]},
            {"urun": "Küçük Kap", "satirlar": [("Dondurma", 120)]},
            {"urun": "Orta Kap", "satirlar": [("Dondurma", 200)]},
            {"urun": "Büyük Kap", "satirlar": [("Dondurma", 250)]},
            {"urun": "Kilo Dondurma", "satirlar": [("Dondurma", 1000)]},
        ],
    },
    "pastane": {
        "ad": "Pastane",
        "dukkan": "Pastane",
        "aciklama": "Pandispanya/krema gibi ara ürünler, dilim ve bütün pasta satışı.",
        "satis_girisi": "dogrudan",
        "kalemler": [
            _k("Un", "kg", tur="Hammadde", alinir=1, birim_fiyat=18, koli_adet=50,
               koli_ad="çuval", kritik_seviye=25),
            _k("Toz Şeker", "kg", tur="Hammadde", alinir=1, birim_fiyat=38, kritik_seviye=20),
            _k("Yumurta", tur="Hammadde", alinir=1, birim_fiyat=6, koli_adet=30,
               koli_ad="viyol", kritik_seviye=60),
            _k("Tereyağı", "kg", tur="Hammadde", alinir=1, birim_fiyat=420, kritik_seviye=5),
            _k("Süt", "litre", tur="Hammadde", alinir=1, birim_fiyat=32, kritik_seviye=20),
            _k("Krema", "litre", tur="Hammadde", alinir=1, birim_fiyat=180, kritik_seviye=10),
            _k("Kakao", "kg", tur="Hammadde", alinir=1, birim_fiyat=350, kritik_seviye=2),
            _k("Çilek", "kg", tur="Hammadde", alinir=1, birim_fiyat=120, kritik_seviye=3),
            _k("Pasta Kutusu", tur="Ambalaj", alinir=1, birim_fiyat=12, koli_adet=100,
               kritik_seviye=50, sayim_tarzi="say", dagit=1),
            _k("Pandispanya", "adet", tur="Ara ürün", uretilir=1, sayim_tarzi="say",
               aciklama="Pastanın tabanı"),
            _k("Çikolatalı Krema", "kg", tur="Ara ürün", uretilir=1, sayim_tarzi="say"),
            _k("Yaş Pasta", "adet", tur="Ürün", uretilir=1, satilir=1, fiyat=900,
               sayim_tarzi="say", sira=1),
            _k("Dilim Yaş Pasta", "dilim", tur="Ürün", satilir=1, takip=0, fiyat=140,
               sayim_tarzi="elle", sira=2),
            _k("Kurabiye", "kg", tur="Ürün", uretilir=1, satilir=1, fiyat=600,
               sayim_tarzi="say", sira=3),
        ],
        "receteler": [
            {"urun": "Pandispanya", "ad": "Pandispanya", "verim": 6, "parti_ad": "tepsi",
             "satirlar": [("Un", 1.2), ("Toz Şeker", 1.2), ("Yumurta", 24)]},
            {"urun": "Çikolatalı Krema", "ad": "Çikolatalı krema", "verim": 5,
             "parti_ad": "tencere",
             "satirlar": [("Krema", 3), ("Toz Şeker", 1), ("Kakao", 0.4), ("Süt", 1)]},
            {"urun": "Yaş Pasta", "ad": "Yaş pasta", "verim": 4, "parti_ad": "parti",
             "satirlar": [("Pandispanya", 4), ("Çikolatalı Krema", 3), ("Çilek", 1)]},
            {"urun": "Kurabiye", "ad": "Kurabiye", "verim": 8, "parti_ad": "fırın",
             "satirlar": [("Un", 4), ("Tereyağı", 2), ("Toz Şeker", 1.5), ("Yumurta", 6)]},
            {"urun": "Dilim Yaş Pasta", "satirlar": [("Yaş Pasta", 0.125)]},
        ],
    },
    "firin": {
        "ad": "Fırın",
        "dukkan": "Fırın",
        "aciklama": "Hamurdan ekmek/simit/poğaça üretimi, raftaki kalanı sayarak satış.",
        "satis_girisi": "sayim",
        "kalemler": [
            _k("Un", "kg", tur="Hammadde", alinir=1, birim_fiyat=18, koli_adet=50,
               koli_ad="çuval", kritik_seviye=100),
            _k("Maya", "kg", tur="Hammadde", alinir=1, birim_fiyat=90, kritik_seviye=3),
            _k("Tuz", "kg", tur="Hammadde", alinir=1, birim_fiyat=12, kritik_seviye=5),
            _k("Su", "litre", tur="Hammadde", alinir=1, takip=0),
            _k("Susam", "kg", tur="Hammadde", alinir=1, birim_fiyat=140, kritik_seviye=3),
            _k("Pekmez", "kg", tur="Hammadde", alinir=1, birim_fiyat=95, kritik_seviye=2),
            _k("Peynir", "kg", tur="Hammadde", alinir=1, birim_fiyat=280, kritik_seviye=3),
            _k("Ekmek Poşeti", tur="Ambalaj", alinir=1, birim_fiyat=0.6, koli_adet=1000,
               kritik_seviye=500, sayim_tarzi="koli", dagit=1),
            _k("Ekmek", "adet", tur="Ürün", uretilir=1, satilir=1, fiyat=15,
               sayim_tarzi="say", sira=1),
            _k("Simit", "adet", tur="Ürün", uretilir=1, satilir=1, fiyat=20,
               sayim_tarzi="say", sira=2),
            _k("Peynirli Poğaça", "adet", tur="Ürün", uretilir=1, satilir=1, fiyat=35,
               sayim_tarzi="say", sira=3),
        ],
        "receteler": [
            {"urun": "Ekmek", "ad": "Ekmek hamuru", "verim": 120, "parti_ad": "tekne",
             "satirlar": [("Un", 50), ("Su", 32), ("Maya", 1), ("Tuz", 1)]},
            {"urun": "Simit", "ad": "Simit hamuru", "verim": 100, "parti_ad": "tekne",
             "satirlar": [("Un", 25), ("Su", 15), ("Maya", 0.6), ("Tuz", 0.5),
                          ("Susam", 3), ("Pekmez", 1.5)]},
            {"urun": "Peynirli Poğaça", "ad": "Poğaça", "verim": 60, "parti_ad": "tepsi",
             "satirlar": [("Un", 10), ("Su", 5), ("Maya", 0.3), ("Tuz", 0.2),
                          ("Peynir", 3)]},
        ],
    },
    "restoran": {
        "ad": "Restoran",
        "dukkan": "Restoran",
        "aciklama": "Porsiyon reçeteleri; satışlar adisyondan doğrudan girilir.",
        "satis_girisi": "dogrudan",
        "kalemler": [
            # Restoranda "hammadde" tek basliga sigmiyor; turler dukkana gore yazilir.
            _k("Kıyma", "kg", tur="Et", alinir=1, birim_fiyat=520, kritik_seviye=10),
            _k("Tavuk But", "kg", tur="Et", alinir=1, birim_fiyat=180, kritik_seviye=10),
            _k("Domates", "kg", tur="Sebze", alinir=1, birim_fiyat=35, kritik_seviye=10),
            _k("Soğan", "kg", tur="Sebze", alinir=1, birim_fiyat=20, kritik_seviye=10),
            _k("Pirinç", "kg", tur="Kuru gıda", alinir=1, birim_fiyat=60, kritik_seviye=20),
            _k("Mercimek", "kg", tur="Kuru gıda", alinir=1, birim_fiyat=48, kritik_seviye=10),
            _k("Ayçiçek Yağı", "litre", tur="Kuru gıda", alinir=1, birim_fiyat=75,
               kritik_seviye=10),
            _k("Lavaş", "adet", tur="Kuru gıda", alinir=1, birim_fiyat=6, koli_adet=50,
               kritik_seviye=100, sayim_tarzi="say"),
            _k("Peçete", "paket", tur="Sarf", alinir=1, birim_fiyat=25, koli_adet=1,
               kritik_seviye=5, sayim_tarzi="koli", dagit=1),
            _k("Adana Porsiyon", "porsiyon", tur="Yemek", satilir=1, takip=0, fiyat=380,
               sayim_tarzi="elle", sira=1),
            _k("Tavuk Şiş", "porsiyon", tur="Yemek", satilir=1, takip=0, fiyat=320,
               sayim_tarzi="elle", sira=2),
            _k("Mercimek Çorbası", "kase", tur="Yemek", satilir=1, takip=0, fiyat=110,
               sayim_tarzi="elle", sira=3),
            _k("Ayran (kutu)", "adet", tur="İçecek", alinir=1, satilir=1, birim_fiyat=9,
               fiyat=30, koli_adet=24, kritik_seviye=48, sayim_tarzi="say", sira=4),
        ],
        "receteler": [
            {"urun": "Adana Porsiyon",
             "satirlar": [("Kıyma", 0.18), ("Soğan", 0.05), ("Domates", 0.1),
                          ("Lavaş", 1), ("Ayçiçek Yağı", 0.02)]},
            {"urun": "Tavuk Şiş",
             "satirlar": [("Tavuk But", 0.22), ("Soğan", 0.05), ("Domates", 0.1),
                          ("Lavaş", 1), ("Pirinç", 0.1)]},
            {"urun": "Mercimek Çorbası",
             "satirlar": [("Mercimek", 0.08), ("Soğan", 0.02), ("Ayçiçek Yağı", 0.01)]},
        ],
    },
    "bos": {
        "ad": "Boş başla",
        "dukkan": "Dükkanım",
        "aciklama": "Hiçbir şey eklenmez; malzemeleri ve ürünleri sen girersin.",
        "satis_girisi": "ikisi",
        "kalemler": [],
        "receteler": [],
    },
}


def sablon_uygula(baglanti, anahtar):
    """Secilen sablonun kalemlerini ve recetelerini bos veritabanina yazar."""
    sablon = SABLONLAR.get(anahtar)
    if sablon is None:
        return False

    kimlikler = {}
    for kalem in sablon["kalemler"]:
        alanlar = ", ".join(kalem)
        isaretler = ", ".join("?" * len(kalem))
        baglanti.execute(
            f"INSERT OR IGNORE INTO kalemler ({alanlar}) VALUES ({isaretler})",
            tuple(kalem.values()),
        )
        kimlikler[kalem["ad"]] = baglanti.execute(
            "SELECT id FROM kalemler WHERE ad = ?", (kalem["ad"],)
        ).fetchone()["id"]

    for sira, recete in enumerate(sablon["receteler"]):
        urun_id = kimlikler.get(recete["urun"])
        if not urun_id:
            continue
        recete_id = baglanti.execute(
            "INSERT INTO receteler (urun_id, ad, verim, parti_ad, sira) VALUES (?, ?, ?, ?, ?)",
            (urun_id, recete.get("ad", ""), recete.get("verim", 1),
             recete.get("parti_ad", "parti"), sira),
        ).lastrowid
        for malzeme_adi, miktar in recete["satirlar"]:
            malzeme_id = kimlikler.get(malzeme_adi)
            if malzeme_id:
                baglanti.execute(
                    "INSERT OR IGNORE INTO recete_satirlari (recete_id, kalem_id, miktar)"
                    " VALUES (?, ?, ?)",
                    (recete_id, malzeme_id, miktar),
                )

    ayar_yaz(baglanti, "dukkan_adi", sablon["dukkan"])
    ayar_yaz(baglanti, "satis_girisi", sablon["satis_girisi"])
    ayar_yaz(baglanti, "kurulum_bitti", "1")
    baglanti.commit()
    return True


# ---------------------------------------------------------------- eski surumden goc

def _eski_surum_mu(baglanti):
    tablolar = _tablolar(baglanti)
    return "malzemeler" in tablolar and "kalemler" not in tablolar


def _cok_eski_kolonlari_duzelt(baglanti):
    """Daha da eski surumleri once son 'malzemeler' duzenine getirir.

    Ilk surumler dondurma stogunu 'top' ile tutuyordu. Kaplarin gram/top orani
    birbirini tutmadigi icin hesap grama cevrilmisti; o gunun 'bir top kac gram'
    ayariyla eski kayitlar da grama donusturulur.
    """
    eksikler = {
        "malzemeler": {
            "takip": "INTEGER NOT NULL DEFAULT 1",
            "tur": "TEXT NOT NULL DEFAULT 'hammadde'",
            "koli_adet": "REAL NOT NULL DEFAULT 0",
        },
        "satislar": {"sayim_id": "INTEGER"},
    }
    for tablo, kolonlar in eksikler.items():
        mevcut = _kolonlar(baglanti, tablo)
        for kolon, tanim in kolonlar.items():
            if kolon not in mevcut:
                baglanti.execute(f"ALTER TABLE {tablo} ADD COLUMN {kolon} {tanim}")

    top_gram = sayi(ayar(baglanti, "top_gram", ""), 0) or 75.0
    for tablo in ("dondurma_hareketleri", "uretimler", "satislar"):
        mevcut = _kolonlar(baglanti, tablo)
        if "top" in mevcut and "gram" not in mevcut:
            baglanti.execute(f"ALTER TABLE {tablo} RENAME COLUMN top TO gram")
            baglanti.execute(f"UPDATE {tablo} SET gram = gram * ?", (top_gram,))

    if "gram" not in _kolonlar(baglanti, "satis_sekilleri"):
        baglanti.execute("ALTER TABLE satis_sekilleri ADD COLUMN gram REAL NOT NULL DEFAULT 0")
        baglanti.execute("UPDATE satis_sekilleri SET gram = top_sayisi * ?", (top_gram,))
    baglanti.commit()


def _goc(baglanti):
    """Malzeme/karisim/satis-sekli uclusunu tek 'kalem' duzenine tasir.

    Eski surumde ayni sey iki yerde duruyordu: 'Kulah' hem bir ambalaj
    malzemesiydi hem de bir satis sekli. Yeni duzende bunlar tek kalem olur;
    kulah hem alinan hem satilan bir seydir. Kilo satisi gibi kendi stogu
    olmayanlar ise ayri bir kalem olarak acilir.
    """
    _cok_eski_kolonlari_duzelt(baglanti)
    eski = {
        tablo: [dict(satir) for satir in baglanti.execute(f"SELECT * FROM {tablo}")]
        for tablo in ("malzemeler", "karisimlar", "receteler", "satis_sekilleri",
                      "uretimler", "satislar", "alimlar", "sayim_satirlari",
                      "stok_hareketleri", "dondurma_hareketleri")
        if tablo in _tablolar(baglanti)
    }
    eski.setdefault("dondurma_hareketleri", [])

    baglanti.execute("PRAGMA foreign_keys = OFF")
    for tablo in list(eski):
        baglanti.execute(f"ALTER TABLE {tablo} RENAME TO goc_{tablo}")
    baglanti.executescript(SEMA)

    kutu_kg = sayi(ayar(baglanti, "kutu_kg", "5"), 5)

    # Bir ambalaj, adet ile satilan bir satis seklinde birebir kullaniliyorsa
    # ikisi ayni kalemdir. Ayni ambalaji paylasan ikinci satis sekli ayri kalir.
    birlesen = {}
    for sekil in sorted(eski.get("satis_sekilleri", []), key=lambda s: (s["sira"], s["id"])):
        if (sekil["giris_birimi"] == "adet" and sekil["ambalaj_malzeme_id"]
                and abs(sekil["ambalaj_adet"] - 1) < 0.001):
            birlesen.setdefault(sekil["ambalaj_malzeme_id"], sekil)
    sekil_kalem = {}   # eski satis_sekli_id -> yeni kalem_id

    # Eski 'tur' kolonu (hammadde/ambalaj/sarf) artik hicbir hesaba girmiyor ama
    # duzen bilgisi olarak degerli; baslik olarak tasiniyor.
    TUR_ADI = {"hammadde": "Hammadde", "ambalaj": "Ambalaj", "sarf": "Sarf"}

    for malzeme in eski.get("malzemeler", []):
        sekil = birlesen.get(malzeme["id"])
        if sekil is not None:
            sayim_tarzi, dagit = "say", 0
        elif malzeme["tur"] == "ambalaj":
            sayim_tarzi, dagit = "say", 1
        elif malzeme["tur"] == "sarf":
            sayim_tarzi, dagit = "koli", 1
        else:
            sayim_tarzi, dagit = "yok", 0
        if not malzeme["takip"]:
            sayim_tarzi, dagit = "yok", 0

        baglanti.execute(
            "INSERT INTO kalemler (id, ad, birim, aciklama, tur, alinir, uretilir,"
            " satilir, takip, birim_fiyat, fiyat, koli_adet, koli_ad, kritik_seviye,"
            " tedarikci, sayim_tarzi, dagit, sira)"
            " VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, ?, 'koli', ?, ?, ?, ?, ?)",
            (malzeme["id"], malzeme["ad"], malzeme["birim"],
             _top_notu(sekil),
             "Ürün" if sekil else TUR_ADI.get(malzeme["tur"], ""),
             1 if sekil else 0, malzeme["takip"],
             malzeme["birim_fiyat"], sekil["fiyat"] if sekil else 0.0,
             malzeme["koli_adet"], malzeme["kritik_seviye"], malzeme["tedarikci"],
             sayim_tarzi, dagit, sekil["sira"] + 1 if sekil else 0),
        )
        if sekil is not None:
            sekil_kalem[sekil["id"]] = malzeme["id"]

    # Butun karisimlar tek bir "Dondurma" stoguna akiyordu; kalem de tek olur,
    # her karisim onun bir recetesi haline gelir.
    dondurma_id, karisim_recete = None, {}
    if eski.get("karisimlar"):
        dondurma_id = baglanti.execute(
            "INSERT INTO kalemler (ad, birim, aciklama, tur, uretilir, takip, koli_adet,"
            " koli_ad, sayim_tarzi) VALUES (?, 'gram', ?, 'Ara ürün', 1, 1, ?, 'kutu', 'say')",
            (_bos_ad(baglanti, "Dondurma"), "Dolapta bekleyen hazır dondurma",
             kutu_kg * 1000),
        ).lastrowid
        for sira, karisim in enumerate(eski["karisimlar"]):
            karisim_recete[karisim["id"]] = baglanti.execute(
                "INSERT INTO receteler (urun_id, ad, verim, parti_ad, sira, aktif)"
                " VALUES (?, ?, ?, 'kazan', ?, ?)",
                (dondurma_id, karisim["ad"], karisim["parti_kg"] * 1000, sira,
                 karisim["aktif"]),
            ).lastrowid
        for satir in eski.get("receteler", []):
            recete_id = karisim_recete.get(satir["karisim_id"])
            if recete_id:
                baglanti.execute(
                    "INSERT OR IGNORE INTO recete_satirlari (recete_id, kalem_id, miktar)"
                    " VALUES (?, ?, ?)",
                    (recete_id, satir["malzeme_id"], satir["miktar"]),
                )

    # Satis sekilleri: birlesenlere satis recetesi yazilir, kalanlara yeni kalem.
    for sekil in eski.get("satis_sekilleri", []):
        kalem_id = sekil_kalem.get(sekil["id"])
        if kalem_id is None:
            kalem_id = baglanti.execute(
                "INSERT INTO kalemler (ad, birim, aciklama, tur, satilir, takip, fiyat,"
                " sayim_tarzi, sira, aktif) VALUES (?, ?, ?, 'Ürün', 1, 0, ?, 'elle', ?, ?)",
                (_bos_ad(baglanti, sekil["ad"]),
                 "kg" if sekil["giris_birimi"] == "kg" else "adet",
                 _top_notu(sekil), sekil["fiyat"], sekil["sira"] + 1, sekil["aktif"]),
            ).lastrowid
            sekil_kalem[sekil["id"]] = kalem_id

        satirlar = []
        if sekil["gram"] > 0 and dondurma_id:
            satirlar.append((dondurma_id, sekil["gram"]))
        # Birlesen kalemde ambalaj zaten kalemin kendisi; ikinci kez yazilmaz.
        if (sekil["id"] not in [s["id"] for s in birlesen.values()]
                and sekil["ambalaj_malzeme_id"] and sekil["ambalaj_adet"] > 0):
            satirlar.append((sekil["ambalaj_malzeme_id"], sekil["ambalaj_adet"]))
        if satirlar:
            recete_id = baglanti.execute(
                "INSERT INTO receteler (urun_id, ad, verim, sira) VALUES (?, '', 1, 0)",
                (kalem_id,),
            ).lastrowid
            for malzeme_id, miktar in satirlar:
                baglanti.execute(
                    "INSERT OR IGNORE INTO recete_satirlari (recete_id, kalem_id, miktar)"
                    " VALUES (?, ?, ?)", (recete_id, malzeme_id, miktar))

    # --- hareket kayitlari
    for satir in eski.get("stok_hareketleri", []):
        baglanti.execute(
            "INSERT INTO stok_hareketleri (id, tarih, kalem_id, miktar, sebep,"
            " kaynak_tur, kaynak_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (satir["id"], satir["tarih"], satir["malzeme_id"], satir["miktar"],
             satir["sebep"], satir["kaynak_tur"], satir["kaynak_id"]),
        )
    for satir in eski.get("dondurma_hareketleri", []):
        if dondurma_id:
            baglanti.execute(
                "INSERT INTO stok_hareketleri (tarih, kalem_id, miktar, sebep,"
                " kaynak_tur, kaynak_id) VALUES (?, ?, ?, ?, ?, ?)",
                (satir["tarih"], dondurma_id, satir["gram"], satir["sebep"],
                 satir["kaynak_tur"], satir["kaynak_id"]),
            )
    for satir in eski.get("uretimler", []):
        baglanti.execute(
            "INSERT INTO uretimler (id, tarih, recete_id, kalem_id, sayi, miktar,"
            " maliyet, kayit_zamani) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (satir["id"], satir["tarih"], karisim_recete.get(satir["karisim_id"]),
             dondurma_id, satir["parti_sayisi"], satir["gram"], satir["maliyet"],
             satir["kayit_zamani"]),
        )
    for satir in eski.get("satislar", []):
        kalem_id = sekil_kalem.get(satir["satis_sekli_id"])
        if kalem_id:
            baglanti.execute(
                "INSERT INTO satislar (id, tarih, kalem_id, miktar, tutar, maliyet,"
                " sayim_id, kayit_zamani) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (satir["id"], satir["tarih"], kalem_id, satir["miktar"],
                 satir["tutar"], satir["maliyet"], satir.get("sayim_id"),
                 satir["kayit_zamani"]),
            )
    for satir in eski.get("alimlar", []):
        baglanti.execute(
            "INSERT INTO alimlar (id, tarih, kalem_id, miktar, tutar, odeme,"
            " tedarikci, kayit_zamani) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (satir["id"], satir["tarih"], satir["malzeme_id"], satir["miktar"],
             satir["tutar"], satir["odeme"], satir["tedarikci"], satir["kayit_zamani"]),
        )
    for satir in eski.get("sayim_satirlari", []):
        baglanti.execute(
            "INSERT OR IGNORE INTO sayim_satirlari (id, sayim_id, kalem_id, koli,"
            " adet, kalan, tuketim) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (satir["id"], satir["sayim_id"], satir["malzeme_id"], satir["koli"],
             satir["adet"], satir["kalan"], satir["tuketim"]),
        )

    for tablo in eski:
        baglanti.execute(f"DROP TABLE IF EXISTS goc_{tablo}")
    ayar_yaz(baglanti, "kurulum_bitti", "1")
    baglanti.commit()
    baglanti.execute("PRAGMA foreign_keys = ON")


def _top_notu(sekil):
    """Eski 'kac top' bilgisi hesaba girmiyordu; aciklama olarak saklanir."""
    if sekil and sekil.get("top_sayisi"):
        adet = sekil["top_sayisi"]
        yazi = f"{adet:g}".replace(".", ",")
        return f"yaklaşık {yazi} top"
    return ""


def _bos_ad(baglanti, ad):
    """Ad zaten kullaniliyorsa sonuna ayirt edici bir ek koyar."""
    if not baglanti.execute("SELECT 1 FROM kalemler WHERE ad = ?", (ad,)).fetchone():
        return ad
    for ek in [" (satış)"] + [f" ({sayac})" for sayac in range(2, 50)]:
        if not baglanti.execute(
            "SELECT 1 FROM kalemler WHERE ad = ?", (ad + ek,)
        ).fetchone():
            return ad + ek
    return f"{ad} {datetime.datetime.now():%H%M%S}"


# ---------------------------------------------------------------- kurulum

def _tek_dukkandan_gocur():
    """Tek dukkanli surumden kalan dosyayi dukkan 1'in yerine tasir.

    Sadece dukkan 1'in dosyasi henuz yokken calisir, yani bir kere. Kopya
    degil tasima: iki ayri dosyada iki ayri kayit birikmesin.
    """
    os.makedirs(DUKKAN_KLASORU, exist_ok=True)
    birinci = db_yolu(1)
    if os.path.exists(birinci):
        return
    for eski in (TEK_DB_YOLU, ESKI_DB_YOLU):
        if os.path.exists(eski):
            os.rename(eski, birinci)
            print(f"  {os.path.basename(eski)} -> {os.path.basename(birinci)} tasindi.")
            return


def hazirla(dukkan_id=1):
    """Bir dukkanin veritabanini acar; gerekiyorsa olusturur ya da gocurur."""
    os.makedirs(VERI_KLASORU, exist_ok=True)
    _tek_dukkandan_gocur()

    baglanti = baglan(dukkan_id)
    if _eski_surum_mu(baglanti):
        baglanti.close()
        yedek = os.path.join(
            VERI_KLASORU, f"yedek-{datetime.datetime.now():%Y%m%d-%H%M%S}.db"
        )
        shutil.copy2(db_yolu(dukkan_id), yedek)
        baglanti = baglan(dukkan_id)
        _goc(baglanti)
        print(f"  Veriler yeni duzene tasindi. Eski surumun yedegi: {os.path.basename(yedek)}")

    baglanti.executescript(SEMA)
    _kolonlari_tamamla(baglanti)
    for anahtar, deger in VARSAYILAN_AYARLAR.items():
        baglanti.execute(
            "INSERT OR IGNORE INTO ayarlar (anahtar, deger) VALUES (?, ?)", (anahtar, deger)
        )
    baglanti.commit()
    # Resmi tatiller ve bilinen dini bayramlar takvime yazilir. Zaten varsa
    # hicbir sey olmaz; boylece yil donunce takvim kendini uzatir.
    takvim.tatilleri_uret(baglanti)
    return baglanti


def kurulum_gerekli(baglanti):
    """Sablon secimi henuz yapilmadi mi. 'Bos basla' secilirse de bitmis sayilir."""
    return ayar(baglanti, "kurulum_bitti", "0") != "1"


if __name__ == "__main__":
    baglanti = hazirla()
    for tablo in ("kalemler", "receteler", "recete_satirlari", "satislar", "uretimler"):
        adet = baglanti.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0]
        print(f"{tablo}: {adet} kayit")
    print(f"\nVeritabani hazir: {db_yolu(1)}")
