# 🚚 Chuyển Railway sang account mới (domain mới) — CHECKLIST

> ✅ **ĐÃ HOÀN TẤT 05/10/2026.** URL mới: `https://web-production-f53c5.up.railway.app`
> (đã đổi đủ relay-config.json, relay/dist/app-config.json, .env RELAY_URL,
> vite.config.ts, config.py fallback). Checklist giữ lại làm tài liệu tham khảo
> cho lần đổi domain sau.

> Bối cảnh: account Railway cũ hết free $5. Project chuyển sang account Railway
> mới để dùng tiếp $5 free. URL production sẽ ĐỔI từ
> `https://web-production-19398.up.railway.app` → `https://<URL-MỚI>`.
>
> Sau khi acc Railway mới deploy xong và có URL, làm theo thứ tự dưới đây.

---

## 1. Deploy web trên Railway acc mới

Chọn 1 trong 2 cách:

**Cách A — Git (như cũ, khuyến nghị):**
1. Đăng nhập GitHub acc mới, fork/clone repo
   `conist-z/Dau-Hu-Chien-MMO` (hoặc add acc mới làm collaborator).
2. Railway acc mới → New Project → Deploy from GitHub repo → chọn repo.
3. Root directory = `web_client/relay` (Railway build relay.js + phục vụ `dist/`).
4. Sau deploy: Railway → Settings → Networking → Generate Domain → lấy `<URL-MỚI>`.

**Cách B — Railway CLI (không cần GitHub):**
```bash
npm i -g @railway/cli
railway login                 # login acc RAILWAY mới
cd web_client/relay
railway init                  # tạo service mới
railway up                    # deploy thư mục relay lên
railway domain                # sinh <URL-MỚI>
```

## 2. Discord Developer Portal (app id 965153822861307914)

- OAuth2 → Redirects → **Add Redirect**: `https://<URL-MỚI>/`
  (giữ redirect cũ, không xóa — không ảnh hưởng gì).

## 3. Đổi domain trong repo (4 file)

Thay `web-production-19398.up.railway.app` → `<URL-MỚI>` trong:

| File | Ý nghĩa |
|---|---|
| `web_client/relay/relay-config.json` | `WEB_REDIRECT_URI` — relay trả cho client khi fetch `/config.json` |
| `web_client/relay/dist/app-config.json` | bản build tĩnh client fetch lúc bấm Login |
| `.env` trên PANEL BOT (không phải repo) | `RELAY_URL=wss://<URL-MỚI>/bot` — bot cloud kết nối vào relay |
| `web_client/vite.config.ts` | 2 dòng proxy (chỉ dùng lúc dev, làm sau cũng được) |

Debug-only (có thể bỏ qua): `scripts/_probe_prod_gate.py`.

## 4. Rebuild + push web client

```bash
cd web_client
npm run build
rm -rf relay/dist
cp -r dist relay/dist
# recreate app-config.json (build sẽ wipe):
echo '{"client_id":"965153822861307914","redirect_uri":"https://<URL-MỚI>/"}' > relay/dist/app-config.json
cd ..
git add web_client/relay/relay-config.json web_client/vite.config.ts web_client/dist web_client/relay/dist
git commit -m "migrate web to new Railway domain"
git push origin main
```

## 5. Restart + verify

1. Railway acc mới: để service restart sau khi pull code mới (relay-config đổi).
2. Panel bot: bấm **Restart** (để nó đọc `RELAY_URL` mới).
3. Mở `https://<URL-MỚI>/` → login Discord → join map → đánh quái test.
4. Console (F12) không được có lỗi WS trắng đen: kết nối `wss://<URL-MỚI>/bot`
   phải hiện `[WEB] relay connected` trong log panel bot.

## ⚠️ Lưu ý dữ liệu

- SQLite (`data/`) nằm trên **panel bot**, KHÔNG nằm trên Railway → chuyển
  Railway không mất gì cả (map, túi đồ, scenario đều còn).
- Token bot không đổi. Session login cũ trong trình duyệt sẽ hết hiệu lực —
  login lại bằng Discord là xong.
