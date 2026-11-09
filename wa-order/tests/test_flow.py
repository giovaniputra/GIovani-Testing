import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app import engine, store
from app.parser import parse_rules

TOKO1, TOKO2, TOKO3 = "6281234567801", "6281234567802", "6281234567803"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    from app.main import app
    with TestClient(app) as c:
        yield c


def sim(c, phone, text):
    return c.post("/simulate", json={"phone": phone, "text": text}).json()


# ---- Langkah 2: parser ----
def test_parser_variasi_chat():
    r = parse_rules("Halo kak, mau order 2 dus hit lavender sama stella gel 1 dus, tolong ya")
    assert [(l.qty, l.unit, l.product_text) for l in r.lines] == [
        (2, "dus", "hit lavender"), (1, "dus", "stella gel")]


def test_parser_angka_kata_dan_qty_belakang():
    r = parse_rules("dua karton mitu wipes\nhit orange 3 ctn")
    assert [(l.qty, l.unit) for l in r.lines] == [(2, "dus"), (3, "dus")]


def test_parser_ukuran_bukan_qty():
    r = parse_rules("2 dus hit aerosol lavender 600 ml")
    assert r.lines[0].qty == 2 and "600" in r.lines[0].product_text


def test_parser_seperti_biasa_dan_obrolan():
    assert parse_rules("seperti biasa ya kak").repeat_usual
    assert not parse_rules("kak kapan barangnya sampai?").is_order
    assert not parse_rules("terima kasih kak").is_order


# ---- Langkah 3: matching & validasi ----
def test_matching_typo_dan_alias_toko():
    cust = engine.find_customer(TOKO1)
    assert engine.match_sku("stela gel", cust)["sku"] == "STL-GEL-ORG"
    assert engine.match_sku("obat nyamuk", cust)["sku"] == "HIT-AERO-LAV-600"  # alias khusus toko


def test_matching_ambigu_dan_tak_dikenal():
    m = engine.match_sku("hit", None)
    assert m["status"] == "ambiguous" and len(m["candidates"]) >= 2
    assert engine.match_sku("sepatu bola", None)["status"] == "unmatched"


def test_telepon_dinormalisasi():
    assert engine.find_customer("0812-3456-7801")["code"] == "TK-001"
    assert engine.find_customer("+62 812 3456 7801")["code"] == "TK-001"


# ---- Langkah 4: konfirmasi + alur penuh ----
def test_order_bersih_minta_konfirmasi_lalu_confirmed(client):
    r = sim(client, TOKO1, "kak 2 dus hit lavender sama stella gel 1 dus")
    assert r["status"] == "awaiting_confirmation"
    assert "HIT Aerosol Lavender 600ml - 2 dus (24 pcs)" in r["reply"]
    assert "Balas *OK*" in r["reply"]
    r2 = sim(client, TOKO1, "ok")
    assert r2["status"] == "confirmed" and r2["order_id"] == r["order_id"]


def test_seperti_biasa_pakai_histori(client):
    r = sim(client, TOKO1, "seperti biasa ya kak")
    assert r["status"] == "awaiting_confirmation"
    assert "Stella Gel Orange" in r["reply"]


def test_ambigu_ditanya_lalu_dijawab_nomor(client):
    r = sim(client, TOKO1, "hit 2 dus")
    assert r["status"] == "awaiting_clarification" and "maksudnya yang mana" in r["reply"]
    r2 = sim(client, TOKO1, "1")
    assert r2["status"] == "awaiting_confirmation" and r2["order_id"] == r["order_id"]


def test_isu_internal_tidak_bocor_ke_toko(client):
    r = sim(client, TOKO2, "1 dus godrej no 1")  # toko overdue 45 hari
    assert r["status"] == "needs_review"
    assert any(i["code"] == "overdue" for i in r["issues"])
    assert "overdue" not in r["reply"].lower() and "limit" not in r["reply"].lower()
    r = sim(client, TOKO3, "3 dus stella matic")  # melebihi limit kredit
    assert any(i["code"] == "credit_limit" for i in r["issues"]) and r["status"] == "needs_review"


def test_stok_kurang_dan_anomali(client):
    r = sim(client, TOKO1, "5 dus hit orange")  # stok 24 pcs, minta 60
    assert any(i["code"] == "low_stock" for i in r["issues"])
    r = sim(client, TOKO1, "50 dus hit lavender")  # >5x rata-rata
    assert any(i["code"] == "qty_anomaly" for i in r["issues"])


def test_nomor_tak_terdaftar_dan_obrolan_biasa(client):
    r = sim(client, "6289999999999", "2 dus hit lavender")
    assert r["status"] == "needs_review" and any(i["code"] == "unknown_customer" for i in r["issues"])
    assert sim(client, TOKO1, "kak kapan barang sampai?")["status"] == "not_order"


def test_ubah_batal(client):
    sim(client, TOKO1, "2 dus hit lavender")
    assert sim(client, TOKO1, "salah")["status"] == "superseded"
    sim(client, TOKO1, "2 dus hit lavender")
    assert sim(client, TOKO1, "batal")["status"] == "cancelled"


# ---- Langkah 1: webhook WhatsApp ----
def wa_payload(wa_id, text, frm=TOKO1, mtype="text"):
    msg = {"from": frm, "id": wa_id, "type": mtype}
    if mtype == "text":
        msg["text"] = {"body": text}
    return {"entry": [{"changes": [{"value": {"messages": [msg]}}]}]}


def test_webhook_verifikasi(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "rahasia")
    ok = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "rahasia", "hub.challenge": "123"})
    assert ok.status_code == 200 and ok.text == "123"
    assert client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1"}).status_code == 403


def test_webhook_idempoten_dan_media(client):
    p = wa_payload("wamid.1", "2 dus hit lavender")
    client.post("/webhook", json=p)
    client.post("/webhook", json=p)  # WA kirim ulang
    assert len(client.get("/api/orders").json()) == 1
    client.post("/webhook", json=wa_payload("wamid.2", None, mtype="audio"))
    last = client.get("/api/orders").json()[0]
    assert last["status"] == "needs_review" and last["issues"][0]["code"] == "media"


def test_webhook_signature(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "s3cret")
    body = json.dumps(wa_payload("wamid.9", "2 dus hit lavender")).encode()
    bad = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": "sha256=salah"})
    assert bad.status_code == 403
    sig = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    good = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig})
    assert good.status_code == 200


# ---- Mode production & nomor demo ----
def test_production_menutup_endpoint_debug_dan_menolak_tanpa_secret(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
    assert client.get("/health").status_code == 200
    assert client.post("/simulate", json={"phone": TOKO1, "text": "2 dus hit lavender"}).status_code == 404
    assert client.get("/api/orders").status_code == 404
    assert client.get("/").status_code == 404
    body = json.dumps(wa_payload("wamid.p1", "2 dus hit lavender")).encode()
    assert client.post("/webhook", content=body).status_code == 403  # tanpa secret -> ditolak


def test_demo_phone_dipetakan_ke_toko_demo(monkeypatch):
    monkeypatch.setenv("DEMO_PHONE", "081200000000")
    engine.load_master.cache_clear()
    try:
        assert engine.find_customer("6281200000000")["code"] == "TK-001"
    finally:
        monkeypatch.delenv("DEMO_PHONE")
        engine.load_master.cache_clear()


def test_production_wajib_verify_token(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("WHATSAPP_VERIFY_TOKEN", raising=False)
    r = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "dev-verify-token", "hub.challenge": "1"})
    assert r.status_code == 403


# ---- Katalog WhatsApp (keranjang) ----
def cart_payload(wa_id, items, frm=TOKO1):
    msg = {"from": frm, "id": wa_id, "type": "order",
           "order": {"catalog_id": "CAT1", "product_items": items}}
    return {"entry": [{"changes": [{"value": {"messages": [msg]}}]}]}


def test_keranjang_katalog_jadi_order_terstruktur(client):
    items = [{"product_retailer_id": "HIT-AERO-LAV-600", "quantity": 2, "item_price": 456000, "currency": "IDR"},
             {"product_retailer_id": "STL-GEL-ORG", "quantity": 1, "item_price": 372000, "currency": "IDR"}]
    client.post("/webhook", json=cart_payload("wamid.c1", items))
    o = client.get("/api/orders").json()[0]
    assert o["status"] == "awaiting_confirmation"
    assert [(i["sku"], i["qty"], i["unit_final"]) for i in o["items"]] == [
        ("HIT-AERO-LAV-600", 2, "dus"), ("STL-GEL-ORG", 1, "dus")]
    assert o["total"] == 1258320  # harga dihitung sistem (diskon toko), bukan item_price dari WA
    assert "Balas *OK*" in client.get("/api/outbox").json()[0]["body"]
    assert sim(client, TOKO1, "ok")["status"] == "confirmed"


def test_keranjang_sku_tak_dikenal_dan_di_luar_assortment(client):
    client.post("/webhook", json=cart_payload("wamid.c2", [{"product_retailer_id": "XXX-999", "quantity": 1}]))
    o = client.get("/api/orders").json()[0]
    assert o["status"] == "needs_review" and any(i["code"] == "unmatched" for i in o["issues"])
    # TK-002 hanya boleh membeli sebagian produk; Expert Hair Color tidak termasuk
    client.post("/webhook", json=cart_payload("wamid.c3", [{"product_retailer_id": "EXP-HC-HITAM", "quantity": 1}], frm=TOKO2))
    o = client.get("/api/orders").json()[0]
    assert any(i["code"] == "not_in_assortment" for i in o["issues"])


def test_minta_katalog_dikirim_per_toko(client):
    r = sim(client, TOKO1, "kak minta katalog")
    assert r["status"] == "catalog_sent"
    msg = client.get("/api/outbox").json()[0]
    payload = json.loads(msg["payload"])
    assert payload["interactive"]["type"] == "product_list"
    ids = [i["product_retailer_id"] for s in payload["interactive"]["action"]["sections"] for i in s["product_items"]]
    assert len(ids) == 8
    # TK-002: hanya 4 produk
    sim(client, TOKO2, "katalog")
    ids2 = [i["product_retailer_id"] for s in json.loads(client.get("/api/outbox").json()[0]["payload"])["interactive"]["action"]["sections"] for i in s["product_items"]]
    assert sorted(ids2) == sorted(["GNO1-SOAP-100", "MITU-WIPE-50", "STL-GEL-ORG", "HIT-AERO-LAV-600"])


def test_katalog_bukan_order_bila_ada_item(client):
    assert sim(client, TOKO1, "2 dus hit lavender dari katalog kemarin")["status"] == "awaiting_confirmation"


def test_feed_katalog_meta():
    from app.catalog_feed import COLUMNS, feed_rows
    rows = feed_rows("https://x.id/p", "https://x.id/i")
    assert len(rows) == 8 and set(rows[0]) == set(COLUMNS)
    lav = next(r for r in rows if r["id"] == "HIT-AERO-LAV-600")
    assert lav["price"] == "456000 IDR" and lav["image_link"].endswith("HIT-AERO-LAV-600.jpg")
    assert lav["availability"] == "in stock"
