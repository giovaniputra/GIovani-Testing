# Demo dengan WhatsApp asli (nomor uji Meta + hosting cloud)

Alur: HP Anda (WhatsApp pribadi) -> nomor uji Meta -> app ini di cloud -> balasan kembali ke HP Anda.
Pakai data uji saja. Jangan arahkan nomor toko asli ke akun uji.

## A. Hosting (contoh: Render, paket gratis)

1. Buka render.com, daftar, pilih **New > Web Service**, hubungkan akun GitHub dan pilih repo `GIovani-Testing`.
2. Isi:
   - **Branch:** `claude/upbeat-gauss-sbr6c1` (atau `main` setelah di-merge)
   - **Root Directory:** `wa-order`
   - **Runtime:** Docker
   - **Health Check Path:** `/health`
3. Di **Environment**, isi variabel dari `.env.example`. Dua yang pertama Anda buat sendiri:
   - `APP_ENV` = `production`
   - `WHATSAPP_VERIFY_TOKEN` = teks acak buatan Anda (bebas, mis. 24 karakter)
   - `DEMO_PHONE` = nomor WhatsApp Anda, format `62812...` tanpa `+`
   - Tiga lainnya (`WHATSAPP_APP_SECRET`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`) diisi setelah langkah B.
4. Deploy. Catat alamatnya, misalnya `https://wa-order-xxxx.onrender.com`.
   Paket gratis tidur saat sepi, jadi balasan pertama bisa lambat sekitar 1 menit.

## B. Meta (WhatsApp Cloud API)

1. Buka developers.facebook.com, **My Apps > Create App**, pilih tipe **Business**.
2. Tambahkan produk **WhatsApp**, lalu buka **WhatsApp > API Setup**. Di sini Anda mendapat:
   - nomor uji Meta,
   - **Phone number ID**,
   - **Temporary access token** (berlaku 24 jam).
3. Di kolom **To**, tambahkan nomor WhatsApp Anda sebagai penerima uji dan verifikasi dengan kode yang dikirim.
4. **App settings > Basic**: salin **App Secret**.
5. Kembali ke hosting, isi `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, lalu deploy ulang.
6. **WhatsApp > Configuration > Webhook**:
   - Callback URL: `https://<alamat-hosting>/webhook`
   - Verify token: sama persis dengan `WHATSAPP_VERIFY_TOKEN`
   - Klik **Verify and save**, lalu **Manage** dan **subscribe ke `messages`**.

## C. Coba

Dari WhatsApp pribadi Anda, kirim pesan ke nomor uji Meta, misalnya:

    kak mau order 2 dus hit lavender sama stella gel 1 dus

Bot membalas ringkasan order. Balas `ok` untuk konfirmasi.

Catatan:
- Bot hanya bisa membalas dalam 24 jam setelah Anda mengirim pesan terakhir. Itu aturan WhatsApp untuk balasan bebas.
- Token sementara habis dalam 24 jam. Untuk demo berhari-hari, buat token permanen lewat System User di Meta Business Settings.
- Di production, halaman simulator dan endpoint `/simulate`, `/api/*` sengaja dimatikan. Order yang terbentuk bisa dilihat di log hosting.
- Database SQLite di paket gratis hilang saat layanan restart. Cukup untuk demo, bukan untuk produksi.
