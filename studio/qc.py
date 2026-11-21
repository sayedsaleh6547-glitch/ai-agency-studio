"""Employee 5: checks the final MP4 and the script text. Exit code 1 = rejected."""
import json, re, subprocess, sys, os, argparse

BANNED = ["ضمان الشفاء", "شفاء تام", "شفاء 100", "نتائج مضمونة", "نتيجة مضمونة", "بدون أي ألم نهائيا", "علاج نهائي مضمون"]

def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("job"); ap.add_argument("--report", required=True)
    ap.add_argument("--allow-silent", action="store_true")
    a = ap.parse_args()
    checks = []
    def add(name, ok, detail=""): checks.append({"check": name, "ok": bool(ok), "detail": str(detail)})
    if not os.path.exists(a.video):
        add("file_exists", False)
    else:
        add("file_exists", True, f"{os.path.getsize(a.video)//1024} KB")
        p = json.loads(sh(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", a.video]).stdout or "{}")
        v = next((s for s in p.get("streams", []) if s["codec_type"] == "video"), {})
        au = next((s for s in p.get("streams", []) if s["codec_type"] == "audio"), None)
        d = float(p.get("format", {}).get("duration", 0))
        add("codec_h264", v.get("codec_name") == "h264", v.get("codec_name"))
        add("size_1080x1920", (v.get("width"), v.get("height")) in [(1080, 1920), (1920, 1080)], f'{v.get("width")}x{v.get("height")}')
        add("duration_5_to_90s", 5 <= d <= 90, f"{d:.1f}s")
        add("size_under_50MB", os.path.getsize(a.video) < 50 * 1024 * 1024)
        add("has_audio_track", au is not None)
        r = sh(["ffmpeg", "-i", a.video, "-af", "volumedetect", "-vn", "-f", "null", "-"])
        m = re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr)
        mv = float(m.group(1)) if m else -99
        add("voice_audible", a.allow_silent or mv > -45, f"{mv} dB" + (" (silent allowed for test)" if a.allow_silent else ""))
    text = " ".join(s["text"] + " " + s.get("voice", "") for s in json.load(open(a.job, encoding="utf-8"))["scenes"])
    hits = [b for b in BANNED if b in text]
    add("no_medical_claims", not hits, hits or "clean")
    ok = all(c["ok"] for c in checks)
    json.dump({"ok": ok, "checks": checks}, open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
