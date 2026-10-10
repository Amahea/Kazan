# Siteye ilk kez gelen birine gosterilen tanitim sayfasi (TR/EN).
# Icerigi degistirmek icin asagidaki GOVDE_TR / GOVDE_EN govdelerini duzenle.
# Dil, istek diline gore (diller.simdiki) secilir; ustte bayrak dugmesi vardir.

import diller

FONTS = '<meta name="description" content="Stok, maliyet ve kar takibi.">\n<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Hanken+Grotesk:wght@400;500;600;700&family=Spline+Sans+Mono:wght@400;500;600&display=swap">'

STIL = r'''<style>
/* Renkler programin kendi mavi temasiyla eslesir (uygulama acik tema; tanitim
   da tek acik tema, OS karanlik modunda sapmaz). */
:root{
  --kagit:#f4f6f8;
  --kart:#ffffff;
  --kenar:#e6ebf0;
  --murekkep:#1c2733;
  --yesil:#0f4c75;
  --yesil-ac:#1b7f4f;
  --bal:#ffb703;
  --bal-koyu:#b8860b;
  --sonuk:#6b7c8f;
  --kirmizi:#c1392b;
  --golge:rgba(28,39,51,.09);
  --golge-sert:rgba(28,39,51,.14);
  --cizgi:rgba(28,39,51,.08);
  color-scheme:light;
}

*{box-sizing:border-box}
body{
  margin:0;background:var(--kagit);color:var(--murekkep);
  font-family:"Hanken Grotesk",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:17px;line-height:1.65;-webkit-font-smoothing:antialiased;
}
.sinir{max-width:920px;margin:0 auto;padding-inline:22px}
h1,h2,h3{font-family:"Bricolage Grotesque","Hanken Grotesk",system-ui,sans-serif;
  text-wrap:balance;line-height:1.08;letter-spacing:-.015em;margin:0}
a{color:var(--yesil);text-decoration-thickness:1px;text-underline-offset:2px}
mono,.mono,.sayi{font-family:"Spline Sans Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.etiket{font-family:"Spline Sans Mono",ui-monospace,monospace;text-transform:uppercase;
  letter-spacing:.14em;font-size:12px;font-weight:500;color:var(--bal-koyu)}

/* ---------- şerit üst ---------- */
.ust{border-bottom:1px solid var(--cizgi);background:var(--kagit)}
.ust .sinir{display:flex;align-items:center;justify-content:space-between;
  padding-block:16px;gap:16px;flex-wrap:wrap}
.marka{display:flex;align-items:center;gap:10px;font-family:"Bricolage Grotesque",sans-serif;
  font-weight:800;font-size:19px;letter-spacing:-.02em}
.marka .mim{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;
  background:var(--yesil);color:var(--kagit);font-size:16px;box-shadow:0 2px 0 var(--golge-sert)}
.ust nav{display:flex;gap:20px;font-size:14.5px;flex-wrap:wrap}
.ust nav a{color:var(--sonuk);text-decoration:none;font-weight:500}
.ust nav a:hover{color:var(--yesil)}

/* ---------- hero ---------- */
.hero{padding-block:64px 52px;position:relative;overflow:hidden}
.hero .sinir{position:relative;z-index:1}
.hero .rozet{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--kenar);
  background:var(--kart);border-radius:999px;padding:6px 14px;margin-bottom:26px;
  box-shadow:0 1px 0 var(--golge)}
.hero .rozet .nokta{width:8px;height:8px;border-radius:50%;background:var(--yesil-ac);
  box-shadow:0 0 0 4px color-mix(in srgb,var(--yesil-ac) 22%,transparent)}
.hero .rozet span{font-size:13.5px;color:var(--sonuk);font-weight:500}
.hero h1{font-size:clamp(38px,7.5vw,68px);font-weight:800;max-width:14ch}
.hero h1 .vurgu{color:var(--yesil);position:relative}
.hero h1 .vurgu::after{content:"";position:absolute;left:-2px;right:-2px;bottom:.07em;height:.26em;
  background:color-mix(in srgb,var(--bal) 42%,transparent);z-index:-1;border-radius:3px}
.hero .alt{font-size:clamp(18px,2.4vw,21px);color:var(--sonuk);max-width:52ch;margin-top:22px;line-height:1.55}
.hero .dugmeler{display:flex;gap:14px;flex-wrap:wrap;margin-top:34px;align-items:center}
.dugme{display:inline-flex;align-items:center;gap:9px;border-radius:11px;padding:14px 24px;
  font-weight:600;font-size:16px;text-decoration:none;border:1px solid transparent;transition:transform .12s,box-shadow .12s}
.dugme.ana{background:var(--yesil);color:var(--kagit);box-shadow:0 3px 0 var(--bal-koyu)}
.dugme.ana:hover{transform:translateY(-1px);box-shadow:0 5px 0 var(--bal-koyu)}
.dugme.yan{background:var(--kart);color:var(--murekkep);border-color:var(--kenar);box-shadow:0 1px 0 var(--golge)}
.dugme.yan:hover{border-color:var(--yesil)}
.hero .ipucu{margin-top:18px;font-size:14px;color:var(--sonuk)}
.hero .ipucu .mono{font-size:13.5px;background:color-mix(in srgb,var(--bal) 14%,var(--kart));
  padding:2px 7px;border-radius:5px;border:1px solid var(--kenar)}
.kagit-doku{position:absolute;inset:0;z-index:0;pointer-events:none;opacity:.5;
  background-image:repeating-linear-gradient(transparent 0 37px,var(--cizgi) 37px 38px);
  mask-image:linear-gradient(to bottom,transparent,#000 30%,#000 70%,transparent)}

/* ---------- genel bölüm ---------- */
section{padding-block:56px}
.baslik-blok{max-width:60ch;margin-bottom:38px}
.baslik-blok h2{font-size:clamp(27px,4vw,38px);font-weight:700;margin-top:10px}
.baslik-blok p{color:var(--sonuk);font-size:18px;margin:14px 0 0}
.ayrac{border:none;border-top:1px solid var(--cizgi);margin:0}

/* ---------- "kalem" fikri ---------- */
.fikir{background:var(--kart);border:1px solid var(--kenar);border-radius:18px;
  padding:34px;box-shadow:0 1px 0 var(--golge)}
.kutucuklar{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:26px}
.kutucuk{border:1px solid var(--kenar);border-radius:13px;padding:18px;background:var(--kagit)}
.kutucuk .onay{display:inline-grid;place-items:center;width:26px;height:26px;border-radius:7px;
  background:var(--yesil);color:var(--kagit);font-weight:700;font-size:15px;margin-bottom:12px}
.kutucuk b{display:block;font-size:16.5px;margin-bottom:4px}
.kutucuk span{color:var(--sonuk);font-size:14.5px}
.fikir .not{margin:24px 0 0;padding:16px 18px;border-left:3px solid var(--bal);
  background:color-mix(in srgb,var(--bal) 9%,transparent);border-radius:0 10px 10px 0;
  color:var(--murekkep);font-size:15.5px}
.fikir .not b{color:var(--bal-koyu)}

/* ---------- günlük döngü ---------- */
.dongu{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;counter-reset:adim}
.adim{background:var(--kart);border:1px solid var(--kenar);border-radius:15px;padding:22px;
  position:relative;box-shadow:0 1px 0 var(--golge)}
.adim .sira{counter-increment:adim;font-family:"Spline Sans Mono",monospace;font-size:13px;
  color:var(--bal-koyu);font-weight:600}
.adim .sira::before{content:"0" counter(adim)}
.adim .ikon{font-size:26px;margin:8px 0 10px;display:block}
.adim h3{font-size:18px;font-weight:700;margin-bottom:6px}
.adim p{margin:0;color:var(--sonuk);font-size:14.5px;line-height:1.5}
.dongu-not{text-align:center;margin-top:24px;color:var(--sonuk);font-size:15px}
.dongu-not b{color:var(--murekkep)}

/* ---------- ekranlar ızgarası ---------- */
.ekranlar{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}
.ekran{background:var(--kart);border:1px solid var(--kenar);border-radius:15px;padding:24px;
  display:flex;gap:18px;box-shadow:0 1px 0 var(--golge)}
.ekran .amblem{flex:none;width:48px;height:48px;border-radius:12px;display:grid;place-items:center;
  font-size:23px;background:color-mix(in srgb,var(--yesil) 12%,var(--kagit));border:1px solid var(--kenar)}
.ekran h3{font-size:18.5px;font-weight:700;margin-bottom:6px;display:flex;align-items:baseline;gap:8px}
.ekran h3 .yol{font-family:"Spline Sans Mono",monospace;font-size:12.5px;color:var(--sonuk);font-weight:500}
.ekran p{margin:0;color:var(--sonuk);font-size:15px;line-height:1.55}

/* ---------- sayım demosu ---------- */
.sayim{display:grid;grid-template-columns:1.1fr 1fr;gap:34px;align-items:center}
.fis{background:var(--kart);border:1px solid var(--kenar);border-radius:14px;padding:26px 28px;
  box-shadow:0 10px 30px -14px var(--golge-sert);position:relative}
.fis::before,.fis::after{content:"";position:absolute;left:0;right:0;height:10px;
  background-image:radial-gradient(circle at 6px -2px,transparent 6px,var(--kagit) 6px);
  background-size:16px 10px;background-repeat:repeat-x}
.fis::before{top:-5px}
.fis::after{bottom:-5px;transform:scaleY(-1)}
.fis h3{font-size:15px;font-family:"Spline Sans Mono",monospace;text-transform:uppercase;
  letter-spacing:.1em;color:var(--sonuk);font-weight:600;margin-bottom:18px}
.fis-satir{display:flex;justify-content:space-between;align-items:center;padding:10px 0;
  border-bottom:1px dashed var(--cizgi);font-size:15px}
.fis-satir:last-of-type{border-bottom:none}
.fis-satir .ad{color:var(--sonuk)}
.fis-satir .deg{font-family:"Spline Sans Mono",monospace;font-weight:600;font-size:16px}
.fis-satir input{width:92px;text-align:right;font-family:"Spline Sans Mono",monospace;font-size:16px;
  font-weight:600;padding:6px 9px;border:1px solid var(--kenar);border-radius:8px;background:var(--kagit);
  color:var(--murekkep)}
.fis-satir input:focus{outline:2px solid var(--yesil);outline-offset:1px}
.fis-vurgu{margin-top:14px;padding:16px;border-radius:11px;background:color-mix(in srgb,var(--yesil) 11%,var(--kagit));
  display:flex;justify-content:space-between;align-items:center}
.fis-vurgu .ad{font-weight:600}
.fis-vurgu .buyuk{font-family:"Spline Sans Mono",monospace;font-size:28px;font-weight:600;color:var(--yesil)}
.fis-vurgu .ciro{font-family:"Spline Sans Mono",monospace;font-size:15px;color:var(--sonuk);margin-top:2px;text-align:right}
.sayim-yazi h2{font-size:clamp(26px,4vw,34px);font-weight:700}
.sayim-yazi p{color:var(--sonuk);font-size:17px}
.sayim-yazi .dene{font-size:14px;color:var(--bal-koyu);font-family:"Spline Sans Mono",monospace;margin-top:6px}

/* ---------- derin özellikler ---------- */
.ozellikler{display:grid;grid-template-columns:repeat(2,1fr);gap:24px}
.oz{border-top:2px solid var(--murekkep);padding-top:18px}
.oz .etiket{display:block;margin-bottom:10px}
.oz h3{font-size:20px;font-weight:700;margin-bottom:8px}
.oz p{margin:0 0 10px;color:var(--sonuk);font-size:15.5px;line-height:1.6}
.oz ul{margin:0;padding-left:18px;color:var(--sonuk);font-size:15px;line-height:1.7}
.oz ul li::marker{color:var(--bal)}

/* ---------- öğrenme çizelgesi ---------- */
.ogrenme{background:var(--kart);border:1px solid var(--kenar);border-radius:16px;overflow:hidden;
  box-shadow:0 1px 0 var(--golge)}
.ogrenme .sr{display:grid;grid-template-columns:140px 1fr;gap:18px;padding:16px 22px;
  border-bottom:1px solid var(--cizgi);align-items:baseline}
.ogrenme .sr:last-child{border-bottom:none}
.ogrenme .gun{font-family:"Spline Sans Mono",monospace;font-weight:600;color:var(--yesil);font-size:15px}
.ogrenme .ne{color:var(--sonuk);font-size:15px}

/* ---------- güven ---------- */
.guven{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.gv{display:flex;gap:14px;padding:20px;background:var(--kart);border:1px solid var(--kenar);
  border-radius:13px;box-shadow:0 1px 0 var(--golge)}
.gv .im{flex:none;font-size:22px;width:42px;height:42px;display:grid;place-items:center;border-radius:10px;
  background:color-mix(in srgb,var(--yesil) 10%,var(--kagit))}
.gv b{display:block;font-size:16px;margin-bottom:3px}
.gv span{color:var(--sonuk);font-size:14.5px;line-height:1.5}

/* ---------- başla ---------- */
.basla{background:var(--yesil);color:var(--kagit);border-radius:22px;padding:48px 40px;text-align:center;
  position:relative;overflow:hidden}
.basla h2{font-size:clamp(28px,4.5vw,40px);font-weight:800;color:var(--kagit)}
.basla p{color:color-mix(in srgb,var(--kagit) 82%,var(--yesil));max-width:48ch;margin:16px auto 0;font-size:17.5px}
.sablonlar{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin:28px 0 30px}
.sablonlar span{border:1px solid color-mix(in srgb,var(--kagit) 30%,transparent);border-radius:999px;
  padding:8px 16px;font-size:14px;font-weight:500;background:color-mix(in srgb,var(--kagit) 8%,transparent)}
.basla .dugme.ana{background:var(--bal);color:#2a1c05;box-shadow:0 3px 0 var(--bal-koyu)}
.basla .dugme.ana:hover{box-shadow:0 5px 0 var(--bal-koyu)}

/* ---------- alt ---------- */
footer{border-top:1px solid var(--cizgi);padding-block:34px;margin-top:20px}
footer .sinir{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;
  color:var(--sonuk);font-size:14px}
footer .marka{font-size:16px}

@media (max-width:760px){
  .kutucuklar{grid-template-columns:1fr}
  .dongu{grid-template-columns:1fr 1fr}
  .ekranlar{grid-template-columns:1fr}
  .sayim{grid-template-columns:1fr}
  .ozellikler{grid-template-columns:1fr}
  .guven{grid-template-columns:1fr}
  .ogrenme .sr{grid-template-columns:110px 1fr;gap:12px}
  section{padding-block:44px}
  .hero{padding-block:46px 40px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>'''

BETIK = r'''<script>
(function(){
  var kalan=document.getElementById("kalan");
  var satildiEl=document.getElementById("satildi");
  var ciroEl=document.getElementById("ciro");
  var BASLANGIC=3000, TOP_GRAM=60, GRAM_FIYAT=1; // 1 top = 60 gr = 60 ₺
  function bicim(n){return n.toLocaleString("tr-TR");}
  function hesapla(){
    var k=parseInt(kalan.value,10);
    if(isNaN(k)) k=0;
    if(k<0) k=0;
    if(k>BASLANGIC) k=BASLANGIC;
    var satildi=BASLANGIC-k;
    satildiEl.textContent=bicim(satildi);
    // örnek: her külah ~1 top dondurma = 60 ₺, basit bir temsil
    ciroEl.textContent=bicim(satildi*60)+" ₺";
  }
  kalan.addEventListener("input",hesapla);
  hesapla();
})();
</script>

</body></html>
'''

GOVDE_TR = r'''
{SECICI}


<header class="ust">
  <div class="sinir">
    <div class="marka"><span class="mim">📒</span> Dükkan Takip</div>
    <nav>
      <a href="#fikir">Nasıl düşünür</a>
      <a href="#ekranlar">Ekranlar</a>
      <a href="#sayim">Gün sonu sayımı</a>
      <a href="#tahmin">Tahmin</a>
      <a href="#guven">Verilerin</a>
    </nav>
  </div>
</header>

<section class="hero">
  <div class="kagit-doku"></div>
  <div class="sinir">
    <div class="rozet"><span class="nokta"></span><span>Dondurmacı · Pastane · Fırın · Lokanta</span></div>
    <h1>Dükkânın bütün <span class="vurgu">hesabı</span> tek bir yerde.</h1>
    <p class="alt">Stok, maliyet ve kâr takibi. Ne aldığını, ne ürettiğini, ne sattığını yazarsın;
      program kasanı, borcunu, kârını ve “yarın şu kadar al” önerisini kendisi çıkarır.
      Muhasebe bilmeni istemez — dükkânı sen anlatırsın.</p>
    <div class="dugmeler">
      <a class="dugme ana" href="#basla">Nasıl başlanır →</a>
      <a class="dugme yan" href="#ekranlar">Neler yapabildiğine bak</a>
    </div>
    <p class="ipucu">Bilgisayarda açılır, telefondan da bakılır. İnternet gerekmez.
      Bütün kayıt kendi cihazında kalır.</p>
  </div>
</section>

<hr class="ayrac">

<!-- FİKİR -->
<section id="fikir">
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">Programın tek kuralı</span>
      <h2>Dükkândaki her şey bir “kalem”.</h2>
      <p>Un bir kalem, hamur bir kalem, ekmek bir kalem; dondurmada süt, külah, çilek aroması
        hepsi birer kalem. Program hiçbir ürünü baştan bilmez — bir kalemin ne olduğunu,
        yanındaki üç kutucuğu işaretleyerek sen söylersin.</p>
    </div>
    <div class="fikir">
      <div class="kutucuklar">
        <div class="kutucuk">
          <span class="onay">✓</span>
          <b>Satın alınır</b>
          <span>Alım ekranında çıkar, alış fiyatı ve tedarikçisi olur.</span>
        </div>
        <div class="kutucuk">
          <span class="onay">✓</span>
          <b>Üretilir</b>
          <span>Reçetesi olur, üretim ekranında çıkar.</span>
        </div>
        <div class="kutucuk">
          <span class="onay">✓</span>
          <b>Satılır</b>
          <span>Satış fiyatı olur, satış ekranında çıkar.</span>
        </div>
      </div>
      <p class="not"><b>Bir kalem birkaçını birden taşıyabilir.</b> Külah hem alınır hem satılır;
        pandispanya hem üretilir hem başka bir reçetede malzeme olur. Reçeteler zincirlenir:
        <span class="mono">dilim pasta ← yaş pasta ← pandispanya ← un</span>. Sen bir kez kurarsın,
        gerisi kendiliğinden işler.</p>
    </div>
  </div>
</section>

<!-- GÜNLÜK DÖNGÜ -->
<section id="dongu">
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">Günlük kullanım</span>
      <h2>Günü dört adımda kapatırsın.</h2>
      <p>Her gün aynı sıra. Fazlası yok: aldığını, ürettiğini, sattığını gir — gün sonunda
        her şeyin özeti karşında.</p>
    </div>
    <div class="dongu">
      <div class="adim">
        <span class="sira"></span>
        <span class="ikon">💰</span>
        <h3>Alım / Gider</h3>
        <p>Malzeme aldığında gir. Koli veya çuvalla aldıysan “kaç koli” dersin, program birime
          çevirir. Kira, elektrik, maaş da buraya.</p>
      </div>
      <div class="adim">
        <span class="sira"></span>
        <span class="ikon">🥛</span>
        <h3>Üretim</h3>
        <p>Kaç parti yaptığını yazarsın. Reçetedeki malzemeler stoktan düşer, çıkan ürün stoğa girer.</p>
      </div>
      <div class="adim">
        <span class="sira"></span>
        <span class="ikon">🍦</span>
        <h3>Satış</h3>
        <p>İstersen kaç sattığını yazarsın, istersen akşam rafta kalanı sayarsın — program
          farkı satış kabul eder.</p>
      </div>
      <div class="adim">
        <span class="sira"></span>
        <span class="ikon">🏠</span>
        <h3>Bugün</h3>
        <p>Kasan, borcun, kârın ve “şu malzemeden şu kadar al” önerilerin tek ekranda görünür.</p>
      </div>
    </div>
    <p class="dongu-not">Sıra önemli: o gün malzeme aldıysan <b>önce alımı gir, sonra sayımı yap.</b>
      Yanlış girersen <b>sil</b> dersin — stok ve kasa geri alınır.</p>
  </div>
</section>

<hr class="ayrac">

<!-- EKRANLAR -->
<section id="ekranlar">
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">Programın içi</span>
      <h2>Yedi ekran, hepsi işini bilir.</h2>
      <p>Soldaki menüden geçersin. Her ekran tek bir işi yapar ve seni rakamla boğmaz.</p>
    </div>
    <div class="ekranlar">
      <div class="ekran">
        <div class="amblem">🍦</div>
        <div>
          <h3>Satış <span class="yol">/satis</span></h3>
          <p>Gün sonu sayımı ya da doğrudan satış girişi — hangisini seçtiysen o. Kiloyla,
            topla, porsiyonla; dükkânın nasıl satıyorsa öyle.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">🥛</div>
        <div>
          <h3>Üretim <span class="yol">/uretim</span></h3>
          <p>Kaç kazan dondurma, kaç tepsi pasta, kaç tekne hamur yaptığını girersin.
            Verimi sen yazarsın — 4,5 kg girip 7,5 kg çıkabilir, program onu bilir.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">📦</div>
        <div>
          <h3>Stok <span class="yol">/stok</span></h3>
          <p>Elinde ne var, türlere göre ara toplamlarıyla. Biten ve azalan malzemeler
            baş köşede uyarır.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">💰</div>
        <div>
          <h3>Alım / Gider <span class="yol">/para</span></h3>
          <p>Alımlar, tedarikçiye ödemeler, sabit giderler. Alım girdikçe o kalemin alış
            fiyatı kendiliğinden güncellenir.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">🧑‍🍳</div>
        <div>
          <h3>Çalışanlar <span class="yol">/calisanlar</span></h3>
          <p>Kadroyu, maaşı ve SGK’yı tutarsın; aylık maaş yükü gidere kendiliğinden işlenir.
            Ayrılanı “ayrıldı” yaparsın, geçmiş bozulmaz.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">📊</div>
        <div>
          <h3>Raporlar <span class="yol">/ozet</span></h3>
          <p>Ciro, maliyet, kâr; hangi ürün ne kadar kazandırıyor. Yanında Tahmin ve Özel
            Günler sayfaları.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">⚙️</div>
        <div>
          <h3>Ayarlar <span class="yol">/ayarlar</span></h3>
          <p>Fiyatları tek tabloda topluca güncellersin, ili seçersin, menü dönemlerini
            kurarsın. Ürün &amp; Malzeme ve reçeteler de burada.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">🗂️</div>
        <div>
          <h3>Çok dükkan</h3>
          <p>Birden fazla dükkânın mı var? Her birinin kendi girişi, kendi kalemleri, kendi
            raporu olur — biri diğerine karışmaz.</p>
        </div>
      </div>
    </div>
  </div>
</section>

<hr class="ayrac">

<!-- SAYIM DEMOSU -->
<section id="sayim">
  <div class="sinir">
    <div class="sayim">
      <div class="fis">
        <h3>Gün sonu sayımı · Külah</h3>
        <div class="fis-satir">
          <span class="ad">Sabah raftaki</span>
          <span class="deg sayi">3.000</span>
        </div>
        <div class="fis-satir">
          <span class="ad">Akşam saydığın</span>
          <input id="kalan" type="number" min="0" max="3000" value="2962" inputmode="numeric" aria-label="Akşam rafta kalan külah">
        </div>
        <div class="fis-vurgu">
          <div>
            <span class="ad">Satılmış</span>
            <div class="ciro">Ciro: <span id="ciro">2.280 ₺</span></div>
          </div>
          <span class="buyuk"><span id="satildi">38</span></span>
        </div>
      </div>
      <div class="sayim-yazi">
        <span class="etiket">Akşam en sevdiğin kısım</span>
        <h2>Kaç sattığını saymazsın. Kaç <em>kaldığını</em> sayarsın.</h2>
        <p>Program farkı satış kabul eder. 3.000 külahtan akşam 2.962 kaldıysa 38 külah satılmış
          demektir; ciro ve kâr oradan çıkar. Kaşık, peçete gibi “tek tek saymam” dediklerin için
          “bir kolisi bitti” dersin yeter.</p>
        <p class="dene">↑ Kalan sayıyı değiştir, satış kendiliğinden hesaplansın.</p>
      </div>
    </div>
  </div>
</section>

<hr class="ayrac">

<!-- DERİN ÖZELLİKLER -->
<section id="tahmin">
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">Program yalnızca saymaz</span>
      <h2>Öğrenir, hesaplar ve asla uydurmaz.</h2>
      <p>Günler biriktikçe dükkânını tanır. Elinde yeterli veri yoksa tahmin vermeyi reddeder
        ve neyin eksik olduğunu söyler — bu kasıtlı.</p>
    </div>
    <div class="ozellikler">
      <div class="oz">
        <span class="etiket">Hava &amp; satış tahmini</span>
        <h3>Yarın ne beklemeli?</h3>
        <p>Önümüzdeki günlerin havasını resmî MGM servisinden alır, her günün cirosuyla eşleştirir
          ve ilişkiyi kendisi çıkarır:</p>
        <ul>
          <li>“Sıcaklık 1 derece artınca ciro şu kadar artıyor”</li>
          <li>“Yağmurlu günlerde şu kadar düşüyor”</li>
          <li>“Cumartesi normalin şu katı”</li>
        </ul>
      </div>
      <div class="oz">
        <span class="etiket">Üretim önerisi</span>
        <h3>7 gün için ne üretmeli?</h3>
        <p>Beklenen satışları reçetelerden geçirir, önümüzdeki hafta kaç kazan / tepsi / tekne
          gerektiğini hesaplar. Boşa üretim de, raf boşluğu da azalır.</p>
      </div>
      <div class="oz">
        <span class="etiket">Maliyet &amp; kâr</span>
        <h3>Hangi ürün kazandırıyor?</h3>
        <p>Satın alınanın maliyeti son alış fiyatı; üretilenin maliyeti gerçek üretim kayıtlarının
          ortalaması. Bir satışın maliyeti, kalemin kendisi artı reçetesi — ikisi iki kez
          sayılmaz. İlk günden kâr sıfır çıkmaz.</p>
      </div>
      <div class="oz">
        <span class="etiket">Özel günler &amp; menü dönemleri</span>
        <h3>Bayram, mevsim, hafta sonu.</h3>
        <p>Bayramı, tatili işaretlersin; program o günlerin satışını ayrı öğrenir. Yaz–kış menüsü
          kurarsın, mevsim gelince önerir; menü dışı ürünler satış ve sayımdan kendiliğinden kalkar.</p>
      </div>
    </div>
  </div>
</section>

<hr class="ayrac">

<!-- ÖĞRENME ÇİZELGESİ -->
<section>
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">Tahmin ne zaman açılır</span>
      <h2>Veri biriktikçe akıllanır.</h2>
      <p>İlk günden ahkâm kesmez. Ne kadar günün varsa ona göre konuşur.</p>
    </div>
    <div class="ogrenme">
      <div class="sr"><span class="gun">İlk 10 gün</span><span class="ne">Tahmin yok. “Kaç gün daha lazım” der. Hava yine de her gün kaydedilir.</span></div>
      <div class="sr"><span class="gun">10. günden</span><span class="ne">Ciro tahmini başlar; aralık geniştir, veri arttıkça daralır.</span></div>
      <div class="sr"><span class="gun">14. günden</span><span class="ne">Sıcaklık etkisi devreye girer — havalar birbirinden yeterince farklıysa.</span></div>
      <div class="sr"><span class="gun">28. günden</span><span class="ne">Haftanın günü etkisi devreye girer; cumartesi ile salı ayrışır.</span></div>
    </div>
  </div>
</section>

<hr class="ayrac">

<!-- GÜVEN -->
<section id="guven">
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">İçin rahat olsun</span>
      <h2>Verilerin sende kalır.</h2>
      <p>Program senin için çalışır, senin sırtından değil. Dört söz veriyor:</p>
    </div>
    <div class="guven">
      <div class="gv">
        <div class="im">🔒</div>
        <div><b>Kayıtlar cihazında</b><span>Bütün kayıt kendi bilgisayarında bir dosyada durur, hiçbir yere gönderilmez. Yedeklemek için o dosyayı kopyalaman yeter.</span></div>
      </div>
      <div class="gv">
        <div class="im">📴</div>
        <div><b>İnternetsiz çalışır</b><span>Bağlantı yoksa program sorunsuz devam eder, yalnızca hava tahmini susar. İli seçene kadar internete hiç çıkmaz.</span></div>
      </div>
      <div class="gv">
        <div class="im">🛟</div>
        <div><b>Verin kaybolmaz</b><span>Hata ekranı çıksa bile kayıtlar olduğu gibi durur. Her işlem ya tamamen yazılır ya hiç yazılmaz.</span></div>
      </div>
      <div class="gv">
        <div class="im">🎯</div>
        <div><b>Uydurmaz</b><span>Yeterli veri yoksa tahmin vermeyi reddeder. Verdiği her tahminin yanında, geçmişte ne kadar yanıldığından çıkan bir aralık vardır.</span></div>
      </div>
    </div>
  </div>
</section>

<!-- BAŞLA -->
<section id="basla">
  <div class="sinir">
    <div class="basla">
      <span class="etiket" style="color:var(--bal)">İlk açılış</span>
      <h2>Dükkânını seç, gerisini birlikte kuralım.</h2>
      <p>İlk açılışta bir şablon seçersin. Şablon sana hazır bir malzeme–ürün–reçete listesi
        verir; hepsi örnektir, sonradan dilediğin gibi değiştirirsin.</p>
      <div class="sablonlar">
        <span>🍦 Dondurmacı</span>
        <span>🧁 Pastane</span>
        <span>🍞 Fırın</span>
        <span>🍽️ Lokanta</span>
        <span>📄 Boş başla</span>
      </div>
      <a class="dugme ana" href="/giris">Programa gir →</a>
    </div>
  </div>
</section>

<footer>
  <div class="sinir">
    <div class="marka"><span class="mim">📒</span> Dükkan Takip</div>
    <div>Stok · maliyet · kâr — esnafın kendi defteri. Kayıtlar cihazında kalır.</div>
  </div>
</footer>

'''

GOVDE_EN = r'''
{SECICI}

<header class="ust">
  <div class="sinir">
    <div class="marka"><span class="mim">📒</span> Dükkan Takip</div>
    <nav>
      <a href="#fikir">How it thinks</a>
      <a href="#ekranlar">Screens</a>
      <a href="#sayim">End-of-day count</a>
      <a href="#tahmin">Forecast</a>
      <a href="#guven">Your data</a>
    </nav>
  </div>
</header>

<section class="hero">
  <div class="kagit-doku"></div>
  <div class="sinir">
    <div class="rozet"><span class="nokta"></span><span>Ice cream shop · Patisserie · Bakery · Restaurant</span></div>
    <h1>Your whole shop's <span class="vurgu">books</span> in one place.</h1>
    <p class="alt">Stock, cost and profit tracking. You enter what you bought, made and sold;
      the program works out your till, your debt, your profit and a "buy this much tomorrow"
      suggestion by itself. It doesn't expect you to know accounting — you describe the shop.</p>
    <div class="dugmeler">
      <a class="dugme ana" href="#basla">How to start →</a>
      <a class="dugme yan" href="#ekranlar">See what it can do</a>
    </div>
    <p class="ipucu">Opens on the computer, viewable from your phone too. No internet needed.
      Every record stays on your own device.</p>
  </div>
</section>

<hr class="ayrac">

<!-- IDEA -->
<section id="fikir">
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">The program's only rule</span>
      <h2>Everything in the shop is an "item".</h2>
      <p>Flour is an item, dough is an item, bread is an item; for ice cream the milk, cone and
        strawberry flavor are each an item. The program knows no product up front — you say what
        an item is by ticking the three boxes beside it.</p>
    </div>
    <div class="fikir">
      <div class="kutucuklar">
        <div class="kutucuk">
          <span class="onay">✓</span>
          <b>Bought</b>
          <span>Appears on the Purchases screen, gets a buy price and a supplier.</span>
        </div>
        <div class="kutucuk">
          <span class="onay">✓</span>
          <b>Produced</b>
          <span>Gets a recipe, appears on the Production screen.</span>
        </div>
        <div class="kutucuk">
          <span class="onay">✓</span>
          <b>Sold</b>
          <span>Gets a sell price, appears on the Sales screen.</span>
        </div>
      </div>
      <p class="not"><b>One item can carry several of these.</b> A cone is both bought and sold;
        sponge cake is both produced and a material in another recipe. Recipes chain:
        <span class="mono">cake slice ← layer cake ← sponge ← flour</span>. You set it up once,
        the rest runs by itself.</p>
    </div>
  </div>
</section>

<!-- DAILY LOOP -->
<section id="dongu">
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">Daily use</span>
      <h2>You close the day in four steps.</h2>
      <p>The same order every day. Nothing more: enter what you bought, made and sold — at day's
        end the summary of everything is in front of you.</p>
    </div>
    <div class="dongu">
      <div class="adim">
        <span class="sira"></span>
        <span class="ikon">💰</span>
        <h3>Purchases / Expenses</h3>
        <p>Enter it when you buy material. If you bought by case or sack, say "how many cases" and
          the program converts to units. Rent, electricity and salary go here too.</p>
      </div>
      <div class="adim">
        <span class="sira"></span>
        <span class="ikon">🥛</span>
        <h3>Production</h3>
        <p>You enter how many batches you made. The recipe's materials come out of stock, the
          output goes into stock.</p>
      </div>
      <div class="adim">
        <span class="sira"></span>
        <span class="ikon">🍦</span>
        <h3>Sales</h3>
        <p>Either enter how much you sold, or count what's left on the shelf in the evening — the
          program treats the difference as sales.</p>
      </div>
      <div class="adim">
        <span class="sira"></span>
        <span class="ikon">🏠</span>
        <h3>Today</h3>
        <p>Your till, debt, profit and "buy this much of that material" suggestions all show on one screen.</p>
      </div>
    </div>
    <p class="dongu-not">Order matters: if you bought material that day, <b>enter the purchase first,
      then do the count.</b> Entered something wrong? Press <b>delete</b> — stock and till are reverted.</p>
  </div>
</section>

<hr class="ayrac">

<!-- SCREENS -->
<section id="ekranlar">
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">Inside the program</span>
      <h2>Seven screens, each knows its job.</h2>
      <p>You move through the menu on the left. Each screen does one thing and doesn't drown you in numbers.</p>
    </div>
    <div class="ekranlar">
      <div class="ekran">
        <div class="amblem">🍦</div>
        <div>
          <h3>Sales <span class="yol">/satis</span></h3>
          <p>End-of-day count or direct sales entry — whichever you chose. By the kilo, by the
            scoop, by the portion; however your shop sells.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">🥛</div>
        <div>
          <h3>Production <span class="yol">/uretim</span></h3>
          <p>You enter how many batches of ice cream, trays of cake, troughs of dough you made.
            You write the yield — 4.5 kg in can become 7.5 kg out, and the program knows it.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">📦</div>
        <div>
          <h3>Stock <span class="yol">/stok</span></h3>
          <p>What you have, with subtotals by type. Out-of-stock and running-low materials warn
            you at the top.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">💰</div>
        <div>
          <h3>Purchases / Expenses <span class="yol">/para</span></h3>
          <p>Purchases, payments to suppliers, fixed expenses. As you enter purchases, that item's
            buy price updates on its own.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">🧑‍🍳</div>
        <div>
          <h3>Staff <span class="yol">/calisanlar</span></h3>
          <p>You keep the roster, salaries and social security; the monthly salary load posts to
            expenses by itself. Mark a leaver as "left", and history stays intact.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">📊</div>
        <div>
          <h3>Reports <span class="yol">/ozet</span></h3>
          <p>Revenue, cost, profit; which product earns how much. The Forecast and Special Days
            pages sit alongside.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">⚙️</div>
        <div>
          <h3>Settings <span class="yol">/ayarlar</span></h3>
          <p>Update all prices in one table, pick your province, set up menu periods. Products &amp;
            Materials and recipes are here too.</p>
        </div>
      </div>
      <div class="ekran">
        <div class="amblem">🗂️</div>
        <div>
          <h3>Multiple shops</h3>
          <p>Have more than one shop? Each gets its own login, its own items, its own reports —
            one never mixes into another.</p>
        </div>
      </div>
    </div>
  </div>
</section>

<hr class="ayrac">

<!-- COUNT DEMO -->
<section id="sayim">
  <div class="sinir">
    <div class="sayim">
      <div class="fis">
        <h3>End-of-day count · Cone</h3>
        <div class="fis-satir">
          <span class="ad">On the shelf this morning</span>
          <span class="deg sayi">3,000</span>
        </div>
        <div class="fis-satir">
          <span class="ad">Counted this evening</span>
          <input id="kalan" type="number" min="0" max="3000" value="2962" inputmode="numeric" aria-label="Cones left on the shelf this evening">
        </div>
        <div class="fis-vurgu">
          <div>
            <span class="ad">Sold</span>
            <div class="ciro">Revenue: <span id="ciro">2,280 ₺</span></div>
          </div>
          <span class="buyuk"><span id="satildi">38</span></span>
        </div>
      </div>
      <div class="sayim-yazi">
        <span class="etiket">Your favorite part of the evening</span>
        <h2>You don't count what you sold. You count what's <em>left</em>.</h2>
        <p>The program treats the difference as sales. If 2,962 of 3,000 cones are left in the
          evening, 38 cones were sold; revenue and profit come from there. For things you mark
          "I don't count individually" — spoons, napkins — you just say "a case ran out".</p>
        <p class="dene">↑ Change the leftover number and watch the sales compute on their own.</p>
      </div>
    </div>
  </div>
</section>

<hr class="ayrac">

<!-- DEEP FEATURES -->
<section id="tahmin">
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">The program doesn't just count</span>
      <h2>It learns, calculates and never makes things up.</h2>
      <p>As days build up it gets to know your shop. If it doesn't have enough data it refuses to
        give a forecast and tells you what's missing — on purpose.</p>
    </div>
    <div class="ozellikler">
      <div class="oz">
        <span class="etiket">Weather &amp; sales forecast</span>
        <h3>What to expect tomorrow?</h3>
        <p>It takes the coming days' weather from the official MGM service, matches it with each
          day's revenue, and works out the relationship by itself:</p>
        <ul>
          <li>"Each 1 degree warmer, revenue rises this much"</li>
          <li>"On rainy days it drops this much"</li>
          <li>"Saturday is this many times normal"</li>
        </ul>
      </div>
      <div class="oz">
        <span class="etiket">Production suggestion</span>
        <h3>What to produce for 7 days?</h3>
        <p>It runs the expected sales through the recipes and works out how many batches / trays /
          troughs you need next week. Both wasted production and empty shelves go down.</p>
      </div>
      <div class="oz">
        <span class="etiket">Cost &amp; profit</span>
        <h3>Which product earns?</h3>
        <p>A bought item's cost is its last buy price; a produced item's cost is the average of
          real production records. A sale's cost is the item itself plus its recipe — never counted
          twice. Profit isn't zero from day one.</p>
      </div>
      <div class="oz">
        <span class="etiket">Special days &amp; menu periods</span>
        <h3>Holidays, seasons, weekends.</h3>
        <p>You mark holidays and breaks; the program learns those days' sales separately. You set a
          summer–winter menu, it suggests the switch when the season comes; off-menu products drop
          off sales and counting on their own.</p>
      </div>
    </div>
  </div>
</section>

<hr class="ayrac">

<!-- LEARNING TIMELINE -->
<section>
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">When the forecast turns on</span>
      <h2>It gets smarter as data builds.</h2>
      <p>It doesn't pass judgment from day one. It speaks according to how many days you have.</p>
    </div>
    <div class="ogrenme">
      <div class="sr"><span class="gun">First 10 days</span><span class="ne">No forecast. It says "how many more days are needed". Weather is still recorded every day.</span></div>
      <div class="sr"><span class="gun">From day 10</span><span class="ne">Revenue forecast begins; the range is wide and narrows as data grows.</span></div>
      <div class="sr"><span class="gun">From day 14</span><span class="ne">The temperature effect kicks in — if the days differ enough in weather.</span></div>
      <div class="sr"><span class="gun">From day 28</span><span class="ne">The day-of-week effect kicks in; Saturday and Tuesday diverge.</span></div>
    </div>
  </div>
</section>

<hr class="ayrac">

<!-- TRUST -->
<section id="guven">
  <div class="sinir">
    <div class="baslik-blok">
      <span class="etiket">Rest easy</span>
      <h2>Your data stays with you.</h2>
      <p>The program works for you, not off you. It makes four promises:</p>
    </div>
    <div class="guven">
      <div class="gv">
        <div class="im">🔒</div>
        <div><b>Records on your device</b><span>Every record sits in a file on your own computer and is sent nowhere. To back it up, just copy that file.</span></div>
      </div>
      <div class="gv">
        <div class="im">📴</div>
        <div><b>Works offline</b><span>With no connection the program carries on fine; only the weather forecast goes quiet. Until you pick a province it never goes online at all.</span></div>
      </div>
      <div class="gv">
        <div class="im">🛟</div>
        <div><b>Your data isn't lost</b><span>Even if an error screen appears, the records stay as they are. Every operation is either fully written or not at all.</span></div>
      </div>
      <div class="gv">
        <div class="im">🎯</div>
        <div><b>No making things up</b><span>Without enough data it refuses to forecast. Every forecast it does give comes with a range, drawn from how far off it has been in the past.</span></div>
      </div>
    </div>
  </div>
</section>

<!-- START -->
<section id="basla">
  <div class="sinir">
    <div class="basla">
      <span class="etiket" style="color:var(--bal)">First launch</span>
      <h2>Choose your shop, and we'll set up the rest together.</h2>
      <p>On first launch you pick a template. The template gives you a ready material–product–recipe
        list; it's all examples, and you change it however you like afterwards.</p>
      <div class="sablonlar">
        <span>🍦 Ice cream shop</span>
        <span>🧁 Patisserie</span>
        <span>🍞 Bakery</span>
        <span>🍽️ Restaurant</span>
        <span>📄 Start empty</span>
      </div>
      <a class="dugme ana" href="/giris">Enter the program →</a>
    </div>
  </div>
</section>

<footer>
  <div class="sinir">
    <div class="marka"><span class="mim">📒</span> Dükkan Takip</div>
    <div>Stock · cost · profit — the tradesperson's own ledger. Records stay on your device.</div>
  </div>
</footer>
'''


_BAYRAK_TR = ('<svg viewBox="0 0 30 20" width="22" height="15" aria-hidden="true" '
    'style="display:block;border-radius:2px"><rect width="30" height="20" fill="#E30A17"/>'
    '<circle cx="11.5" cy="10" r="5" fill="#fff"/><circle cx="12.9" cy="10" r="4" fill="#E30A17"/>'
    '<polygon fill="#fff" points="18.40,7.30 19.03,9.13 20.97,9.17 19.43,10.33 19.99,12.18 '
    '18.40,11.08 16.81,12.18 17.37,10.33 15.83,9.17 17.77,9.13"/></svg>')
_BAYRAK_EN = ('<svg viewBox="0 0 60 40" width="22" height="15" aria-hidden="true" '
    'style="display:block;border-radius:2px"><clipPath id="ukj2"><rect width="60" height="40"/>'
    '</clipPath><g clip-path="url(#ukj2)"><rect width="60" height="40" fill="#012169"/>'
    '<path d="M0,0 60,40 M60,0 0,40" stroke="#fff" stroke-width="8"/>'
    '<path d="M0,0 60,40 M60,0 0,40" stroke="#C8102E" stroke-width="5"/>'
    '<rect x="25" width="10" height="40" fill="#fff"/><rect y="15" width="60" height="10" fill="#fff"/>'
    '<rect x="26.5" width="7" height="40" fill="#C8102E"/><rect y="16.5" width="60" height="7" fill="#C8102E"/>'
    '</g></svg>')
_BAYRAKLAR = {"tr": _BAYRAK_TR, "en": _BAYRAK_EN}


def _secici():
    simdi = diller.simdiki()

    def bag(kod):
        bayrak = _BAYRAKLAR[kod]
        if kod == simdi:
            return ('<span style="opacity:1;box-shadow:0 0 0 2px #0f3d3e;border-radius:3px;'
                    'display:inline-flex">' + bayrak + '</span>')
        return ('<a href="/dil?d=' + kod + '&geri=/tanitim" style="opacity:.5;'
                'display:inline-flex;border-radius:3px">' + bayrak + '</a>')

    return ('<div style="position:fixed;top:14px;right:14px;z-index:50;display:inline-flex;'
            'gap:8px;align-items:center;background:rgba(255,253,247,.92);border:1px solid #e7dec9;'
            'border-radius:9px;padding:6px 8px;box-shadow:0 2px 8px rgba(27,45,42,.12)">'
            + bag("tr") + bag("en") + '</div>')


BASLIK = {"tr": "Dükkan Takip", "en": "Dükkan Takip"}


def sayfa():
    """Istek diline gore TR ya da EN tanitim belgesi."""
    dil = diller.simdiki()
    govde = (GOVDE_EN if dil == "en" else GOVDE_TR).replace("{SECICI}", _secici())
    return ("<!DOCTYPE html>\n<html lang=\"" + dil + "\"><head><meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "<title>" + BASLIK.get(dil, BASLIK["tr"]) + "</title>\n"
            + FONTS + "\n" + STIL + "\n</head>\n<body>" + govde + "\n" + BETIK)
