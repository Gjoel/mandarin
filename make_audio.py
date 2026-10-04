"""
Make the recorded audio pack for Xiao Laoshi (小老师).

Run this on your own computer, in the same folder as index.html and texts.json:

    pip install edge-tts
    python make_audio.py                 # lessons + numbers (~1,100 clips, ~5 minutes)
    python make_audio.py --dictionary    # also every Look up word (~8,000 clips, ~45 minutes)

It creates an "audio" folder with one MP3 per line plus audio/index.json.
Upload the whole audio folder to your GitHub repo next to index.html.
Running it again only makes clips that are missing, so it is safe to re-run.
"""
import argparse
import asyncio
import json
import os
import re
import sys

try:
    import edge_tts
except ImportError:
    sys.exit("edge-tts is not installed. Run:  pip install edge-tts")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "audio")


def fnv1a(text: str) -> str:
    """Same hash as the web page uses (FNV-1a 32-bit over UTF-8, whitespace removed)."""
    h = 0x811C9DC5
    for b in re.sub(r"\s+", "", text).encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return format(h, "08x")


async def make_clip(text, path, voice, sem, stats, retries=3):
    async with sem:
        for attempt in range(1, retries + 1):
            try:
                tmp = path + ".part"
                await edge_tts.Communicate(text, voice, rate="-5%").save(tmp)
                if os.path.getsize(tmp) < 500:
                    raise RuntimeError("empty audio")
                os.replace(tmp, path)
                stats["done"] += 1
                if stats["done"] % 25 == 0 or stats["done"] == stats["todo"]:
                    print(f"  {stats['done']}/{stats['todo']} clips made")
                return
            except Exception as e:  # network hiccups: wait and retry
                if attempt == retries:
                    stats["failed"].append((text, str(e)))
                else:
                    await asyncio.sleep(2 * attempt)


async def main():
    ap = argparse.ArgumentParser(description="Make the 小老师 audio pack")
    ap.add_argument("--dictionary", action="store_true", help="also record every Look up word (large)")
    ap.add_argument("--voice", default="zh-CN-XiaoxiaoNeural",
                    help="edge-tts voice, e.g. zh-CN-YunxiNeural (male) or zh-CN-XiaoyiNeural")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    texts_path = os.path.join(HERE, "texts.json")
    if not os.path.exists(texts_path):
        sys.exit("texts.json not found. Put it in the same folder as this script.")
    with open(texts_path, encoding="utf-8") as f:
        groups = json.load(f)

    texts = list(groups.get("core", [])) + list(groups.get("numbers", []))
    if args.dictionary:
        texts += list(groups.get("dictionary", []))

    os.makedirs(OUT_DIR, exist_ok=True)
    jobs = []
    seen = set()
    for t in texts:
        k = fnv1a(t)
        if k in seen:
            continue
        seen.add(k)
        path = os.path.join(OUT_DIR, k + ".mp3")
        if not os.path.exists(path):
            jobs.append((t, path))

    print(f"{len(seen)} lines in total, {len(jobs)} still to record with {args.voice}.")
    stats = {"done": 0, "todo": len(jobs), "failed": []}
    sem = asyncio.Semaphore(max(1, args.concurrency))
    await asyncio.gather(*(make_clip(t, p, args.voice, sem, stats) for t, p in jobs))

    files = sorted(f[:-4] for f in os.listdir(OUT_DIR) if f.endswith(".mp3"))
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"voice": args.voice, "files": files}, f)

    print(f"Done. {len(files)} clips in the audio folder, index.json updated.")
    if stats["failed"]:
        print(f"{len(stats['failed'])} lines failed (run the script again to retry), e.g.:")
        for t, e in stats["failed"][:5]:
            print("   ", t, "->", e)


if __name__ == "__main__":
    asyncio.run(main())
