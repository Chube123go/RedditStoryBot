#!/usr/bin/env python3
import os
from pathlib import Path
from typing import Tuple
import re

# import sox
# from mutagen import MutagenError
# from mutagen.mp3 import MP3, HeaderNotFoundError
import numpy as np
import translators as ts
from moviepy.audio.AudioClip import AudioClip
from moviepy.audio.fx.volumex import volumex
from rich.progress import track
from moviepy.editor import AudioFileClip, CompositeAudioClip, concatenate_audioclips
from utils.console import print_step, print_substep
from utils.voice import sanitize_text
from utils import settings

DEFUALT_MAX_LENGTH: int = 50  # video length variable


class TTSEngine:
    """Calls the given TTS engine to reduce code duplication and allow multiple TTS engines.

    Args:
        tts_module          : The TTS module. Your module should handle the TTS itself and saving to the given path under the run method.
        reddit_object         : The reddit object that contains the posts to read.
        path (Optional)       : The unix style path to save the mp3 files to. This must not have leading or trailing slashes.
        max_length (Optional) : The maximum length of the mp3 files in total.

    Notes:
        tts_module must take the arguments text and filepath.
    """

    def __init__(
            self,
            tts_module,
            reddit_object: dict,
            path: str = "assets/temp/mp3",
            max_length: int = DEFUALT_MAX_LENGTH,
    ):
        self.tts_module = tts_module()
        self.reddit_object = reddit_object
        self.path = path
        self.max_length = max_length
        self.length = 0

    def run(self) -> Tuple[int, int]:

        Path(self.path).mkdir(parents=True, exist_ok=True)

        # This file needs to be removed in case this post does not use post text, so that it won't appear in the final video
        try:
            Path(f"{self.path}/posttext.mp3").unlink()
        except OSError:
            pass

        print_step("Saving Text to MP3 files...")

        self.call_tts("title", self.reddit_object["thread_title"])
        if (
                self.reddit_object["thread_post"] != ""
                and settings.config["settings"]["storymode"] == True
        ):
            self.call_tts("posttext", self.reddit_object["thread_post"])

        idx = None
        for idx, comment in track(enumerate(self.reddit_object["comments"]), "Saving..."):
            # ! Stop creating mp3 files if the length is greater than max length.
            if self.length > self.max_length:
                break
            if (
                    len(comment["comment_body"]) > self.tts_module.max_chars
            ):  # Split the comment if it is too long
                self.split_post(comment["comment_body"], idx)  # Split the comment
            else:  # If the comment is not too long, just call the tts engine
                self.call_tts(f"{idx}", comment["comment_body"])

        print_substep("Saved Text to MP3 files successfully.", style="bold green")
        return self.length, idx

    def split_post(self, text: str, idx: int):
        split_files = []
        split_text = [
            x.group().strip()
            for x in re.finditer(
                r" *(((.|\n){0," + str(self.tts_module.max_chars) + "})(\.|.$))", text
            )
        ]
        try:
            silence_duration = settings.config["settings"]["tts"]["silence_duration"]
        except AttributeError:
            silence_duration = 0.3
        silence = AudioClip(make_frame=lambda t: np.sin(440 * 2 * np.pi * t), duration=silence_duration, fps=44100)
        silence = volumex(silence, 0)
        silence.write_audiofile(f"{self.path}/silence.mp3", fps=44100, verbose=False, logger=None)

        idy = None
        for idy, text_cut in enumerate(split_text):
            newtext = process_text(text_cut)
            #print(f"{idx}-{idy}: {newtext}\n")

            if not newtext or newtext.isspace():
                print("newtext was blank because sanitized split text resulted in none")
                continue
            else:
                self.call_tts(f"{idx}-{idy}.part", newtext)
                with open(f"{self.path}/list.txt", 'w') as f:
                    for idz in range(0, len(split_text)):
                        f.write("file " + f"'{idx}-{idz}.part.mp3'" + "\n")
                    split_files.append(str(f"{self.path}/{idx}-{idy}.part.mp3"))
                    f.write("file " + f"'silence.mp3'" + "\n")
                f.close()

                os.system("ffmpeg -f concat -y -hide_banner -loglevel panic -safe 0 " +
                          "-i " + f"{self.path}/list.txt " +
                          "-c copy " + f"{self.path}/{idx}.mp3")
        try:
            for i in range(0, len(split_files)):
                os.unlink(split_files[i])
        except FileNotFoundError:
            print("file not found error")
        except OSError:
            print("OSError")

    def call_tts(self, filename: str, text: str):

        if filename == "title":
            try:
                self.tts_module.run(text, filepath=f"{self.path}/title_no_silence.mp3")
                try:
                    silence_duration = settings.config["settings"]["tts"]["silence_duration"]
                except AttributeError:
                    silence_duration = 0.3
                silence = AudioClip(make_frame=lambda t: np.sin(440 * 2 * np.pi * t), duration=silence_duration,
                                    fps=44100)
                silence = volumex(silence, 0)
                silence.write_audiofile(f"{self.path}/silence.mp3", fps=44100, verbose=False, logger=None)

                with open(f"{self.path}/title.txt", 'w') as f:
                    f.write("file " + f"'title_no_silence.mp3'" + "\n")
                    f.write("file " + f"'silence.mp3'" + "\n")
                f.close()
                os.system("ffmpeg -f concat -y -hide_banner -loglevel panic -safe 0 " +
                          "-i " + f"{self.path}/title.txt " +
                          "-c copy " + f"{self.path}/title.mp3")
                clip = AudioFileClip(f"{self.path}/title.mp3")
                self.length += clip.duration
                clip.close()
                try:
                    name = ["title_no_silence.mp3", "silence.mp3", "title.txt"]
                    for i in range(0, len(name)):
                        os.unlink(str(rf"{self.path}/" + name[i]))
                except FileNotFoundError:
                    print("file not found error")
                except OSError:
                    print("OSError")
            except:
                self.length = 0
        else:
            try:
                self.tts_module.run(text=text, filepath=f"{self.path}/{filename}.mp3")
                clip = AudioFileClip(f"{self.path}/{filename}.mp3")
                self.length += clip.duration
                clip.close()
            except:
                self.length = 0


def process_text(text: str):
    lang = settings.config["reddit"]["thread"]["post_lang"]
    new_text = sanitize_text(text)
    if lang:
        print_substep("Translating Text...")
        translated_text = ts.google(text, to_language=lang)
        new_text = sanitize_text(translated_text)
    return new_text
