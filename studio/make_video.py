"""Employee 4: builds an MP4 from a job file. Free tools only: Pillow + FFmpeg (+ Piper voice if installed)."""
import json, os, subprocess, sys, shutil, argparse
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONTS = ["/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
         "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]

def font(size):
    for p in FONTS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)

def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if draw.textlength(t, font=fnt, direction="rtl") <= max_w or not cur:
            cur = t
        else:
            lines.append(cur); cur = word
    if cur: lines.append(cur)
    return lines

def frame(text, brand, path):
    img = Image.new("RGB", (W, H), brand["bg"])
    d = ImageDraw.Draw(img)
    f = font(78)
    lines = wrap(d, text, f, W - 220)
    lh = 130
    y = (H - lh * len(lines)) // 2
    for ln in lines:
        w = d.textlength(ln, font=f, direction="rtl")
        d.text(((W - w) / 2, y), ln, font=f, fill=brand["fg"], direction="rtl", language="ar")
        y += lh
    d.rectangle([W//2 - 120, y + 30, W//2 + 120, y + 42], fill=brand["accent"])
    fb = font(44)
    name = brand.get("name", "")
    if name:
        w = d.textlength(name, font=fb, direction="rtl")
        d.text(((W - w) / 2, H - 170), name, font=fb, fill=brand["accent"], direction="rtl", language="ar")
    img.save(path)

def voice(text, model, out):
    p = subprocess.run([sys.executable, "-m", "piper", "--model", model, "--output_file", out],
                       input=text, text=True, capture_output=True)
    return p.returncode == 0 and os.path.exists(out)

def dur(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(r.stdout.strip())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job"); ap.add_argument("--out", required=True)
    ap.add_argument("--voice-model", default=""); ap.add_argument("--no-voice", action="store_true")
    a = ap.parse_args()
    job = json.load(open(a.job, encoding="utf-8"))
    brand = {"bg": "#12302f", "fg": "#ffffff", "accent": "#e0a100", **job.get("brand", {})}
    tmp = "build"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    clips = []
    for i, sc in enumerate(job["scenes"]):
        png, wav, mp4 = f"{tmp}/s{i}.png", f"{tmp}/s{i}.wav", f"{tmp}/s{i}.mp4"
        frame(sc["text"], brand, png)
        has_voice = False
        if not a.no_voice and a.voice_model and os.path.exists(a.voice_model):
            has_voice = voice(sc.get("voice", sc["text"]), a.voice_model, wav)
        d = max(float(sc.get("seconds", 4)), (dur(wav) + 0.7) if has_voice else 0)
        n = int(d * 30)
        vf = (f"scale=2160:-1,zoompan=z='min(zoom+0.0006,1.10)':d={n}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=30,"
              f"fade=t=in:st=0:d=0.4,fade=t=out:st={d-0.4:.2f}:d=0.4,format=yuv420p")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", png]
        cmd += ["-i", wav] if has_voice else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]
        cmd += ["-vf", vf]
        if has_voice:
            cmd += ["-af", "apad"]
        cmd += ["-t", f"{d:.2f}", "-c:v", "libx264", "-c:a", "aac", "-ar", "44100", "-ac", "1", mp4]
        run(cmd); clips.append(mp4)
    with open(f"{tmp}/list.txt", "w") as f:
        for c in clips: f.write(f"file '{os.path.basename(c)}'\n")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{tmp}/list.txt",
         "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", "-movflags", "+faststart", a.out])
    print("built", a.out, round(dur(a.out), 1), "sec")

if __name__ == "__main__":
    main()
