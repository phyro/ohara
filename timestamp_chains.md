# Timestamp Chains

## Core Insight

**Claim:** If we timestamp H1(F) at time t and H2(F) at time t+k (while H1 is still secure), the H2 timestamp inherits the earlier timestamp t.

This works because:
1. H1(F) commits to F (hash preimage)
2. F binds to outputs of all deterministic functions, including H2(F)
3. Therefore: H1(F) → F → H2(F)

The chain holds as long as H1 was secure when H2(F) was timestamped.

## Security Model

```
Timeline:  t -------- t+5 -------- t+20
           │          │            │
           H1(F)      H2(F)        H1 broken
           timestamped timestamped
```

Since H1 was secure at t+5 when H2(F) was timestamped, H1(F) committed to exactly one F, which binds to exactly one H2(F). The H2 timestamp can use t as its effective timestamp.

If H1 broke *before* the H2 timestamp, because H1(F) can commit to more than just F, the reasoning chain H1(F) → F → H2(F) can no longer be trusted because an attacker could have swapped F for F'.

## Practical Application

**Problem:** Consider a scenario where we have a year or two before AI can generate or edit large videos effortlessly and we don't have a lot of time to timestamp videos. We have SHA1 hashes of large files (e.g., video metadata from Internet Archive). Computing SHA256 requires downloading everything which is too slow given that we don't have much time.

**Solution:**
1. Timestamp SHA1 commitments now (fast—hashes already exist)
2. Later, download files and compute SHA256 hashes
3. Timestamp SHA256 commitments, inheriting the earlier SHA1 timestamp

```
Timeline:  t -------- t+2 -------- t+5 -------- t+20
           │          │            │            │
           SHA1       AI video     SHA256       SHA1
           timestamp  manipulation timestamp    broken
                      possible     (inherits t)
```

This buys us time because SHA256 timestamps can occur *after* AI manipulation becomes possible, yet still inherit timestamps from *before* that event. At least as long as SHA1 remained secure when SHA256 was timestamped.
