from icrawler.builtin import BingImageCrawler
from moviepy import ImageClip, concatenate_videoclips
import os
import shutil
import glob

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================
# KONFIGURASI
# ==========================================
KEYWORD_FILE = "keyword.txt"
TEMP_DIR = "temp_gambar"
JUMLAH_GAMBAR = 10
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def bersihkan_folder(folder):
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)


def get_youtube_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, file_path, title, description="", category_id="22", privacy_status="private"):
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    return response.get("id")


def buat_dan_upload():
    if not os.path.exists(KEYWORD_FILE):
        print("❌ File keyword.txt tidak ditemukan!")
        return

    with open(KEYWORD_FILE, "r", encoding="utf-8") as f:
        daftar_keyword = [line.strip() for line in f if line.strip()]

    if not daftar_keyword:
        print("❌ Kata kunci kosong.")
        return

    youtube = get_youtube_service()

    for i, keyword in enumerate(daftar_keyword):
        print(f"\n[{i+1}/{len(daftar_keyword)}] Mencari gambar untuk: '{keyword}'")

        folder_keyword = os.path.join(TEMP_DIR, f"kw_{i}")
        bersihkan_folder(folder_keyword)

        crawler = BingImageCrawler(storage={"root_dir": folder_keyword})
        crawler.crawl(keyword=keyword, max_num=JUMLAH_GAMBAR)

        daftar_gambar = sorted(
            glob.glob(f"{folder_keyword}/*.jpg") + glob.glob(f"{folder_keyword}/*.png")
        )

        if not daftar_gambar:
            print(f"   ⚠️ Gagal mengunduh gambar untuk {keyword}. Lanjut...")
            continue

        print(f"   ✅ Berhasil mengunduh {len(daftar_gambar)} gambar.")

        clips = []
        for img_path in daftar_gambar:
            try:
                clip = ImageClip(img_path).with_duration(3)
                clip = clip.resized(height=1920)
                clip = clip.cropped(x_center=clip.w / 2, width=1080)
                clips.append(clip)
            except Exception:
                pass

        if clips:
            video_final = concatenate_videoclips(clips, method="compose")

            nama_aman = "".join(c if c.isalnum() else "_" for c in keyword)
            output_video = f"video_{nama_aman}.mp4"

            video_final.write_videofile(output_video, fps=30, codec="libx264", logger=None)
            print(f"   🎬 Selesai! Video disimpan: {output_video}")

            video_final.close()
            for c in clips:
                c.close()

            if os.path.exists(folder_keyword):
                shutil.rmtree(folder_keyword)

            judul = f"{keyword.title()} Shorts"
            deskripsi = f"Visual compilation for {keyword}."

            try:
                video_id = upload_video(
                    youtube=youtube,
                    file_path=output_video,
                    title=judul,
                    description=deskripsi,
                    privacy_status="private",
                )
                print(f"   ✅ Terunggah: {judul} (ID: {video_id})")
                os.remove(output_video)
            except Exception as e:
                print(f"   ❌ Gagal upload {output_video}: {e}")


if __name__ == "__main__":
    buat_dan_upload()
