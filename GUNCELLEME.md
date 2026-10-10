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
