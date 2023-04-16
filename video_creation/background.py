import json
import random
import re
from pathlib import Path
from random import randrange
from typing import Any, Tuple

from moviepy.editor import VideoFileClip
from utils import settings
from utils.console import print_step, print_substep
import yt_dlp

from queue import Queue
import sys
from threading import Thread
from tqdm import tqdm
import ffmpeg

# Load background videos
with open("./utils/backgrounds.json") as json_file:
    background_options = json.load(json_file)

# Remove "__comment" from backgrounds
background_options.pop("__comment", None)

# Add position lambda function
# (https://zulko.github.io/moviepy/ref/VideoClip/VideoClip.html#moviepy.video.VideoClip.VideoClip.set_position)
for name in list(background_options.keys()):
    pos = background_options[name][3]

    if pos != "center":
        background_options[name][3] = lambda t: ("center", pos + t)


def get_start_and_end_times(video_length: int, length_of_clip: int) -> Tuple[int, int]:
    """Generates a random interval of time to be used as the background of the video.

    Args:
        video_length (int): Length of the video
        length_of_clip (int): Length of the video to be used as the background

    Returns:
        tuple[int,int]: Start and end time of the randomized interval
    """
    random_time = randrange(180, int(length_of_clip) - int(video_length))
    return random_time, random_time + video_length


def get_background_config():
    """Fetch the background/s configuration"""
    try:
        choice = str(
            settings.config["settings"]["background"]["background_choice"]
        ).casefold()
    except AttributeError:
        print_substep("No background selected. Picking random background'")
        choice = None

    # Handle default / not supported background using default option.
    # Default : pick random from supported background.
    if not choice or choice not in background_options:
        choice = random.choice(list(background_options.keys()))

    return background_options[choice]


def download_background(background_config: Tuple[str, str, str, Any]):
    """Downloads the background/s video from YouTube."""
    Path("./assets/backgrounds/").mkdir(parents=True, exist_ok=True)
    # note: make sure the file name doesn't include an - in it
    uri, filename, credit, _ = background_config
    if Path(f"assets/backgrounds/{credit}-{filename}").is_file():
        return
    print_step(
        "We need to download the backgrounds videos. they are fairly large but it's only done once. 😎"
    )
    print_substep("Downloading the backgrounds videos... please be patient 🙏 ")
    print_substep(f"Downloading {filename} from {uri}")
    ydl_opts = {
        "format": "bestvideo[height<=1080][ext=mp4]",
        "outtmpl": f"assets/backgrounds/{credit}-{filename}",
        "retries": 10,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(uri)
    print_substep("Background video downloaded successfully! 🎉", style="bold green")


def reader(pipe, queue):
    try:
        with pipe:
            for line in iter(pipe.readline, b""):
                queue.put((pipe, line))
    finally:
        queue.put(None)


def extract_subclip(filename, start_time, end_time, output_file):
    total_duration = float(ffmpeg.probe(filename)["format"]["duration"])
    error = list()

    try:
        video = (
            ffmpeg.input(filename, ss=start_time)
            .trim(start=0, end=(end_time - start_time))
            .setpts("PTS-STARTPTS")
            .output(output_file, codec="copy", format="mp4")
            .run_async(pipe_stdout=True, pipe_stderr=True)
        )
        q = Queue()
        Thread(target=reader, args=[video.stdout, q]).start()
        Thread(target=reader, args=[video.stderr, q]).start()
        bar = tqdm(total=round(total_duration, 2))
        for _ in range(2):
            for source, line in iter(q.get, None):
                line = line.decode()
                if source == video.stderr:
                    error.append(line)
                else:
                    line = line.rstrip()
                    parts = line.split("=")
                    key = parts[0] if len(parts) > 0 else None
                    value = parts[1] if len(parts) > 1 else None
                    if key == "out_time_ms":
                        time = max(round(float(value) / 1000000.0, 2), 0)
                        bar.update(time - bar.n)
                    elif key == "progress" and value == "end":
                        bar.update(bar.total - bar.n)
        bar.update(bar.total)
        bar.close()

    except ffmpeg.Error as e:
        print(error, file=sys.stderr)
        sys.exit(1)


def chop_background_video(
    background_config: Tuple[str, str, str, Any], video_length: int, reddit_object: dict
):
    """Generates the background footage to be used in the video and writes it to assets/temp/background.mp4

    Args:
        background_config (Tuple[str, str, str, Any]) : Current background configuration
        video_length (int): Length of the clip where the background footage is to be taken out of
    """

    print_step("Finding a spot in the backgrounds video to chop...✂️")
    choice = f"{background_config[2]}-{background_config[1]}"
    id = re.sub(r"[^\w\s-]", "", reddit_object["thread_id"])
    background = VideoFileClip(f"assets/backgrounds/{choice}")

    start_time, end_time = get_start_and_end_times(video_length, background.duration)
    try:
        extract_subclip(
            f"assets/backgrounds/{choice}",
            start_time,
            end_time,
            f"assets/temp/{id}/background.mp4",
        )
    except (OSError, IOError):  # ffmpeg issue see #348
        print_substep("FFMPEG issue. Trying again...")
        with VideoFileClip(f"assets/backgrounds/{choice}") as video:
            new = video.subclip(start_time, end_time)
            new.write_videofile(f"assets/temp/{id}/background.mp4")
    print_substep("Background video chopped successfully!", style="bold green")
    return background_config[2]
