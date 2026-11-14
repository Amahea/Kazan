# Siteyi (esnaf.duckdns.org) nasıl güncellerim

Program iki yerde çalışır:

- **Bu bilgisayarda** — `baslat.bat` ile; sadece sen görürsün.
- **İnternette** — https://esnaf.duckdns.org; Google Cloud'daki `kazan`
  sunucusunda, `kazan.service` (systemd) + önünde Caddy ile.

Bilgisayarda yaptığın kod değişikliği **kendiliğinden** siteye yansımaz.
Siteyi güncellemek iki adımdır: (1) kodu GitHub'a gönder, (2) sunucuya çektir.

> **Render YOK.** `render.yaml` eski bir denemeden kalmadır, kullanılmıyor.

---

## 1. Kodu GitHub'a gönder (bu bilgisayarda)

Sunucu, `raporlar-ve-satis-modeli` dalından kod çeker. O yüzden değişiklikleri
commit edip **o dala** (ve istersen `main`'e de) push et:

```bash
git add -A
git commit -m "ne değiştirdiysen kısa açıklama"
git push origin raporlar-ve-satis-modeli
```

> Gerçek veri (`*.db`, `*.csv`) `.gitignore` sayesinde GitHub'a hiç gitmez;
> sadece kod gider.

---

## 2. Yeni kodu sunucuya çektir

1. https://console.cloud.google.com → **Compute Engine → VM instances**
2. `kazan` satırındaki **SSH** düğmesine bas (tarayıcıda terminal açılır).
3. Şunu yapıştır:

```bash
cd ~/Kazan
git pull
sudo systemctl restart kazan
systemctl status kazan --no-pager
```

- `git pull` → yeni kodu indirir.
- `restart` → programı yeni kodla yeniden başlatır.
- `status` → **`active (running)`** (yeşil) görürsen tamam. Çıkmak için `q`.

4. https://esnaf.duckdns.org adresini aç, **Ctrl+F5** ile yenile.

---

## Kurallar ve güvenlik

- **`sudo python3 uygulama.py` ÇALIŞTIRMA.** Veri dosyalarını root'a geçirip
  servisi çökertir. Sadece yukarıdaki `restart` komutunu kullan.
- **Veri güvende:** `git pull` yalnızca kodu günceller. Dükkan kayıtları
  (`dukkanlar/*.db`, `kullanicilar.db`) sunucuda `.gitignore`'da olduğu için
  pull'a takılmaz, silinmez.
- **Giriş şifresi:** Bu bilgisayardaki `kullanicilar.db` sunucuya gitmez.
  Sitede **sunucudaki** hesap/şifreyle girersin; onlar ayrı.
- **Yeni Python paketi eklersen** (şu an hiç yok, hepsi Python'un kendi
  kütüphanesi), sunucuda `git pull`'dan sonra şunu da çalıştır:
  `pip install -r requirements.txt` (hangi ortamda çalıştığına göre
  `~/Kazan` içinde).

---

## `git pull` hata verirse

Körlemesine bir şey silme. En sık görülen:

- **"Your local changes … would be overwritten"** → sunucuda elle düzenleme
  yapılmış demektir. `git status` ile neyin değiştiğini gör; genelde
  `git stash` sonra `git pull` çözer.
- **Çakışma (conflict)** → mesajı not al, yardım iste.

Takılırsan ekrandaki yazıyı olduğu gibi aktar, birlikte bakarız.

---

## Otomatik güncelleme (bir kez kur, sonra sadece `git push`)

Her seferinde SSH'a girmek istemiyorsan, sunucu GitHub'ı kendisi kontrol
edebilir: `otomatik-guncelle.sh` birkaç dakikada bir bakar, yeni sürüm varsa
çeker ve servisi yeniden başlatır. Yoksa hiçbir şey yapmaz; pull başarısız
olursa servise dokunmaz (site çalışır kalır).

**Tek seferlik kurulum** (sunucuda, SSH'ta):

```bash
cd ~/Kazan
git pull                         # betiği ilk kez getir
chmod +x otomatik-guncelle.sh

# cron'un şifresiz restart edebilmesi için (yalnızca bu tek komuta izin):
echo "$USER ALL=(ALL) NOPASSWD: $(which systemctl) restart kazan" \
  | sudo tee /etc/sudoers.d/kazan-restart
sudo chmod 440 /etc/sudoers.d/kazan-restart

# 3 dakikada bir kontrol eden cron görevini ekle:
( crontab -l 2>/dev/null; echo "*/3 * * * * $HOME/Kazan/otomatik-guncelle.sh" ) | crontab -
```

Bundan sonra: bilgisayarda `git push` → site ~3 dakika içinde kendiliğinden
güncellenir. Kayıtlar `~/kazan-guncelleme.log`'da.

**Kapatmak** istersen: `crontab -e` ile o satırı sil.

> Dikkat: Otomatik olduğu için **bozuk bir kodu push edersen** site de birkaç
> dakikada bozulur. Test edilmiş kodu push et; bir terslik olursa cron'u
> durdurup (yukarıdaki satırı sil) elle düzelt.
